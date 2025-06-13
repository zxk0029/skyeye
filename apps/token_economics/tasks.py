from celery import shared_task
from apps.token_economics.services import CMCAllocationService
from apps.token_unlocks.models import TokenUnlock


@shared_task
def update_token_allocations_task():
    """
    更新代币分配数据的Celery任务
    """
    updated_count = 0
    error_count = 0
    for token in TokenUnlock.objects.all():
        try:
            CMCAllocationService.update_allocation(token.cmc_id)
            updated_count += 1
        except Exception as e:
            error_count += 1
            print(f"更新代币ID {token.cmc_id} 的分配信息失败: {str(e)}")
    return f"代币分配数据已更新: 成功{updated_count}个，失败{error_count}个" 