import asyncio
from typing import Dict, List, Optional

from common.helpers import getLogger
from apps.exchange.adapters import get_exchange_adapter
from apps.exchange.consts import STABLECOIN_PRICE_MONITOR_INTERVAL, EXCHANGE_SPECIFIC_INTERVALS
from apps.exchange.data_persistor import DataPersistor
from apps.exchange.interfaces import ExchangeInterface
from apps.exchange.market_data_provider import MarketDataProvider
from apps.exchange.price_fetcher import PriceFetcher
from apps.exchange.tasks.ticker_task import TickerTask

logger = getLogger(__name__)


class StablecoinPriceServiceOrchestrator:
    def __init__(
            self,
            exclude_exchanges_cli: Optional[List[str]] = None,
            only_exchanges_cli: Optional[List[str]] = None,
            monitor_interval: int = STABLECOIN_PRICE_MONITOR_INTERVAL
    ):
        self.exclude_exchanges_cli = exclude_exchanges_cli or []
        self.only_exchanges_cli = only_exchanges_cli or []
        self.default_monitor_interval = monitor_interval
        
        # 初始化交易所特定的监控间隔
        self.exchange_intervals = dict(EXCHANGE_SPECIFIC_INTERVALS)

        self.market_provider = MarketDataProvider()
        self.price_fetcher = PriceFetcher()
        self.persistor = DataPersistor()

        self.ticker_tasks: List[TickerTask] = []
        self.adapters: Dict[str, ExchangeInterface] = {}
        self._is_running = False
        self._initialized = False
        self._main_loop_task = None

    def _get_interval_for_exchange(self, exchange_id: str) -> int:
        """根据交易所ID获取合适的监控间隔"""
        # 返回特定交易所的间隔，如果没有则使用默认间隔
        return self.exchange_intervals.get(exchange_id, self.default_monitor_interval)

    async def initialize_service(self, fetch_all_available_on_exchange: bool = False) -> bool:
        """初始化服务组件"""
        if self._initialized:
            logger.info("Orchestrator: 服务已初始化，跳过")
            return True

        logger.info("Orchestrator: 初始化服务...")

        try:
            # 初始化市场数据提供者
            await self.market_provider._initialize_slug_map()
            await self.market_provider.initialize_filters(
                cli_only_exchanges=self.only_exchanges_cli, 
                cli_exclude_exchanges=self.exclude_exchanges_cli
            )

            # 初始化Redis连接
            redis_client = await self.persistor._get_redis_client()
            if not redis_client:
                logger.error("Orchestrator: 无法获取Redis客户端")
                return False
            await redis_client.ping()

            # 获取目标交易对
            target_pairs_by_exchange = {}
            
            if fetch_all_available_on_exchange:
                # 获取所有可用交易对模式
                effective_slugs = self.market_provider._get_effective_exchange_slugs()
                temp_adapters = {}
                
                for ex_id in effective_slugs:
                    try:
                        if ex_id not in self.adapters:
                            temp_adapters[ex_id] = get_exchange_adapter(ex_id)
                    except Exception as e:
                        logger.error(f"Orchestrator: 创建{ex_id}的适配器失败: {e}")
                
                target_pairs_by_exchange = await self.market_provider.get_all_available_stablecoin_pairs(
                    exchange_adapters=temp_adapters
                )
            else:
                # 基于数据库的目标交易对模式
                target_pairs_by_exchange = await self.market_provider.get_target_exchange_pairs()

            # 创建TickerTask
            for exchange_id, pairs_for_exchange in target_pairs_by_exchange.items():
                if not pairs_for_exchange:
                    continue

                try:
                    # 获取或创建适配器
                    adapter = self.adapters.get(exchange_id)
                    if not adapter:
                        adapter = get_exchange_adapter(exchange_id)
                        self.adapters[exchange_id] = adapter
                    
                    # 获取该交易所的监控间隔
                    exchange_interval = self._get_interval_for_exchange(exchange_id)
                    
                    # 创建任务
                    task = TickerTask(
                        exchange_id=exchange_id,
                        exchange_adapter=adapter,
                        price_fetcher=self.price_fetcher,
                        data_persistor=self.persistor,
                        pairs_to_monitor=pairs_for_exchange,
                        monitor_interval=exchange_interval,  # 使用交易所特定的间隔
                        task_id=f"{exchange_id}-task"
                    )
                    self.ticker_tasks.append(task)
                    logger.info(f"Orchestrator: 为{exchange_id}创建了任务，监控{len(pairs_for_exchange)}个交易对，间隔{exchange_interval}秒")
                except Exception as e:
                    logger.error(f"Orchestrator: 为{exchange_id}创建任务失败: {e}")

            self._initialized = True
            logger.info(f"Orchestrator: 服务初始化完成，创建了{len(self.ticker_tasks)}个任务")
            return True

        except Exception as e:
            logger.error(f"Orchestrator: 服务初始化过程中发生错误: {e}", exc_info=True)
            await self._cleanup()
            return False

    async def start_monitoring(self):
        """启动价格监控"""
        if self._is_running:
            logger.warning("Orchestrator: 监控已在运行中")
            return

        # 如果未初始化，先进行初始化
        if not self._initialized and not await self.initialize_service(fetch_all_available_on_exchange=False):
            logger.error("Orchestrator: 初始化失败，无法启动监控")
            return

        if not self.ticker_tasks:
            logger.warning("Orchestrator: 没有任务可启动")
            return

        logger.info(f"Orchestrator: 开始监控{len(self.ticker_tasks)}个任务")
        self._is_running = True

        # 创建并启动所有监控任务
        monitoring_futures = [asyncio.create_task(task.start_monitoring()) for task in self.ticker_tasks]

        try:
            # 等待所有任务完成
            await asyncio.gather(*monitoring_futures)
        except asyncio.CancelledError:
            logger.info("Orchestrator: 主监控循环被取消")
        except Exception as e:
            logger.error(f"Orchestrator: 监控过程中发生错误: {e}", exc_info=True)
        finally:
            if self._is_running:
                await self.stop()
            self._is_running = False

    async def _cleanup(self):
        """清理资源"""
        logger.info("Orchestrator: 开始清理资源...")

        # 关闭交易所适配器
        for ex_id, adapter in list(self.adapters.items()): 
            try:
                await adapter.close()
            except Exception as e:
                logger.error(f"Orchestrator: 关闭{ex_id}适配器失败: {e}")
        self.adapters.clear()

        # 关闭Redis客户端
        try:
            await self.persistor.close_redis_client()
        except Exception as e:
            logger.error(f"Orchestrator: 关闭Redis客户端失败: {e}")

        self.ticker_tasks.clear()
        self._initialized = False
        logger.info("Orchestrator: 资源清理完成")

    async def stop(self):
        """停止所有监控并清理资源"""
        if not self._is_running and not self._initialized:
            return

        # 使用锁避免重复停止
        if not hasattr(self, '_stopping'):
            self._stopping = True
        else:
            logger.debug("Orchestrator: 停止过程已在进行中，跳过重复调用")
            return

        logger.info("Orchestrator: 接收到停止信号，开始优雅关闭...")
        self._is_running = False

        # 停止所有TickerTask
        for task in self.ticker_tasks:
            task.stop()

        # 取消主循环任务
        if self._main_loop_task and not self._main_loop_task.done():
            self._main_loop_task.cancel()
            try:
                await self._main_loop_task
            except asyncio.CancelledError:
                pass

        # 清理资源
        await self._cleanup()
        logger.info("Orchestrator: 关闭完成")

    @property
    def is_running(self) -> bool:
        return self._is_running
