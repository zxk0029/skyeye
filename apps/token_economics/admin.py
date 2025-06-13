from django.contrib import admin

from .models import TokenAllocation, AllocationCategory


@admin.register(TokenAllocation)
class TokenAllocationAdmin(admin.ModelAdmin):
    list_display = ('cmc_id', 'symbol', 'name', 'updated_at')
    search_fields = ('symbol', 'name')


@admin.register(AllocationCategory)
class AllocationCategoryAdmin(admin.ModelAdmin):
    list_display = ('token', 'name', 'percentage', 'unlocked_percent', 'unlock_progress')
    search_fields = ('token__symbol', 'name')
