from typing import Dict, List, Any, Optional
import asyncio

from common.helpers import getLogger
from apps.exchange.adapters.base import BaseExchangeAdapter
from apps.exchange.data_structures import TickerData, PairDefinition
from ccxt.base.errors import BadSymbol, NetworkError

logger = getLogger(__name__)


class LbankAdapter(BaseExchangeAdapter):
    """
    Lbank专用适配器，处理不支持的交易对
    
    对于lbank交易所，我们可以一次性获取所有交易对行情，然后在内存中筛选
    """
    
    async def fetch_tickers(self, pair_defs: List[PairDefinition]) -> Dict[str, TickerData]:
        """
        对于lbank，使用无参数的fetch_tickers获取所有交易对行情，然后筛选
        """
        if not self.client:
            logger.warning(f"[{self.exchange_id}] Client not available for fetch_tickers.")
            return {}
            
        if not pair_defs:
            logger.debug(f"[{self.exchange_id}] No pair definitions provided to fetch_tickers.")
            return {}
        
        logger.info(f"[{self.exchange_id}] 获取所有交易对行情，然后筛选需要的{len(pair_defs)}个交易对")
        
        # 设置更长的超时时间
        self.client.timeout = 30000  # 30秒
        
        try:
            # 获取所有交易对行情（lbank支持不传symbols参数）
            all_tickers = await self.client.fetch_tickers()
            
            # 创建交易对映射，用于快速查找
            exchange_symbols = {pair_def.exchange_symbol: pair_def for pair_def in pair_defs}
            
            # 筛选出需要的交易对
            result = {}
            for symbol, ticker in all_tickers.items():
                if symbol in exchange_symbols:
                    pair_def = exchange_symbols[symbol]
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
            
            logger.info(f"[{self.exchange_id}] 成功筛选出{len(result)}/{len(pair_defs)}个需要的交易对行情")
            logger.info(f"[{self.exchange_id}] fetch_tickers completed. Fetched {len(result)} tickers out of {len(pair_defs)} requested symbols.")
            return result
            
        except NetworkError as e:
            logger.error(f"[{self.exchange_id}] 获取所有交易对行情失败，网络错误: {e}")
            # 如果获取所有行情失败，则逐个获取（回退方案）
            return await self._fetch_tickers_one_by_one(pair_defs)
            
        except Exception as e:
            logger.error(f"[{self.exchange_id}] 获取所有交易对行情失败: {e}")
            return await self._fetch_tickers_one_by_one(pair_defs)
    
    async def _fetch_tickers_one_by_one(self, pair_defs: List[PairDefinition]) -> Dict[str, TickerData]:
        """备用方法：逐个获取交易对行情"""
        logger.info(f"[{self.exchange_id}] 使用备用方法逐个获取{len(pair_defs)}个交易对行情")
        
        result = {}
        failed_symbols = []
        
        # 对每个交易对单独获取行情，忽略不支持的交易对
        for pair_def in pair_defs:
            try:
                # 获取单个交易对行情
                ticker = await self.client.fetch_ticker(pair_def.exchange_symbol)
                
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
            except BadSymbol:
                # 忽略不支持的交易对
                failed_symbols.append(pair_def.exchange_symbol)
                continue
            except Exception as e:
                logger.warning(f"[{self.exchange_id}] 获取{pair_def.exchange_symbol}行情失败: {e}")
                continue
                
            # 每获取几个交易对休眠一下，避免请求过快
            if len(result) % 10 == 0:
                await asyncio.sleep(0.5)
                
        logger.info(f"[{self.exchange_id}] 备用方法完成。已获取{len(result)}/{len(pair_defs)}个交易对行情")
        if failed_symbols:
            logger.info(f"[{self.exchange_id}] {len(failed_symbols)}个不支持的交易对: {failed_symbols[:5]}{'...' if len(failed_symbols) > 5 else ''}")
        
        return result 