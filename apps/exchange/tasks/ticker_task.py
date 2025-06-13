import asyncio
import time
from datetime import datetime, timezone
from typing import List, Optional

from common.helpers import getLogger
from apps.exchange.consts import (
    STABLECOIN_MAX_RETRIES,
    STABLECOIN_RETRY_DELAY,
    STABLECOIN_PRICE_MONITOR_INTERVAL
)
from apps.exchange.data_persistor import DataPersistor
from apps.exchange.data_structures import PairDefinition, PriceUpdateInfo
from apps.exchange.interfaces import ExchangeInterface
from apps.exchange.price_fetcher import PriceFetcher

logger = getLogger(__name__)


class TickerTask:
    def __init__(
            self,
            exchange_id: str,
            exchange_adapter: ExchangeInterface,
            price_fetcher: PriceFetcher,
            data_persistor: DataPersistor,
            pairs_to_monitor: List[PairDefinition],
            monitor_interval: int = STABLECOIN_PRICE_MONITOR_INTERVAL,
            task_id: Optional[str] = None
    ):
        self.exchange_id = exchange_id
        self.adapter = exchange_adapter
        self.fetcher = price_fetcher
        self.persistor = data_persistor
        self.pairs_to_monitor = pairs_to_monitor
        self.monitor_interval = monitor_interval
        self.task_id = task_id or exchange_id

        self._is_running = False
        self._stop_event = asyncio.Event()
        self._current_retry_count = 0
        self._running_lock = asyncio.Lock()  # 添加互斥锁
        self._last_execution_time = 0  # 上次执行的时间戳
        self._last_execution_duration = 0  # 上次执行的持续时间

    async def run_once(self) -> bool:
        """执行单次价格获取和持久化操作"""
        log_prefix = f"[{self.task_id}]"
        
        if not self.pairs_to_monitor:
            return True

        try:
            # 1. 获取价格
            fetched_prices = await self.fetcher.fetch_prices(
                self.adapter,
                self.pairs_to_monitor
            )

            if not fetched_prices:
                logger.warning(f"{log_prefix}: 从{self.exchange_id}未获取到价格")
                return False

            # 2. 转换为PriceUpdateInfo对象
            price_update_infos = []
            current_time = datetime.now(timezone.utc)
            pair_def_map = {pd.raw_pair_string: pd for pd in self.pairs_to_monitor}

            for raw_pair_string, price in fetched_prices.items():
                pair_def = pair_def_map.get(raw_pair_string)
                if pair_def:
                    price_update_infos.append(
                        PriceUpdateInfo(
                            pair_def=pair_def,
                            price=price,
                            source_exchange_id=self.exchange_id,
                            timestamp=current_time
                        )
                    )

            if not price_update_infos:
                logger.warning(f"{log_prefix}: 获取到价格但无法创建更新对象")
                return False

            # 3. 只更新Redis，不再更新数据库
            # 数据库更新将由专门的命令处理
            await self.persistor.update_redis_prices(price_update_infos)
            
            logger.info(f"{log_prefix}: 已将{len(price_update_infos)}个价格更新到Redis")
            return True

        except Exception as e:
            logger.error(f"{log_prefix}: 运行出错: {e}", exc_info=True)
            return False

    async def start_monitoring(self):
        """启动持续监控循环"""
        log_prefix = f"[{self.task_id}]"
        logger.info(f"{log_prefix}: 开始监控{self.exchange_id}，间隔{self.monitor_interval}秒")
        
        self._is_running = True
        self._stop_event.clear()
        self._current_retry_count = 0

        while not self._stop_event.is_set():
            # 如果已经有任务在执行，则跳过本次执行
            if self._running_lock.locked():
                logger.info(f"{log_prefix}: 上一个任务仍在执行中，跳过本次执行")
                # 等待一段时间后再次检查
                try:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=5)
                    if self._stop_event.is_set():
                        break
                except asyncio.TimeoutError:
                    # 忽略超时异常，这是正常的
                    pass
                continue
                
            # 计算自适应间隔
            current_time = time.time()
            time_since_last_run = current_time - self._last_execution_time
            
            # 如果距离上次执行时间不足执行时长的1.5倍，等待一段时间
            if self._last_execution_time > 0 and self._last_execution_duration > 0:
                min_interval = max(self._last_execution_duration * 1.5, 5)  # 至少5秒
                
                if time_since_last_run < min_interval:
                    wait_time = min_interval - time_since_last_run
                    logger.info(f"{log_prefix}: 上次执行耗时{self._last_execution_duration:.2f}秒，"
                               f"等待{wait_time:.2f}秒后再次执行")
                    try:
                        await asyncio.wait_for(self._stop_event.wait(), timeout=wait_time)
                        if self._stop_event.is_set():
                            break
                    except asyncio.TimeoutError:
                        # 忽略超时异常，这是正常的
                        pass
                    continue
            
            # 获取锁并执行任务
            async with self._running_lock:
                execution_start = time.time()
                self._last_execution_time = execution_start
                
                try:
                    # 执行一次价格获取和持久化
                    success = await self.run_once()

                    # 记录执行时长
                    self._last_execution_duration = time.time() - execution_start
                    logger.info(f"{log_prefix}: 本次执行耗时{self._last_execution_duration:.2f}秒")

                    if success:
                        # 成功执行，重置重试计数
                        self._current_retry_count = 0
                        
                        # 计算下次执行前等待时间 (考虑执行时长)
                        effective_interval = max(0.1, self.monitor_interval - self._last_execution_duration)
                        
                        # 等待直到下次执行或收到停止信号
                        if effective_interval > 0:
                            logger.info(f"{log_prefix}: 将在{effective_interval:.2f}秒后执行下一次任务")
                            try:
                                await asyncio.wait_for(self._stop_event.wait(), timeout=effective_interval)
                                if self._stop_event.is_set():
                                    break
                            except asyncio.TimeoutError:
                                # 忽略超时异常，这是正常的
                                pass
                    else:
                        # 执行失败，进行重试
                        self._current_retry_count += 1
                        
                        # 判断是否超过最大重试次数
                        if self._current_retry_count > STABLECOIN_MAX_RETRIES:
                            # 超过最大重试次数，休眠较长时间后重置
                            logger.error(f"{log_prefix}: 达到最大重试次数，休眠{self.monitor_interval * 2}秒后重置")
                            try:
                                await asyncio.wait_for(self._stop_event.wait(), timeout=self.monitor_interval * 2)
                                if self._stop_event.is_set():
                                    break
                            except asyncio.TimeoutError:
                                pass
                            self._current_retry_count = 0
                        else:
                            # 使用指数退避策略计算重试延迟
                            delay = STABLECOIN_RETRY_DELAY * (2 ** (self._current_retry_count - 1))
                            logger.info(f"{log_prefix}: {self._current_retry_count}/{STABLECOIN_MAX_RETRIES}次重试，{delay}秒后重试")
                            try:
                                await asyncio.wait_for(self._stop_event.wait(), timeout=delay)
                                if self._stop_event.is_set():
                                    break
                            except asyncio.TimeoutError:
                                pass

                except asyncio.TimeoutError:
                    # 等待超时，继续下一轮
                    pass
                except asyncio.CancelledError:
                    # 任务被取消，退出循环
                    logger.info(f"{log_prefix}: 监控任务被取消")
                    break
                except Exception as e:
                    # 处理未预期的错误
                    logger.error(f"{log_prefix}: 监控循环出现意外错误: {e}", exc_info=True)
                    self._current_retry_count += 1
                    self._last_execution_duration = time.time() - execution_start
                    await asyncio.sleep(STABLECOIN_RETRY_DELAY)

        self._is_running = False
        logger.info(f"{log_prefix}: 监控循环已停止")

    def stop(self):
        """停止监控任务"""
        logger.info(f"[{self.task_id}]: 收到停止信号")
        self._stop_event.set()

    @property
    def is_running(self) -> bool:
        return self._is_running
