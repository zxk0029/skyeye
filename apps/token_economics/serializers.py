from rest_framework import serializers

from .models import TokenAllocation, AllocationCategory


class AllocationCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = AllocationCategory
        fields = ['name', 'percentage', 'unlocked_percent', 'unlock_progress']


class TokenAllocationSerializer(serializers.ModelSerializer):
    categories = AllocationCategorySerializer(many=True, read_only=True)

    class Meta:
        model = TokenAllocation
        fields = ['cmc_id', 'name', 'symbol', 'categories', 'created_at', 'updated_at']
