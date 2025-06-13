from typing import Dict, List, Optional
import asyncio

import ccxt  # For error types

from common.helpers import getLogger
from apps.exchange.adapters.base import BaseExchangeAdapter
from apps.exchange.data_structures import TickerData, PairDefinition
from ccxt.base.errors import NetworkError, ExchangeError

logger = getLogger(__name__)


class YobitAdapter(BaseExchangeAdapter):
    """
    Yobit专用适配器
    
    Yobit交易所API较慢且不稳定，需要特殊处理
    """
    
    MAX_RETRIES = 5  # 最大重试次数
    BASE_DELAY = 5  # 基础延迟（秒）
    MAX_DELAY = 60  # 最大延迟（秒）
    
    def __init__(self, exchange_id: str = 'yobit', ccxt_config: Optional[Dict] = None):
        # 合并默认配置和用户提供的配置
        default_config = {
            'timeout': 30000,  # 30秒超时
            'enableRateLimit': True,
        }
        
        merged_config = {**default_config, **(ccxt_config or {})}
        super().__init__(exchange_id, ccxt_config=merged_config)

    async def fetch_tickers(self, pair_defs: List[PairDefinition]) -> Dict[str, TickerData]:
        """
        获取Yobit交易所的行情数据，带有增强的重试逻辑
        """
        if not self.client:
            logger.warning(f"[{self.exchange_id}] Client not available for fetch_tickers.")
            return {}
            
        if not pair_defs:
            logger.debug(f"[{self.exchange_id}] No pair definitions provided to fetch_tickers.")
            return {}
        
        # 先尝试直接获取所有行情（Yobit支持不带参数的fetch_tickers获取所有行情）
        all_tickers = await self._fetch_all_tickers_with_retry()
        
        if not all_tickers:
            logger.warning(f"[{self.exchange_id}] 无法获取行情数据，返回空结果")
            return {}
            
        # 筛选出我们需要的交易对
        result = {}
        for pair_def in pair_defs:
            symbol = pair_def.exchange_symbol
            if symbol in all_tickers:
                ticker = all_tickers[symbol]
                if ticker and 'last' in ticker and ticker['last'] is not None:
                    result[pair_def.raw_pair_string] = TickerData(
                        pair_def=pair_def,
                        price=float(ticker['last']),
                        bid=float(ticker.get('bid', 0)) if ticker.get('bid') is not None else None,
                        ask=float(ticker.get('ask', 0)) if ticker.get('ask') is not None else None,
                        last=float(ticker['last']),
                        timestamp=int(ticker.get('timestamp', 0)) if ticker.get('timestamp') is not None else None,
                        raw_ticker=ticker
                    )
        
        logger.info(f"[{self.exchange_id}] fetch_tickers completed. Fetched {len(result)} tickers out of {len(pair_defs)} requested symbols.")
        return result
        
    async def _fetch_all_tickers_with_retry(self) -> Optional[Dict]:
        """
        带有增强重试逻辑的获取所有行情方法
        使用指数退避策略进行重试
        """
        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                # 添加params={'all': True}参数，确保获取所有交易对
                logger.info(f"[{self.exchange_id}] 尝试获取所有交易对行情 (尝试 {attempt}/{self.MAX_RETRIES})")
                all_tickers = await self.client.fetch_tickers(params={'all': True})
                return all_tickers
                
            except (NetworkError, ExchangeError) as e:
                # 计算退避延迟
                delay = min(self.BASE_DELAY * (2 ** (attempt - 1)), self.MAX_DELAY)
                
                if attempt < self.MAX_RETRIES:
                    logger.warning(f"[{self.exchange_id}] NetworkError fetching all tickers (attempt {attempt}/{self.MAX_RETRIES}). Details: {str(e)[:100]}")
                    logger.info(f"[{self.exchange_id}] Retrying fetch all tickers in {delay}s...")
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"[{self.exchange_id}] Failed to fetch all tickers after {self.MAX_RETRIES} attempts. Last error: {e}")
                    return None
                    
            except Exception as e:
                logger.error(f"[{self.exchange_id}] Unexpected error fetching all tickers: {e}")
                return None
                
        return None
