from django.db import models


class TokenAllocation(models.Model):
    cmc_id = models.IntegerField(unique=True, verbose_name="CMC ID")
    name = models.CharField(max_length=255, verbose_name="代币名称")
    symbol = models.CharField(max_length=50, verbose_name="代币符号")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        db_table = "token_allocations"
        verbose_name = "代币分配"
        verbose_name_plural = "代币分配"

    def __str__(self):
        return f"{self.symbol} ({self.cmc_id})"


class AllocationCategory(models.Model):
    token = models.ForeignKey(TokenAllocation, on_delete=models.CASCADE, related_name="categories", verbose_name="代币")
    name = models.CharField(max_length=100, null=True, blank=True, verbose_name="分配类别")
    percentage = models.DecimalField(max_digits=7, decimal_places=4, verbose_name="分配比例")
    unlocked_percent = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True, verbose_name="已解锁比例")
    unlock_progress = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True, verbose_name="解锁进度")

    class Meta:
        db_table = "token_allocation_categories"
        verbose_name = "分配类别"
        verbose_name_plural = "分配类别"

    def __str__(self):
        return f"{self.token.symbol} - {self.name} - {self.percentage}%"
