from django.core.management.base import BaseCommand

from apps.backoffice.models import MgObPersistence
from common.helpers import getLogger
from apps.exchange.models import Market, MarketStatusChoices
from apps.exchange.controllers import get_merged_orderbook

logger = getLogger(__name__)


class Command(BaseCommand):
    help = 'Updates the database with the latest order book data for all exchange symbols.'

    def handle(self, *args, **options):
        logger.info("Starting merged orderbook persistence task")
        market_list = Market.objects.filter(
            status=MarketStatusChoices.TRADING,
            exchange__status='Active'
        ).select_related('exchange', 'trading_pair', 'trading_pair__base_asset', 'trading_pair__quote_asset')

        if not market_list.exists():
            logger.warning("No active markets found to persist orderbooks for.")
            return

        for market in market_list:
            try:
                exchange_name = market.exchange.name
                symbol_display = market.trading_pair.symbol_display
                
                orderbook = get_merged_orderbook(symbol_display)
                if not orderbook or not orderbook.bids or not orderbook.asks:
                    logger.debug(f"No merged orderbook data for {exchange_name} - {symbol_display}. Skipping persistence.")
                    continue

                MgObPersistence.objects.create(
                    exchange_name=exchange_name,
                    symbol_display=symbol_display,
                    market_symbol=market.market_symbol,
                    exchange=market.exchange,
                    symbol=market.trading_pair,
                    orderbook=orderbook.as_json(),
                    base_asset=market.trading_pair.base_asset,
                    quote_asset=market.trading_pair.quote_asset
                )
                logger.info(f"Persisted merged orderbook for {exchange_name} - {symbol_display} (Market: {market.market_symbol})")
            except Exception as e:
                logger.error(
                    f"Error persisting merged orderbook for market {market.id if market else 'UnknownMarket'} ({market.market_symbol if market else 'N/A'}): {e}",
                    exc_info=True
                )
        logger.info("Finished merged orderbook persistence task")
