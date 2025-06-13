import time
import asyncio
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from asgiref.sync import sync_to_async

from common.helpers import getLogger
from apps.exchange.ccxt_client import get_client
from apps.klines.models import Kline, KlineProcessingLog
from apps.exchange.models import Market

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


class KlineService:
    """K线数据服务，负责获取和处理K线数据"""
    
    def __init__(self, exchange_id: str):
        self.exchange_id = exchange_id
        self.client = None
        self._initialized = False
    
    async def initialize(self):
        """初始化CCXT客户端"""
        if not self._initialized:
            self.client = get_client(self.exchange_id, sync_type="async")
            if not self.client:
                raise ValueError(f"无法初始化{self.exchange_id}的CCXT客户端")
            
            self._initialized = True
            logger.info(f"KlineService for {self.exchange_id} initialized")
    
    async def fetch_klines(self, symbol: str, timeframe: str, 
                          since: Optional[int] = None, 
                          limit: Optional[int] = None) -> List[List]:
        """
        获取K线数据
        
        Args:
            symbol: 交易对符号
            timeframe: 时间周期
            since: 起始时间戳（毫秒）
            limit: 返回的最大数据条数
            
        Returns:
            K线数据列表 [[timestamp, open, high, low, close, volume], ...]
        """
        if not self._initialized:
            await self.initialize()
            
        try:
            # 确保时间周期有效
            if timeframe not in self.client.timeframes:
                available_timeframes = list(self.client.timeframes.keys())
                logger.warning(f"Timeframe {timeframe} not supported by {self.exchange_id}, "
                             f"available timeframes: {available_timeframes}")
                if '1d' in self.client.timeframes:
                    timeframe = '1d'
                    logger.info(f"Falling back to '1d' timeframe")
                else:
                    timeframe = available_timeframes[0]
                    logger.info(f"Falling back to '{timeframe}' timeframe")
                
            # 获取K线数据
            ohlcv = await self.client.fetch_ohlcv(symbol, timeframe, since=since, limit=limit)
            logger.info(f"Fetched {len(ohlcv)} klines for {self.exchange_id} {symbol} {timeframe}")
            return ohlcv
            
        except Exception as e:
            logger.error(f"Error fetching klines for {self.exchange_id} {symbol} {timeframe}: {e}", 
                        exc_info=True)
            raise
    
    async def save_klines_to_db(self, market_identifier: str, 
                              interval: str, 
                              kline_data: List[List]) -> int:
        """
        将K线数据保存到数据库
        
        Args:
            market_identifier: 市场标识符
            interval: 时间周期
            kline_data: K线数据列表 [[timestamp, open, high, low, close, volume], ...]
            
        Returns:
            保存的记录数
        """
        if not kline_data:
            logger.warning(f"No kline data to save for {market_identifier} {interval}")
            return 0
            
        @sync_to_async
        def get_market():
            try:
                return Market.objects.get(market_identifier=market_identifier)
            except Market.DoesNotExist:
                logger.error(f"Market {market_identifier} not found")
                return None
                
        @sync_to_async
        def bulk_create_klines(klines):
            with transaction.atomic():
                created = 0
                for kline in klines:
                    # 使用获取或创建逻辑，避免重复
                    try:
                        # open_time是唯一索引的一部分，所以我们可以先检查是否存在
                        Kline.objects.get(
                            market_id=kline.market_id, 
                            interval=kline.interval, 
                            open_time=kline.open_time
                        )
                    except Kline.DoesNotExist:
                        kline.save()
                        created += 1
                return created
        
        market = await get_market()
        if not market:
            return 0
            
        klines_to_create = []
        
        for k in kline_data:
            timestamp, open_price, high, low, close, volume = k[:6]
            quote_volume = k[6] if len(k) > 6 else None
            trade_count = k[7] if len(k) > 7 else None
            
            # 转换时间戳为datetime
            open_time = datetime.fromtimestamp(timestamp / 1000)
            
            klines_to_create.append(
                Kline(
                    market=market,
                    interval=interval,
                    open_time=open_time,
                    open_price=Decimal(str(open_price)),
                    high_price=Decimal(str(high)),
                    low_price=Decimal(str(low)),
                    close_price=Decimal(str(close)),
                    volume=Decimal(str(volume)),
                    quote_volume=Decimal(str(quote_volume)) if quote_volume else None,
                    trade_count=trade_count,
                    is_final=True  # 假设所有历史数据都是最终的
                )
            )
            
        # 分批保存，避免一次性保存太多记录
        batch_size = 500
        saved_count = 0
        
        for i in range(0, len(klines_to_create), batch_size):
            batch = klines_to_create[i:i + batch_size]
            saved_count += await bulk_create_klines(batch)
            
        logger.info(f"Saved {saved_count} new klines for {market_identifier} {interval}")
        return saved_count
    
    async def update_klines(self, market_identifier: str, 
                          interval: str,
                          days_back: int = 30,
                          create_log: bool = True) -> Tuple[int, str]:
        """
        更新K线数据
        
        Args:
            market_identifier: 市场标识符
            interval: 时间周期
            days_back: 获取多少天前的数据
            create_log: 是否创建处理日志
            
        Returns:
            (保存的记录数, 状态)
        """
        @sync_to_async
        def get_market_info():
            try:
                market = Market.objects.get(market_identifier=market_identifier)
                return {
                    'market': market,
                    'exchange_id': market.exchange.slug,
                    'symbol': market.market_symbol
                }
            except Market.DoesNotExist:
                logger.error(f"Market {market_identifier} not found")
                return None
        
        @sync_to_async
        def create_processing_log(exchange, symbol, interval, status, start_time, end_time, records=0, error=None):
            if not create_log:
                return
                
            KlineProcessingLog.objects.create(
                exchange=exchange,
                symbol=symbol,
                interval=interval,
                start_time=start_time,
                end_time=end_time,
                status=status,
                records_count=records,
                error_message=error
            )
        
        market_info = await get_market_info()
        if not market_info:
            return 0, "failed"
            
        market = market_info['market']
        exchange_id = market_info['exchange_id']
        symbol = market_info['symbol']
        
        # 重新初始化服务，确保使用正确的交易所
        self.exchange_id = exchange_id
        self.client = None
        self._initialized = False
        
        try:
            await self.initialize()
            
            # 计算开始和结束时间
            end_time = datetime.now()
            start_time = end_time - timedelta(days=days_back)
            
            # 创建处理日志（状态：处理中）
            await create_processing_log(
                exchange_id, symbol, interval, 
                'processing', start_time, end_time
            )
            
            # 转换为毫秒时间戳
            since = int(start_time.timestamp() * 1000)
            
            # 获取K线数据
            kline_data = await self.fetch_klines(
                symbol, interval, since=since
            )
            
            # 保存K线数据
            records_count = await self.save_klines_to_db(
                market_identifier, interval, kline_data
            )
            
            # 更新处理日志（状态：已完成）
            await create_processing_log(
                exchange_id, symbol, interval, 
                'completed', start_time, end_time, 
                records=records_count
            )
            
            return records_count, "completed"
            
        except Exception as e:
            logger.error(f"Error updating klines: {e}", exc_info=True)
            
            # 更新处理日志（状态：失败）
            await create_processing_log(
                exchange_id, symbol, interval, 
                'failed', start_time, end_time, 
                error=str(e)
            )
            
            return 0, "failed"
            
    async def close(self):
        """关闭CCXT客户端"""
        if self.client:
            await self.client.close()
            self._initialized = False 