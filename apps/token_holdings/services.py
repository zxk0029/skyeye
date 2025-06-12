import asyncio
import logging
from typing import Dict, List, Optional, Tuple

import aiohttp

from apps.cmc_proxy.models import CmcAsset
from apps.token_holdings.models import TokenHolder, TokenHoldingsSummary

logger = logging.getLogger(__name__)


class TokenHoldingsService:
    """代币持仓数据服务"""

    BASE_URL = "https://api.coinmarketcap.com/dexer/v3/dexer/crypto-holder-data"

    def __init__(self):
        self.session = None

    async def __aenter__(self):
        """异步上下文管理器入口"""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        if self.session:
            await self.session.close()

    async def fetch_token_holdings(self, cmc_id: int, page: int = 1, page_size: int = 50) -> Optional[Dict]:
        if not self.session:
            raise ValueError("Service must be used within async context manager")

        params = {'cryptoId': cmc_id, 'page': page, 'pageSize': page_size}

        try:
            async with self.session.get(self.BASE_URL, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"Successfully fetched holdings data for CMC ID {cmc_id}")
                    return data
                else:
                    logger.warning(f"Failed to fetch holdings data for CMC ID {cmc_id}, status: {response.status}")
                    return None
        except Exception as e:
            logger.error(f"Error fetching holdings data for CMC ID {cmc_id}: {str(e)}")
            return None

    async def save_token_holdings(self, cmc_id: int, api_data: Dict) -> Tuple[bool, str]:
        try:
            # 获取CMC资产记录
            asset = await CmcAsset.objects.filter(cmc_id=cmc_id).afirst()
            if not asset:
                return False, f"CMC asset with ID {cmc_id} not found"

            data = api_data.get('data', {})
            holders_data = data.get('holders', [])

            if not holders_data:
                logger.info(f"No holders data found for CMC ID {cmc_id}")
                return True, "No holders data available"

            # 使用Manager保存汇总信息
            await TokenHoldingsSummary.objects.update_or_create_from_api_data(asset, api_data)

            # 使用Manager批量保存持有者数据
            saved_count = await TokenHolder.objects.batch_save_from_api_data(asset, holders_data)

            logger.info(f"Successfully saved {saved_count} holders for CMC ID {cmc_id}")
            return True, f"Saved {saved_count} holders"

        except Exception as e:
            logger.error(f"Error saving holdings data for CMC ID {cmc_id}: {str(e)}")
            return False, str(e)

    async def update_token_holdings(self, cmc_id: int) -> Tuple[bool, str]:
        api_data = await self.fetch_token_holdings(cmc_id)
        if not api_data:
            return False, f"Failed to fetch data for CMC ID {cmc_id}"

        return await self.save_token_holdings(cmc_id, api_data)

    async def batch_update_holdings(self, cmc_ids: List[int], max_concurrent: int = 10) -> Dict[int, Tuple[bool, str]]:
        semaphore = asyncio.Semaphore(max_concurrent)
        results = {}

        async def update_single(cmc_id: int):
            async with semaphore:
                try:
                    result = await self.update_token_holdings(cmc_id)
                    results[cmc_id] = result
                except Exception as e:
                    results[cmc_id] = (False, str(e))

        tasks = [update_single(cmc_id) for cmc_id in cmc_ids]
        await asyncio.gather(*tasks, return_exceptions=True)

        return results

    async def get_token_holdings_summary(self, cmc_id: int) -> Optional[Dict]:
        try:
            asset = await CmcAsset.objects.filter(cmc_id=cmc_id).afirst()
            if not asset:
                return None

            summary = await TokenHoldingsSummary.objects.filter(asset=asset).afirst()
            if not summary:
                return None

            # 获取前50名持有者
            holders = TokenHolder.objects.filter(asset=asset).order_by('order')[:50]

            holders_data = []
            async for holder in holders:
                holders_data.append({
                    'address': holder.address,
                    'balance': float(holder.balance) if holder.balance else 0,
                    'amount_usd': float(holder.total_amount) if holder.total_amount else 0,
                    'percent': holder.percent,
                    'order': holder.order,
                    'explorer_url': holder.explorer_url,
                })

            return {
                'symbol': asset.symbol,
                'cmc_id': asset.cmc_id,
                'top_holders': holders_data,
                'summary': {
                    'holder_count': summary.holder_count,
                    'last_updated': summary.last_updated.isoformat() if summary.last_updated else None
                }
            }

        except Exception as e:
            logger.error(f"Error getting holdings summary for CMC ID {cmc_id}: {str(e)}")
            return None


# 导出服务实例
token_holdings_service = TokenHoldingsService
