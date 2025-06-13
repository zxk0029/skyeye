from abc import ABC, abstractmethod
from typing import Dict, List

from .data_structures import MarketInfo, TickerData, PairDefinition


class ExchangeInterface(ABC):
    @abstractmethod
    async def get_id(self) -> str:
        pass

    @abstractmethod
    async def load_markets(self, reload: bool = False) -> Dict[str, MarketInfo]:  # Key: exchange_symbol
        pass

    @abstractmethod
    async def fetch_tickers(self, pair_defs: List[PairDefinition]) -> Dict[str, TickerData]:  # Key: exchange_symbol
        pass

    @abstractmethod
    async def close(self):
        pass
