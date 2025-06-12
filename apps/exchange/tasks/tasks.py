import asyncio
import socket
import time
from decimal import Decimal

import aiohttp
from celery import shared_task
from django.utils import timezone
from django.core.management import call_command

from common.helpers import getLogger
from apps.exchange.ccxt_client import get_client
from apps.exchange.consts import STABLECOIN_SYMBOLS
from apps.exchange.models import Exchange, TradingPair, Asset, Market, MarketStatusChoices, AssetStatusChoices, SymbolCat

logger = getLogger(__name__)


@shared_task(name='run_broker_crawler')
def run_broker_crawler():
    """
    执行broker_crawler管理命令的Celery任务
    该命令会批量处理所有交易所的数据，支持并行处理
    """
    logger.info("开始执行定时爬取任务，通过broker_crawler管理命令")
    start_time = time.time()
    
    try:
        # 执行broker_crawler管理命令
        call_command('broker_crawler')
        
        elapsed = time.time() - start_time
        logger.info(f"broker_crawler命令执行完成，总耗时: {elapsed:.2f}秒")
        return {'status': 'success', 'elapsed': f"{elapsed:.2f}秒"}
    except Exception as exc:
        elapsed = time.time() - start_time
        logger.error(f"执行broker_crawler命令时出错: {exc}，已耗时: {elapsed:.2f}秒", exc_info=True)
        raise


# 自定义DNS解析配置
async def get_custom_connector():
    """创建自定义连接器，使用ThreadedResolver替代有问题的c-ares"""
    # 使用ThreadedResolver，它基于标准库而非aiodns/pycares
    resolver = aiohttp.ThreadedResolver()
    connector = aiohttp.TCPConnector(
        resolver=resolver,
        ssl=False,
        limit=10,  # 限制同时连接数
        ttl_dns_cache=300,  # DNS缓存5分钟
        family=socket.AF_INET,  # 只使用IPv4，避免IPv6问题
        use_dns_cache=True
    )
    return connector


@shared_task(bind=True, max_retries=3)
def process_exchange(self, exchange_slug):
    """处理单个交易所的任务"""
    logger.info(f"开始处理交易所: {exchange_slug}")
    start_time = time.time()

    try:
        # 使用asyncio.run运行异步任务
        result = asyncio.run(handle_exchange_async(exchange_slug))
        elapsed = time.time() - start_time
        logger.info(f"交易所 {exchange_slug} 处理完成，耗时: {elapsed:.2f}秒")
        return {'status': 'success', 'exchange': exchange_slug, 'elapsed': f"{elapsed:.2f}秒"}
    except Exception as exc:
        elapsed = time.time() - start_time
        logger.error(f"处理交易所 {exchange_slug} 时出错: {exc}，已耗时: {elapsed:.2f}秒", exc_info=True)
        # 重试任务，每次重试间隔增加
        retry_countdown = 60 * (2 ** self.request.retries)  # 指数退避: 1分钟, 2分钟, 4分钟
        self.retry(exc=exc, countdown=retry_countdown)


