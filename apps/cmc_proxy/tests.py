#!/usr/bin/env python
"""
CoinMarketCap 数据服务功能测试脚本

使用方法：
    python manage.py shell < apps/cmc_proxy/tests.py

或者使用 uv:
    uv run manage.py shell < apps/cmc_proxy/tests.py
    uv run python -m apps.cmc_proxy.tests
"""

import asyncio
import os
from datetime import datetime

import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "skyeye.settings")
django.setup()
from django.conf import settings

from apps.cmc_proxy.consts import CMC_BATCH_REQUESTS_PENDING_KEY
from apps.cmc_proxy.services import CoinMarketCapClient, get_cmc_service
from apps.cmc_proxy.utils import CMCRedisClient
from common.redis_client import get_async_redis_client


class CMCServiceTester:
    """CoinMarketCap 服务测试类"""

    def __init__(self):
        self.redis_client = None
        self.cmc_service = None

    async def setup(self):
        """初始化测试环境"""
        self.redis_client = await get_async_redis_client(settings.REDIS_CMC_URL)
        self.cmc_service = await get_cmc_service()

    async def cleanup(self):
        """清理测试环境"""
        if self.redis_client:
            await self.redis_client.aclose()

    async def test_cmc_client(self):
        """测试 CoinMarketCap API 客户端"""
        print("\n===== 测试 CoinMarketCap API 客户端 =====")
        client = CoinMarketCapClient()

        print("\n1. 测试获取热门列表 (get_listings_latest)")
        try:
            response = await client.get_listings_latest()
            print(f"获取热门列表成功，返回 {len(response.get('data', []))} 条数据")
            for token in response.get('data', [])[:3]:
                print(
                    f"  - {token.get('name')} ({token.get('symbol')}): ${token.get('quote', {}).get('USD', {}).get('price', 0):.4f}")
        except Exception as e:
            print(f"获取热门列表失败: {e}")

        print("\n2. 测试获取特定代币价格 (get_quotes_latest)")
        try:
            # 获取比特币价格
            response = await client.get_quotes_latest(ids=["1"])  # 1 是比特币的 ID
            data = response.get('data', {})
            if data and "1" in data:
                bitcoin = data["1"]
                price = bitcoin.get('quote', {}).get('USD', {}).get('price', 0)
                print(f"比特币价格: ${price:.2f}")
            else:
                print("未能获取比特币数据")
        except Exception as e:
            print(f"获取比特币价格失败: {e}")

    async def test_cached_data(self):
        """测试缓存数据获取功能"""
        print("\n===== 测试缓存数据获取功能 =====")

        try:
            # 使用CMCRedisClient的工厂方法获取实例，避免初始化参数错误
            cmc_redis = await CMCRedisClient.create(settings.REDIS_CMC_URL)

            # 测试常见代币的ID直接查询
            symbol_ids = ["1", "1027", "825", "1839", "5426"]  # BTC, ETH, USDT, BNB, SOL
            for symbol_id in symbol_ids:
                cached_data = await cmc_redis.get_token_quote_data(symbol_id)
                if cached_data:
                    symbol = cached_data.get('symbol')
                    price = cached_data.get('quote', {}).get('USD', {}).get('price')
                    print(f"ID {symbol_id} ({symbol}) 缓存命中! 价格: ${price:.4f}")
                else:
                    print(f"ID {symbol_id} 缓存未命中")
        except Exception as e:
            print(f"缓存测试出错: {e}")

    async def test_service_flow(self):
        """测试完整的服务流程"""
        print("\n===== 测试完整的服务流程 =====")

        # 测试一些代币ID，包括热门和非热门的
        symbol_ids = ["1", "1027", "7278", "24478", "74"]  # BTC, ETH, AAVE, PEPE, DOGE

        for symbol_id in symbol_ids:
            print(f"\n测试代币ID: {symbol_id}")

            # 使用集成的服务函数获取数据
            print(f"调用 get_token_market_data({symbol_id})...")
            token_data = await self.cmc_service.get_token_market_data(symbol_id)

            if token_data:
                price = token_data.get('quote', {}).get('USD', {}).get('price')
                symbol = token_data.get('symbol')
                print(f"获取成功! ID: {symbol_id}, 符号: {symbol}, 价格: ${price:.4f}")
            else:
                print(f"获取失败. ID: {symbol_id}")

    async def test_redis_operations(self):
        """测试Redis操作"""
        print("\n===== 测试Redis操作 =====")

        try:
            # 检查 Redis 连接状态
            ping_result = await self.redis_client.ping()
            print(f"Redis 连接状态: {'正常' if ping_result else '异常'}")

            # 检查待处理请求队列
            pending_count = await self.redis_client.llen(CMC_BATCH_REQUESTS_PENDING_KEY)
            print(f"当前待处理请求数量: {pending_count}")
            if pending_count > 0:
                pending_items = await self.redis_client.lrange(CMC_BATCH_REQUESTS_PENDING_KEY, 0, 5)
                print(f"前5个待处理请求: {pending_items}")
        except Exception as e:
            print(f"Redis操作测试出错: {e}")

    async def run_all_tests(self):
        """运行所有测试"""
        print(f"===== CoinMarketCap 数据服务测试 =====")
        print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"API Key: {'已配置' if settings.COINMARKETCAP_API_KEY else '未配置'}")
        print(f"Redis URL: {settings.REDIS_CMC_URL}")

        await self.setup()

        try:
            await self.test_redis_operations()
            # await self.test_cmc_client()
            await self.test_cached_data()
            await self.test_service_flow()
        finally:
            await self.cleanup()


async def main():
    """主测试函数"""
    tester = CMCServiceTester()
    await tester.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())
else:
    # 在 Django shell 中执行
    print("在 Django shell 中执行测试...")
    asyncio.get_event_loop().run_until_complete(main())
