from django.core.management.base import BaseCommand
from django.utils import timezone
from decimal import Decimal

from apps.backoffice.models import OtcAssetPrice
from apps.backoffice.utils import get_usd_cny_rate, get_prices_from_orderbook
from apps.exchange.models import Market, MarketStatusChoices
from common.helpers import getLogger

logger = getLogger(__name__)


class Command(BaseCommand):
    help = 'Calculates and updates OTC asset prices based on exchange order book data and stored USD/CNY rate.'

    def handle(self, *args, **options):
        logger.info("Starting OTC asset price update task")
        usd_cny_rate = get_usd_cny_rate()
        if not usd_cny_rate:
            logger.error("Could not retrieve USD to CNY rate. Aborting OTC asset price update.")
            return

        # Iterate over active Markets. OTC price relevance might require specific market filters (e.g., specific exchanges or categories)
        # For now, let's assume we process for all active trading markets as a starting point.
        market_list = Market.objects.filter(
            status=MarketStatusChoices.TRADING,
            exchange__status='Active' 
        ).select_related(
            'exchange', 'trading_pair', 'trading_pair__base_asset', 'trading_pair__quote_asset'
        )

        if not market_list.exists():
            logger.warning("No active markets found to process for OTC asset prices.")
            return

        updated_count = 0
        created_count = 0
        skipped_count = 0

        for market in market_list:
            try:
                # get_prices_from_orderbook expects a TradingPair and an Exchange object.
                # This util might need adjustment if it was deeply tied to ExchangeSymbolShip structure
                # For now, assuming it can work with market.trading_pair and market.exchange
                price_data = get_prices_from_orderbook(symbol=market.trading_pair, exchange=market.exchange)

                if price_data is None:
                    logger.debug(f"No price data from orderbook for {market.exchange.name} - {market.trading_pair.symbol_display}. Skipping OTC price update.")
                    skipped_count += 1
                    continue
                
                avg_price, sell_price, buy_price = price_data
                cny_price_calculated = avg_price * usd_cny_rate

                # OtcAssetPrice links directly to an Asset. We need to decide which asset to price.
                # Typically, it would be the base_asset of the trading_pair.
                asset_to_price = market.trading_pair.base_asset

                otc_price_obj, created = OtcAssetPrice.objects.update_or_create(
                    asset=asset_to_price, # Link to the base asset
                    exchange_name=market.exchange.name, # Store which exchange this price observation comes from
                    defaults={
                        'sell_price': sell_price,
                        'buy_price': buy_price,
                        'usd_price': avg_price,
                        'cny_price': cny_price_calculated,
                        'avg_price': avg_price, # Redundant with usd_price? Retaining for now.
                        'margin': Decimal("0.05"),  # Example margin, should be configurable
                        'last_updated': timezone.now()
                    }
                )

                if created:
                    created_count += 1
                    logger.info(f"Created OtcAssetPrice for {asset_to_price.symbol} from {market.exchange.name} market {market.market_symbol}: USD {avg_price}, CNY {cny_price_calculated}")
                else:
                    updated_count += 1
                    logger.info(f"Updated OtcAssetPrice for {asset_to_price.symbol} from {market.exchange.name} market {market.market_symbol}: USD {avg_price}, CNY {cny_price_calculated}")

            except Exception as e:
                logger.error(
                    f"Error updating OtcAssetPrice for asset from market {market.id} ({market.market_symbol}): {e}",
                    exc_info=True
                )
                skipped_count += 1

        logger.info(f"Finished OTC asset price update. Created: {created_count}, Updated: {updated_count}, Skipped: {skipped_count}")
