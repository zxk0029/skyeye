import json
import time
from datetime import datetime, timezone as dt_timezone
from decimal import Decimal
from typing import Dict, List, Optional

import redis.asyncio as aioredis
from asgiref.sync import sync_to_async
from django.conf import settings  # Added for REDIS_URL

from apps.backoffice.models import MgObPersistence, ExchangeRate
from common.helpers import getLogger
from common.redis_client import get_async_redis_client
from apps.exchange.consts import (
    STABLECOIN_PRICE_KEY,
    STABLECOIN_LAST_UPDATE_KEY,
    REDIS_PIPELINE_BATCH_SIZE,
    STABLECOIN_PRICE_EXPIRE_TIME,  # For Redis key expiration
    STABLECOIN_SYMBOLS  # 导入稳定币符号列表
)
from apps.exchange.data_structures import PriceUpdateInfo
from apps.exchange.models import Asset, Market, TradingPair, Exchange

logger = getLogger(__name__)


class RedisDataPersistor:
    """Redis数据持久化类，负责将价格数据更新到Redis"""

    def __init__(self, redis_url: Optional[str] = None):
        self.redis_url = redis_url or getattr(settings, 'REDIS_URL', 'redis://localhost:6379/0')
        logger.info(f"RedisDataPersistor: 初始化，使用Redis URL: {self.redis_url}")
        self._redis_client = None

    async def _get_redis_client(self) -> Optional[aioredis.Redis]:
        """获取Redis客户端，如果未连接则创建新连接"""
        if not self._redis_client:
            try:
                self._redis_client = get_async_redis_client(self.redis_url)
                await self._redis_client.ping()
                logger.info("RedisDataPersistor: 成功连接到Redis")
            except Exception as e:
                logger.error(f"RedisDataPersistor: 连接Redis失败: {e}", exc_info=True)
                self._redis_client = None
        return self._redis_client

    async def update_prices(self, price_updates: List[PriceUpdateInfo]):
        """更新价格数据到Redis"""
        if not price_updates:
            logger.debug("RedisDataPersistor: 没有价格更新需要发送到Redis")
            return

        client = await self._get_redis_client()
        if not client:
            logger.warning("RedisDataPersistor: Redis客户端不可用，无法更新价格")
            return

        logger.debug(f"RedisDataPersistor: 正在更新{len(price_updates)}条价格记录到Redis")

        # 按交易所分组
        updates_by_exchange = {}
        for pu in price_updates:
            updates_by_exchange.setdefault(pu.source_exchange_id, []).append(pu)

        pipeline = client.pipeline()
        redis_update_count = 0

        try:
            # 处理价格更新
            for exchange_id, ex_updates in updates_by_exchange.items():
                for price_info in ex_updates:
                    pair_def = price_info.pair_def
                    redis_key = STABLECOIN_PRICE_KEY % pair_def.raw_pair_string

                    data_to_store = {
                        'price': price_info.price,
                        'symbol': pair_def.identifier.base_asset,
                        'quote': pair_def.identifier.quote_asset,
                        'pair': pair_def.raw_pair_string,
                        'source_exchange_id': price_info.source_exchange_id,
                        'exchange_symbol': pair_def.exchange_symbol,
                        'timestamp': price_info.timestamp.isoformat(),
                    }

                    await pipeline.set(redis_key, json.dumps(data_to_store), ex=STABLECOIN_PRICE_EXPIRE_TIME)
                    redis_update_count += 1

                    # 定期执行pipeline
                    if redis_update_count % REDIS_PIPELINE_BATCH_SIZE == 0:
                        await pipeline.execute()
                        pipeline = client.pipeline()

                # 更新交易所最后更新时间
                await pipeline.set(
                    STABLECOIN_LAST_UPDATE_KEY % exchange_id,
                    datetime.now(dt_timezone.utc).timestamp(),
                    ex=STABLECOIN_PRICE_EXPIRE_TIME * 2
                )

            # 执行剩余命令
            if pipeline.command_stack:
                await pipeline.execute()

            logger.info(
                f"RedisDataPersistor: 成功更新{redis_update_count}个价格键和{len(updates_by_exchange)}个交易所最后更新时间")

        except Exception as e:
            logger.error(f"RedisDataPersistor: Redis批量更新出错: {e}", exc_info=True)

    async def get_price(self, pair_string: str) -> Optional[dict]:
        """从Redis获取价格数据"""
        client = await self._get_redis_client()
        if not client:
            logger.warning("RedisDataPersistor: Redis客户端不可用，无法获取价格")
            return None

        try:
            redis_key = STABLECOIN_PRICE_KEY % pair_string
            price_data = await client.get(redis_key)
            if price_data:
                # 处理data可能是字节或字符串的情况
                data_str = price_data.decode() if isinstance(price_data, bytes) else price_data
                return json.loads(data_str)
            return None
        except Exception as e:
            logger.error(f"RedisDataPersistor: 从Redis获取价格数据失败: {e}", exc_info=True)
            return None

    async def get_all_prices(self) -> Dict[str, dict]:
        """从Redis获取所有价格数据"""
        client = await self._get_redis_client()
        if not client:
            logger.warning("RedisDataPersistor: Redis客户端不可用，无法获取价格")
            return {}

        result = {}
        try:
            # 使用scan迭代器获取所有符合模式的键
            pattern = STABLECOIN_PRICE_KEY.replace("%s", "*")
            async for key in client.scan_iter(match=pattern):
                data = await client.get(key)
                if data:
                    # 提取pair字符串，这是键的最后一部分
                    # 处理key可能是字节或字符串的情况
                    key_str = key.decode() if isinstance(key, bytes) else key
                    pair = key_str.split(":")[-1]

                    # 处理data可能是字节或字符串的情况
                    data_str = data.decode() if isinstance(data, bytes) else data
                    result[pair] = json.loads(data_str)
            return result
        except Exception as e:
            logger.error(f"RedisDataPersistor: 从Redis获取所有价格数据失败: {e}", exc_info=True)
            return {}

    async def close(self):
        """关闭Redis客户端连接"""
        if self._redis_client:
            try:
                client = self._redis_client
                self._redis_client = None
                await client.close()
                logger.info("RedisDataPersistor: Redis客户端已关闭")
            except Exception as e:
                logger.error(f"RedisDataPersistor: 关闭Redis客户端时出错: {e}", exc_info=True)


