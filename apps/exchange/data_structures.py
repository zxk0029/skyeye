from datetime import datetime
from typing import NamedTuple, Optional, Dict


class PairIdentifier(NamedTuple):
    base_asset: str
    quote_asset: str


class PairDefinition(NamedTuple):
    identifier: PairIdentifier
    exchange_symbol: str  # Symbol as expected by the exchange
    raw_pair_string: str  # Standardized "BASE/QUOTE" string
    market_id: Optional[str] = None


class MarketInfo(NamedTuple):
    pair_def: PairDefinition
    is_active: bool
    category: str  # e.g. 'Spot'


class TickerData(NamedTuple):
    pair_def: PairDefinition
    price: Optional[float]
    bid: Optional[float]
    ask: Optional[float]
    last: Optional[float]  # 'last' is often the one used for price
    timestamp: Optional[int]  # Unix timestamp ms
    raw_ticker: Dict  # The original ticker from CCXT for additional data


class PriceUpdateInfo(NamedTuple):
    pair_def: PairDefinition
    price: float
    source_exchange_id: str
    timestamp: datetime  # Python datetime object
