from celery import shared_task

from apps.token_unlocks.services import CMCUnlockService


@shared_task
def update_token_unlocks_task():
    """
    更新代币解锁数据的Celery任务
    """
    result = CMCUnlockService.update_unlocks()
    return f"代币解锁数据已更新: 新增{result['created']}个，更新{result['updated']}个"
