#!/usr/bin/env python
# -*- coding: utf-8 -*-

import asyncio
import json
from collections import defaultdict

from django.core.management.base import BaseCommand
from django.utils import timezone

from common.helpers import getLogger
from apps.exchange.data_persistor import RedisDataPersistor

logger = getLogger(__name__)


class Command(BaseCommand):
    help = '分析Redis中的价格数据，统计各个维度的数据量'

    def handle(self, *args, **options):
        loop = asyncio.get_event_loop()
        try:
            loop.run_until_complete(self.analyze_redis_data())
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"分析Redis数据时出错: {e}"))

    async def analyze_redis_data(self):
        redis_persistor = RedisDataPersistor()
        
        try:
            self.stdout.write(self.style.SUCCESS("开始分析Redis中的价格数据..."))
            
            # 从Redis获取所有价格数据
            prices = await redis_persistor.get_all_prices()
            if not prices:
                self.stdout.write(self.style.WARNING("Redis中没有找到价格数据"))
                return
                
            self.stdout.write(self.style.SUCCESS(f"从Redis获取到{len(prices)}条价格记录"))
            
            # 分析统计
            base_assets = set()
            quote_assets = set()
            exchanges = set()
            base_asset_count = defaultdict(int)
            quote_asset_count = defaultdict(int)
            exchange_count = defaultdict(int)
            base_exchange_pairs = set()  # 基础资产和交易所的组合
            
            for pair_string, price_data in prices.items():
                base_symbol = price_data.get('symbol')
                quote_symbol = price_data.get('quote')
                exchange = price_data.get('source_exchange_id', 'unknown')
                
                if base_symbol:
                    base_assets.add(base_symbol)
                    base_asset_count[base_symbol] += 1
                    
                if quote_symbol:
                    quote_assets.add(quote_symbol)
                    quote_asset_count[quote_symbol] += 1
                    
                if exchange:
                    exchanges.add(exchange)
                    exchange_count[exchange] += 1
                
                if base_symbol and exchange:
                    base_exchange_pairs.add((base_symbol, exchange))
            
            # 输出统计结果
            self.stdout.write("\n== 统计结果 ==")
            self.stdout.write(f"总价格记录数: {len(prices)}")
            self.stdout.write(f"唯一基础资产数: {len(base_assets)}")
            self.stdout.write(f"唯一计价资产数: {len(quote_assets)}")
            self.stdout.write(f"唯一交易所数: {len(exchanges)}")
            self.stdout.write(f"基础资产和交易所组合数: {len(base_exchange_pairs)}")
            
            # 输出前10个最常见的基础资产
            self.stdout.write("\n== 最常见的基础资产 (前10个) ==")
            for base, count in sorted(base_asset_count.items(), key=lambda x: x[1], reverse=True)[:10]:
                self.stdout.write(f"{base}: {count}条记录")
                
            # 输出前5个最常见的计价资产
            self.stdout.write("\n== 最常见的计价资产 (前5个) ==")
            for quote, count in sorted(quote_asset_count.items(), key=lambda x: x[1], reverse=True)[:5]:
                self.stdout.write(f"{quote}: {count}条记录")
                
            # 输出各交易所的记录数
            self.stdout.write("\n== 各交易所的记录数 ==")
            for exchange, count in sorted(exchange_count.items(), key=lambda x: x[1], reverse=True):
                self.stdout.write(f"{exchange}: {count}条记录")
                
            # 对基础资产数量为1的检查，判断是否已经去重
            single_base_assets = [base for base, count in base_asset_count.items() if count == 1]
            self.stdout.write(f"\n只有一条记录的基础资产数: {len(single_base_assets)}")
            self.stdout.write(f"多于一条记录的基础资产数: {len(base_assets) - len(single_base_assets)}")
            
            # 基础资产与交易所的关系
            assets_per_exchange = defaultdict(set)
            for pair_string, price_data in prices.items():
                base_symbol = price_data.get('symbol')
                exchange = price_data.get('source_exchange_id', 'unknown')
                if base_symbol and exchange:
                    assets_per_exchange[exchange].add(base_symbol)
            
            self.stdout.write("\n== 各交易所的资产覆盖 ==")
            for exchange, assets in sorted(assets_per_exchange.items(), key=lambda x: len(x[1]), reverse=True):
                self.stdout.write(f"{exchange}: {len(assets)}种资产")
            
            # 查找多条记录的具体基础资产
            multi_record_assets = {base: count for base, count in base_asset_count.items() if count > 1}
            if multi_record_assets:
                self.stdout.write("\n== 具有多条记录的资产 (前20个) ==")
                for base, count in sorted(multi_record_assets.items(), key=lambda x: x[1], reverse=True)[:20]:
                    self.stdout.write(f"{base}: {count}条记录")
                    
                    # 详细分析第一个多记录资产
                    if base == list(sorted(multi_record_assets.items(), key=lambda x: x[1], reverse=True))[0][0]:
                        self.stdout.write(f"\n== {base}的详细记录 ==")
                        for pair_string, price_data in prices.items():
                            if price_data.get('symbol') == base:
                                exchange = price_data.get('source_exchange_id', 'unknown')
                                quote = price_data.get('quote')
                                price = price_data.get('price')
                                self.stdout.write(f"交易对: {pair_string}, 交易所: {exchange}, 计价货币: {quote}, 价格: {price}")
            
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"分析过程中出错: {e}"))
        finally:
            # 关闭Redis连接
            await redis_persistor.close()
            self.stdout.write(self.style.SUCCESS("分析完成")) 