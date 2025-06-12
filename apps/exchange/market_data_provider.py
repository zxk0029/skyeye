from typing import Dict, List, Optional, Set
import json
import os

from asgiref.sync import sync_to_async
from django.db.models import Q

from common.helpers import getLogger
from apps.exchange.consts import STABLECOIN_SYMBOLS, EXCHANGE_PRIORITY
from apps.exchange.data_structures import PairDefinition, PairIdentifier, MarketInfo
from apps.exchange.interfaces import ExchangeInterface
from apps.exchange.models import Market, MarketStatusChoices
from apps.exchange.utils import get_exchange_slug_map

logger = getLogger(__name__)


class MarketDataProvider:
    def __init__(self):
        self.db_slug_resolver_map: Dict[str, str] = {}
        self.resolved_only_exchanges: Set[str] = set()
        self.resolved_exclude_exchanges: Set[str] = set()
        self._initialized_filters = False
        self._initialized_slug_map = False
        self._log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '../../logs')
        os.makedirs(self._log_dir, exist_ok=True)
        
        # 生成优先级映射
        self.quote_priority = {symbol: i+1 for i, symbol in enumerate(STABLECOIN_SYMBOLS)}

    async def _initialize_slug_map(self):
        """初始化交易所slug映射"""
        if self._initialized_slug_map:
            return
            
        try:
            self.db_slug_resolver_map = await sync_to_async(
                get_exchange_slug_map, thread_sensitive=True
            )(only_active=True, only_cex=True)
            
            if not self.db_slug_resolver_map:
                logger.warning("获取交易所slug映射失败，服务可能无法正常工作")
                self.db_slug_resolver_map = {}
                
            self._initialized_slug_map = True
            
        except Exception as e:
            logger.error(f"初始化slug映射出错: {e}", exc_info=True)
            self.db_slug_resolver_map = {}

    async def initialize_filters(self, cli_only_exchanges: Optional[List[str]],
                                 cli_exclude_exchanges: Optional[List[str]]):
        """根据命令行参数初始化交易所过滤条件"""
        await self._initialize_slug_map()

        # 处理--only-exchanges参数
        if cli_only_exchanges:
            self.resolved_only_exchanges = {self.db_slug_resolver_map.get(ex.lower()) for ex in cli_only_exchanges}
            self.resolved_only_exchanges.discard(None)
            if self.resolved_only_exchanges:
                logger.info(f"仅处理以下交易所: {self.resolved_only_exchanges}")

        # 处理--exclude-exchanges参数
        if cli_exclude_exchanges:
            self.resolved_exclude_exchanges = {self.db_slug_resolver_map.get(ex.lower()) for ex in cli_exclude_exchanges}
            self.resolved_exclude_exchanges.discard(None)
            if self.resolved_exclude_exchanges:
                logger.info(f"排除以下交易所: {self.resolved_exclude_exchanges}")
                
        self._initialized_filters = True

    def _get_effective_exchange_slugs(self) -> List[str]:
        """获取有效的交易所slugs列表，已应用过滤条件"""
        if not self._initialized_filters:
            logger.warning("过滤条件未初始化，使用默认优先级顺序")
            return [self.db_slug_resolver_map.get(ex.lower()) for ex in EXCHANGE_PRIORITY if
                    self.db_slug_resolver_map.get(ex.lower())]

        effective_exchange_slugs_ordered = []
        seen_effective_slugs = set()

        # 确定优先级源
        priority_source = EXCHANGE_PRIORITY
        if self.resolved_only_exchanges:
            priority_source = [
                ex for ex in EXCHANGE_PRIORITY 
                if self.db_slug_resolver_map.get(ex.lower()) in self.resolved_only_exchanges
            ]

        # 按优先级构建有效的交易所列表
        for entry in priority_source:
            canonical_slug = self.db_slug_resolver_map.get(entry.lower())
            if canonical_slug and canonical_slug not in seen_effective_slugs:
                if canonical_slug in self.resolved_exclude_exchanges:
                    continue
                effective_exchange_slugs_ordered.append(canonical_slug)
                seen_effective_slugs.add(canonical_slug)

        logger.info(f"有效交易所顺序: {effective_exchange_slugs_ordered}")
        return effective_exchange_slugs_ordered

    @sync_to_async(thread_sensitive=True)
    def _fetch_markets_from_db_sync(self, exchange_slug_list: List[str]) -> List[Market]:
        """从数据库获取市场数据"""
        if not exchange_slug_list:
            return []

        db_filter = Q(
            category='Spot',
            status=MarketStatusChoices.TRADING,
            trading_pair__quote_asset__symbol__in=STABLECOIN_SYMBOLS,
            exchange__slug__in=exchange_slug_list
        )

        markets_qs = Market.objects.filter(db_filter).select_related(
            'exchange',
            'trading_pair__base_asset',
            'trading_pair__quote_asset',
            'trading_pair'
        ).order_by('exchange__slug')

        return list(markets_qs)

    def _market_to_pair_definition(self, market_obj: Market) -> Optional[PairDefinition]:
        """将Market对象转换为PairDefinition"""
        try:
            base_sym = market_obj.trading_pair.base_asset.symbol.upper()
            quote_sym = market_obj.trading_pair.quote_asset.symbol.upper()

            pair_identifier = PairIdentifier(base_asset=base_sym, quote_asset=quote_sym)
            ccxt_expected_symbol = market_obj.trading_pair.symbol_display or f"{base_sym}/{quote_sym}"

            return PairDefinition(
                identifier=pair_identifier,
                exchange_symbol=ccxt_expected_symbol,
                raw_pair_string=f"{base_sym}/{quote_sym}",
                market_id=str(market_obj.market_identifier) if market_obj.market_identifier else None
            )
        except Exception as e:
            logger.warning(f"Market对象转换为PairDefinition失败 (ID: {market_obj.id}): {e}")
            return None

    async def get_target_exchange_pairs(self) -> Dict[str, List[PairDefinition]]:
        """获取目标交易对（基于数据库）并进行去重"""
        await self._initialize_slug_map()
        if not self._initialized_filters:
            await self.initialize_filters(None, None)

        # 获取有效交易所列表
        effective_exchange_slugs = self._get_effective_exchange_slugs()
        if not effective_exchange_slugs:
            logger.error("没有有效的交易所，无法获取市场数据")
            return {}

        # 从数据库获取市场数据
        all_db_markets = await self._fetch_markets_from_db_sync(exchange_slug_list=effective_exchange_slugs)

        # 记录去重前的总数
        self._total_before_dedup = len(all_db_markets)

        # 创建优先级映射
        exchange_priority_map = {slug: i for i, slug in enumerate(effective_exchange_slugs)}

        # 根据交易所优先级排序市场
        sorted_markets = sorted(
            all_db_markets,
            key=lambda m: (
                exchange_priority_map.get(m.exchange.slug, float('inf')),
                m.trading_pair.base_asset.symbol,
                self.quote_priority.get(m.trading_pair.quote_asset.symbol, 999)  # 使用报价资产优先级
            )
        )

        # 构建最终的交易对列表
        final_pairs_by_exchange = {slug: [] for slug in effective_exchange_slugs}
        seen_base_assets = set()  # 跟踪已处理的基础资产

        for market_obj in sorted_markets:
            pair_def = self._market_to_pair_definition(market_obj)
            if not pair_def:
                continue

            base_asset = pair_def.identifier.base_asset
            
            # 如果这个基础资产已经处理过了，跳过
            if base_asset in seen_base_assets:
                continue
            
            # 记录这个基础资产已被处理
            seen_base_assets.add(base_asset)
            
            # 添加到对应交易所的列表中
            if market_obj.exchange.slug in final_pairs_by_exchange:
                final_pairs_by_exchange[market_obj.exchange.slug].append(pair_def)

        # 移除没有交易对的交易所
        final_pairs_by_exchange = {ex: pairs for ex, pairs in final_pairs_by_exchange.items() if pairs}
        
        # 日志记录去重前后的数量
        total_markets = len(all_db_markets)
        total_pairs_after_dedup = sum(len(pairs) for pairs in final_pairs_by_exchange.values())
        logger.info(f"去重前共有{total_markets}个交易对，去重后保留{total_pairs_after_dedup}个交易对")
        logger.info(f"共为{len(final_pairs_by_exchange)}个交易所构建了目标交易对")
        
        # # 记录每个交易所的交易对到日志文件
        # self._log_pair_defs(final_pairs_by_exchange)
        
        return final_pairs_by_exchange

    def _log_pair_defs(self, pairs_by_exchange: Dict[str, List[PairDefinition]]):
        """将每个交易所的交易对信息保存到日志文件"""
        try:
            log_file = os.path.join(self._log_dir, 'exchange_pairs.log')
            with open(log_file, 'w') as f:
                f.write(f"记录时间: {__import__('datetime').datetime.now().isoformat()}\n\n")
                f.write(f"【去重后的交易对】\n")
                f.write(f"去重逻辑: 同一基础资产只保留优先级最高的交易所的优先级最高的计价单位\n")
                
                # 获取交易对总数
                total_pairs = sum(len(pairs) for pairs in pairs_by_exchange.values())
                
                # 显示去重信息
                if hasattr(self, '_total_before_dedup'):
                    f.write(f"去重前共有{self._total_before_dedup}个交易对，去重后保留{total_pairs}个交易对，减少了{self._total_before_dedup - total_pairs}个重复交易对\n")
                
                # 显示计价单位优先级
                priority_info = ', '.join([f'{q}({p})' for q, p in sorted(self.quote_priority.items(), key=lambda x: x[1])])
                f.write(f"计价单位优先级: {priority_info}\n\n")
                
                for exchange, pairs in pairs_by_exchange.items():
                    f.write(f"交易所: {exchange}, 交易对数量: {len(pairs)}\n")
                    pair_symbols = [pair.exchange_symbol for pair in pairs]
                    f.write(f"交易对列表: {json.dumps(pair_symbols[:10])}... (仅显示前10个)\n")
                    f.write(f"完整交易对详情:\n")
                    for i, pair in enumerate(pairs):
                        f.write(f"  {i+1}. {pair.exchange_symbol} (原始: {pair.raw_pair_string}, 市场ID: {pair.market_id})\n")
                    f.write("\n" + "-"*80 + "\n\n")
            logger.info(f"已将交易对信息保存到日志文件: {log_file}")
        except Exception as e:
            logger.error(f"保存交易对信息到日志文件时出错: {e}")

    async def get_all_available_stablecoin_pairs(self, exchange_adapters: Dict[str, ExchangeInterface]) -> Dict[
        str, List[PairDefinition]]:
        """获取所有可用的稳定币交易对（直接从交易所API）"""
        await self._initialize_slug_map()
        if not self._initialized_filters:
            await self.initialize_filters(None, None)

        effective_exchange_slugs = self._get_effective_exchange_slugs()
        target_adapters = {slug: adapter for slug, adapter in exchange_adapters.items() if
                           slug in effective_exchange_slugs}

        all_exchange_pairs = {}
        all_pairs_raw = {}  # 临时存储所有获取到的交易对

        # 第一步：从所有交易所获取所有交易对
        for ex_slug, adapter in target_adapters.items():
            try:
                # 通过交易所API获取市场数据
                markets_from_adapter = await adapter.load_markets(reload=True)

                current_exchange_pairs = []
                if markets_from_adapter:
                    for _, market_info_obj in markets_from_adapter.items():
                        # 筛选活跃的现货稳定币交易对
                        if (not market_info_obj.is_active or 
                            market_info_obj.category != 'spot' or
                            market_info_obj.pair_def.identifier.quote_asset not in STABLECOIN_SYMBOLS):
                            continue

                        current_exchange_pairs.append(market_info_obj.pair_def)

                if current_exchange_pairs:
                    all_pairs_raw[ex_slug] = current_exchange_pairs
                    logger.info(f"从{ex_slug}获取到{len(current_exchange_pairs)}个活跃的稳定币现货交易对")
            except Exception as e:
                logger.error(f"从{ex_slug}加载市场数据失败: {e}", exc_info=True)

        # 记录去重前的总数
        self._total_before_dedup = sum(len(pairs) for pairs in all_pairs_raw.values())

        # 第二步：按交易所优先级进行去重
        seen_base_assets = set()
        
        for ex_slug in effective_exchange_slugs:
            if ex_slug not in all_pairs_raw:
                continue
                
            ex_pairs = all_pairs_raw[ex_slug]
            # 按计价单位优先级排序
            sorted_pairs = sorted(
                ex_pairs,
                key=lambda p: self.quote_priority.get(p.identifier.quote_asset, 999)
            )
            
            filtered_pairs = []
            for pair in sorted_pairs:
                base_asset = pair.identifier.base_asset
                if base_asset not in seen_base_assets:
                    filtered_pairs.append(pair)
                    seen_base_assets.add(base_asset)
            
            if filtered_pairs:
                all_exchange_pairs[ex_slug] = filtered_pairs

        # 记录去重前后的数量
        total_before = sum(len(pairs) for pairs in all_pairs_raw.values())
        total_after = sum(len(pairs) for pairs in all_exchange_pairs.values())
        logger.info(f"去重前从所有交易所获取到{total_before}个交易对，去重后保留{total_after}个交易对")

        # # 记录获取到的交易对信息
        # self._log_pair_defs(all_exchange_pairs)
        
        return all_exchange_pairs
