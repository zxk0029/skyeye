#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import time
import json
import asyncio
import aiohttp
from typing import Dict, List, Optional, Any

from django.conf import settings

from common.helpers import getLogger
from common.decorators import retry_on

logger = getLogger(__name__)

# The Graph API端点
GRAPH_API_BASE = "https://api.thegraph.com/subgraphs/name/"

# Subgraph ID映射
SUBGRAPHS = {
    "uniswap_v2": "uniswap/uniswap-v2",
    "uniswap_v3": "uniswap/uniswap-v3",
    "pancakeswap_v2": "pancakeswap/exchange-v2",
    "pancakeswap_v3": "pancakeswap/exchange-v3",
    "sushiswap_ethereum": "sushi-labs/sushiswap-ethereum",
}


class GraphQLClient:
    """GraphQL客户端，用于查询The Graph协议上的Subgraph"""
    
    def __init__(self):
        self.session = None
        self.logger = getLogger('graphql_client')
    
    async def initialize(self):
        """初始化HTTP会话"""
        if self.session is None:
            self.session = aiohttp.ClientSession()
    
    async def close(self):
        """关闭HTTP会话"""
        if self.session:
            await self.session.close()
            self.session = None
    
    @retry_on(max_tries=3, delay=2)
    async def query(self, subgraph_id: str, query: str, variables: Optional[Dict] = None) -> Dict:
        """执行GraphQL查询
        
        Args:
            subgraph_id: Subgraph标识符
            query: GraphQL查询字符串
            variables: 查询变量
            
        Returns:
            查询结果
        """
        await self.initialize()
        
        url = f"{GRAPH_API_BASE}{SUBGRAPHS.get(subgraph_id, subgraph_id)}"
        payload = {
            "query": query,
            "variables": variables or {}
        }
        
        try:
            async with self.session.post(url, json=payload) as response:
                if response.status != 200:
                    error_text = await response.text()
                    self.logger.error(f"GraphQL API error: {response.status} - {error_text}")
                    raise Exception(f"API request failed with status {response.status}")
                
                result = await response.json()
                
                if "errors" in result:
                    self.logger.error(f"GraphQL query errors: {result['errors']}")
                    raise Exception(f"GraphQL query returned errors: {result['errors']}")
                
                return result["data"]
        except Exception as e:
            self.logger.error(f"Error executing GraphQL query on {subgraph_id}", exc_info=True)
            raise