class DatabasePersistor:
    """数据库持久化类，负责将价格数据更新到数据库"""

    def __init__(self):
        logger.info("DatabasePersistor: 初始化数据库持久化组件")

    @sync_to_async(thread_sensitive=True)
    def _get_assets_sync(self, symbols: List[str]) -> Dict[str, Asset]:
        """同步获取资产信息"""
        assets = Asset.objects.filter(symbol__in=symbols)
        return {asset.symbol.upper(): asset for asset in assets}

    @sync_to_async(thread_sensitive=True)
    def _get_reference_market_sync(self, market_identifier: Optional[str]) -> Optional[Market]:
        """同步获取参考市场"""
        if not market_identifier:
            return None
        try:
            return Market.objects.filter(market_identifier=market_identifier).first()
        except Market.DoesNotExist:
            return None

    async def update_mgob_persistence(self, price_updates: List[PriceUpdateInfo]):
        """更新价格数据到MgObPersistence表"""

        if not price_updates:
            return 0, 0

        start_time = time.time()
        logger.info(f"DatabasePersistor: 正在更新{len(price_updates)}条价格记录到MgObPersistence表")

        # 1. 获取CNY汇率
        @sync_to_async
        def get_cny_rate():
            try:
                # 获取最新的CNY汇率
                rate = ExchangeRate.objects.filter(base_currency='USD', quote_currency='CNY').order_by(
                    '-updated_at').first()
                if rate:
                    return rate.rate
                else:
                    logger.warning("无法获取CNY汇率，将使用默认值7.0")
                    return Decimal('7.0')  # 默认汇率，如果无法获取
            except Exception as e:
                logger.error(f"获取CNY汇率时出错: {e}")
                return Decimal('7.0')  # 默认汇率

        cny_rate = await get_cny_rate()
        logger.info(f"当前CNY汇率: {cny_rate}")

        # 2. 收集所有需要的交易所ID
        exchange_ids = set()
        for update in price_updates:
            exchange_ids.add(update.source_exchange_id)

        logger.info(f"需要处理的交易所ID: {exchange_ids}")

        # 3. 获取所有需要的交易所对象
        @sync_to_async
        def get_exchanges():
            exchanges = {ex.slug: ex for ex in Exchange.objects.filter(slug__in=list(exchange_ids))}
            return exchanges

        exchange_map = await get_exchanges()

        # 4. 收集和去重交易对信息，并按交易所分组
        exchange_pairs = {}  # 交易所ID -> 交易对信息列表
        for update in price_updates:
            pair_def = update.pair_def
            base = pair_def.identifier.base_asset.upper()
            quote = pair_def.identifier.quote_asset.upper()
            key = f"{base}_{quote}"

            exchange_id = update.source_exchange_id

            # 确保交易所存在
            if exchange_id not in exchange_map:
                logger.warning(f"找不到交易所ID '{exchange_id}'，跳过该价格更新")
                continue

            # 按交易所ID分组并去重交易对
            if exchange_id not in exchange_pairs:
                exchange_pairs[exchange_id] = {}

            # 只保留相同交易对的最新价格
            exchange_pairs[exchange_id][key] = {
                'base': base,
                'quote': quote,
                'price': update.price,
                'raw_pair': pair_def.raw_pair_string
            }

        # 计算去重后的总交易对数
        total_pairs = sum(len(pairs) for pairs in exchange_pairs.values())
        logger.info(f"去重后需要处理{total_pairs}个唯一交易对")

        # 5. 收集所有符号
        all_symbols = set()
        for exchange_data in exchange_pairs.values():
            for pair_info in exchange_data.values():
                all_symbols.add(pair_info['base'])
                all_symbols.add(pair_info['quote'])

        # 6. 获取或创建所有资产
        @sync_to_async
        def get_all_assets():
            # 查询已存在的资产
            existing_assets = {asset.symbol.upper(): asset
                               for asset in Asset.objects.filter(symbol__in=list(all_symbols))}

            # 创建缺失的资产
            missing_symbols = all_symbols - {symbol.upper() for symbol in existing_assets.keys()}
            if missing_symbols:
                # 批量创建资产
                new_assets = Asset.objects.bulk_create([
                    Asset(symbol=symbol, name=symbol) for symbol in missing_symbols
                ])
                for asset in new_assets:
                    existing_assets[asset.symbol.upper()] = asset

            return existing_assets

        # 执行资产查询/创建
        asset_map = await get_all_assets()

        # 7. 处理所有交易对和MgObPersistence记录
        @sync_to_async
        def process_all_pairs():
            # 准备更新数据
            successful = 0
            trading_pairs_to_create = []  # 需要创建的交易对

            # 预处理所有交易对
            all_pair_data = []  # [(exchange_obj, key, pair_info), ...]

            # 按交易所处理
            for exchange_id, exchange_data in exchange_pairs.items():
                exchange = exchange_map[exchange_id]

                for pair_key, pair_info in exchange_data.items():
                    base_asset = asset_map.get(pair_info['base'])
                    quote_asset = asset_map.get(pair_info['quote'])

                    if base_asset and quote_asset:
                        key = (base_asset.id, quote_asset.id)
                        all_pair_data.append((exchange, key, pair_info, base_asset, quote_asset))

            # 如果没有有效的交易对，直接返回
            if not all_pair_data:
                return 0

            # 收集所有需要查询的base_id和quote_id
            base_ids = [base_id for _, (base_id, _), _, _, _ in all_pair_data]
            quote_ids = [quote_id for _, (_, quote_id), _, _, _ in all_pair_data]

            # 查询所有已存在的交易对
            existing_pairs = TradingPair.objects.filter(
                base_asset_id__in=base_ids,
                quote_asset_id__in=quote_ids
            )

            # 构建查找映射
            tp_map = {(tp.base_asset_id, tp.quote_asset_id): tp for tp in existing_pairs}

            # 处理交易对
            mgob_updates = []  # 需要创建或更新的MgOb记录

            for exchange, key, pair_info, base_asset, quote_asset in all_pair_data:
                # 获取或创建交易对
                trading_pair = tp_map.get(key)
                if not trading_pair:
                    # 需要创建交易对
                    trading_pair = TradingPair(
                        symbol_display=f"{pair_info['base']}/{pair_info['quote']}",
                        base_asset=base_asset,
                        quote_asset=quote_asset,
                        status='Active',
                        category='Spot'
                    )
                    trading_pairs_to_create.append(trading_pair)
                    # 暂时为其分配一个临时ID
                    tp_map[key] = trading_pair

                price = pair_info['price']
                is_usd = pair_info['quote'] in STABLECOIN_SYMBOLS

                # 添加到更新列表，注意这里使用对应的exchange
                mgob_updates.append({
                    'exchange': exchange,
                    'tp': trading_pair,
                    'ba': base_asset,
                    'qa': quote_asset,
                    'price': price,
                    'is_usd': is_usd,
                })

            # 如果有交易对需要创建，先批量创建
            if trading_pairs_to_create:
                try:
                    created_pairs = TradingPair.objects.bulk_create(trading_pairs_to_create)
                    # 更新引用
                    for i, tp in enumerate(created_pairs):
                        original = trading_pairs_to_create[i]
                        key = (original.base_asset_id, original.quote_asset_id)
                        tp_map[key] = tp
                except Exception as e:
                    logger.error(f"批量创建交易对失败: {e}")

            # 按交易所分组查询已存在的MgObPersistence记录
            all_mgob_creates = []  # 所有需要创建的记录
            all_mgob_updates = []  # 所有需要更新的记录

            # 按交易所分组处理
            exchange_to_pairs = {}  # 交易所 -> 交易对数据列表
            for data in mgob_updates:
                exchange = data['exchange']
                if exchange not in exchange_to_pairs:
                    exchange_to_pairs[exchange] = []
                exchange_to_pairs[exchange].append(data)

            # 对每个交易所，查询其现有记录并处理更新/创建
            for exchange, exchange_data in exchange_to_pairs.items():
                # 收集该交易所下的所有交易对ID
                tp_ids = [data['tp'].id for data in exchange_data if data['tp'].id]

                if not tp_ids:
                    continue

                # 查询该交易所下已存在的MgObPersistence记录
                existing_mgobs = (MgObPersistence.objects
                                  .filter(exchange=exchange, symbol_id__in=tp_ids)
                                  .values('id', 'symbol_id', 'base_asset_id', 'quote_asset_id'))

                # 构建查找映射
                mgob_map = {(mgob['symbol_id'], mgob['base_asset_id'], mgob['quote_asset_id']): mgob['id']
                            for mgob in existing_mgobs}

                # 分离需要创建和更新的记录
                for data in exchange_data:
                    tp = data['tp']
                    ba = data['ba']
                    qa = data['qa']

                    if not tp.id:
                        continue

                    lookup_key = (tp.id, ba.id, qa.id)

                    if lookup_key in mgob_map:
                        # 需要更新
                        all_mgob_updates.append({
                            'id': mgob_map[lookup_key],
                            'avg_price': data['price'],
                            'buy_price': data['price'],
                            'sell_price': data['price'],
                            'usd_price': data['price'] if data['is_usd'] else None,
                            'cny_price': Decimal(str(data['price'])) * cny_rate if data['is_usd'] else None
                        })
                    else:
                        # 需要创建 - 使用对应的exchange
                        all_mgob_creates.append(
                            MgObPersistence(
                                exchange=exchange,
                                symbol=tp,
                                base_asset=ba,
                                quote_asset=qa,
                                avg_price=data['price'],
                                buy_price=data['price'],
                                sell_price=data['price'],
                                usd_price=data['price'] if data['is_usd'] else 0,
                                cny_price=Decimal(str(data['price'])) * cny_rate if data['is_usd'] else 0
                            )
                        )

            # 批量创建新记录
            if all_mgob_creates:
                try:
                    MgObPersistence.objects.bulk_create(all_mgob_creates)
                    successful += len(all_mgob_creates)
                    logger.info(f"创建{len(all_mgob_creates)}条新价格记录")
                except Exception as e:
                    logger.error(f"批量创建MgObPersistence记录失败: {e}")

            # 批量更新记录
            if all_mgob_updates:
                try:
                    from django.db import connection

                    with connection.cursor() as cursor:
                        cursor.execute("BEGIN")
                        try:
                            for update in all_mgob_updates:
                                cursor.execute(
                                    "UPDATE backoffice_mgobpersistence SET avg_price = %s, buy_price = %s, sell_price = %s, updated_at = NOW() WHERE id = %s",
                                    [update['avg_price'], update['buy_price'], update['sell_price'], update['id']]
                                )

                                # 更新USD价格
                                if update.get('usd_price') is not None:
                                    cursor.execute(
                                        "UPDATE backoffice_mgobpersistence SET usd_price = %s WHERE id = %s",
                                        [update['usd_price'], update['id']]
                                    )

                                    # 同时更新CNY价格 - 使用USD价格乘以汇率
                                    cursor.execute(
                                        "UPDATE backoffice_mgobpersistence SET cny_price = %s WHERE id = %s",
                                        [Decimal(str(update['usd_price'])) * cny_rate if update[
                                                                                             'usd_price'] is not None else None,
                                         update['id']]
                                    )
                            cursor.execute("COMMIT")
                            logger.info(f"更新{len(all_mgob_updates)}条价格记录")
                        except Exception as e:
                            cursor.execute("ROLLBACK")
                            raise e

                    successful += len(all_mgob_updates)
                except Exception as e:
                    logger.error(f"批量更新MgObPersistence记录失败: {e}")

            return successful

        # 执行处理
        successful = await process_all_pairs()
        failed = total_pairs - successful

        # 最终统计
        success_rate = (successful / total_pairs * 100) if total_pairs else 0
        process_time = time.time() - start_time

        logger.info(
            f"DatabasePersistor: MgObPersistence表更新完成。处理了{len(price_updates)}条原始数据，{total_pairs}个唯一交易对。")
        logger.info(f"成功: {successful}, 失败: {failed}, 成功率: {success_rate:.2f}%, 耗时: {process_time:.2f}秒")

        return successful, failed


