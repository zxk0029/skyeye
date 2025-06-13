from django.contrib import admin
from django_celery_beat.admin import PeriodicTaskAdmin
from apps.exchange.models import (
    Asset,
    Exchange,
    ExchangeAccount,
    TradingPair,
    Market,
    Kline
)


@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display = ('symbol', 'name', 'uint', 'is_stablecoin', 'status', 'chain_name', 'contract_address')
    search_fields = ('symbol', 'name', 'contract_address')
    list_filter = ('status', 'is_stablecoin', 'chain_name')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(Exchange)
class ExchangeAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'slug', 'exchange_category', 'status', 'chain_name', 'created_at')
    search_fields = ('name', 'slug', 'chain_name')
    list_filter = ('status', 'exchange_category', 'chain_name')
    readonly_fields = ('created_at', 'updated_at')
    list_per_page = 50
    ordering = ('-created_at',)
    list_display_links = ('id', 'name')


@admin.register(ExchangeAccount)
class ExchangeAccountAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'status')


@admin.register(TradingPair)
class TradingPairAdmin(admin.ModelAdmin):
    list_display = ('id', 'symbol_display', 'base_asset', 'quote_asset', 'category', 'status')
    search_fields = ('symbol_display', 'base_asset__symbol', 'quote_asset__symbol')
    list_filter = ('category', 'status')
    raw_id_fields = ('base_asset', 'quote_asset')


@admin.register(Market)
class MarketAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'exchange', 'trading_pair', 'market_symbol', 'market_identifier',
        'status', 'is_active_on_exchange', 'last_synced_at',
        'created_at', 'updated_at'
    )
    search_fields = (
        'exchange__name', 'exchange__slug', 'trading_pair__symbol_display',
        'market_symbol', 'market_identifier'
    )
    list_filter = (
        'status',
        'trading_pair__category',
        'exchange__name',
        'is_active_on_exchange'
    )
    raw_id_fields = ('exchange', 'trading_pair')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(Kline)
class KlineAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'market', 'interval', 'open_time', 'open_price',
        'high_price', 'low_price', 'close_price', 'volume', 'is_final',
        'created_at', 'updated_at'
    )
    search_fields = ('market__market_identifier',)
    list_filter = ('interval', 'is_final', 'market')
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'open_time'
