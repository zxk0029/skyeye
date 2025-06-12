from django.contrib import admin

from .models import TokenUnlock, UnlockEvent


@admin.register(TokenUnlock)
class TokenUnlockAdmin(admin.ModelAdmin):
    list_display = ('cmc_id', 'symbol', 'name', 'next_unlock_date', 'updated_at')
    search_fields = ('symbol', 'name')


@admin.register(UnlockEvent)
class UnlockEventAdmin(admin.ModelAdmin):
    list_display = ('token', 'unlock_date', 'unlock_percentage')
    search_fields = ('token__symbol',)
