from django.db import models


class TokenUnlock(models.Model):
    cmc_id = models.IntegerField(unique=True, verbose_name="CMC ID")
    name = models.CharField(max_length=255, verbose_name="代币名称")
    symbol = models.CharField(max_length=50, verbose_name="代币符号")
    next_unlock_date = models.DateTimeField(null=True, blank=True, verbose_name="下次解锁日期")
    next_unlock_amount = models.DecimalField(max_digits=50, decimal_places=10, null=True, blank=True, verbose_name="下次解锁数量")
    next_unlock_percentage = models.DecimalField(max_digits=7, decimal_places=4, null=True, blank=True, verbose_name="下次解锁百分比")
    total_locked = models.DecimalField(max_digits=50, decimal_places=10, null=True, blank=True, verbose_name="总锁仓量")
    total_unlocked = models.DecimalField(max_digits=50, decimal_places=10, null=True, blank=True, verbose_name="已解锁量")
    total_supply = models.DecimalField(max_digits=50, decimal_places=10, null=True, blank=True, verbose_name="总供应量")
    locked_ratio = models.DecimalField(max_digits=7, decimal_places=4, null=True, blank=True, verbose_name="锁仓百分比")
    unlocked_ratio = models.DecimalField(max_digits=7, decimal_places=4, null=True, blank=True, verbose_name="释放百分比")
    max_supply = models.DecimalField(max_digits=50, decimal_places=10, null=True, blank=True, verbose_name="最大供应量")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        db_table = "token_unlocks"
        verbose_name = "代币解锁"
        verbose_name_plural = "代币解锁"

    def __str__(self):
        return f"{self.symbol} ({self.cmc_id})"


class UnlockEvent(models.Model):
    token = models.ForeignKey(TokenUnlock, on_delete=models.CASCADE, related_name="events", verbose_name="代币")
    unlock_date = models.DateTimeField(verbose_name="解锁日期")
    unlock_amount = models.DecimalField(max_digits=50, decimal_places=10, verbose_name="解锁数量")
    unlock_percentage = models.DecimalField(max_digits=7, decimal_places=4, null=True, blank=True, verbose_name="解锁百分比")
    allocation_name = models.CharField(max_length=100, null=True, blank=True, verbose_name="分配名称")
    vesting_type = models.CharField(max_length=50, null=True, blank=True, verbose_name="归属类型")
    
    class Meta:
        db_table = "token_unlock_events"
        verbose_name = "解锁事件"
        verbose_name_plural = "解锁事件"
        ordering = ['unlock_date']

    def __str__(self):
        return f"{self.token.symbol} - {self.unlock_date.strftime('%Y-%m-%d')} - {self.unlock_percentage}%"
