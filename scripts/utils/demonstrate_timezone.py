#!/usr/bin/env python3
"""
时区配置演示脚本
清楚地展示当前系统的时区配置和环境变量的作用
"""

import os
import sys
import time
import datetime
from pathlib import Path

def demonstrate_timezone_config():
    """演示时区配置的实际效果"""
    
    print("🕐 SkyEye 时区配置演示")
    print("=" * 60)
    
    # 1. 环境变量状态
    print("\n📋 环境变量状态：")
    time_zone = os.environ.get('TIME_ZONE')
    celery_timezone = os.environ.get('CELERY_TIMEZONE')
    
    print(f"  TIME_ZONE = {time_zone if time_zone else '未设置'}")
    print(f"  CELERY_TIMEZONE = {celery_timezone if celery_timezone else '未设置'}")
    
    # 2. 各组件时区配置
    print("\n⚙️ 各组件时区配置：")
    
    # Django配置（模拟）
    django_timezone = 'UTC'  # 固定在settings.py中
    print(f"  Django TIME_ZONE: {django_timezone} (固定在settings.py)")
    print(f"  ├─ 作用: 数据库存储、API返回、django.utils.timezone.now()")
    print(f"  └─ 受环境变量影响: ❌ 不受TIME_ZONE环境变量影响")
    
    # Celery配置
    def detect_celery_timezone():
        if celery_timezone:
            return celery_timezone
        
        # 自动检测逻辑（简化版）
        if Path('/etc/localtime').is_symlink():
            link_target = os.readlink('/etc/localtime')
            if '/zoneinfo/' in link_target:
                return link_target.split('/zoneinfo/')[-1]
        
        utc_offset = time.timezone / -3600
        offset_mapping = {8: 'Asia/Shanghai', 9: 'Asia/Tokyo', 0: 'UTC', -5: 'America/New_York'}
        return offset_mapping.get(utc_offset, 'UTC')
    
    celery_tz = detect_celery_timezone()
    print(f"  Celery timezone: {celery_tz}")
    print(f"  ├─ 作用: 定时任务调度（crontab执行时间）")
    print(f"  └─ 受环境变量影响: ✅ 受CELERY_TIMEZONE环境变量影响")
    
    # 3. 时间对比
    print("\n🌍 时间对比演示：")
    now_local = datetime.datetime.now()
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    
    print(f"  服务器本地时间: {now_local.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  UTC时间:        {now_utc.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    
    # 4. 定时任务执行示例
    print(f"\n⏰ 定时任务执行示例（基于{celery_tz}）：")
    print(f"  配置: crontab(hour=3, minute=40)")
    print(f"  执行: 服务器本地时间 03:40")
    if celery_tz != 'UTC':
        # 计算UTC时间
        utc_offset = time.timezone / -3600
        utc_hour = (3 - utc_offset) % 24
        print(f"  对应UTC时间: {utc_hour:02.0f}:40")
    
    # 5. 数据存储示例
    print(f"\n📊 数据存储示例：")
    print(f"  假设本地时间: 2025-06-12 15:30:00")
    print(f"  存储到数据库: 2025-06-12 07:30:00 UTC (假设UTC+8)")
    print(f"  API返回时间:  2025-06-12 07:30:00 UTC")
    print(f"  客户端显示:   根据客户端时区转换")
    
    # 6. 配置建议
    print(f"\n💡 配置建议：")
    
    if time_zone:
        print(f"  ⚠️  发现TIME_ZONE环境变量: {time_zone}")
        print(f"      这个变量现在不再生效，建议删除")
        print(f"      如需配置定时任务时区，请使用: CELERY_TIMEZONE={time_zone}")
    
    if not celery_timezone:
        print(f"  ✅ 当前使用自动检测: {celery_tz}")
        print(f"     如需手动指定定时任务时区，可设置: CELERY_TIMEZONE={celery_tz}")
    else:
        print(f"  ✅ 手动配置定时任务时区: {celery_timezone}")
    
    print(f"\n📚 详细说明请参考: docs/deployment/TIMEZONE_CONFIG.md")

def main():
    demonstrate_timezone_config()

if __name__ == '__main__':
    main()