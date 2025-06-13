#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import time

from celery import group
from django.core.management.base import BaseCommand

from common.helpers import getLogger
from apps.exchange.tasks.tasks import process_exchange
from apps.exchange.utils import get_exchange_slug_map

logger = getLogger(__name__)


class Command(BaseCommand):
    help = 'Crawls exchanges for symbols and updates Market information using Celery for parallel processing.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--exchanges', nargs='*', type=str,
            help='Specific exchange names to crawl. If not provided, crawls all active CEX exchanges.',
        )
        parser.add_argument(
            '--parallel', action='store_true',
            help='Run tasks in parallel using Celery (default). Use --no-parallel to execute tasks immediately in process.',
        )
        parser.add_argument(
            '--no-parallel', dest='parallel', action='store_false',
            help='Execute tasks immediately in process without using Celery.',
        )
        parser.add_argument(
            '--batch-size', type=int, default=10,
            help='Number of exchanges to process in each batch (default: 10)',
        )
        parser.set_defaults(parallel=True)

    def handle(self, *args, **options):
        exchanges_param = options['exchanges']
        use_parallel = options['parallel']
        batch_size = options['batch_size']

        # 根据CPU核心数自动调整批次大小
        cpu_count = os.cpu_count() or 4
        if batch_size == 10:  # 如果使用默认值，则根据CPU核心数调整
            batch_size = max(5, min(cpu_count * 2, 20))  # 最小5个，最大20个

        self.stdout.write(f"CPU 核心数: {cpu_count}, 批次大小: {batch_size}")

        slug_map = get_exchange_slug_map()
        if exchanges_param:
            mapped_slugs = []
            for param in exchanges_param:
                key = param.lower()
                if key in slug_map:
                    mapped_slugs.append(slug_map[key])
                else:
                    self.stdout.write(self.style.WARNING(f"交易所 '{param}' 未在slug或别名中找到，跳过。"))
            exchange_slugs = list(set(mapped_slugs))
        else:
            exchange_slugs = list(set(slug_map.values()))

        if not exchange_slugs:
            self.stdout.write(self.style.WARNING("数据库中未找到活跃的CEX交易所。"))
            return

        self.stdout.write(self.style.SUCCESS(f"开始为以下交易所启动broker crawler: {', '.join(exchange_slugs)}"))

        total_start_time = time.time()

        if use_parallel:
            # 使用Celery并行处理
            total_exchanges = len(exchange_slugs)
            total_batches = (total_exchanges + batch_size - 1) // batch_size  # 向上取整

            self.stdout.write(
                self.style.SUCCESS(f"将 {total_exchanges} 个交易所分为 {total_batches} 批处理，每批 {batch_size} 个"))

            # 按批次处理交易所
            for i in range(0, total_exchanges, batch_size):
                batch = exchange_slugs[i:i + batch_size]
                batch_num = i // batch_size + 1

                self.stdout.write(f"提交批次 {batch_num}/{total_batches}: {', '.join(batch)}")

                # 为这一批创建任务组并执行
                tasks = [process_exchange.s(slug) for slug in batch]
                job = group(tasks)
                result = job.apply_async()

                # 如果不是最后一批，等待1秒再提交下一批，避免过度拥堵
                if i + batch_size < total_exchanges:
                    time.sleep(1)

            total_duration = time.time() - total_start_time
            self.stdout.write(self.style.SUCCESS(
                f"已分批提交 {total_exchanges} 个交易所爬取任务到Celery队列，总用时 {total_duration:.2f}秒"))
            self.stdout.write(self.style.SUCCESS("任务在后台处理中，您可以通过查看Celery日志跟踪进度"))
        else:
            # 不使用Celery，直接在当前进程中执行（主要用于调试）
            self.stdout.write(self.style.WARNING("在不使用Celery的情况下执行 - 这将在当前进程中同步运行所有任务"))
            for slug in exchange_slugs:
                self.stdout.write(f"开始处理交易所: {slug}")
                start = time.time()
                process_exchange(slug)
                duration = time.time() - start
                self.stdout.write(f"完成处理交易所: {slug}，耗时: {duration:.2f}秒")

            total_duration = time.time() - total_start_time
            self.stdout.write(self.style.SUCCESS(f"所有交易所处理完成，总用时: {total_duration:.2f}秒"))
