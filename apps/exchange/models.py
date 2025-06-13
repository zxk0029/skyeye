#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import pickle
import time
from typing import Optional

from django.db import models
from django.db.models import Q, UniqueConstraint, JSONField
from django.utils.translation import gettext_lazy as _

from common.helpers import getLogger
from common.models import BaseModel
from common.redis_client import local_redis

logger = getLogger(__name__)


class CommonStatus(models.TextChoices):
    ACTIVE = 'Active', _('活跃')
    DOWN = 'Down', _('下线')


class ExchangeCate(models.TextChoices):
    CEX = 'Cex', _('中心化交易所')
    DEX = 'Dex', _('去中心化交易所')


class AssetStatusChoices(models.TextChoices):
    ACTIVE = 'Active', _('活跃')
    DELISTED = 'Delisted', _('已下架')


class SymbolCat(models.TextChoices):
    SPOT = 'Spot', _('现货')
    FUTURE = 'Future', _('期货')
    OPTION = 'Option', _('期权')
    UNKNOWN = 'Unknown', _('未知')


class MarketStatusChoices(models.TextChoices):
    TRADING = 'Trading', '交易中'
    HALTED = 'Halted', '已停牌'
    DELISTED = 'Delisted', '已下架'
    UNTRACKED = 'Untracked', '未追踪'
    PRE_LAUNCH = 'PreLaunch', '预上线'


class CacheManager(models.Manager):
    def filter(self, *args, expire: Optional[int] = None, **kwargs):
        if not expire:
            return super().filter(*args, **kwargs)
        r = local_redis()
        sub_keys = ",".join(f"{k}={v}" for k, v in kwargs.items())
        try:
            pickle_data = r.get(sub_keys)
            assert pickle_data, f'{self} did not get pickle data by {sub_keys} '
            json_data = pickle.loads(pickle_data)
            res = json_data['data']
        except:
            res = super().filter(*args, **kwargs)
            json_data = {'timestamp': time.time(), 'data': res.all()[:]}
            pickle_data = pickle.dumps(json_data)
            if len(pickle_data) < 5E7:
                r.set(sub_keys, pickle_data, ex=expire)
            else:
                logger.warning(f'Cache too large for query {sub_keys}')
        finally:
            return res


class Asset(BaseModel):
    symbol = models.CharField(
        max_length=50,
        verbose_name='资产符号',
        db_index=True,
        help_text="标准化的资产符号, e.g., BTC, ETH"
    )
    name = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="资产全名",
        help_text="资产全名, e.g., Bitcoin, Ethereum"
    )
    uint = models.PositiveSmallIntegerField("精度", null=True, blank=True, help_text="资产在交易所的下单精度")
    is_stablecoin = models.BooleanField(
        default=False,
        verbose_name='是否为稳定币'
    )
    status = models.CharField(
        max_length=20,
        choices=AssetStatusChoices,
        default='Active',
        verbose_name='资产状态'
    )
    chain_name = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        verbose_name="归属链",
        db_index=True,
        help_text="资产归属的链, e.g., ethereum, tron"
    )
    contract_address = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name="合约地址",
        db_index=True,
        help_text="链上资产的合约地址"
    )
    circulating_supply = models.DecimalField(
        max_digits=38, decimal_places=18, null=True, blank=True, verbose_name="流通供应量"
    )
    total_supply = models.DecimalField(
        max_digits=38, decimal_places=18, null=True, blank=True, verbose_name="总供应量"
    )
    max_supply = models.DecimalField(
        max_digits=38, decimal_places=18, null=True, blank=True, verbose_name="最大供应量"
    )
    supply_data_source = models.CharField(
        max_length=100, null=True, blank=True, verbose_name="供应量数据来源"
    )
    supply_last_updated = models.DateTimeField(
        null=True, blank=True, verbose_name="供应量最后更新时间"
    )
    logo_url = models.CharField(
        max_length=255, null=True, blank=True, verbose_name="Logo URL"
    )
    meta_data = JSONField(null=True, blank=True, verbose_name="其他元数据")

    class Meta:
        verbose_name = "资产"
        verbose_name_plural = "资产列表"
        constraints = [
            UniqueConstraint(
                fields=['chain_name', 'contract_address'],
                condition=Q(contract_address__isnull=False),
                name='uq_asset_token_chain_contract'
            ),
            UniqueConstraint(
                fields=['chain_name', 'symbol'],
                condition=Q(contract_address__isnull=True),
                name='uq_asset_native_chain_symbol'
            ),
            UniqueConstraint(
                fields=['symbol'],
                condition=Q(chain_name__isnull=True) & Q(contract_address__isnull=True),
                name='uq_asset_generic_symbol'
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.symbol})"

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "symbol": self.symbol,
            "unit": self.unit,
            "status": self.status
        }