# 为了保持向后兼容，保留原来的DataPersistor类，但内部使用新的分离类
class DataPersistor:
    """兼容层，保持原有API不变，但内部使用分离的实现"""

    def __init__(self, redis_url: Optional[str] = None):
        self.redis_persistor = RedisDataPersistor(redis_url)
        self.db_persistor = DatabasePersistor()
        self._redis_client = None  # 保持属性兼容
        self._redis_client_connected = False  # 保持属性兼容

    async def _get_redis_client(self) -> Optional[aioredis.Redis]:
        """获取Redis客户端（兼容方法）"""
        client = await self.redis_persistor._get_redis_client()
        self._redis_client = client  # 更新兼容属性
        self._redis_client_connected = client is not None
        return client

    async def update_redis_prices(self, price_updates: List[PriceUpdateInfo]):
        """更新价格到Redis（兼容方法）"""
        await self.redis_persistor.update_prices(price_updates)

    async def close_redis_client(self):
        """关闭Redis客户端（兼容方法）"""
        await self.redis_persistor.close()
        self._redis_client = None
        self._redis_client_connected = False

    async def update_mgob_persistence(self, price_updates: List[PriceUpdateInfo]):
        """更新数据库MgObPersistence表（便捷方法）"""
        await self.db_persistor.update_mgob_persistence(price_updates)
