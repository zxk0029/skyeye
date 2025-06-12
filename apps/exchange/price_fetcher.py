from typing import Dict, List

from apps.exchange.data_structures import PairDefinition, TickerData
from apps.exchange.interfaces import ExchangeInterface


# from ...common.helpers import getLogger # Optional: if logging specific to PriceFetcher is needed

# logger = getLogger(__name__)

class PriceFetcher:
    """
    Responsible for fetching prices for a given list of pairs from a specific exchange adapter.
    """

    async def fetch_prices(
            self,
            exchange_adapter: ExchangeInterface,
            pair_defs: List[PairDefinition]
    ) -> Dict[str, float]:  # Returns a map of raw_pair_string -> price
        """
        Fetches tickers using the provided exchange adapter and extracts prices.

        Args:
            exchange_adapter: An instance of ExchangeInterface for a specific exchange.
            pair_defs: A list of PairDefinition objects for which to fetch prices.

        Returns:
            A dictionary mapping the standardized pair string (e.g., "BTC/USDT") to its price (float).
            Returns an empty dictionary if no prices could be fetched or extracted.
        """
        if not pair_defs:
            # logger.debug(f"PriceFetcher: No pair definitions provided for {exchange_adapter.get_id()}.") # get_id() is async
            return {}

        # The exchange_adapter.fetch_tickers is expected to handle its own errors (e.g. network, API) 
        # and ideally return an empty dict or raise a specific exception if it fails critically.
        # It returns a Dict[str, TickerData] where key is exchange_symbol (usually BASE/QUOTE).
        fetched_tickers: Dict[str, TickerData] = await exchange_adapter.fetch_tickers(pair_defs)

        prices: Dict[str, float] = {}
        if fetched_tickers:
            for _exchange_symbol, ticker_data in fetched_tickers.items():
                # ticker_data.price is already extracted by the adapter's _map_ccxt_ticker_to_tickerdata
                if ticker_data and ticker_data.price is not None:
                    # We use ticker_data.pair_def.raw_pair_string as the key for consistency
                    prices[ticker_data.pair_def.raw_pair_string] = ticker_data.price

        # logger.debug(f"PriceFetcher: Extracted {len(prices)} prices for {await exchange_adapter.get_id()}.")
        return prices
