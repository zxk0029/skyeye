from typing import Dict, List
import asyncio

from common.helpers import getLogger
from apps.exchange.adapters.base import BaseExchangeAdapter
from apps.exchange.data_structures import TickerData, PairDefinition

logger = getLogger(__name__)


class CryptocomAdapter(BaseExchangeAdapter):
    """
    Crypto.com 专用适配器
    
    注意：Crypto.com API 对 fetch_tickers 有以下限制：
    1. fetch_tickers() 方法不支持传递多个交易对，只能一次获取一个
    2. 如果传递多个交易对会抛出错误: "fetchTickers() symbols argument cannot contain more than 1 symbol"
    
    因此，这里改用逐个获取的方式
    """
    
    async def fetch_tickers(self, pair_defs: List[PairDefinition]) -> Dict[str, TickerData]:
        """
        Crypto.com 只能一次获取一个交易对的行情，因此直接使用逐个获取的方式
        """
        if not self.client:
            logger.warning(f"[{self.exchange_id}] Client not available for fetch_tickers.")
            return {}
            
        if not pair_defs:
            logger.debug(f"[{self.exchange_id}] No pair definitions provided to fetch_tickers.")
            return {}
        
        all_fetched_tickers: Dict[str, TickerData] = {}
        total_pairs = len(pair_defs)
        
        logger.info(f"[{self.exchange_id}] 使用单个获取方式获取{total_pairs}个交易对")
        
        # 逐个获取交易对行情
        for i, pair_def in enumerate(pair_defs):
            try:
                # 对于cryptocom，直接使用fetch_ticker获取单个交易对
                raw_ticker = await self.client.fetch_ticker(pair_def.exchange_symbol)
                
                if raw_ticker:
                    mapped_ticker = self._map_ccxt_ticker_to_tickerdata(raw_ticker, pair_def)
                    all_fetched_tickers[pair_def.exchange_symbol] = mapped_ticker
                
                # 每获取10个交易对后显示一次进度
                if (i + 1) % 10 == 0 or (i + 1) == total_pairs:
                    logger.debug(f"[{self.exchange_id}] 已获取{i+1}/{total_pairs}个交易对")
                
                # 每获取50个交易对后休眠1秒，避免触发频率限制
                if (i + 1) % 50 == 0:
                    await asyncio.sleep(1)
                    
            except Exception as e:
                logger.error(f"[{self.exchange_id}] 获取行情失败 ({pair_def.exchange_symbol}): {e}")
        
        logger.info(
            f"[{self.exchange_id}] fetch_tickers completed. Fetched {len(all_fetched_tickers)} tickers out of {total_pairs} requested symbols."
        )
        return all_fetched_tickers 