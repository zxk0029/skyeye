#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import time
from typing import Dict, List, Optional

from common.redis_client import local_redis
from common.helpers import getLogger
from apps.price_oracle.constants import EXCHANGE_PRIORITY, STABLECOIN_SYMBOLS

logger = getLogger(__name__)


class PriceRedisService:
    """Redis价格服务 - 处理价格数据的缓存和队列，支持优先级选择"""
    
    def __init__(self):
        self.redis = local_redis()
        self.raw_price_prefix = "price_oracle:raw_price:"  # 用于存储原始价格
        self.queue_key = "price_oracle:price_queue"
        self.best_price_prefix = "price_oracle:best_price:"  # 存储每个资产的最优价格
    
    def save_prices_to_redis(self, exchange: str, prices: List[Dict]) -> int:
        """将价格数据保存到Redis，同时计算最优价格"""
        try:
            saved_count = 0
            current_time = time.time()
            
            # 获取交易所优先级
            exchange_priority = self._get_exchange_priority(exchange)
            
            pipe = self.redis.pipeline()
            
            # 按基础资产分组处理价格
            asset_prices = {}
            for price_data in prices:
                base_asset = price_data.get('base_asset', '').upper()
                if not base_asset:
                    continue
                
                if base_asset not in asset_prices:
                    asset_prices[base_asset] = []
                
                # 添加优先级信息
                price_data['exchange_priority'] = exchange_priority
                price_data['quote_priority'] = self._get_quote_priority(price_data.get('quote_asset', ''))
                asset_prices[base_asset].append(price_data)
            
            # 为每个资产选择最优价格
            for base_asset, price_list in asset_prices.items():
                best_price = self._select_best_price(base_asset, price_list)
                if best_price:
                    # 保存到队列等待持久化
                    pipe.lpush(self.queue_key, json.dumps(best_price))
                    
                    # 更新最优价格缓存
                    best_key = f"{self.best_price_prefix}{base_asset}"
                    pipe.setex(best_key, 3600, json.dumps(best_price))
                    
                    saved_count += 1
            
            pipe.execute()
            logger.info(f"保存 {saved_count} 个最优价格到Redis")
            return saved_count
            
        except Exception as e:
            logger.error(f"保存价格到Redis失败: {e}")
            return 0
    
    def _get_exchange_priority(self, exchange: str) -> int:
        """获取交易所优先级（数字越小优先级越高）"""
        try:
            return EXCHANGE_PRIORITY.index(exchange.lower())
        except ValueError:
            return 999  # 不在列表中的交易所给最低优先级
    
    def _get_quote_priority(self, quote_asset: str) -> int:
        """获取稳定币优先级（数字越小优先级越高）"""
        try:
            return STABLECOIN_SYMBOLS.index(quote_asset.upper())
        except ValueError:
            return 999  # 不在列表中的稳定币给最低优先级
    
    def _select_best_price(self, base_asset: str, price_list: List[Dict]) -> Optional[Dict]:
        """为资产选择最优价格"""
        if not price_list:
            return None
        
        # 检查Redis中是否已有该资产的价格
        current_best = self._get_current_best_price(base_asset)
        
        # 将新价格加入候选列表
        candidates = price_list.copy()
        if current_best:
            candidates.append(current_best)
        
        # 按优先级排序：先按交易所优先级，再按稳定币优先级
        candidates.sort(key=lambda x: (x.get('exchange_priority', 999), x.get('quote_priority', 999)))
        
        best_candidate = candidates[0]
        
        # 准备最优价格数据
        current_time = time.time()
        return {
            'base_asset': base_asset,
            'symbol': best_candidate.get('symbol', ''),
            'quote_asset': best_candidate.get('quote_asset', ''),
            'exchange': best_candidate.get('exchange', ''),
            'price': str(best_candidate.get('price', '0')),
            'volume_24h': str(best_candidate.get('volume_24h', '0')),
            'price_change_24h': str(best_candidate.get('price_change_24h', '0')),
            'exchange_priority': best_candidate.get('exchange_priority', 999),
            'quote_priority': best_candidate.get('quote_priority', 999),
            'timestamp': current_time
        }
    
    def _get_current_best_price(self, base_asset: str) -> Optional[Dict]:
        """获取当前最优价格"""
        try:
            key = f"{self.best_price_prefix}{base_asset}"
            data = self.redis.get(key)
            if data:
                return json.loads(data)
        except Exception:
            pass
        return None
    
    def get_prices_from_queue(self, batch_size: int = 100) -> List[Dict]:
        """从队列中批量获取价格数据"""
        try:
            prices = []
            
            for _ in range(batch_size):
                data = self.redis.rpop(self.queue_key)
                if not data:
                    break
                
                try:
                    price_data = json.loads(data)
                    prices.append(price_data)
                except json.JSONDecodeError:
                    continue
            
            if prices:
                logger.debug(f"从队列获取 {len(prices)} 个价格数据")
            
            return prices
            
        except Exception as e:
            logger.error(f"从队列获取价格失败: {e}")
            return []
    
    def get_best_price(self, base_asset: str) -> Optional[Dict]:
        """获取资产的最优价格"""
        try:
            key = f"{self.best_price_prefix}{base_asset.upper()}"
            data = self.redis.get(key)
            
            if data:
                return json.loads(data)
            return None
            
        except Exception as e:
            logger.error(f"获取最优价格失败 {base_asset}: {e}")
            return None
    
    def get_queue_size(self) -> int:
        """获取队列大小"""
        try:
            return self.redis.llen(self.queue_key)
        except Exception as e:
            logger.error(f"获取队列大小失败: {e}")
            return 0
    
    def clear_old_prices(self, hours: int = 2):
        """清理过期的价格数据"""
        try:
            current_time = time.time()
            cutoff_time = current_time - (hours * 3600)
            
            # 获取所有价格keys
            pattern = f"{self.raw_price_prefix}*"
            keys = self.redis.keys(pattern)
            
            deleted_count = 0
            
            for key in keys:
                try:
                    data = self.redis.get(key)
                    if data:
                        price_data = json.loads(data)
                        timestamp = price_data.get('timestamp', 0)
                        
                        if timestamp < cutoff_time:
                            self.redis.delete(key)
                            deleted_count += 1
                except (json.JSONDecodeError, KeyError):
                    # 删除无效数据
                    self.redis.delete(key)
                    deleted_count += 1
            
            if deleted_count > 0:
                logger.info(f"清理了 {deleted_count} 个过期价格数据")
            
            return deleted_count
            
        except Exception as e:
            logger.error(f"清理过期价格失败: {e}")
            return 0
    
    def get_stats(self) -> Dict:
        """获取Redis统计信息"""
        try:
            return {
                'queue_size': self.get_queue_size(),
                'best_price_cache_keys': len(self.redis.keys(f"{self.best_price_prefix}*")),
                'redis_memory_usage': self.redis.info().get('used_memory_human', 'unknown')
            }
        except Exception as e:
            logger.error(f"获取Redis统计失败: {e}")
            return {}


# 全局实例
redis_service = PriceRedisService()