import asyncio
from typing import Dict, List

from common.helpers import getLogger
from apps.exchange.adapters.base import BaseExchangeAdapter
from apps.exchange.data_structures import TickerData, PairDefinition

logger = getLogger(__name__)


class BinanceAdapter(BaseExchangeAdapter):
    """
    Binance 专用适配器，处理 Binance API 的特殊情况
    
    注意：Binance API 对 fetch_tickers 有以下限制：
    1. 当通过 symbols 参数传递超过约500个交易对时，会返回错误格式的响应
    2. 当不传递 symbols 参数时，会返回所有交易对的行情数据
    
    因此，这里采用直接获取所有交易对然后在内存中筛选的方式，避免批量大小限制问题
    """

    async def fetch_tickers(self, pair_defs: List[PairDefinition]) -> Dict[str, TickerData]:
        """
        Binance的fetch_tickers无需传递symbols参数可获取所有交易对行情，
        然后在内存中筛选需要的交易对
        """
        if not self.client:
            logger.warning(f"[{self.exchange_id}] Client not available for fetch_tickers.")
            return {}

        if not pair_defs:
            logger.debug(f"[{self.exchange_id}] No pair definitions provided to fetch_tickers.")
            return {}

        # 创建映射以便快速查找
        symbols_set = {pd.exchange_symbol for pd in pair_defs}
        pair_def_map = {pd.exchange_symbol: pd for pd in pair_defs}
        all_fetched_tickers: Dict[str, TickerData] = {}

        try:
            # 直接调用fetch_tickers无需传递symbols参数，获取所有交易对行情
            logger.info(f"[{self.exchange_id}] 获取所有交易对行情，然后筛选需要的{len(pair_defs)}个交易对")
            raw_tickers = await self.client.fetch_tickers()

            if raw_tickers and isinstance(raw_tickers, dict):
                # 筛选需要的交易对
                for symbol, ticker_data in raw_tickers.items():
                    if symbol in symbols_set:
                        corresponding_pair_def = pair_def_map.get(symbol)
                        if corresponding_pair_def:
                            mapped_ticker = self._map_ccxt_ticker_to_tickerdata(ticker_data, corresponding_pair_def)
                            all_fetched_tickers[symbol] = mapped_ticker

                logger.info(
                    f"[{self.exchange_id}] 成功筛选出{len(all_fetched_tickers)}/{len(pair_defs)}个需要的交易对行情")
            else:
                logger.error(f"[{self.exchange_id}] fetch_tickers返回了非预期的格式: {type(raw_tickers)}")
                raise Exception(f"Unexpected format: {type(raw_tickers)}")

        except Exception as e:
            logger.error(f"[{self.exchange_id}] 获取所有交易对行情失败: {e}, 错误类型: {type(e)}")
            logger.info(f"[{self.exchange_id}] 改用逐个获取{len(pair_defs)}个交易对")

            # 如果批量获取失败，改用逐个获取
            counter = 0
            for pair_def in pair_defs:
                try:
                    raw_ticker = await self.client.fetch_ticker(pair_def.exchange_symbol)
                    if raw_ticker:
                        mapped_ticker = self._map_ccxt_ticker_to_tickerdata(raw_ticker, pair_def)
                        all_fetched_tickers[pair_def.exchange_symbol] = mapped_ticker
                        counter += 1

                        # 每获取10个交易对后显示一次进度
                        if counter % 10 == 0:
                            logger.debug(f"[{self.exchange_id}] 已获取{counter}/{len(pair_defs)}个交易对")

                        # 每获取50个交易对后休眠1秒，避免触发频率限制
                        if counter % 50 == 0:
                            await asyncio.sleep(1)

                except Exception as e2:
                    logger.error(f"[{self.exchange_id}] 单个获取失败 ({pair_def.exchange_symbol}): {e2}")

        logger.info(
            f"[{self.exchange_id}] fetch_tickers completed. Fetched {len(all_fetched_tickers)} tickers out of {len(pair_defs)} requested symbols."
        )
        return all_fetched_tickers
