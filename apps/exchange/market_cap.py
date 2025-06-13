#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import time
import asyncio
import aiohttp
from typing import Dict, Optional
from decimal import Decimal

from django.conf import settings

from common.helpers import getLogger
from common.decorators import retry_on
from apps.exchange.cache_ops import set_market_data, get_market_data, get_24ticker
from apps.exchange.models import Asset, TradingPair, Market, MarketStatusChoices, AssetStatusChoices
from services.savourrpc import market_pb2_grpc

logger = getLogger(__name__)

# CoinGecko API配置
COINGECKO_API_BASE = "https://api.coingecko.com/api/v3"
COINGECKO_PRO_API_BASE = "https://pro-api.coingecko.com/api/v3"
COINGECKO_API_KEY = getattr(settings, "COINGECKO_API_KEY", None)

# 代币ID映射表 - 将交易对映射到CoinGecko代币ID
# 实际使用时应该从数据库或配置加载
TOKEN_ID_MAPPING = {
    "BTC/USDT": "bitcoin",
    "ETH/USDT": "ethereum",
    "SOL/USDT": "solana",
    # ... 其他代币映射
}


class MarketCapCalculator:
    """市值计算器，负责获取代币流通量和计算市值"""
    
    def __init__(self):
        self.session = None
        self.logger = getLogger('market_cap_calculator')
        self.cache = {}  # 简单的内存缓存
        self.cache_expiry = {}  # 缓存过期时间
    
    async def initialize(self):
        """初始化HTTP会话"""
        if self.session is None:
            self.session = aiohttp.ClientSession()
    
    async def close(self):
        """关闭HTTP会话"""
        if self.session:
            await self.session.close()
            self.session = None
    
    def _get_api_url(self):
        """根据是否有API密钥，返回适当的API基础URL"""
        if COINGECKO_API_KEY:
            return COINGECKO_PRO_API_BASE
        return COINGECKO_API_BASE
    
    def _get_headers(self):
        """获取API请求头"""
        headers = {
            'Accept': 'application/json',
            'User-Agent': 'SkyEye Market Data Service'
        }
        if COINGECKO_API_KEY:
            headers['x-cg-pro-api-key'] = COINGECKO_API_KEY
        return headers
    
    def _get_coin_id(self, symbol_name: str) -> Optional[str]:
        """获取代币的CoinGecko ID
        
        Args:
            symbol_name: 交易对名称 (如 BTC/USDT)
            
        Returns:
            代币ID或None
        """
        return TOKEN_ID_MAPPING.get(symbol_name)
    
    @retry_on()
    async def fetch_token_supply_data(self, coin_id: str) -> Dict:
        """从CoinGecko获取代币供应量数据
        
        Args:
            coin_id: CoinGecko代币ID
            
        Returns:
            包含流通量和总供应量的字典
        """
        await self.initialize()
        
        # 检查缓存
        cache_key = f"supply_{coin_id}"
        if cache_key in self.cache and self.cache_expiry.get(cache_key, 0) > time.time():
            return self.cache[cache_key]
        
        url = f"{self._get_api_url()}/coins/{coin_id}"
        params = {
            'localization': 'false',
            'tickers': 'false',
            'market_data': 'true',
            'community_data': 'false',
            'developer_data': 'false'
        }
        
        try:
            async with self.session.get(url, params=params, headers=self._get_headers()) as response:
                if response.status != 200:
                    error_text = await response.text()
                    self.logger.error(f"CoinGecko API error: {response.status} - {error_text}")
                    raise Exception(f"API request failed with status {response.status}")
                
                data = await response.json()
                
                result = {
                    'circulating_supply': data['market_data']['circulating_supply'],
                    'total_supply': data['market_data']['total_supply'],
                    'max_supply': data['market_data']['max_supply'],
                    'last_updated': int(time.time())
                }
                
                # 缓存结果，有效期1小时
                self.cache[cache_key] = result
                self.cache_expiry[cache_key] = time.time() + 3600
                
                return result
        except Exception as e:
            self.logger.error(f"Error fetching supply data for {coin_id}", exc_info=True)
            raise
    
    async def calculate_market_cap(self, symbol_name: str, price: float) -> Dict:
        """计算代币的市值
        
        Args:
            symbol_name: 交易对名称
            price: 当前价格
            
        Returns:
            包含流通市值和全稀释市值的字典
        """
        coin_id = self._get_coin_id(symbol_name)
        if not coin_id:
            self.logger.warning(f"No coin ID mapping found for {symbol_name}")
            return {
                'circulating_market_cap': None,
                'fully_diluted_market_cap': None
            }
        
        try:
            supply_data = await self.fetch_token_supply_data(coin_id)
            
            circulating_supply = supply_data.get('circulating_supply')
            total_supply = supply_data.get('total_supply')
            max_supply = supply_data.get('max_supply')
            
            # 计算流通市值
            circulating_market_cap = None
            if circulating_supply:
                circulating_market_cap = price * circulating_supply
            
            # 计算全稀释市值
            fully_diluted_market_cap = None
            if max_supply:
                fully_diluted_market_cap = price * max_supply
            elif total_supply:
                fully_diluted_market_cap = price * total_supply
            
            return {
                'circulating_market_cap': circulating_market_cap,
                'fully_diluted_market_cap': fully_diluted_market_cap,
                'circulating_supply': circulating_supply,
                'max_supply': max_supply
            }
        except Exception as e:
            self.logger.error(f"Error calculating market cap for {symbol_name}", exc_info=True)
            return {
                'circulating_market_cap': None,
                'fully_diluted_market_cap': None
            }
    
    async def update_market_cap_data(self, exchange_name: str, symbol_name: str) -> bool:
        """更新某个交易对的市值数据
        
        Args:
            exchange_name: 交易所名称
            symbol_name: 交易对名称
            
        Returns:
            是否成功更新
        """
        # 获取当前市场数据
        market_data = get_market_data(exchange_name, symbol_name)
        if not market_data or 'price' not in market_data:
            self.logger.warning(f"No price data available for {exchange_name}:{symbol_name}")
            return False
        
        # 计算市值
        price = market_data['price']
        market_cap_data = await self.calculate_market_cap(symbol_name, price)
        
        # 更新市场数据
        market_data.update(market_cap_data)
        set_market_data(exchange_name, symbol_name, market_data)
        
        self.logger.debug(f"Updated market cap for {exchange_name}:{symbol_name}")
        return True