class Exchange(BaseModel):
    name = models.CharField(
        max_length=100,
        unique=True,
        verbose_name='交易所名称'
    )
    status = models.CharField(
        max_length=20,
        choices=CommonStatus,
        default='Active',
        verbose_name='状态'
    )
    slug = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        verbose_name='唯一标识符',
        default="binance",
        help_text="用于内部代码引用和market_identifier构建的唯一简称, e.g., binance, uniswap_v3_ethereum"
    )
    exchange_category = models.CharField(
        max_length=20,
        choices=ExchangeCate,
        default="Cex",
        verbose_name='交易所类型'
    )
    meta_data = models.JSONField(
        null=True,
        blank=True,
        default=dict,
        verbose_name='元数据配置',
        help_text="DEX的Factory/Router地址、CEX的API限频或特殊参数等"
    )
    base_api_url = models.JSONField(
        null=True,
        blank=True,
        verbose_name='CEX API基地址',
        help_text="CEX的API基础地址"
    )
    chain_name = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        db_index=True,
        verbose_name='归属链名',
        help_text="DEX平台所在的链, e.g., ethereum, bsc"
    )
    logo_url = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name='Logo URL',
        help_text="交易所Logo图片的URL"
    )

    class Meta:
        verbose_name = "交易所"
        verbose_name_plural = "交易所列表"

    @property
    def is_active(self) -> bool:
        return self.status == 'Active'

    @property
    def is_down(self) -> bool:
        return not self.is_active

    def __str__(self):
        return self.name


class ExchangeAccount(BaseModel):
    exchange = models.ForeignKey(
        Exchange,
        related_name='accounts',
        on_delete=models.CASCADE
    )
    name = models.CharField(
        max_length=100,
        default='default',
        db_index=True
    )
    api_key = models.CharField(
        max_length=100,
        null=False
    )
    encrypted_secret = models.TextField(
        null=False,
        blank=True,
        default=''
    )
    secret = models.CharField(
        max_length=100,
        null=False,
        blank=True,
        default=''
    )
    password = models.CharField(
        max_length=100, null=True, default='', blank=True
    )
    alias = models.CharField(
        max_length=100, null=True, default='', blank=True
    )
    proxy = models.TextField(blank=True, null=True)
    testnet = models.BooleanField(default=False, blank=True)
    status = models.CharField(max_length=100, default='ACTIVE')
    enable = models.BooleanField(default=True)
    info = models.TextField(blank=True, null=True)

    class Meta:
        pass

    def __str__(self) -> str:
        return f'exchange: {self.exchange}, account: {self.name}'

    def to_dict(self):
        return {
            'name': self.exchange,
            'symbol': self.name,
            'api_key': self.api_key,
            'secret': self.secret,
            'alias': self.alias,
        }


class TradingPair(BaseModel):
    symbol_display = models.CharField(
        max_length=100,
        verbose_name='交易对显示名称'
    )
    base_asset = models.ForeignKey(
        Asset,
        blank=False,
        related_name='base_trading_pairs',
        null=False,
        on_delete=models.CASCADE,
        verbose_name='base资产'
    )
    quote_asset = models.ForeignKey(
        Asset,
        blank=False,
        related_name='quote_trading_pairs',
        null=False,
        on_delete=models.CASCADE,
        verbose_name='报价资产'
    )
    status = models.CharField(
        max_length=20,
        choices=AssetStatusChoices,
        default='Active',
        verbose_name='状态'
    )
    category = models.CharField(
        max_length=20,
        choices=SymbolCat.choices,
        default=SymbolCat.SPOT,
        verbose_name='类型'
    )

    class Meta:
        verbose_name = "通用交易对"
        verbose_name_plural = "通用交易对列表"
        constraints = [
            models.UniqueConstraint(fields=['base_asset', 'quote_asset', 'category'],
                                    name='uq_trading_pair_base_quote_cat')
        ]

    def __str__(self):
        return self.symbol_display

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.symbol_display,
            "symbol": self.base_asset.symbol,
            "uint": self.base_asset.uint,
            "status": self.status
        }


