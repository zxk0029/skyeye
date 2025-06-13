from typing import Dict, List

from common.helpers import getLogger
from apps.exchange.adapters.base import BaseExchangeAdapter
from apps.exchange.data_structures import TickerData, PairDefinition

logger = getLogger(__name__)


class GenericExchangeAdapter(BaseExchangeAdapter):
    async def fetch_tickers(self, pair_defs: List[PairDefinition]) -> Dict[str, TickerData]:
        """Fetches tickers by delegating to the batched method in BaseExchangeAdapter."""
        if not self.client:
            logger.warning(f"[{self.exchange_id}] Client not available for fetch_tickers.")
            return {}
        if not pair_defs:
            logger.debug(f"[{self.exchange_id}] No pair definitions provided to fetch_tickers.")
            return {}
        return await self._fetch_tickers_by_symbols_batched(pair_defs)
