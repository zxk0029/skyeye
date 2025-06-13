#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import time
from typing import Dict

import aiohttp

from common.decorators import retry_on
from common.helpers import getLogger

logger = getLogger(__name__)

# DeFi Llama API端点
DEFILLAMA_API_BASE = "https://api.llama.fi"
DEFILLAMA_VOLUME_API_BASE = "https://api.llama.fi/overview/dexs"
DEFILLAMA_DEX_API_BASE = "https://api.llama.fi/protocol"


class DefiLlamaClient:
    """DeFi Llama API客户端，用于获取DEX的TVL和交易量数据"""

    def __init__(self):
        self.session = None
        self.logger = getLogger('defillama_client')
        self.cache = {}
        self.cache_expiry = {}

    async def initialize(self):
        """初始化HTTP会话"""
        if self.session is None:
            self.session = aiohttp.ClientSession()

    async def close(self):
        """关闭HTTP会话"""
        if self.session:
            await self.session.close()
            self.session = None

    @retry_on()
    async def fetch_dex_tvl(self, dex_name: str) -> Dict:
        """获取特定DEX的TVL数据
        
        Args:
            dex_name: DeFi Llama上的DEX名称 (如 uniswap, pancakeswap, sushiswap)
            
        Returns:
            TVL数据
        """
        await self.initialize()

        # 检查缓存
        cache_key = f"tvl_{dex_name}"
        if cache_key in self.cache and self.cache_expiry.get(cache_key, 0) > time.time():
            return self.cache[cache_key]

        url = f"{DEFILLAMA_DEX_API_BASE}/{dex_name}"

        try:
            async with self.session.get(url) as response:
                if response.status != 200:
                    error_text = await response.text()
                    self.logger.error(f"DeFi Llama API error: {response.status} - {error_text}")
                    raise Exception(f"API request failed with status {response.status}")

                data = await response.json()

                # 缓存结果，有效期1小时
                self.cache[cache_key] = data
                self.cache_expiry[cache_key] = time.time() + 3600

                return data
        except Exception as e:
            self.logger.error(f"Error fetching TVL data for {dex_name}", exc_info=True)
            raise

    @retry_on()
    async def fetch_dex_volumes(self) -> Dict:
        """获取所有DEX的交易量数据
        
        Returns:
            所有DEX的交易量数据
        """
        await self.initialize()

        # 检查缓存
        cache_key = "all_dex_volumes"
        if cache_key in self.cache and self.cache_expiry.get(cache_key, 0) > time.time():
            return self.cache[cache_key]

        url = DEFILLAMA_VOLUME_API_BASE

        try:
            async with self.session.get(url) as response:
                if response.status != 200:
                    error_text = await response.text()
                    self.logger.error(f"DeFi Llama Volume API error: {response.status} - {error_text}")
                    raise Exception(f"API request failed with status {response.status}")

                data = await response.json()

                # 缓存结果，有效期1小时
                self.cache[cache_key] = data
                self.cache_expiry[cache_key] = time.time() + 3600

                return data
        except Exception as e:
            self.logger.error("Error fetching DEX volumes", exc_info=True)
            raise

    async def get_dex_data(self, dex_name: str) -> Dict:
        """获取特定DEX的综合数据
        
        Args:
            dex_name: DeFi Llama上的DEX名称
            
        Returns:
            DEX的TVL和交易量数据
        """
        # 获取TVL数据
        tvl_data = await self.fetch_dex_tvl(dex_name)

        # 获取交易量数据
        all_volumes = await self.fetch_dex_volumes()

        # 查找特定DEX的交易量数据
        dex_volume_data = None
        for dex in all_volumes["protocols"]:
            if dex["name"].lower() == dex_name.lower():
                dex_volume_data = dex
                break

        # 组合数据
        result = {
            "name": dex_name,
            "tvl": tvl_data.get("tvl"),
            "tvlHistory": tvl_data.get("tvlHistory", []),
            "chainTvls": tvl_data.get("chainTvls", {}),
        }

        if dex_volume_data:
            result.update({
                "volume24h": dex_volume_data.get("total24h"),
                "volume7d": dex_volume_data.get("total7d"),
                "change_24h": dex_volume_data.get("change_1d"),
                "change_7d": dex_volume_data.get("change_7d"),
                "chains": dex_volume_data.get("chains", [])
            })

        return result


