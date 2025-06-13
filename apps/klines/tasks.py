import asyncio
from celery import shared_task
from typing import Optional

from common.helpers import getLogger
from apps.exchange.models import Market
from apps.klines.services import KlineService

logger = getLogger(__name__)


@shared_task(name="update_market_klines")
def update_market_klines(market_identifier: str, interval: str = '1d', days_back: int = 30):
    """
    更新指定市场的K线数据
    
    Args:
        market_identifier: 市场标识符
        interval: K线时间周期
        days_back: 获取多少天前的数据
    
    Returns:
        任务执行状态
    """
    loop = None
    try:
        logger.info(f"启动K线更新任务: {market_identifier} {interval}")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # 执行K线更新
        service = KlineService("")  # 初始化时交易所ID为空，会在update_klines中设置
        records_count, status = loop.run_until_complete(
            service.update_klines(market_identifier, interval, days_back)
        )
        loop.run_until_complete(service.close())
        
        return {
            "status": status,
            "market": market_identifier,
            "interval": interval,
            "records_count": records_count
        }
        
    except Exception as e:
        logger.error(f"更新K线时出错: {e}", exc_info=True)
        return {
            "status": "error",
            "market": market_identifier,
            "interval": interval,
            "message": str(e)
        }
    finally:
        if loop and not loop.is_closed():
            loop.close()


@shared_task(name="update_all_market_klines")
def update_all_market_klines(exchange_id: Optional[str] = None,
                           symbol_filter: Optional[str] = None,
                           interval: str = '1d',
                           days_back: int = 30,
                           limit: Optional[int] = None):
    """
    更新所有或指定交易所/交易对的K线数据
    
    Args:
        exchange_id: 可选，限定交易所ID
        symbol_filter: 可选，限定交易对（可以是部分匹配）
        interval: K线时间周期
        days_back: 获取多少天前的数据
        limit: 限制处理的市场数量
    
    Returns:
        任务执行状态汇总
    """
    from django.db.models import Q
    
    try:
        # 构建查询条件
        query = Q(status='Trading')
        
        if exchange_id:
            query &= Q(exchange__slug=exchange_id)
            
        if symbol_filter:
            query &= Q(market_symbol__icontains=symbol_filter)
        
        # 获取需要更新的市场
        markets = Market.objects.filter(query)
        
        if limit:
            markets = markets[:limit]
            
        market_count = markets.count()
        logger.info(f"找到 {market_count} 个符合条件的市场，准备更新K线数据")
        
        # 为每个市场创建更新任务
        tasks = []
        for market in markets:
            task = update_market_klines.delay(
                market.market_identifier,
                interval=interval,
                days_back=days_back
            )
            tasks.append(task.id)
            
        return {
            "status": "scheduled",
            "markets_count": market_count,
            "interval": interval,
            "tasks": tasks
        }
    
    except Exception as e:
        logger.error(f"调度K线更新任务时出错: {e}", exc_info=True)
        return {
            "status": "error",
            "message": str(e)
        } 