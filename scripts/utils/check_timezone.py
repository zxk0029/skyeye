#!/usr/bin/env python3
"""
时区检测验证工具
用于验证系统的自动时区检测功能是否正常工作
"""

import os
import sys
import time
import datetime
from pathlib import Path

def detect_system_timezone():
    """
    自动检测系统时区，用于Celery定时任务执行
    优先级：CELERY_TIMEZONE环境变量 > 系统检测 > UTC默认
    """
    detection_methods = []
    
    # 1. 优先使用CELERY_TIMEZONE环境变量设置（专门用于定时任务）
    env_timezone = os.environ.get('CELERY_TIMEZONE')
    if env_timezone:
        detection_methods.append(f"环境变量 CELERY_TIMEZONE: {env_timezone}")
        return env_timezone, detection_methods
    
    try:
        # 2. 尝试从系统文件读取时区（Linux/macOS）
        if Path('/etc/timezone').exists():
            with open('/etc/timezone', 'r') as f:
                tz = f.read().strip()
                detection_methods.append(f"系统文件 /etc/timezone: {tz}")
                return tz, detection_methods
        
        # 3. 尝试从符号链接获取时区（大多数Linux系统）
        if Path('/etc/localtime').is_symlink():
            link_target = os.readlink('/etc/localtime')
            detection_methods.append(f"符号链接 /etc/localtime: {link_target}")
            # 提取类似 /usr/share/zoneinfo/Asia/Shanghai 中的 Asia/Shanghai
            if '/zoneinfo/' in link_target:
                tz = link_target.split('/zoneinfo/')[-1]
                detection_methods.append(f"解析得到时区: {tz}")
                return tz, detection_methods
        
        # 4. macOS方式：使用系统命令
        import subprocess
        try:
            result = subprocess.run(['readlink', '/etc/localtime'], 
                                    capture_output=True, text=True, timeout=5)
            if result.returncode == 0 and '/zoneinfo/' in result.stdout:
                tz = result.stdout.strip().split('/zoneinfo/')[-1]
                detection_methods.append(f"macOS readlink命令: {tz}")
                return tz, detection_methods
        except (subprocess.TimeoutExpired, FileNotFoundError):
            detection_methods.append("macOS readlink命令: 不可用")
        
        # 5. 使用Python的时区检测
        local_tz = datetime.datetime.now().astimezone().tzinfo
        tz_name = str(local_tz)
        detection_methods.append(f"Python时区对象: {tz_name}")
        
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
            mapped_tz = timezone_mapping[tz_name]
            detection_methods.append(f"时区映射 {tz_name} -> {mapped_tz}")
            return mapped_tz, detection_methods
        
        # 6. 根据UTC偏移量推测时区
        utc_offset = time.timezone / -3600  # 转换为小时
        detection_methods.append(f"UTC偏移量: {utc_offset}小时")
        
        offset_mapping = {
            8: 'Asia/Shanghai',      # UTC+8 (中国、新加坡等)
            9: 'Asia/Tokyo',         # UTC+9 (日本、韩国)
            0: 'UTC',                # UTC+0 (英国等)
            -5: 'America/New_York',  # UTC-5 (美东)
            -8: 'America/Los_Angeles', # UTC-8 (美西)
        }
        
        if utc_offset in offset_mapping:
            mapped_tz = offset_mapping[utc_offset]
            detection_methods.append(f"偏移量映射 UTC{utc_offset:+} -> {mapped_tz}")
            return mapped_tz, detection_methods
            
    except Exception as e:
        detection_methods.append(f"检测异常: {str(e)}")
    
    # 7. 默认返回UTC
    detection_methods.append("使用默认时区: UTC")
    return 'UTC', detection_methods

def main():
    """主函数：执行时区检测并显示详细信息"""
    print("🕐 SkyEye 智能时区检测工具")
    print("=" * 50)
    
    print("\n🎯 时区设计说明：")
    print("  📊 数据存储时区: UTC (确保数据一致性)")
    print("  ⏰ 定时任务时区: 服务器本地时区 (便于理解执行时间)")
    
    # 检测时区
    detected_tz, methods = detect_system_timezone()
    
    # 显示检测过程
    print("\n📋 定时任务时区检测过程：")
    for i, method in enumerate(methods, 1):
        print(f"  {i}. {method}")
    
    # 显示结果
    print(f"\n✅ 定时任务时区检测结果：{detected_tz}")
    
    # 显示当前时间信息
    now = datetime.datetime.now()
    utc_now = datetime.datetime.now(datetime.timezone.utc)
    
    print(f"\n🌍 时间信息对比：")
    print(f"  本地时间: {now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print(f"  UTC时间:  {utc_now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print(f"  时差:     UTC{time.timezone/-3600:+.0f}")
    
    # 显示定时任务时间示例
    print(f"\n⏰ 定时任务执行时间示例（基于 {detected_tz}）：")
    print(f"  每日3:40全量同步 = 本地时间 03:40")
    print(f"  每日4:00持仓更新 = 本地时间 04:00") 
    print(f"  每小时15分K线更新 = 每小时 xx:15")
    
    # 显示数据存储信息
    print(f"\n📊 数据存储说明：")
    print(f"  Django TIME_ZONE: UTC (固定)")
    print(f"  数据库时间戳: 统一使用UTC时间")
    print(f"  API返回时间: UTC时间（客户端可转换为本地时间）")
    
    # 环境变量建议
    print(f"\n⚙️ 环境变量配置：")
    celery_tz = os.environ.get('CELERY_TIMEZONE')
    if celery_tz:
        print(f"  当前设置: CELERY_TIMEZONE={celery_tz}")
        print(f"  检测结果: {detected_tz}")
        if celery_tz != detected_tz:
            print(f"  ⚠️  注意：环境变量与自动检测结果不同！")
    else:
        print(f"  建议配置: CELERY_TIMEZONE={detected_tz}")
        print(f"  或者保持空白，使用自动检测")
    
    print(f"\n✨ 检测完成！修改配置后需重启 Celery Beat 生效。")
    print(f"\n📚 详细说明请参考: docs/deployment/TIMEZONE_CONFIG.md")

if __name__ == '__main__':
    main()