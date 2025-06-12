#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import time
import asyncio
from typing import Dict, List, Optional, Any, Tuple

import ccxt.async_support as async_ccxt
from ccxt.async_support.base.exchange import Exchange as ASYNCCCXTExchange
from django.conf import settings

from common.helpers import getLogger
from common.decorators import retry_on
from apps.exchange import ccxt_client
from apps.exchange.models import TradingPair
from apps.exchange.cache_ops import set_ohlcv, set_market_data

logger = getLogger(__name__)

# 支持的K线时间周期
TIMEFRAMES = {
    '1m': '1min',
    '30m': '30m',
    '1h': '1h',
    '1d': '1d',
    '1w': '1w',
    '1M': '1month',
    '3M': '3months',
    '1y': '12months'
}

class CCXTExtendedClient:
    """扩展CCXT客户端，提供更多市场数据获取功能"""
    
    def __init__(self, exchange_name: str):
        self.exchange_name = exchange_name
        self.client = ccxt_client.get_async_client(exchange_name)
        self.logger = getLogger(f'ccxt_extended.{exchange_name}')
    
    async def close(self):
        """关闭CCXT客户端连接"""
        if self.client:
            await self.client.close()
    
    @retry_on()
    async def fetch_ohlcv(self, symbol_name: str, timeframe: str) -> List[List]:
        """获取特定时间周期的K线数据
        
        Args:
            symbol_name: 交易对名称
            timeframe: K线周期 (1m, 30m, 1h, 1d, 1w, 1M, 3M, 1y)
            
        Returns:
            K线数据列表 [timestamp, open, high, low, close, volume]
        """
        ccxt_client.select_proxy(self.client)
        
        # 确保时间周期有效
        if timeframe not in self.client.timeframes:
            self.logger.warning(f"Timeframe {timeframe} not supported by {self.exchange_name}, using 1d instead")
            timeframe = '1d'
            
        # 获取K线数据
        try:
            ohlcv = await self.client.fetch_ohlcv(symbol_name, timeframe)
            normalized_timeframe = TIMEFRAMES.get(timeframe, timeframe)
            set_ohlcv(self.exchange_name, symbol_name, normalized_timeframe, ohlcv)
            return ohlcv
        except Exception as e:
            self.logger.error(f"Error fetching OHLCV for {symbol_name} with timeframe {timeframe}", exc_info=True)
            raise
    
    @retry_on()
    async def fetch_market_data(self, symbol_name: str) -> Dict:
        """获取综合市场数据，包括价格、涨幅、交易量、市值等
        
        Args:
            symbol_name: 交易对名称
            
        Returns:
            市场数据字典
        """
        ccxt_client.select_proxy(self.client)
        
        try:
            # 获取基础市场数据
            ticker = await self.client.fetch_ticker(symbol_name)
            
            # 构建标准化的市场数据结构
            market_data = {
                'price': ticker['last'],
                'change_24h': ticker['percentage'],
                'volume_24h': ticker['quoteVolume'],
                'timestamp': int(time.time() * 1000),
                'source': f"{self.exchange_name}@ccxt"
            }
            
            # 存储市场数据
            set_market_data(self.exchange_name, symbol_name, market_data)
            return market_data
        except Exception as e:
            self.logger.error(f"Error fetching market data for {symbol_name}", exc_info=True)
            raise

class MarketDataCrawler:
    """市场数据抓取器，负责定期从多个数据源获取市场数据"""
    
    def __init__(self, exchange_names: List[str]):
        self.exchange_names = exchange_names
        self.clients = {}
        self.logger = getLogger('market_data_crawler')
        
    async def init_clients(self):
        """初始化所有交易所客户端"""
        for exchange_name in self.exchange_names:
            self.clients[exchange_name] = CCXTExtendedClient(exchange_name)
    
    async def close_clients(self):
        """关闭所有客户端连接"""
        for client in self.clients.values():
            await client.close()
    
    async def crawl_ohlcv_all_timeframes(self, symbol: TradingPair):
        """抓取指定交易对的所有时间周期K线数据"""
        client = self.clients.get(symbol.exchange.name)
        if not client:
            self.logger.warning(f"No client initialized for {symbol.exchange.name}")
            return
            
        for timeframe in TIMEFRAMES.keys():
            try:
                await client.fetch_ohlcv(symbol.symbol_display, timeframe)
                self.logger.debug(f"Successfully fetched {timeframe} OHLCV for {symbol.symbol_display} from {symbol.exchange.name}")
            except Exception as e:
                self.logger.error(f"Failed to fetch {timeframe} OHLCV", exc_info=True)
                
    async def crawl_all_market_data(self, symbol: TradingPair):
        """抓取指定交易对的综合市场数据"""
        client = self.clients.get(symbol.exchange.name)
        if not client:
            self.logger.warning(f"No client initialized for {symbol.exchange.name}")
            return
            
        try:
            await client.fetch_market_data(symbol.symbol_display)
            self.logger.debug(f"Successfully fetched market data for {symbol.symbol_display} from {symbol.exchange.name}")
        except Exception as e:
            self.logger.error(f"Failed to fetch market data", exc_info=True)
    
    async def start_periodic_crawl(self, symbols: List[TradingPair], interval: int = 60):
        """启动定期数据抓取
        
        Args:
            symbols: 要抓取的交易对列表
            interval: 抓取间隔(秒)
        """
        await self.init_clients()
        
        try:
            while True:
                for symbol in symbols:
                    if symbol.exchange.name in self.clients:
                        await self.crawl_all_market_data(symbol)
                        # K线数据抓取频率可以降低，这里示例每4个循环抓取一次
                        if int(time.time()) % (interval * 4) < interval:
                            await self.crawl_ohlcv_all_timeframes(symbol)
                
                await asyncio.sleep(interval)
        finally:
            await self.close_clients() 