class DexDataFetcher:
    """DEX数据获取器，使用The Graph获取DEX数据"""
    
    def __init__(self):
        self.client = GraphQLClient()
        self.logger = getLogger('dex_data_fetcher')
    
    async def initialize(self):
        """初始化GraphQL客户端"""
        await self.client.initialize()
    
    async def close(self):
        """关闭客户端连接"""
        await self.client.close()
    
    async def fetch_uniswap_v2_pair_data(self, pair_address: str) -> Dict:
        """获取Uniswap V2交易对数据
        
        Args:
            pair_address: 交易对合约地址
            
        Returns:
            交易对数据，包括价格、交易量、流动性等
        """
        query = """
        query GetPairData($id: ID!) {
          pair(id: $id) {
            id
            token0 {
              id
              symbol
              name
              decimals
            }
            token1 {
              id
              symbol
              name
              decimals
            }
            reserve0
            reserve1
            volumeToken0
            volumeToken1
            token0Price
            token1Price
            totalSupply
            reserveUSD
            volumeUSD
            txCount
          }
        }
        """
        
        variables = {
            "id": pair_address.lower()
        }
        
        result = await self.client.query("uniswap_v2", query, variables)
        return result["pair"]
    
    async def fetch_uniswap_v3_pool_data(self, pool_address: str) -> Dict:
        """获取Uniswap V3交易池数据
        
        Args:
            pool_address: 交易池合约地址
            
        Returns:
            交易池数据，包括价格、交易量、TVL等
        """
        query = """
        query GetPoolData($id: ID!) {
          pool(id: $id) {
            id
            token0 {
              id
              symbol
              name
              decimals
            }
            token1 {
              id
              symbol
              name
              decimals
            }
            feeTier
            liquidity
            sqrtPrice
            token0Price
            token1Price
            volumeToken0
            volumeToken1
            volumeUSD
            totalValueLockedToken0
            totalValueLockedToken1
            totalValueLockedUSD
            txCount
          }
        }
        """
        
        variables = {
            "id": pool_address.lower()
        }
        
        result = await self.client.query("uniswap_v3", query, variables)
        return result["pool"]
    
    async def fetch_pancakeswap_v2_pair_data(self, pair_address: str) -> Dict:
        """获取PancakeSwap V2交易对数据
        
        Args:
            pair_address: 交易对合约地址
            
        Returns:
            交易对数据
        """
        query = """
        query GetPairData($id: ID!) {
          pair(id: $id) {
            id
            token0 {
              id
              symbol
              name
              decimals
            }
            token1 {
              id
              symbol
              name
              decimals
            }
            reserve0
            reserve1
            volumeToken0
            volumeToken1
            token0Price
            token1Price
            totalSupply
            reserveUSD
            volumeUSD
            txCount
          }
        }
        """
        
        variables = {
            "id": pair_address.lower()
        }
        
        result = await self.client.query("pancakeswap_v2", query, variables)
        return result["pair"]
    
    async def fetch_top_pairs(self, dex: str, count: int = 100) -> List[Dict]:
        """获取DEX上交易量最大的交易对
        
        Args:
            dex: DEX名称 (uniswap_v2, uniswap_v3, pancakeswap_v2, etc.)
            count: 返回的交易对数量
            
        Returns:
            交易对列表
        """
        # 不同DEX的查询结构可能不同
        if dex == "uniswap_v2":
            query = """
            query GetTopPairs($count: Int!) {
              pairs(first: $count, orderBy: volumeUSD, orderDirection: desc) {
                id
                token0 {
                  id
                  symbol
                  name
                }
                token1 {
                  id
                  symbol
                  name
                }
                reserve0
                reserve1
                volumeUSD
                token0Price
                token1Price
              }
            }
            """
        elif dex == "uniswap_v3":
            query = """
            query GetTopPools($count: Int!) {
              pools(first: $count, orderBy: volumeUSD, orderDirection: desc) {
                id
                token0 {
                  id
                  symbol
                  name
                }
                token1 {
                  id
                  symbol
                  name
                }
                volumeUSD
                token0Price
                token1Price
                totalValueLockedUSD
              }
            }
            """
            result = await self.client.query(dex, query, {"count": count})
            return result["pools"]
        elif dex == "pancakeswap_v2":
            query = """
            query GetTopPairs($count: Int!) {
              pairs(first: $count, orderBy: volumeUSD, orderDirection: desc) {
                id
                token0 {
                  id
                  symbol
                  name
                }
                token1 {
                  id
                  symbol
                  name
                }
                reserve0
                reserve1
                volumeUSD
                token0Price
                token1Price
              }
            }
            """
        else:
            raise ValueError(f"Unsupported DEX: {dex}")
        
        result = await self.client.query(dex, query, {"count": count})
        return result["pairs"]
    
    async def save_dex_data(self, dex: str, data: Dict):
        """保存DEX数据
        
        Args:
            dex: DEX标识符
            data: 要保存的数据
        """
        # 这里应该实现将数据存储到数据库或缓存的逻辑
        pass


async def periodic_dex_data_update(interval=300):
    """定期更新DEX数据
    
    Args:
        interval: 更新间隔(秒)，默认5分钟
    """
    fetcher = DexDataFetcher()
    
    try:
        await fetcher.initialize()
        
        while True:
            # 更新Uniswap V2数据
            try:
                top_pairs = await fetcher.fetch_top_pairs("uniswap_v2", 50)
                # 处理和保存数据...
                logger.info(f"Updated top 50 Uniswap V2 pairs")
            except Exception as e:
                logger.error("Failed to update Uniswap V2 data", exc_info=True)
            
            # 更新Uniswap V3数据
            try:
                top_pools = await fetcher.fetch_top_pairs("uniswap_v3", 50)
                # 处理和保存数据...
                logger.info(f"Updated top 50 Uniswap V3 pools")
            except Exception as e:
                logger.error("Failed to update Uniswap V3 data", exc_info=True)
            
            # 更新PancakeSwap V2数据
            try:
                top_pancake_pairs = await fetcher.fetch_top_pairs("pancakeswap_v2", 50)
                # 处理和保存数据...
                logger.info(f"Updated top 50 PancakeSwap V2 pairs")
            except Exception as e:
                logger.error("Failed to update PancakeSwap V2 data", exc_info=True)
            
            # 等待下一次更新周期
            await asyncio.sleep(interval)
    finally:
        await fetcher.close() 