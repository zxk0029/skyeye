import asyncio
import logging
from typing import List

from celery import shared_task

from apps.cmc_proxy.models import CmcAsset
from apps.token_holdings.services import TokenHoldingsService

logger = logging.getLogger(__name__)


@shared_task(bind=True)
def update_token_holdings_daily_task(cmc_ids: List[int] = None, max_concurrent: int = 5):
    """
    每日更新代币持仓数据的Celery任务
    
    Args:
        cmc_ids: 指定要更新的CMC ID列表，为空则更新所有
        max_concurrent: 最大并发数，默认5（避免API限制）
    """
    return asyncio.run(_async_update_token_holdings(cmc_ids, max_concurrent))


async def _async_update_token_holdings(cmc_ids: List[int] = None, max_concurrent: int = 5):
    """异步更新代币持仓数据"""
    try:
        if not cmc_ids:
            # 获取所有CMC资产
            cmc_ids = []
            async for asset in CmcAsset.objects.all():
                cmc_ids.append(asset.cmc_id)

        if not cmc_ids:
            logger.info("No CMC assets found to update")
            return {'success': True, 'message': 'No assets to update'}

        logger.info(f"Starting daily token holdings update for {len(cmc_ids)} assets")

        async with TokenHoldingsService() as service:
            results = await service.batch_update_holdings(cmc_ids, max_concurrent=max_concurrent)

            success_count = sum(1 for success, _ in results.values() if success)
            failure_count = len(results) - success_count

            logger.info(f"Token holdings update completed: {success_count} successful, {failure_count} failed")

            return {
                'success': True,
                'total': len(cmc_ids),
                'success_count': success_count,
                'failure_count': failure_count,
                'message': f'Updated {success_count}/{len(cmc_ids)} assets'
            }

    except Exception as e:
        logger.error(f"Error in daily token holdings update: {str(e)}")
        return {'success': False, 'error': str(e)}