# 将DeFi Llama上的DEX名称映射到代码中使用的标识符
DEX_NAME_MAPPING = {
    "uniswap": "uniswap_v2",
    "uniswap-v3": "uniswap_v3",
    "pancakeswap": "pancakeswap_v2",
    "sushiswap": "sushiswap",
    # 添加其他DEX映射...
}


class DexAggregatorService:
    """DEX数据聚合服务，集成多个第三方数据源"""

    def __init__(self):
        self.defillama_client = DefiLlamaClient()
        self.logger = getLogger('dex_aggregator_service')

    async def initialize(self):
        """初始化所有数据源客户端"""
        await self.defillama_client.initialize()

    async def close(self):
        """关闭所有客户端连接"""
        await self.defillama_client.close()

    async def get_dex_overview(self, dex_name: str) -> Dict:
        """获取DEX概览数据
        
        Args:
            dex_name: 内部使用的DEX标识符
            
        Returns:
            DEX概览数据
        """
        # 转换为DeFi Llama使用的DEX名称
        defillama_name = None
        for llama_name, internal_name in DEX_NAME_MAPPING.items():
            if internal_name == dex_name:
                defillama_name = llama_name
                break

        if not defillama_name:
            self.logger.warning(f"No DeFi Llama mapping found for DEX: {dex_name}")
            return {}

        try:
            # 从DeFi Llama获取数据
            data = await self.defillama_client.get_dex_data(defillama_name)

            # 标准化数据格式
            result = {
                "name": dex_name,
                "display_name": data.get("name", dex_name),
                "tvl_usd": data.get("tvl"),
                "volume_24h_usd": data.get("volume24h"),
                "volume_7d_usd": data.get("volume7d"),
                "change_24h_percent": data.get("change_24h"),
                "chains": data.get("chains", []),
                "timestamp": int(time.time()),
                "source": "defillama"
            }

            return result
        except Exception as e:
            self.logger.error(f"Error getting overview for DEX: {dex_name}", exc_info=True)
            return {
                "name": dex_name,
                "error": str(e),
                "timestamp": int(time.time())
            }


async def get_all_major_dexes_data():
    """获取所有主要DEX的数据"""
    service = DexAggregatorService()

    try:
        await service.initialize()

        major_dexes = [
            "uniswap_v2", "uniswap_v3", "pancakeswap_v2",
            "sushiswap", "curve", "balancer"
        ]

        results = {}
        for dex in major_dexes:
            try:
                data = await service.get_dex_overview(dex)
                results[dex] = data
            except Exception as e:
                logger.error(f"Failed to get data for {dex}", exc_info=True)
                results[dex] = {"error": str(e)}

        return results
    finally:
        await service.close()


async def periodic_dex_overview_update(interval=3600):
    """定期更新DEX概览数据
    
    Args:
        interval: 更新间隔(秒)，默认1小时
    """
    service = DexAggregatorService()

    try:
        await service.initialize()

        while True:
            major_dexes = [
                "uniswap_v2", "uniswap_v3", "pancakeswap_v2",
                "sushiswap", "curve", "balancer"
            ]

            for dex in major_dexes:
                try:
                    data = await service.get_dex_overview(dex)
                    # 这里应实现数据存储逻辑...
                    logger.info(f"Updated overview data for {dex}")
                except Exception as e:
                    logger.error(f"Failed to update {dex} overview", exc_info=True)

            # 等待下一次更新周期
            await asyncio.sleep(interval)
    finally:
        await service.close()
