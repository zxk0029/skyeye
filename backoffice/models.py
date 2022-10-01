from django.db import models
from common.model_fields import DecField
from exchange.models import Symbol, Asset, Exchange
from common.models import BaseModel


class MgObPersistence(BaseModel):
    symbol = models.ForeignKey(
        Symbol, related_name='price_symbol',
        null=True, blank=True,
        on_delete=models.CASCADE
    )
    exchange = models.ForeignKey(
        Exchange, related_name='price_exchange',
        null=True, blank=True,
        on_delete=models.CASCADE
    )
    base_asset = models.ForeignKey(
        Asset, related_name='base_asset',
        null=True, blank=True,
        on_delete=models.CASCADE
    )
    qoute_asset = models.ForeignKey(
        Asset, related_name='qoute_asset',
        null=True, blank=True,
        on_delete=models.CASCADE
    )
    sell_price = DecField(default=0)
    buy_price = DecField(default=0)
    usd_price = DecField(default=0)
    cny_price = DecField(default=0)
    avg_price = DecField(default=0)
    margin = DecField(default=0)
    ratio = DecField(default=0)

    class Meta:
        pass

    def as_dict(self):
        return {
            'symbol': self.symbol.name,
            'base_asset': self.base_asset.name,
            'qoute_asset': self.qoute_asset.name,
            'sell_price': format(self.sell_price, ".4f"),
            'buy_price': format(self.buy_price, ".4f"),
            'avg_price': format(self.avg_price, ".4f"),
            'usd_price': format(self.usd_price, ".4f"),
            'cny_price': format(self.cny_price, ".4f"),
            'margin':  format(self.margin, ".2f"),
        }


class OtcAssetPrice(BaseModel):
    asset = models.ForeignKey(
        Asset, related_name='otc_asset',
        null=True, blank=True,
        on_delete=models.CASCADE
    )
    usd_price = DecField(default=0)
    cny_price = DecField(default=0)
    margin =  DecField(default=0)

    class Meta:
        pass

    def as_dict(self):
        return {
            'asset': self.asset.name,
            'usd_price': format(self.usd_price, ".4f"),
            'cny_price': format(self.cny_price, ".4f"),
            'margin': format(self.cny_price, ".4f")
        }
