from django.contrib import admin

from .models import TokenHolder, TokenHoldingsSummary


@admin.register(TokenHolder)
class TokenHolderAdmin(admin.ModelAdmin):
    list_display = ['asset_symbol', 'address_short', 'balance', 'percent', 'order', 'last_updated']
    list_filter = ['asset', 'token_creator', 'last_updated']
    search_fields = ['asset__symbol', 'address']
    ordering = ['asset', 'order']
    readonly_fields = ['last_updated', 'created_at', 'updated_at']
    
    def asset_symbol(self, obj):
        return obj.asset.symbol
    asset_symbol.short_description = '代币符号'
    
    def address_short(self, obj):
        return f"{obj.address[:10]}...{obj.address[-8:]}" if len(obj.address) > 20 else obj.address
    address_short.short_description = '地址'


@admin.register(TokenHoldingsSummary)
class TokenHoldingsSummaryAdmin(admin.ModelAdmin):
    list_display = ['asset_symbol', 'holder_count', 'fgp', 'others', 'last_updated']
    search_fields = ['asset__symbol']
    readonly_fields = ['last_updated', 'created_at', 'updated_at']
    ordering = ['-holder_count']
    
    def asset_symbol(self, obj):
        return obj.asset.symbol
    asset_symbol.short_description = '代币符号'