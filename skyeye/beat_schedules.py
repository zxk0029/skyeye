from celery.schedules import crontab


# 定时任务配置 (使用模块路径.函数名格式，便于追溯和调试)
DEFAULT_BEAT_SCHEDULE = {
    'daily_full_data_sync': {
        'task': 'apps.cmc_proxy.tasks.daily_full_data_sync',
        'schedule': crontab(hour=3, minute=0),  # 每天凌晨3点执行
        'options': {'queue': 'celery'},
    },
    'process_pending_cmc_batch_requests': {
        'task': 'apps.cmc_proxy.tasks.process_pending_cmc_batch_requests',
        'schedule': 2.0,  # 每2秒，贴合API限制
        'options': {'queue': 'celery'},
    },
    'sync_cmc_data_to_db': {
        'task': 'apps.cmc_proxy.tasks.sync_cmc_data_task',
        'schedule': 1.0,  # 每1秒同步到数据库
        'options': {'queue': 'celery'},
    },
    'hourly_cmc_klines_update': {
        'task': 'apps.cmc_proxy.tasks.update_cmc_klines',
        'schedule': crontab(minute=15),  # 每小时过15分执行，更新最新1小时K线数据
        'options': {'queue': 'celery'},
        'kwargs': {'count': 1},  # 每次只更新1小时数据
    },
    'daily_token_holdings_update': {
        'task': 'apps.token_holdings.tasks.update_token_holdings_daily_task',
        'schedule': crontab(hour=4, minute=0),  # 每天凌晨4点执行
        'options': {'queue': 'celery'},
        'kwargs': {'max_concurrent': 5},  # 限制并发数避免API限频
    },
    'daily_token_unlocks_update': {
        'task': 'apps.token_unlocks.tasks.update_token_unlocks_task',
        'schedule': crontab(hour=5, minute=0),  # 每天凌晨5点执行
        'options': {'queue': 'celery'},
    },
    'daily_token_allocations_update': {
        'task': 'apps.token_economics.tasks.update_token_allocations_task',
        'schedule': crontab(hour=6, minute=0),  # 每天凌晨6点分执行
        'options': {'queue': 'celery'},
    },
}
