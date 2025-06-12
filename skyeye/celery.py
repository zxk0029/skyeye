import os
import time
from pathlib import Path

from celery import Celery

def detect_system_timezone():
    """
    自动检测系统时区，用于Celery定时任务执行
    优先级：CELERY_TIMEZONE环境变量 > 系统检测 > UTC默认
    """
    # 1. 优先使用CELERY_TIMEZONE环境变量设置（专门用于定时任务）
    env_timezone = os.environ.get('CELERY_TIMEZONE')
    if env_timezone:
        return env_timezone
    
    try:
        # 2. 尝试从系统文件读取时区（Linux/macOS）
        if Path('/etc/timezone').exists():
            with open('/etc/timezone', 'r') as f:
                return f.read().strip()
        
        # 3. 尝试从符号链接获取时区（大多数Linux系统）
        if Path('/etc/localtime').is_symlink():
            link_target = os.readlink('/etc/localtime')
            # 提取类似 /usr/share/zoneinfo/Asia/Shanghai 中的 Asia/Shanghai
            if '/zoneinfo/' in link_target:
                return link_target.split('/zoneinfo/')[-1]
        
        # 4. macOS方式：使用系统命令
        import subprocess
        try:
            result = subprocess.run(['readlink', '/etc/localtime'], 
                                    capture_output=True, text=True, timeout=5)
            if result.returncode == 0 and '/zoneinfo/' in result.stdout:
                return result.stdout.strip().split('/zoneinfo/')[-1]
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        
        # 5. 使用Python的时区检测
        import datetime
        local_tz = datetime.datetime.now().astimezone().tzinfo
        tz_name = str(local_tz)
        
        # 映射常见的时区缩写到标准IANA时区名称
        timezone_mapping = {
            'CST': 'Asia/Shanghai',  # 中国标准时间
            'JST': 'Asia/Tokyo',     # 日本标准时间
            'KST': 'Asia/Seoul',     # 韩国标准时间
            'EST': 'America/New_York', # 美东标准时间
            'PST': 'America/Los_Angeles', # 美西标准时间
            'GMT': 'Europe/London',   # 格林威治标准时间
            'CET': 'Europe/Paris',    # 中欧时间
        }
        
        if tz_name in timezone_mapping:
            return timezone_mapping[tz_name]
        
        # 6. 根据UTC偏移量推测时区
        utc_offset = time.timezone / -3600  # 转换为小时
        offset_mapping = {
            8: 'Asia/Shanghai',      # UTC+8 (中国、新加坡等)
            9: 'Asia/Tokyo',         # UTC+9 (日本、韩国)
            0: 'UTC',                # UTC+0 (英国等)
            -5: 'America/New_York',  # UTC-5 (美东)
            -8: 'America/Los_Angeles', # UTC-8 (美西)
        }
        
        if utc_offset in offset_mapping:
            return offset_mapping[utc_offset]
            
    except Exception:
        pass
    
    # 7. 默认返回UTC
    return 'UTC'

# 设置默认Django settings模块
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'skyeye.settings')

app = Celery('skyeye')

# 使用字符串表示，这样worker不需要序列化配置对象
app.config_from_object('django.conf:settings', namespace='CELERY')

# 自定义Celery配置
app.conf.update(
    # 任务速率限制 - 提高限制或取消限制
    # task_default_rate_limit='10/m',  # 默认每分钟最多10个任务

    # 任务执行设置
    task_acks_late=True,  # 任务完成后才确认
    worker_prefetch_multiplier=1,  # 每个 worker 进程一次预取1个任务
    task_time_limit=900,  # 15分钟超时

    # 添加并发设置
    worker_concurrency=8,  # 每个worker的并发数

    # 禁用DNS缓存
    broker_transport_options={
        'global_keyprefix': 'skyeye:',
        'socket_timeout': 60.0,
        'socket_connect_timeout': 30.0,
    },

    # 并发控制
    worker_max_tasks_per_child=20,  # 每个worker进程处理20个任务后重启，有助于释放资源和防止内存泄漏

    # 优化任务路由
    task_default_queue='celery',
    task_create_missing_queues=True,

    # 启用任务优先级
    task_queue_max_priority=10,
    task_default_priority=5,

    # 时区配置：自动检测系统时区
    timezone=detect_system_timezone(),

)

# 自动从所有已注册的Django app中加载tasks
app.autodiscover_tasks()
