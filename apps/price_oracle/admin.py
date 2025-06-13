#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from django.contrib import admin
from django.utils.html import format_html

from .models import AssetPrice


@admin.register(AssetPrice)
class AssetPriceAdmin(admin.ModelAdmin):
    list_display = [
        'base_asset', 'symbol', 'quote_asset', 'exchange', 
        'price', 'price_change_24h', 'volume_24h', 
        'exchange_priority', 'quote_priority', 'price_timestamp',
        'stale_status'
    ]
    list_filter = ['exchange', 'quote_asset', 'exchange_priority', 'quote_priority']
    search_fields = ['base_asset', 'symbol', 'exchange']
    ordering = ['base_asset']
    readonly_fields = ['created_at', 'updated_at', 'stale_status']
    
    def stale_status(self, obj):
        if obj.is_stale:
            return format_html('<span style="color: red;">过期</span>')
        else:
            return format_html('<span style="color: green;">正常</span>')
    stale_status.short_description = '数据状态'
    
    def has_add_permission(self, request):
        return False  # 价格数据由系统自动更新，禁止手动添加
