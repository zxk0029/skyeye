#!/usr/bin/env python
# -*- coding: utf-8 -*-

import asyncio
import json
from datetime import datetime
import time

from django.core.management.base import BaseCommand
from django.utils import timezone

from common.helpers import getLogger
from apps.exchange.data_persistor import RedisDataPersistor, DatabasePersistor
from apps.exchange.data_structures import PriceUpdateInfo, PairDefinition, PairIdentifier

logger = getLogger(__name__)


class Command(BaseCommand):
    help = '从Redis读取最新价格数据并同步到数据库'

    def add_arguments(self, parser):
        parser.add_argument(
            '--interval',
            dest='interval',
            type=int,
            default=5,  # 默认5秒
            help='数据同步间隔(秒)'
        )
        parser.add_argument(
            '--run-once',
            dest='run_once',
            action='store_true',
            default=False,
            help='只运行一次而不是持续运行'
        )

    def handle(self, *args, **options):
        interval = options['interval']
        run_once = options['run_once']
        
        if run_once:
            logger.info(f"将运行一次数据同步任务")
        else:
            logger.info(f"将以{interval}秒的间隔持续运行数据同步任务")
        
        loop = asyncio.get_event_loop()
        try:
            loop.run_until_complete(self.sync_price_data(interval, run_once))
        except KeyboardInterrupt:
            logger.info("收到中断信号，正在关闭...")
        except Exception as e:
            logger.error(f"同步价格数据时出错: {e}", exc_info=True)
    
    async def sync_price_data(self, interval: int, run_once: bool):
        """从Redis读取价格数据并同步到数据库"""
        redis_persistor = RedisDataPersistor()
        db_persistor = DatabasePersistor()
        
        # 用于调试的交易所ID集合
        exchange_ids = set()
        
        while True:
            start_time = time.time()
            try:
                # 从Redis获取所有价格数据
                prices = await redis_persistor.get_all_prices()
                if not prices:
                    logger.warning("Redis中没有找到价格数据")
                else:
                    logger.info(f"从Redis获取到{len(prices)}条价格记录")
                    
                    # 将Redis数据转换为PriceUpdateInfo对象
                    price_updates = []
                    for pair_string, price_data in prices.items():
                        try:
                            # 提取基本信息
                            base_symbol = price_data.get('symbol')
                            quote_symbol = price_data.get('quote')
                            exchange_id = price_data.get('source_exchange_id', 'unknown')
                            
                            # 收集交易所ID
                            exchange_ids.add(exchange_id)
                            
                            price = price_data.get('price')
                            exchange_symbol = price_data.get('exchange_symbol', f"{base_symbol}/{quote_symbol}")
                            timestamp_str = price_data.get('timestamp')
                            
                            if not all([base_symbol, quote_symbol, exchange_id, price]):
                                logger.warning(f"缺少必要数据，跳过记录: {pair_string}")
                                continue
                                
                            # 创建PairDefinition对象
                            pair_def = PairDefinition(
                                identifier=PairIdentifier(
                                    base_asset=base_symbol,
                                    quote_asset=quote_symbol
                                ),
                                exchange_symbol=exchange_symbol,
                                raw_pair_string=pair_string,
                                market_id=exchange_id  # 使用exchange_id作为market_id
                            )
                            
                            # 解析时间戳
                            try:
                                if timestamp_str:
                                    timestamp = datetime.fromisoformat(timestamp_str)
                                else:
                                    timestamp = timezone.now()
                            except ValueError:
                                timestamp = timezone.now()
                            
                            # 创建PriceUpdateInfo对象
                            price_update = PriceUpdateInfo(
                                pair_def=pair_def,
                                price=price,
                                source_exchange_id=exchange_id,
                                timestamp=timestamp
                            )
                            
                            price_updates.append(price_update)
                            
                        except Exception as e:
                            logger.error(f"处理价格记录时出错 ({pair_string}): {e}", exc_info=True)
                    
                    # 使用DatabasePersistor更新MgObPersistence
                    if price_updates:
                        logger.info(f"正在更新{len(price_updates)}条价格记录到MgObPersistence表")
                        successful, failed = await db_persistor.update_mgob_persistence(price_updates)
                        logger.info(f"价格同步完成，成功: {successful}, 失败: {failed}")
                        
                    # 打印收集到的交易所ID列表
                    logger.info(f"从Redis中收集到的交易所ID列表: {sorted(exchange_ids)}")
            
            except Exception as e:
                logger.error(f"同步过程中出错: {e}", exc_info=True)
            
            # 只运行一次则退出
            if run_once:
                break
                
            # 计算等待时间
            elapsed = time.time() - start_time
            wait_time = max(0.1, interval - elapsed)
            logger.info(f"同步完成，耗时{elapsed:.2f}秒，将在{wait_time:.2f}秒后再次运行")
            await asyncio.sleep(wait_time)
        
        # 关闭Redis连接
        await redis_persistor.close()
        logger.info("数据同步任务已完成")