async def handle_exchange_async(exchange_slug):
    """异步处理单个交易所的数据"""
    processed, created, updated = 0, 0, 0
    delisted_count = 0

    try:
        try:
            exchange_obj = await Exchange.objects.aget(slug=exchange_slug)
        except Exchange.DoesNotExist:
            logger.error(f"交易所 '{exchange_slug}' 不存在，跳过。")
            return
        except Exception as e:
            logger.error(f"获取交易所 '{exchange_slug}' 信息时出错: {e}")
            return

        # 获取数据库中已有的市场标识符
        active_db_market_identifiers = set([
            identifier async for identifier in Market.objects.filter(
                exchange=exchange_obj,
                is_active_on_exchange=True
            ).values_list('market_identifier', flat=True)
        ])
        current_exchange_market_identifiers = set()

        # 创建CCXT客户端时传入自定义连接器
        connector = await get_custom_connector()

        # 为ccxt客户端添加自定义配置
        extra_config = {
            'timeout': 60000,  # 增加超时时间到60秒
            'enableRateLimit': True,
            'verbose': False
        }

        # 尝试获取客户端，如果失败则记录错误并返回
        try:
            client = get_client(exchange_obj.slug, sync_type='async', client_type='rest', extra_config=extra_config,
                                aiohttp_connector=connector)
            if not client:
                logger.error(f"交易所 {exchange_slug} 的客户端未能成功创建，跳过。")
                return
        except Exception as e:
            logger.error(f"创建交易所 {exchange_slug} 的客户端失败: {e}")
            return

        try:
            raw_markets_data = await fetch_markets_with_retry(client)
            logger.info(
                f"从 {exchange_slug} 获取了原始市场数据，类型: {type(raw_markets_data)}，条目数/长度: {len(raw_markets_data) if hasattr(raw_markets_data, '__len__') else 'N/A'}。")
        except Exception as e:
            logger.error(f"获取交易所 {exchange_slug} 的市场信息失败: {e}")
            return

        markets_to_iterate = []
        if isinstance(raw_markets_data, list):
            markets_to_iterate = raw_markets_data
        elif isinstance(raw_markets_data, dict):
            markets_to_iterate = list(raw_markets_data.values())
            logger.info(f"交易所 {exchange_slug} 返回了市场字典，已提取 {len(markets_to_iterate)} 个市场进行处理。")
        else:
            logger.error(
                f"交易所 {exchange_slug} 的市场信息返回类型错误。期望得到list或dict，但实际得到 {type(raw_markets_data)}。返回内容预览: {str(raw_markets_data)[:500]}")
            return

        # 批量处理数据
        markets_to_update = []
        assets_to_update = {}

        def get_precision_digits(value):
            if value is None:
                return None
            try:
                decimal_value = Decimal(str(value))
                if decimal_value == 0:
                    return 0
                return abs(decimal_value.as_tuple().exponent)
            except:
                return None

        for market_data in markets_to_iterate:
            try:
                if not isinstance(market_data, dict):
                    logger.warning(
                        f"交易所 {exchange_slug} 的单个市场数据类型错误。期望dict，但实际得到 {type(market_data)}。数据预览: {str(market_data)[:200]}")
                    continue

                # 基础字段提取
                market_id = market_data.get('id')
                symbol_display = market_data.get('symbol')
                base_code = market_data.get('base')
                quote_code = market_data.get('quote')
                is_active = bool(market_data.get('active', False))
                market_type = (market_data.get('type') or '').lower()
                if not all([market_id, symbol_display, base_code, quote_code]) or market_type != 'spot':
                    continue

                # 准备资产数据
                base_symbol = base_code.upper()
                quote_symbol = quote_code.upper()

                precision_data = market_data.get('precision', {})

                base_val_for_digits = precision_data.get('base')
                if base_val_for_digits is None:
                    base_val_for_digits = precision_data.get('amount')
                base_asset_uint = get_precision_digits(base_val_for_digits)
                if base_asset_uint is None:
                    base_asset_uint = 6

                quote_val_for_digits = precision_data.get('quote')
                if quote_val_for_digits is None:
                    quote_val_for_digits = precision_data.get('price')
                quote_asset_uint = get_precision_digits(quote_val_for_digits)
                if quote_asset_uint is None:
                    quote_asset_uint = 6

                # 收集资产数据以便后续批量处理
                if base_symbol not in assets_to_update:
                    assets_to_update[base_symbol] = {
                        'symbol': base_symbol,
                        'name': base_symbol,
                        'uint': base_asset_uint,
                        'status': AssetStatusChoices.ACTIVE,
                        'is_stablecoin': base_symbol in STABLECOIN_SYMBOLS
                    }

                if quote_symbol not in assets_to_update:
                    assets_to_update[quote_symbol] = {
                        'symbol': quote_symbol,
                        'name': quote_symbol,
                        'uint': quote_asset_uint,
                        'status': AssetStatusChoices.ACTIVE,
                        'is_stablecoin': quote_symbol in STABLECOIN_SYMBOLS
                    }

                # 市场状态和元数据
                market_status = MarketStatusChoices.TRADING if is_active else MarketStatusChoices.HALTED
                trading_rules = {k: v for k, v in {
                    'precision': market_data.get('precision'),
                    'limits': market_data.get('limits'),
                    'taker_fee': market_data.get('taker'),
                    'maker_fee': market_data.get('maker'),
                }.items() if v is not None}

                info_preview = {}
                raw_info = market_data.get('info')
                if isinstance(raw_info, dict):
                    info_preview = {k: type(v).__name__ for k, v in raw_info.items()}
                elif raw_info is not None:
                    info_preview = {'error': 'unexpected_info_type', 'type': type(raw_info).__name__,
                                    'preview': str(raw_info)[:200]}

                meta_data = {'ccxt_raw_info_structure_preview': info_preview}
                if trading_rules:
                    meta_data['trading_rules'] = trading_rules

                market_url = raw_info.get('url') if isinstance(raw_info, dict) else None

                # 市场参数提取
                precision = market_data.get('precision', {})
                limits = market_data.get('limits', {})

                precision_amount = get_precision_digits(precision.get('amount'))
                min_trade_size_base = limits.get('amount', {}).get('min')
                min_trade_size_quote = limits.get('cost', {}).get('min')

                # 构建交易对和市场标识符
                market_identifier = f"{exchange_obj.slug.lower()}_spot_{base_symbol.lower()}_{quote_symbol.lower()}"
                current_exchange_market_identifiers.add(market_identifier)

                # 收集市场数据以便后续批量处理
                markets_to_update.append({
                    'market_identifier': market_identifier,
                    'exchange_id': exchange_obj.id,
                    'market_symbol': market_id,
                    'status': market_status,
                    'is_active_on_exchange': is_active,
                    'market_url': market_url,
                    'meta_data': meta_data if meta_data else None,
                    'last_synced_at': timezone.now(),
                    'precision_amount': precision_amount,
                    'min_trade_size_base': min_trade_size_base,
                    'min_trade_size_quote': min_trade_size_quote,
                    'base_symbol': base_symbol,
                    'quote_symbol': quote_symbol,
                    'symbol_display': symbol_display,
                })

                processed += 1
            except Exception as e:
                market_id_for_log = 'N/A'
                if isinstance(market_data, dict):
                    market_id_for_log = market_data.get('id', 'N/A')
                elif market_data is not None:
                    market_id_for_log = f"非字典类型数据: {str(market_data)[:100]}"

                logger.error(f"处理交易所 {exchange_slug} 的市场 {market_id_for_log} 时出错: {e}")

        # 批量处理资产
        for symbol, asset_data in assets_to_update.items():
            try:
                await Asset.objects.aupdate_or_create(
                    symbol=symbol,
                    defaults=asset_data
                )
            except Exception as e:
                logger.error(f"更新资产 {symbol} 时出错: {e}")

        # 批量处理市场数据
        batch_size = 100
        for i in range(0, len(markets_to_update), batch_size):
            batch = markets_to_update[i:i + batch_size]

            for market_info in batch:
                try:
                    base_asset = await Asset.objects.aget(symbol=market_info['base_symbol'])
                    quote_asset = await Asset.objects.aget(symbol=market_info['quote_symbol'])

                    # 获取或创建交易对
                    trading_pair, pair_created = await TradingPair.objects.aupdate_or_create(
                        base_asset=base_asset,
                        quote_asset=quote_asset,
                        category=SymbolCat.SPOT,
                        defaults={
                            'symbol_display': market_info['symbol_display'],
                            'status': AssetStatusChoices.ACTIVE
                        }
                    )

                    # 移除不需要的临时字段
                    del market_info['base_symbol']
                    del market_info['quote_symbol']
                    del market_info['symbol_display']

                    # 添加交易对ID
                    market_info['trading_pair_id'] = trading_pair.id

                    # 更新或创建市场
                    market_obj, m_created = await Market.objects.aupdate_or_create(
                        market_identifier=market_info['market_identifier'],
                        defaults={
                            'exchange_id': market_info['exchange_id'],
                            'trading_pair_id': market_info['trading_pair_id'],
                            'market_symbol': market_info['market_symbol'],
                            'status': market_info['status'],
                            'is_active_on_exchange': market_info['is_active_on_exchange'],
                            'market_url': market_info['market_url'],
                            'meta_data': market_info['meta_data'],
                            'last_synced_at': market_info['last_synced_at'],
                            'precision_amount': market_info['precision_amount'],
                            'min_trade_size_base': market_info['min_trade_size_base'],
                            'min_trade_size_quote': market_info['min_trade_size_quote'],
                        }
                    )

                    if m_created:
                        created += 1
                    else:
                        updated += 1
                except Exception as e:
                    logger.error(f"保存市场 {market_info.get('market_identifier')} 时出错: {e}")

        # 处理下架的市场
        delisted_market_identifiers = active_db_market_identifiers - current_exchange_market_identifiers
        if delisted_market_identifiers:
            logger.info(f"发现 {len(delisted_market_identifiers)} 个需要标记为下架的市场 ({exchange_slug})。")
            delisted_count = await Market.objects.filter(
                exchange=exchange_obj,
                market_identifier__in=delisted_market_identifiers
            ).aupdate(
                status=MarketStatusChoices.HALTED,
                is_active_on_exchange=False,
                last_synced_at=timezone.now()
            )
            logger.info(f"已将 {delisted_count} 个市场标记为下架/暂停。")

        logger.info(f"完成 {exchange_slug}: 处理了 {processed}, 新建 {created}, 更新 {updated}, 下架 {delisted_count}。")
        return {'processed': processed, 'created': created, 'updated': updated, 'delisted': delisted_count}

    except Exception as e:
        logger.error(f"处理交易所 {exchange_slug} 时发生意外错误: {e}", exc_info=True)
        raise
    finally:
        if client:
            try:
                await client.close()
            except Exception as e:
                logger.error(f"关闭交易所 {exchange_slug} 的客户端时出错: {e}")


async def fetch_markets_with_retry(client, max_retries=3):
    """带重试的市场获取函数"""
    for attempt in range(max_retries):
        try:
            # 使用 load_markets(True) 强制重新加载市场数据
            return await client.load_markets(True)
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            wait_time = 2 ** attempt  # 指数退避: 1s, 2s, 4s
            logger.warning(
                f"获取市场数据失败 ({client.id if hasattr(client, 'id') else 'N/A'})，将在 {wait_time}秒 后重试: {str(e)}")
            await asyncio.sleep(wait_time)
