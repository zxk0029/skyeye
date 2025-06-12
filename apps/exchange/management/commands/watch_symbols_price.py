#!/usr/bin/env python
# -*- coding: utf-8 -*-

import asyncio
import signal
import time

from django.core.management.base import BaseCommand

from common.helpers import getLogger
from apps.exchange.services.stablecoin_price_service_orchestrator import StablecoinPriceServiceOrchestrator
from apps.exchange.consts import STABLECOIN_PRICE_MONITOR_INTERVAL

logger = getLogger(__name__)


class Command(BaseCommand):
    help = '监控基于稳定币的交易对价格，并更新到Redis和数据库'

    def add_arguments(self, parser):
        parser.add_argument(
            '--exclude-exchanges',
            dest='exclude_exchanges',
            help='要排除的交易所，逗号分隔，例如 "yobit,ascendex"'
        )
        parser.add_argument(
            '--only-exchanges',
            dest='only_exchanges',
            help='只处理指定的交易所，逗号分隔，例如 "binance,okx,kucoin"'
        )
        parser.add_argument(
            '--monitor-interval',
            dest='monitor_interval',
            type=int,
            default=STABLECOIN_PRICE_MONITOR_INTERVAL,
            help=f'默认监控间隔(秒)，默认值: {STABLECOIN_PRICE_MONITOR_INTERVAL}'
        )

    def handle(self, *args, **options):
        exclude_exchanges_cli = []
        if options['exclude_exchanges']:
            exclude_exchanges_cli = [ex.strip().lower() for ex in options['exclude_exchanges'].split(',')]
            logger.info(f"将排除以下交易所 (CLI): {', '.join(exclude_exchanges_cli)}")

        only_exchanges_cli = []
        if options['only_exchanges']:
            only_exchanges_cli = [ex.strip().lower() for ex in options['only_exchanges'].split(',')]
            logger.info(f"只处理以下交易所 (CLI): {', '.join(only_exchanges_cli)}")
            
        monitor_interval = options['monitor_interval']
        logger.info(f"默认监控间隔: {monitor_interval}秒")

        # 创建 Orchestrator 实例
        orchestrator = StablecoinPriceServiceOrchestrator(
            exclude_exchanges_cli=exclude_exchanges_cli,
            only_exchanges_cli=only_exchanges_cli,
            monitor_interval=monitor_interval
        )

        loop = asyncio.get_event_loop()
        main_task = None

        # 用于跟踪信号处理状态
        is_shutting_down = False
        
        # 简化的信号处理函数
        def signal_handler(sig):
            nonlocal is_shutting_down
            
            # 防止重复处理信号
            if is_shutting_down:
                logger.debug(f"已经在关闭过程中，忽略信号 {sig.name}")
                return
                
            is_shutting_down = True
            logger.info(f"收到信号 {sig.name}, 开始关闭...")
            
            # 只有当orchestrator已初始化时才需要停止
            if orchestrator and (orchestrator.is_running or orchestrator._initialized):
                asyncio.ensure_future(orchestrator.stop(), loop=loop)

            # 取消主任务以中断运行
            if main_task and not main_task.done():
                main_task.cancel()

        # 注册信号处理器
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, signal_handler, sig)

        start_time = time.time()
        try:
            logger.info("以持续监控模式启动 Orchestrator...")

            # 创建并运行主任务
            main_task = loop.create_task(orchestrator.start_monitoring())
            loop.run_until_complete(main_task)

        except (KeyboardInterrupt, asyncio.CancelledError):
            logger.info("收到中断信号，正在关闭服务...")

        except Exception as e:
            logger.error(f"Orchestrator 运行出错: {e}", exc_info=True)

        finally:
            # 确保正确关闭
            if orchestrator and not is_shutting_down:  # 只有在尚未通过信号处理开始关闭时才调用
                try:
                    if loop.is_running():
                        loop.run_until_complete(orchestrator.stop())
                    else:
                        # 如果主循环已停止，使用新循环
                        asyncio.run(orchestrator.stop())
                except Exception as e:
                    logger.error(f"关闭 Orchestrator 时出错: {e}", exc_info=True)

            duration = time.time() - start_time
            logger.info(f"Orchestrator 服务已停止，总运行时间: {duration:.2f} 秒")
