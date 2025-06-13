#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import time

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.price_oracle.services import price_service
from apps.price_oracle.redis_service import redis_service
from common.helpers import getLogger

logger = getLogger(__name__)


class Command(BaseCommand):
    help = '从Redis读取价格数据并持久化到数据库'

    def add_arguments(self, parser):
        parser.add_argument(
            '--batch-size', type=int, default=5000,
            help='每次处理的价格数量（默认100）',
        )
        parser.add_argument(
            '--interval', type=int, default=0,
            help='循环处理间隔（秒），0表示只运行一次',
        )
        parser.add_argument(
            '--cleanup', action='store_true',
            help='处理后清理过期的Redis数据',
        )

    def handle(self, *args, **options):
        batch_size = options['batch_size']
        interval = options['interval']
        cleanup = options['cleanup']

        if interval > 0:
            self.stdout.write(f"🔄 循环模式: 每 {interval} 秒处理一次 (Ctrl+C 停止)")
            self.stdout.write(f"📦 批处理大小: {batch_size}")
            self.stdout.write("⚡ 使用优化模式")
            self.run_loop(batch_size, interval, cleanup)
        else:
            self.stdout.write("🚀 单次处理模式")
            self.stdout.write("⚡ 使用优化模式")
            total_processed = self.process_once(batch_size, cleanup)
            self.stdout.write(f"✅ 处理完成，共持久化 {total_processed} 个价格")

    def run_loop(self, batch_size: int, interval: int, cleanup: bool):
        """循环处理模式"""
        try:
            while True:
                self.stdout.write(f"\n📊 {timezone.now().strftime('%Y-%m-%d %H:%M:%S')} 开始处理...")

                # 显示队列状态
                queue_size = redis_service.get_queue_size()
                if queue_size > 0:
                    self.stdout.write(f"📋 Redis队列中有 {queue_size} 个待处理价格")

                    processed_count = self.process_once(batch_size, cleanup)
                    self.stdout.write(f"✅ 本次处理 {processed_count} 个价格")
                else:
                    self.stdout.write("📭 Redis队列为空，等待新数据...")

                self.stdout.write(f"⏳ 等待 {interval} 秒...")
                time.sleep(interval)

        except KeyboardInterrupt:
            self.stdout.write("\n🛑 收到停止信号，退出处理")

    def process_once(self, batch_size: int, cleanup: bool) -> int:
        """单次处理"""
        total_processed = 0

        while True:
            # 从Redis队列获取价格数据
            start_time = time.time()
            prices = redis_service.get_prices_from_queue(batch_size)

            if not prices:
                break

            # 保存到数据库
            saved_count = price_service.save_prices_to_db_upsert(prices)

            total_processed += saved_count
            processing_time = time.time() - start_time

            self.stdout.write(f"  💾 批次处理: {len(prices)} 个价格，保存 {saved_count} 个 "
                              f"(耗时: {processing_time:.2f}s)")

            # 如果这批数据量少于批处理大小，说明队列已空
            if len(prices) < batch_size:
                break

        # 清理过期数据
        if cleanup and total_processed > 0:
            self.stdout.write("🧹 清理过期数据...")

            # 清理Redis中的过期数据
            redis_deleted = redis_service.clear_old_prices(hours=2)
            if redis_deleted > 0:
                self.stdout.write(f"  🗑️  Redis: 清理 {redis_deleted} 个过期缓存")

        return total_processed

    def show_stats(self):
        """显示统计信息"""
        try:
            # Redis统计
            redis_stats = redis_service.get_stats()
            self.stdout.write("📊 系统状态:")
            self.stdout.write(f"  Redis队列: {redis_stats.get('queue_size', 0)} 项")
            self.stdout.write(f"  Redis缓存: {redis_stats.get('total_price_keys', 0)} 项")

            # 数据库统计
            from apps.price_oracle.models import AssetPrice
            db_count = AssetPrice.objects.count()
            self.stdout.write(f"  数据库记录: {db_count} 条")

            # 最近更新统计
            from datetime import timedelta
            recent_cutoff = timezone.now() - timedelta(minutes=30)
            recent_count = AssetPrice.objects.filter(
                price_timestamp__gte=recent_cutoff
            ).count()
            self.stdout.write(f"  近30分钟更新: {recent_count} 条")

        except Exception as e:
            self.stdout.write(f"  ⚠️  获取统计信息失败: {e}")
