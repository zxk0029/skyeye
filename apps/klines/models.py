from django.db import models
from django.utils.translation import gettext_lazy as _
from common.models import BaseModel
from apps.exchange.models import Market


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
        return f"{self.market.market_symbol} - {self.interval} - {self.open_time}"

    class Meta:
        verbose_name = _("K-line Data")
        verbose_name_plural = _("K-line Data")
        unique_together = [('market', 'interval', 'open_time')]
        indexes = [
            models.Index(fields=['market', 'interval', '-open_time']),
        ]
        db_table = 'klines'


class KlineProcessingLog(BaseModel):
    """K线处理日志，用于记录K线数据处理状态"""
    
    STATUS_CHOICES = [
        ('pending', _('等待处理')),
        ('processing', _('处理中')),
        ('completed', _('已完成')),
        ('failed', _('失败')),
    ]
    
    exchange = models.CharField(max_length=100, verbose_name=_('交易所'))
    symbol = models.CharField(max_length=100, verbose_name=_('交易对'))
    interval = models.CharField(max_length=10, choices=Kline.INTERVAL_CHOICES, verbose_name=_('K线周期'))
    start_time = models.DateTimeField(verbose_name=_('开始时间'))
    end_time = models.DateTimeField(verbose_name=_('结束时间'))
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name=_('状态'))
    records_count = models.IntegerField(default=0, verbose_name=_('记录数量'))
    error_message = models.TextField(blank=True, null=True, verbose_name=_('错误信息'))
    
    class Meta:
        verbose_name = _('K线处理日志')
        verbose_name_plural = _('K线处理日志')
        indexes = [
            models.Index(fields=['exchange', 'symbol', 'interval']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"{self.exchange} {self.symbol} {self.interval} ({self.status})"