class Market(BaseModel):
    exchange = models.ForeignKey(
        Exchange,
        on_delete=models.CASCADE,
        related_name='markets',
        verbose_name='交易所'
    )
    trading_pair = models.ForeignKey(
        TradingPair,
        on_delete=models.CASCADE,
        related_name='markets',
        verbose_name='交易对'
    )
    category = models.CharField(
        max_length=20,
        choices=SymbolCat.choices,
        default=SymbolCat.SPOT,
        verbose_name='市场分类',
        db_index=True,
        help_text='该市场在交易所的主要分类 (e.g., Spot, Future, Option)'
    )
    market_identifier = models.CharField(
        max_length=150,
        unique=True,
        db_index=True,
        verbose_name='市场全局唯一标识符',
        help_text='系统生成的全局唯一市场ID, e.g., binance_spot_btc_usdt'
    )
    market_symbol = models.CharField(
        max_length=100,
        db_index=True,
        verbose_name='市场交易对符号',
        help_text="交易所在其API或接口中使用的具体交易对符号, e.g., BTCUSDT, ETH-USD"
    )
    status = models.CharField(
        max_length=20,
        choices=MarketStatusChoices.choices,
        default=MarketStatusChoices.TRADING,
        verbose_name='市场状态'
    )
    is_active_on_exchange = models.BooleanField(
        default=True,
        verbose_name='交易所是否活跃交易',
        help_text="Indicates if the market is currently active/tradable on the exchange according to the exchange API."
    )
    market_url = models.URLField(
        max_length=512, null=True, blank=True, verbose_name='市场URL'
    )
    precision_price = models.IntegerField(
        null=True, blank=True, verbose_name=_("价格精度"),
        help_text=_("价格显示精度的小数位数")
    )
    precision_amount = models.IntegerField(
        null=True, blank=True, verbose_name=_("数量精度"),
        help_text=_("数量显示精度的小数位数")
    )
    min_trade_size_base = models.DecimalField(
        max_digits=38, decimal_places=18, null=True, blank=True,
        verbose_name=_("最小下单量 (基础资产)"),
        help_text=_("最小下单量 - 基础资产")
    )
    min_trade_size_quote = models.DecimalField(
        max_digits=38, decimal_places=18, null=True, blank=True,
        verbose_name=_("最小下单额 (计价资产)"),
        help_text=_("最小下单额 - 计价资产")
    )
    meta_data = models.JSONField(
        null=True, blank=True, verbose_name='其他元数据'
    )
    last_synced_at = models.DateTimeField(
        null=True, blank=True, verbose_name='最后同步时间'
    )

    class Meta:
        verbose_name = "市场"
        verbose_name_plural = "市场列表"
        unique_together = [('exchange', 'trading_pair')]
        indexes = [
            models.Index(fields=['market_identifier']),
            models.Index(fields=['exchange', 'market_symbol']),
        ]

    def __str__(self):
        return f"{self.exchange.name} - {self.trading_pair.symbol_display} ({self.market_symbol})"

    def to_dict(self):
        return {
            "id": self.id,
            "exchange_id": self.exchange_id,
            "exchange_name": self.exchange.name,
            "trading_pair_id": self.trading_pair_id,
            "trading_pair_symbol": self.trading_pair.symbol_display,
            "market_symbol": self.market_symbol,
            "status": self.status,
            "is_active_on_exchange": self.is_active_on_exchange,
            "last_synced_at": self.last_synced_at.isoformat() if self.last_synced_at else None,
        }


class Kline(BaseModel):
    INTERVAL_CHOICES = [
        ('1m', _('1 Minute')),
        ('30m', _('30 Minutes')),
        ('1h', _('1 Hour')),
        ('1d', _('1 Day')),
        ('1w', _('1 Week')),
        ('1mo', _('1 Month')),
        ('3mo', _('3 Months')),
        ('12mo', _('12 Months')),
    ]

    id = models.BigAutoField(primary_key=True, verbose_name=_("Kline Record ID"))
    market = models.ForeignKey(
        Market,
        on_delete=models.CASCADE,
        to_field='market_identifier',
        db_column='market_identifier',
        related_name='klines',
        verbose_name=_("Market")
    )
    interval = models.CharField(max_length=10, choices=INTERVAL_CHOICES, verbose_name=_("K-line Interval"))
    open_time = models.DateTimeField(verbose_name=_("K-line Open Time (UTC)"))  # TIMESTAMPTZ in PG
    open_price = models.DecimalField(max_digits=38, decimal_places=18, verbose_name=_("Open Price"))
    high_price = models.DecimalField(max_digits=38, decimal_places=18, verbose_name=_("High Price"))
    low_price = models.DecimalField(max_digits=38, decimal_places=18, verbose_name=_("Low Price"))
    close_price = models.DecimalField(max_digits=38, decimal_places=18, verbose_name=_("Close Price"))
    volume = models.DecimalField(max_digits=38, decimal_places=18, verbose_name=_("Volume (Base Asset)"))
    quote_volume = models.DecimalField(max_digits=38, decimal_places=18, null=True, blank=True,
                                       verbose_name=_("Quote Volume (Quote Asset)"))
    trade_count = models.IntegerField(null=True, blank=True, verbose_name=_("Trade Count"))
    is_final = models.BooleanField(default=True, verbose_name=_("Is Final K-line"))  # Design: "一期可默认为TRUE"

    def __str__(self):
        return f"{self.market.market_identifier} - {self.interval} - {self.open_time.strftime('%Y-%m-%d %H:%M:%S')}"

    class Meta:
        verbose_name = _("K-line Data")
        verbose_name_plural = _("K-line Data")
        unique_together = [('market', 'interval', 'open_time')]
        indexes = [
            models.Index(fields=['market', 'interval', '-open_time']),
        ]
        db_table = 'klines'
