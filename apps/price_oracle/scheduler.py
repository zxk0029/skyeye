#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import time
from typing import Dict, Set, Callable
from dataclasses import dataclass, field
from collections import deque
from common.helpers import getLogger

logger = getLogger(__name__)


@dataclass
class ExchangeTask:
    """单个交易所的任务状态"""
    name: str
    
    # 响应时间统计
    response_times: deque = field(default_factory=lambda: deque(maxlen=5))
    avg_response_time: float = 0.0
    
    # 调度状态
    is_running: bool = False
    last_start_time: float = 0.0
    consecutive_failures: int = 0
    total_executions: int = 0
    
    # 动态间隔
    min_interval: float = 3.0
    max_interval: float = 120.0
    current_interval: float = 5.0
    
    # 任务对象
    task: asyncio.Task = None
    
    def add_response_time(self, response_time: float):
        """添加响应时间记录"""
        self.response_times.append(response_time)
        if self.response_times:
            self.avg_response_time = sum(self.response_times) / len(self.response_times)
    
    def calculate_next_interval(self) -> float:
        """动态计算下次执行间隔"""
        if not self.response_times:
            return self.current_interval
        
        # 基础间隔 = 响应时间 * 1.15 (给一些缓冲)
        base_interval = max(self.avg_response_time * 1.15, self.min_interval)
        
        # 失败惩罚
        if self.consecutive_failures > 0:
            penalty = min(self.consecutive_failures * 5, 60)
            base_interval += penalty
        
        # 限制范围
        self.current_interval = min(max(base_interval, self.min_interval), self.max_interval)
        return self.current_interval
    
    def get_next_run_time(self) -> float:
        """获取下次运行时间"""
        return self.last_start_time + self.current_interval


class IndependentScheduler:
    """每个交易所独立调度"""
    
    def __init__(self, exchanges: list, collect_func: Callable):
        self.exchanges = exchanges
        self.collect_func = collect_func
        self.tasks: Dict[str, ExchangeTask] = {}
        self.running = False
        
        # 初始化每个交易所任务
        for exchange in exchanges:
            self.tasks[exchange] = ExchangeTask(
                name=exchange,
                min_interval=self._get_min_interval(exchange),
                max_interval=self._get_max_interval(exchange),
                current_interval=self._get_initial_interval(exchange)
            )
    
    def _get_min_interval(self, exchange: str) -> float:
        """获取最小间隔"""
        tier1 = ['binance', 'okx', 'bybit', 'coinbase']
        return 3.0 if exchange in tier1 else 5.0
    
    def _get_max_interval(self, exchange: str) -> float:
        """获取最大间隔"""
        slow_exchanges = ['yobit', 'latoken', 'gate', 'mexc']
        return 120.0 if exchange in slow_exchanges else 60.0
    
    def _get_initial_interval(self, exchange: str) -> float:
        """获取初始间隔"""
        tier1 = ['binance', 'okx', 'bybit', 'coinbase']
        tier2 = ['bitget', 'kucoin', 'cryptocom', 'htx', 'kraken']
        
        if exchange in tier1:
            return 3.0
        elif exchange in tier2:
            return 5.0
        else:
            return 10.0
    
    async def _exchange_worker(self, exchange: str):
        """单个交易所的独立工作循环"""
        task = self.tasks[exchange]
        
        while self.running:
            current_time = time.time()
            next_run_time = task.get_next_run_time()
            
            # 如果还没到运行时间，等待
            if current_time < next_run_time:
                sleep_time = next_run_time - current_time
                await asyncio.sleep(min(sleep_time, 1.0))  # 最多睡1秒，保持响应性
                continue
            
            # 如果已在运行中，跳过
            if task.is_running:
                await asyncio.sleep(0.1)
                continue
            
            # 执行采集
            await self._execute_exchange(exchange)
    
    async def _execute_exchange(self, exchange: str):
        """执行单个交易所采集"""
        task = self.tasks[exchange]
        
        task.is_running = True
        task.last_start_time = time.time()
        task.total_executions += 1
        
        start_time = time.time()
        success = False
        saved_count = 0
        
        try:
            logger.debug(f"🚀 {exchange} 开始采集 (间隔: {task.current_interval:.1f}s)")
            saved_count = await self.collect_func(exchange)
            success = True
            
            response_time = time.time() - start_time
            logger.info(f"✅ {exchange}: {saved_count} 个价格 ({response_time:.1f}s)")
            
        except Exception as e:
            logger.error(f"❌ {exchange}: 采集失败 - {e}")
            
        finally:
            # 更新统计
            response_time = time.time() - start_time
            
            if success:
                task.consecutive_failures = 0
                task.add_response_time(response_time)
            else:
                task.consecutive_failures += 1
            
            # 重新计算间隔
            task.calculate_next_interval()
            task.is_running = False
            
            logger.debug(f"📊 {exchange}: 平均 {task.avg_response_time:.1f}s, 下次间隔 {task.current_interval:.1f}s")
    
    async def start(self):
        """启动调度器"""
        self.running = True
        logger.info(f"🚀 启动独立调度器，管理 {len(self.exchanges)} 个交易所")
        
        # 为每个交易所启动独立的工作协程
        workers = []
        for exchange in self.exchanges:
            worker = asyncio.create_task(self._exchange_worker(exchange))
            workers.append(worker)
            self.tasks[exchange].task = worker
        
        # 启动状态监控协程
        status_task = asyncio.create_task(self._status_monitor())
        
        try:
            # 等待所有工作协程
            await asyncio.gather(*workers, status_task)
        except asyncio.CancelledError:
            logger.info("📴 调度器收到停止信号")
        finally:
            self.running = False
            
            # 取消所有任务
            for exchange, task_info in self.tasks.items():
                if task_info.task and not task_info.task.done():
                    task_info.task.cancel()
            
            # 等待清理
            await asyncio.gather(*[t.task for t in self.tasks.values() if t.task], 
                                status_task, return_exceptions=True)
            
            logger.info("✅ 调度器已停止")
    
    async def _status_monitor(self):
        """状态监控协程"""
        while self.running:
            await asyncio.sleep(30)  # 每30秒输出一次状态
            
            if not self.running:
                break
                
            running_count = sum(1 for t in self.tasks.values() if t.is_running)
            total_executions = sum(t.total_executions for t in self.tasks.values())
            
            logger.info(f"📊 状态: {running_count}/{len(self.exchanges)} 执行中, 总执行 {total_executions} 次")
            
            # 显示快慢交易所
            fast = []
            slow = []
            
            for exchange, task in self.tasks.items():
                if task.avg_response_time > 0:
                    if task.avg_response_time < 5.0:
                        fast.append(f"{exchange}({task.avg_response_time:.1f}s)")
                    else:
                        slow.append(f"{exchange}({task.avg_response_time:.1f}s)")
            
            if fast:
                logger.info(f"⚡ 快速: {', '.join(fast[:5])}")  # 只显示前5个
            if slow:
                logger.info(f"🐌 慢速: {', '.join(slow[:5])}")   # 只显示前5个
    
    def stop(self):
        """停止调度器"""
        self.running = False