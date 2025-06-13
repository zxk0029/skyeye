import logging

import requests

from apps.token_economics.models import TokenAllocation, AllocationCategory
from apps.token_unlocks.models import TokenUnlock

logger = logging.getLogger(__name__)


class CMCAllocationService:
    BASE_URL = "https://api.coinmarketcap.com/data-api/v3/token-unlock/allocations"

    @classmethod
    def fetch_allocation(cls, cmc_id):
        """
        从CoinMarketCap获取代币分配数据
        
        Args:
            cmc_id: CoinMarketCap代币ID
            
        Returns:
            dict: 代币分配数据
        """
        params = {'cryptoId': cmc_id}
        try:
            logger.info(f"正在从CoinMarketCap获取代币(ID:{cmc_id})的分配数据")
            response = requests.get(cls.BASE_URL, params=params)
            response.raise_for_status()
            data = response.json()
            if data['status']['error_message'] == 'SUCCESS':
                logger.info(f"成功获取代币(ID:{cmc_id})的分配数据")
                return data['data']
            else:
                logger.error(f"CMC API错误: {data['status']['error_message']}")
                raise Exception(f"CMC API错误: {data['status']['error_message']}")
        except requests.exceptions.RequestException as e:
            logger.error(f"请求CMC API失败: {str(e)}")
            raise

    @classmethod
    def update_allocation(cls, cmc_id):
        """
        更新指定代币的分配数据
        """
        try:
            allocation_data = cls.fetch_allocation(cmc_id)
            token_unlock = TokenUnlock.objects.get(cmc_id=cmc_id)
            token_name = token_unlock.name
            token_symbol = token_unlock.symbol
            
            token_allocation, created = TokenAllocation.objects.update_or_create(
                cmc_id=cmc_id,
                defaults={
                    'name': token_name,
                    'symbol': token_symbol
                }
            )
            
            # 更新分配类别数据
            token_allocation.categories.all().delete()
            categories_created = 0
            
            # 正确访问tokenAllocations数据
            for category in allocation_data.get('tokenAllocations', []):
                AllocationCategory.objects.create(
                    token=token_allocation,
                    name=category.get('allocationName'),
                    percentage=category.get('totalPercent'),
                    unlocked_percent=category.get('unlockedPercent'),
                    unlock_progress=category.get('unlockProgress')
                )
                categories_created += 1
                
            status = "created" if created else "updated"
            logger.info(f"代币(ID:{cmc_id})的分配数据{status}，共{categories_created}个分配类别")
            return {"token": status, "categories_created": categories_created}
        except Exception as e:
            logger.error(f"更新代币(ID:{cmc_id})的分配数据失败: {str(e)}")
            raise
