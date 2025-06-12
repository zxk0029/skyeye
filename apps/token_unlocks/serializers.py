from rest_framework import serializers

from .models import TokenUnlock, UnlockEvent


class UnlockEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = UnlockEvent
        fields = ['unlock_date', 'unlock_amount', 'unlock_percentage', 'allocation_name', 'vesting_type']


class TokenUnlockSerializer(serializers.ModelSerializer):
    class Meta:
        model = TokenUnlock
        fields = [
            'cmc_id', 'name', 'symbol', 'locked_ratio', 'unlocked_ratio',
            'next_unlock_date', 'next_unlock_amount', 'next_unlock_percentage',
            'updated_at'
        ]


class TokenUnlockDetailSerializer(serializers.ModelSerializer):
    events = UnlockEventSerializer(many=True, read_only=True)

    class Meta:
        model = TokenUnlock
        fields = [
            'cmc_id', 'name', 'symbol', 'locked_ratio', 'unlocked_ratio',
            'next_unlock_date', 'next_unlock_amount', 'next_unlock_percentage',
            'created_at', 'updated_at',
            'events'
        ]
