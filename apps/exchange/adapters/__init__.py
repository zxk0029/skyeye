from typing import Optional, Dict

from apps.exchange.adapters.base import BaseExchangeAdapter
from apps.exchange.adapters.binance_adapter import BinanceAdapter
from apps.exchange.adapters.cryptocom_adapter import CryptocomAdapter
from apps.exchange.adapters.generic_adapter import GenericExchangeAdapter
from apps.exchange.adapters.lbank_adapter import LbankAdapter
from apps.exchange.adapters.yobit_adapter import YobitAdapter

# Import other specific adapters here as they are created
# e.g., from .ascendex_adapter import AscendexAdapter

# ADAPTER_MAP helps in selecting a specific adapter for an exchange.
# Exchanges not in this map will use GenericExchangeAdapter by default.
ADAPTER_MAP: Dict[str, type[BaseExchangeAdapter]] = {
    'yobit': YobitAdapter,
    'binance': BinanceAdapter,
    'cryptocom': CryptocomAdapter,
    'lbank': LbankAdapter,
    # 'ascendex': AscendexAdapter, # Example for another specific adapter
}


def get_exchange_adapter(exchange_id: str, ccxt_config: Optional[Dict] = None) -> BaseExchangeAdapter:
    """
    Factory function to get an instance of the appropriate exchange adapter.

    Args:
        exchange_id: The ID of the exchange (e.g., 'binance', 'yobit').
        ccxt_config: Optional CCXT configuration dictionary for the adapter.

    Returns:
        An instance of a class derived from BaseExchangeAdapter.
    """
    exchange_id_lower = exchange_id.lower()
    AdapterClass = ADAPTER_MAP.get(exchange_id_lower, GenericExchangeAdapter)
    return AdapterClass(exchange_id_lower, ccxt_config=ccxt_config)