async def periodic_market_cap_update(symbols, interval=3600):
    """定期更新市值数据
    
    Args:
        symbols: 要更新的交易对列表
        interval: 更新间隔(秒)，默认1小时
    """
    calculator = MarketCapCalculator()
    
    try:
        await calculator.initialize()
        
        while True:
            for symbol in symbols:
                for exchange in symbol.exchanges.filter(status='Active'):
                    try:
                        await calculator.update_market_cap_data(exchange.name, symbol.name)
                    except Exception as e:
                        logger.error(f"Failed to update market cap for {exchange.name}:{symbol.name}", exc_info=True)
            
            # 等待下一次更新周期
            await asyncio.sleep(interval)
    finally:
        await calculator.close()


def get_asset_market_cap(asset_symbol: str):
    try:
        asset = Asset.objects.get(symbol=asset_symbol)
        # Sum market caps from all active markets for this asset's trading pairs
        # This is a simplified approach. Real market cap might need more complex aggregation
        # based on which pairs are considered primary for market cap calculation.
        total_cap = Decimal('0.0')

        # Find all trading pairs where this asset is the base asset
        trading_pairs = TradingPair.objects.filter(base_asset=asset, status=AssetStatusChoices.ACTIVE)
        
        for tp in trading_pairs:
            # Find active markets for this trading pair
            active_markets = Market.objects.filter(
                trading_pair=tp,
                status=MarketStatusChoices.TRADING,
                exchange__status='Active'
            ).select_related('exchange', 'trading_pair__quote_asset')

            for market in active_markets:
                # This is highly dependent on how ticker data is stored and accessed.
                # Assuming get_24ticker returns data that includes volume and last_price for market.market_symbol
                ticker_data = get_24ticker(market.exchange.name, market.market_symbol) 
                if ticker_data and ticker_data.get('last') and ticker_data.get('quoteVolume'):
                    # If quote asset is USD or a stablecoin pegged to USD, volume can be used.
                    # This logic needs to be very robust depending on the quote currency.
                    if market.trading_pair.quote_asset.symbol in ['USDT', 'USDC', 'USD', 'BUSD'] or market.trading_pair.quote_asset.is_stablecoin:
                        total_cap += Decimal(str(ticker_data['quoteVolume'])) # Assuming quoteVolume is total value in quote currency
        
        return total_cap if total_cap > 0 else None

    except Asset.DoesNotExist:
        logger.warning(f"Asset {asset_symbol} not found for market cap calculation.")
        return None
    except Exception as e:
        logger.error(f"Error calculating market cap for {asset_symbol}: {e}", exc_info=True)
        return None


class MarketCapServicer(market_pb2_grpc.MarketCapServicer):
    pass 