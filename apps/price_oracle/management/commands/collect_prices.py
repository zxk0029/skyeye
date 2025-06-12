#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import time
from django.core.management.base import BaseCommand
from django.utils import timezone
from common.helpers import getLogger
from apps.price_oracle.adapters import AdapterFactory, get_exchange_prices
from apps.price_oracle.redis_service import redis_service
from apps.price_oracle.scheduler import IndependentScheduler

logger = getLogger(__name__)


class Command(BaseCommand):
    help = '采集交易所价格数据并存入Redis'

    def add_arguments(self, parser):
        parser.add_argument(
            '--exchange', type=str,
            help='只采集指定交易所的价格',
        )
        parser.add_argument(
            '--interval', type=int, default=0,
            help='循环采集间隔（秒），0表示只运行一次',
        )

    def handle(self, *args, **options):
        exchange = options.get('exchange')
        interval = options['interval']

        if exchange:
            self.stdout.write(f"🎯 采集交易所: {exchange}")
            exchanges = [exchange]
        else:
            exchanges = AdapterFactory.get_supported_exchanges()
            self.stdout.write(f"🎯 采集所有支持的交易所: {', '.join(exchanges)}")

        if interval > 0:
            self.stdout.write("🎯 独立调度模式 - 每个交易所真正独立调度 (Ctrl+C 停止)")
            self.run_independent_loop(exchanges)
        else:
            self.stdout.write("🚀 单次采集模式")
            self.run_once(exchanges)

    def run_once(self, exchanges: list):
        """单次采集 - 并行执行"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # 并行采集所有交易所
            total_saved = loop.run_until_complete(self.collect_all_exchanges_parallel(exchanges))
            self.stdout.write(f"✅ 采集完成，共保存 {total_saved} 个价格到Redis")
            
        finally:
            loop.close()

    async def collect_all_exchanges_parallel(self, exchanges: list) -> int:
        """并行采集所有交易所"""
        self.stdout.write(f"📡 并行采集 {len(exchanges)} 个交易所...")
        
        # 创建并行任务
        tasks = []
        for exchange in exchanges:
            task = asyncio.create_task(self.collect_exchange_prices(exchange))
            tasks.append(task)
        
        # 等待所有任务完成
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 统计结果
        total_saved = 0
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                self.stdout.write(f"  ❌ {exchanges[i]}: 采集异常 - {result}")
            else:
                total_saved += result
        
        return total_saved

    def run_independent_loop(self, exchanges: list):
        """独立调度循环"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            loop.run_until_complete(self.independent_collect_loop(exchanges))
        finally:
            loop.close()

    async def independent_collect_loop(self, exchanges: list):
        """独立调度采集循环"""
        scheduler = IndependentScheduler(exchanges, self.collect_single_exchange)
        
        try:
            await scheduler.start()
        except KeyboardInterrupt:
            self.stdout.write("\n🛑 收到停止信号，正在停止调度器...")
            scheduler.stop()
            self.stdout.write("✅ 独立调度器已停止")

    async def collect_single_exchange(self, exchange: str) -> int:
        """采集单个交易所（适配调度器接口）"""
        try:
            # 获取价格数据
            prices = await get_exchange_prices(exchange)
            
            if not prices:
                return 0
            
            # 转换为字典格式
            price_dicts = []
            for price_data in prices:
                price_dict = {
                    'symbol': price_data.symbol,
                    'base_asset': price_data.base_asset,
                    'quote_asset': price_data.quote_asset,
                    'exchange': exchange,
                    'price': float(price_data.price),
                    'volume_24h': float(price_data.volume_24h) if price_data.volume_24h else 0,
                    'price_change_24h': float(price_data.price_change_24h) if price_data.price_change_24h else 0,
                }
                price_dicts.append(price_dict)
            
            # 保存到Redis
            saved_count = redis_service.save_prices_to_redis(exchange, price_dicts)
            return saved_count
            
        except Exception as e:
            logger.error(f"采集 {exchange} 价格失败: {e}")
            raise

    async def collect_exchange_prices(self, exchange: str) -> int:
        """采集单个交易所的价格"""
        try:
            self.stdout.write(f"  📡 采集 {exchange} 价格...")
            
            # 获取价格数据
            prices = await get_exchange_prices(exchange)
            
            if not prices:
                self.stdout.write(f"  ⚠️  {exchange}: 未获取到价格数据")
                return 0
            
            # 转换为字典格式
            price_dicts = []
            for price_data in prices:
                price_dict = {
                    'symbol': price_data.symbol,
                    'base_asset': price_data.base_asset,
                    'quote_asset': price_data.quote_asset,
                    'exchange': exchange,
                    'price': float(price_data.price),
                    'volume_24h': float(price_data.volume_24h) if price_data.volume_24h else 0,
                    'price_change_24h': float(price_data.price_change_24h) if price_data.price_change_24h else 0,
                }
                price_dicts.append(price_dict)
            
            # 保存到Redis
            saved_count = redis_service.save_prices_to_redis(exchange, price_dicts)
            
            if saved_count > 0:
                self.stdout.write(f"  ✅ {exchange}: 保存 {saved_count} 个价格到Redis")
            else:
                self.stdout.write(f"  ❌ {exchange}: 保存失败")
            
            return saved_count
            
        except Exception as e:
            self.stdout.write(f"  ❌ {exchange}: 采集失败 - {e}")
            logger.error(f"采集 {exchange} 价格失败: {e}")
            return 0