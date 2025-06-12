import asyncio
from typing import Dict, List, Any, Optional

import ccxt  # Import for ccxt.base.errors
import ccxt.async_support as async_ccxt

from common.helpers import getLogger
from apps.exchange.ccxt_client import get_client
from apps.exchange.consts import (
    STABLECOIN_MAX_RETRIES,
    STABLECOIN_RETRY_DELAY,
    EXCHANGE_TICKERS_BATCH_SIZE
)
from apps.exchange.data_structures import MarketInfo, TickerData, PairDefinition, PairIdentifier
from apps.exchange.interfaces import ExchangeInterface

logger = getLogger(__name__)


class BaseExchangeAdapter(ExchangeInterface):
    def __init__(self, exchange_id: str, ccxt_config: Optional[Dict] = None):
        self.exchange_id = exchange_id.lower()  # Ensure consistent casing
        self.ccxt_config = ccxt_config or {}
        self.client: Optional[async_ccxt.Exchange] = self._get_client()
        self._markets_cache: Optional[Dict[str, MarketInfo]] = None  # exchange_symbol -> MarketInfo

    def _get_client(self) -> object | None:
        """
        Initializes and returns the CCXT async client.
        `get_client` is expected to be a synchronous function that sets up and returns
        an async_ccxt.Exchange instance.
        """
        try:
            client = get_client(self.exchange_id,
                                sync_type="async",
                                client_type="rest",  # Defaulting to "rest" for these adapters
                                extra_config=self.ccxt_config)
            if client:
                logger.info(f"Successfully initialized CCXT async client for {self.exchange_id}")
                return client
            else:
                logger.error(
                    f"Failed to initialize CCXT async client for {self.exchange_id} (get_client returned None)")
                return None
        except Exception as e:
            logger.error(f"Exception initializing CCXT async client for {self.exchange_id}: {e}", exc_info=True)
            return None

    async def get_id(self) -> str:
        return self.exchange_id

    async def close(self):
        if self.client:
            try:
                await self.client.close()
                logger.info(f"Successfully closed CCXT client for {self.exchange_id}")
            except Exception as e:
                logger.error(f"Error closing CCXT client for {self.exchange_id}: {e}", exc_info=True)
        self.client = None  # Ensure client is marked as closed

    def _extract_price_from_raw_ticker(self, raw_ticker: Dict[str, Any]) -> Optional[float]:
        """
        Extracts price from a raw CCXT ticker dict using a predefined priority (last, close, mid-price).
        """
        price_val = None
        if raw_ticker and isinstance(raw_ticker, dict):
            if 'last' in raw_ticker and raw_ticker['last'] is not None:
                price_val = raw_ticker['last']
            elif 'close' in raw_ticker and raw_ticker[
                'close'] is not None:  # 'close' is often same as 'last' for 24h tickers
                price_val = raw_ticker['close']
            elif raw_ticker.get('bid') is not None and raw_ticker.get('ask') is not None:
                try:
                    bid = float(raw_ticker['bid'])
                    ask = float(raw_ticker['ask'])
                    if bid > 0 and ask > 0:  # Ensure bid and ask are positive before averaging
                        price_val = (bid + ask) / 2
                except (ValueError, TypeError):
                    logger.debug(f"[{self.exchange_id}] Could not calculate mid-price from ticker: {raw_ticker}")
                    pass

        if price_val is not None:
            try:
                return float(price_val)
            except (ValueError, TypeError):
                logger.debug(
                    f"[{self.exchange_id}] Could not convert extracted price '{price_val}' to float for ticker: {raw_ticker.get('symbol')}")
                return None
        return None

    def _map_ccxt_market_to_marketinfo(self, ccxt_market: Dict[str, Any]) -> Optional[MarketInfo]:
        """
        Maps a raw CCXT market dictionary to our standardized MarketInfo data structure.
        Returns None if essential information is missing or market is not 'spot'.
        """
        try:
            market_id = ccxt_market.get('id')
            exchange_specific_symbol = ccxt_market.get('symbol')  # This is BASE/QUOTE for CCXT
            base = ccxt_market.get('base')
            quote = ccxt_market.get('quote')

            if not all([exchange_specific_symbol, base, quote]):
                logger.debug(f"[{self.exchange_id}] Skipping market, missing symbol/base/quote: {ccxt_market}")
                return None

            # Standardize pair string (though ccxt_market['symbol'] is usually already this)
            raw_pair_str = f"{base.upper()}/{quote.upper()}"

            pair_identifier = PairIdentifier(base_asset=base.upper(), quote_asset=quote.upper())
            pair_def = PairDefinition(
                identifier=pair_identifier,
                exchange_symbol=exchange_specific_symbol,  # CCXT uses BASE/QUOTE as the symbol key
                raw_pair_string=raw_pair_str,
                market_id=market_id
            )

            # Determine active status. Default to True if not specified or if 'active' is None.
            active_status = ccxt_market.get('active')
            is_active = True if active_status is None else bool(active_status)

            market_type = ccxt_market.get('type', 'spot').lower()

            # We are primarily interested in spot markets for stablecoin pricing
            if market_type != 'spot':
                logger.debug(
                    f"[{self.exchange_id}] Skipping non-spot market {exchange_specific_symbol} of type {market_type}")
                return None

            return MarketInfo(
                pair_def=pair_def,
                is_active=is_active,
                category=market_type  # Store the original type, could be 'spot', 'future', etc.
            )
        except Exception as e:
            logger.warning(
                f"[{self.exchange_id}] Error mapping CCXT market to MarketInfo for market symbol {ccxt_market.get('symbol')}: {e}",
                exc_info=True)
            return None

    def _map_ccxt_ticker_to_tickerdata(self, ccxt_ticker: Dict[str, Any], pair_def: PairDefinition) -> TickerData:
        """Maps a raw CCXT ticker dictionary to our standardized TickerData."""

        extracted_price = self._extract_price_from_raw_ticker(ccxt_ticker)

        return TickerData(
            pair_def=pair_def,
            price=extracted_price,  # Use the consistent extraction logic
            bid=float(ccxt_ticker['bid']) if ccxt_ticker.get('bid') is not None else None,
            ask=float(ccxt_ticker['ask']) if ccxt_ticker.get('ask') is not None else None,
            last=float(ccxt_ticker['last']) if ccxt_ticker.get('last') is not None else None,
            timestamp=int(ccxt_ticker['timestamp']) if ccxt_ticker.get('timestamp') is not None else None,
            raw_ticker=ccxt_ticker
        )

    async def load_markets(self, reload: bool = False) -> Dict[str, MarketInfo]:
        if not self.client:
            logger.warning(f"[{self.exchange_id}] Client not available for load_markets.")
            return {}

        if not reload and self._markets_cache is not None:
            logger.debug(f"[{self.exchange_id}] Returning cached markets.")
            return self._markets_cache

        try:
            logger.debug(f"[{self.exchange_id}] Loading markets from apps.exchange (reload={reload}).")
            # Standard CCXT way to force a reload for its internal cache and fetch fresh data
            raw_markets = await self.client.load_markets(reload=reload)

            mapped_markets: Dict[str, MarketInfo] = {}
            if raw_markets:
                for symbol_key, market_data in raw_markets.items():  # symbol_key is usually like 'BTC/USDT'
                    market_info = self._map_ccxt_market_to_marketinfo(market_data)
                    if market_info:
                        # Keyed by the exchange_symbol (e.g., 'BTC/USDT') which CCXT uses as dict key
                        mapped_markets[market_info.pair_def.exchange_symbol] = market_info

            self._markets_cache = mapped_markets
            logger.info(f"[{self.exchange_id}] Loaded and cached {len(mapped_markets)} markets.")
            return self._markets_cache
        except Exception as e:
            logger.error(f"[{self.exchange_id}] Error loading markets: {e}", exc_info=True)
            return {}

    async def fetch_tickers(self, pair_defs: List[PairDefinition]) -> Dict[str, TickerData]:
        """Public method to be implemented by concrete adapters."""
        raise NotImplementedError("Concrete adapters must implement fetch_tickers")

    async def _fetch_tickers_by_symbols_batched(self, pair_defs: List[PairDefinition]) -> Dict[str, TickerData]:
        if not self.client:
            logger.warning(f"[{self.exchange_id}] Client not available for _fetch_tickers_by_symbols_batched.")
            return {}

        if not pair_defs:
            logger.debug(f"[{self.exchange_id}] No pair definitions provided to _fetch_tickers_by_symbols_batched.")
            return {}

        symbols_to_fetch = [pd.exchange_symbol for pd in pair_defs]
        pair_def_map = {pd.exchange_symbol: pd for pd in pair_defs}

        all_fetched_tickers: Dict[str, TickerData] = {}
        batch_size = EXCHANGE_TICKERS_BATCH_SIZE.get(self.exchange_id, EXCHANGE_TICKERS_BATCH_SIZE.get('default', 100))

        for i in range(0, len(symbols_to_fetch), batch_size):
            batch_symbols = symbols_to_fetch[i:i + batch_size]
            if not batch_symbols:
                continue

            logger.debug(
                f"[{self.exchange_id}] Fetching ticker batch {i // batch_size + 1}/{(len(symbols_to_fetch) + batch_size - 1) // batch_size} with {len(batch_symbols)} symbols.")

            current_retry = 0
            while current_retry <= STABLECOIN_MAX_RETRIES:
                try:
                    raw_batch_tickers = await self.client.fetch_tickers(symbols=batch_symbols)

                    if raw_batch_tickers:
                        for ex_symbol, ticker_data in raw_batch_tickers.items():
                            corresponding_pair_def = pair_def_map.get(ex_symbol)
                            if corresponding_pair_def:
                                mapped_ticker = self._map_ccxt_ticker_to_tickerdata(ticker_data, corresponding_pair_def)
                                all_fetched_tickers[ex_symbol] = mapped_ticker
                            else:
                                logger.warning(
                                    f"[{self.exchange_id}] Received ticker for unrequested/unmappable symbol: {ex_symbol}")
                    break

                except asyncio.TimeoutError as te:
                    logger.warning(
                        f"[{self.exchange_id}] Timeout fetching ticker batch (attempt {current_retry + 1}/{STABLECOIN_MAX_RETRIES + 1}). Details: {te}")
                    current_retry += 1
                except ccxt.NetworkError as ne:
                    logger.warning(
                        f"[{self.exchange_id}] NetworkError fetching ticker batch (attempt {current_retry + 1}/{STABLECOIN_MAX_RETRIES + 1}). Details: {ne}")
                    current_retry += 1
                except ccxt.ExchangeError as ee:
                    logger.error(
                        f"[{self.exchange_id}] ExchangeError fetching ticker batch. Details: {ee}. Not retrying this batch.",
                        exc_info=True)
                    break
                except Exception as e:
                    logger.error(
                        f"[{self.exchange_id}] Unexpected error fetching ticker batch (attempt {current_retry + 1}/{STABLECOIN_MAX_RETRIES + 1}). Details: {e}",
                        exc_info=True)

                if current_retry > STABLECOIN_MAX_RETRIES:
                    logger.error(
                        f"[{self.exchange_id}] Max retries reached for batch starting with {batch_symbols[0]}. Skipping this batch.")
                    break

                if current_retry > 0:
                    delay = STABLECOIN_RETRY_DELAY * (2 ** (current_retry - 1))
                    logger.info(f"[{self.exchange_id}] Retrying batch in {delay}s...")
                    await asyncio.sleep(delay)

        logger.info(
            f"[{self.exchange_id}] _fetch_tickers_by_symbols_batched completed. Fetched {len(all_fetched_tickers)} tickers out of {len(symbols_to_fetch)} requested symbols.")
        return all_fetched_tickers
