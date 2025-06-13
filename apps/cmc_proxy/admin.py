from django.contrib import admin

from .models import CmcAsset, CmcMarketData, CmcKline


@admin.register(CmcAsset)
class CmcAssetAdmin(admin.ModelAdmin):
    list_display = ('id', 'cmc_id', 'symbol', 'name', 'date_added', 'updated_at')
    search_fields = ('symbol', 'name', 'cmc_id')
    readonly_fields = ('created_at', 'updated_at')
    list_filter = ('tags',)


@admin.register(CmcMarketData)
class CmcMarketDataAdmin(admin.ModelAdmin):
    list_display = ('asset', 'asset_symbol', 'timestamp', 'price_usd', 'market_cap', 'volume_24h', 'cmc_rank')
    search_fields = ('asset__symbol', 'asset__name')
    list_select_related = ('asset',)
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'timestamp'
    raw_id_fields = ('asset',)  # 对有大量资产的情况进行性能优化

    @admin.display(description='Symbol', ordering='asset__symbol')
    def asset_symbol(self, obj):
        return obj.asset.symbol


@admin.register(CmcKline)
class CmcKlineAdmin(admin.ModelAdmin):
    list_display = ('id', 'asset_symbol', 'timeframe', 'timestamp', 'open', 'close', 'volume')
    list_filter = ('timeframe',)
    search_fields = ('asset__symbol', 'asset__name')
    list_select_related = ('asset',)
    date_hierarchy = 'timestamp'
    raw_id_fields = ('asset',)

    @admin.display(description='Symbol', ordering='asset__symbol')
    def asset_symbol(self, obj):
        return obj.asset.symbol
