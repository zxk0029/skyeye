import logging

from django.core.management.base import BaseCommand
from common.helpers import d0, dec, sleep
from exchange.models import Symbol
from backoffice.models import OtcAssetPrice
from exchange.controllers import get_history_orderbook


class Command(BaseCommand):
    def handle(self, *args, **options):
        symbol_list = Symbol.objects.filter(status="Active", category="Spot")
        for symbol in symbol_list:
            order_book = get_history_orderbook("binance", symbol.name)
            sell_price = order_book.bids[0].price
            buy_price = order_book.asks[0].price
            avg_price = (sell_price + buy_price) / 2
            usd_cny_price = "6.33"
            OtcAssetPrice.objects.create(
                asset=symbol.quote_asset,
                usd_price=dec(avg_price),
                cny_price=dec(avg_price * dec(usd_cny_price))
            )
