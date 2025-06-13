from django.db import models, transaction
from django.utils import timezone
from decimal import Decimal

from apps.cmc_proxy.models import CmcAsset
from common.model_fields import DecField
from common.models import BaseModel


class TokenHolderManager(models.Manager):
    async def batch_save_from_api_data(self, asset, holders_data: list):
        """批量保存持有者数据"""
        if not holders_data:
            return 0

        # 删除旧数据
        await self.filter(asset=asset).adelete()
        
        # 去重处理：使用字典确保每个地址只保留一条记录
        unique_holders = {}
        for holder_data in holders_data:
            address = holder_data.get('address')
            if not address:
                continue
                
            # 如果地址已存在，保留order较小的（排名更高的）
            if address in unique_holders:
                if holder_data.get('order', 999999) < unique_holders[address].get('order', 999999):
                    unique_holders[address] = holder_data
            else:
                unique_holders[address] = holder_data
        
        # 创建新数据
        holders_to_create = []
        for address, holder_data in unique_holders.items():
            # 计算总金额
            balance = Decimal(str(holder_data.get('balance', 0)))
            price = Decimal(str(holder_data.get('price', 0))) if holder_data.get('price') else None
            total_amount = balance * price if price else None
            
            # 拼接浏览器地址
            explorer_template = holder_data.get('addressExplorerUrl', '')
            explorer_url = explorer_template.replace('%s', address) if explorer_template else None
            
            holder = self.model(
                asset=asset,
                platform_id=holder_data.get('platformId'),
                token_address=holder_data.get('tokenAddress', ''),
                token_creator=holder_data.get('tokenCreator', False),
                address=address,
                balance=balance,
                percent=holder_data.get('percent', 0),
                order=holder_data.get('order', 0),
                price=price,
                total_amount=total_amount,
                explorer_url=explorer_url,
                last_updated=timezone.now()
            )
            holders_to_create.append(holder)
        
        if holders_to_create:
            await self.abulk_create(holders_to_create, batch_size=100)
        
        return len(holders_to_create)


class TokenHoldingsSummaryManager(models.Manager):
    async def update_or_create_from_api_data(self, asset, api_data: dict):
        """从API数据创建或更新持仓汇总信息"""
        data = api_data.get('data', {})
        
        defaults = {
            'fgp': data.get('fgp'),
            'sgp': data.get('sgp'),
            'show_sgp': data.get('showSgp', False),
            'others': data.get('others'),
            'holder_count': data.get('holderCount'),
            'last_updated': timezone.now()
        }
        
        # 过滤掉None值
        defaults = {k: v for k, v in defaults.items() if v is not None}
        
        return await self.aupdate_or_create(asset=asset, defaults=defaults)


class TokenHolder(BaseModel):
    """代币持有者信息"""
    asset = models.ForeignKey(CmcAsset, on_delete=models.CASCADE, related_name="holders")
    platform_id = models.IntegerField(help_text="区块链平台ID")
    token_address = models.CharField(max_length=255, help_text="代币合约地址")
    token_creator = models.BooleanField(default=False, help_text="是否为代币创建者")
    address = models.CharField(max_length=255, db_index=True, help_text="持有者地址")
    balance = DecField(decimal_places=18, max_digits=40, help_text="持有数量")
    percent = models.FloatField(help_text="占比百分比")
    order = models.IntegerField(help_text="排名")
    price = DecField(decimal_places=18, max_digits=40, null=True, blank=True, help_text="代币价格")
    total_amount = DecField(decimal_places=8, max_digits=40, null=True, blank=True, help_text="持仓总金额(USD)")
    explorer_url = models.URLField(blank=True, null=True, help_text="区块浏览器地址")
    last_updated = models.DateTimeField(auto_now=True, help_text="最后更新时间")
    
    objects = TokenHolderManager()
    
    class Meta:
        db_table = "token_holders"
        unique_together = ("asset", "address")
        ordering = ['order']
        verbose_name = "代币持有者"
        verbose_name_plural = "代币持有者"
        
    def __str__(self):
        return f"{self.asset.symbol} - {self.address[:10]}... ({self.percent}%)"


class TokenHoldingsSummary(BaseModel):
    """代币持仓汇总信息"""
    asset = models.OneToOneField(CmcAsset, on_delete=models.CASCADE, related_name="holdings_summary", primary_key=True)
    fgp = models.FloatField(help_text="前几大持有者占比总和")
    sgp = models.FloatField(null=True, blank=True, help_text="二级持有者占比")
    show_sgp = models.BooleanField(default=False, help_text="是否显示二级占比")
    others = models.FloatField(help_text="其他持有者占比")
    holder_count = models.IntegerField(help_text="持有者总数")
    last_updated = models.DateTimeField(auto_now=True, help_text="最后更新时间")
    
    objects = TokenHoldingsSummaryManager()
    
    class Meta:
        db_table = "token_holdings_summary"
        verbose_name = "代币持仓汇总"
        verbose_name_plural = "代币持仓汇总"
        
    def __str__(self):
        return f"{self.asset.symbol} - {self.holder_count} holders"
