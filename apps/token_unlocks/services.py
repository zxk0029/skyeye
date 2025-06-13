import logging
from datetime import datetime, timezone

import requests

from apps.token_unlocks.models import TokenUnlock, UnlockEvent

logger = logging.getLogger(__name__)


class CMCUnlockService:
    BASE_URL = "https://api.coinmarketcap.com/data-api/v3/token-unlock/listing"
    EVENT_URL = "https://api.coinmarketcap.com/data-api/v3/token-unlock/event"

    @classmethod
    def fetch_unlocks(cls, limit=100):
        """
        从CoinMarketCap获取代币解锁数据（支持分页，获取所有记录）
        
        Args:
            limit: 每页获取的记录数，默认100
            
        Returns:
            list: 所有代币解锁数据
        """
        params = {
            'start': '1',
            'limit': str(limit),
            'sort': 'next_unlocked_date',
            'direction': 'desc',
            'enableSmallUnlocks': 'true',
        }
        try:
            # 首次获取并读取总数
            logger.info(f"从CoinMarketCap获取解锁数据，limit={limit}")
            response = requests.get(cls.BASE_URL, params=params)
            response.raise_for_status()
            data = response.json()
            if data['status']['error_message'] != 'SUCCESS':
                logger.error(f"CMC API错误: {data['status']['error_message']}")
                raise Exception(f"CMC API错误: {data['status']['error_message']}")
            total = int(data['data'].get('totalCount', 0))
            items = data['data'].get('tokenUnlockList', [])
            logger.info(f"成功获取第1页 {len(items)} 条，共 {total} 条")
            # 分页获取剩余数据，start表示页数
            total_pages = (total + limit - 1) // limit
            for page in range(2, total_pages + 1):
                params['start'] = str(page)
                logger.info(f"获取第 {page} 页，start={params['start']}")
                resp = requests.get(cls.BASE_URL, params=params)
                resp.raise_for_status()
                page_data = resp.json()
                if page_data['status']['error_message'] != 'SUCCESS':
                    logger.error(f"CMC API分页错误: {page_data['status']['error_message']}")
                    break
                batch = page_data['data'].get('tokenUnlockList', [])
                items.extend(batch)
                logger.info(f"成功获取第 {page} 页 {len(batch)} 条")
            return items
        except requests.exceptions.RequestException as e:
            logger.error(f"请求CMC API失败: {str(e)}")
            raise

    @classmethod
    def update_unlocks(cls, include_events=True):
        """
        更新所有代币的解锁数据
        
        Args:
            include_events: 是否获取并更新解锁事件，默认 True
        """
        unlock_list = cls.fetch_unlocks()
        updated_count = created_count = 0
        for unlock_data in unlock_list:
            crypto_id = unlock_data.get('cryptoId')
            symbol = unlock_data.get('symbol')
            try:
                total_supply = unlock_data.get('totalSupply')
                max_supply = unlock_data.get('maxSupply')

                # 如果total_supply大于max_supply，则使用max_supply的值
                if max_supply is not None and total_supply is not None and total_supply > max_supply:
                    logger.warning(
                        f"代币{symbol}(ID:{crypto_id})的total_supply({total_supply})大于max_supply({max_supply})，使用max_supply作为total_supply")
                    total_supply = max_supply

                # 计算锁仓量和已解锁量
                locked_amt = unlock_data.get('tokenLockedAmount', 0)
                unlocked_amt = unlock_data.get('tokenUnlockedAmount', 0)
                untracked_amt = unlock_data.get('tokenUntrackedAmount', 0)
                base = locked_amt + unlocked_amt + untracked_amt
                if base == 0:
                    base = max_supply or total_supply or 0

                api_pct = unlock_data.get('totalUnlockedPercentage')
                if api_pct is None:
                    api_pct = (unlocked_amt / base * 100) if base else None
                # 计算锁仓比和释放比（百分比）
                locked_pct = round((locked_amt / base * 100), 2) if base else None
                unlocked_pct = round((unlocked_amt / base * 100), 2) if base else None
                # 校验 API 返回的 totalUnlockedPercentage 与自计算的 unlocked_pct 是否一致，允许 0.01% 误差
                if api_pct is not None and unlocked_pct is not None:
                    diff = abs(api_pct - unlocked_pct)
                    if diff > 0.01:
                        logger.warning(
                            f"cmc_id={crypto_id}, symbol={symbol} API total_unlocked_percentage={api_pct}% vs unlocked_ratio={unlocked_pct}%, 差异 {diff}%"
                        )
                token_unlock, created = TokenUnlock.objects.update_or_create(
                    cmc_id=crypto_id,
                    defaults={
                        'name': unlock_data.get('name'),
                        'symbol': unlock_data.get('symbol'),
                        'next_unlock_date': datetime.fromtimestamp(
                            unlock_data.get('nextUnlocked', {}).get('date', 0) / 1000,
                            tz=timezone.utc
                        ) if unlock_data.get('nextUnlocked') else None,
                        'next_unlock_amount': unlock_data.get('nextUnlocked', {}).get('tokenAmount'),
                        'next_unlock_percentage': unlock_data.get('nextUnlocked', {}).get('tokenAmountPercentage'),
                        'total_locked': unlock_data.get('tokenLockedAmount'),
                        'total_unlocked': unlock_data.get('tokenUnlockedAmount'),
                        'total_supply': total_supply,
                        'max_supply': max_supply,
                        'locked_ratio': locked_pct,
                        'unlocked_ratio': unlocked_pct,
                    }
                )
                # 按需更新解锁事件：先删后插
                if include_events and unlock_data.get('nextUnlockedDetail'):
                    token_unlock.events.all().delete()
                    ts = unlock_data['nextUnlocked']['date'] / 1000
                    event_date = datetime.fromtimestamp(ts, timezone.utc)
                    for detail in unlock_data.get('nextUnlockedDetail', []):
                        UnlockEvent.objects.create(
                            token=token_unlock,
                            unlock_date=event_date,
                            unlock_amount=detail.get('tokenAmount'),
                            unlock_percentage=detail.get('tokenAmountPercentage'),
                            allocation_name=detail.get('allocationName'),
                            vesting_type=detail.get('vestingType')
                        )
                if created:
                    created_count += 1
                else:
                    updated_count += 1
            except Exception as e:
                logger.error(f"cmc_id={crypto_id}, symbol={symbol} 更新失败: {e}")
                continue
        logger.info(f"代币解锁数据更新完成: 新增{created_count}个，更新{updated_count}个")
        return {"created": created_count, "updated": updated_count}

    @classmethod
    def fetch_events(cls, cmc_id, page=1, limit=10, enable_small_unlocks=True):
        """
        从CoinMarketCap获取代币解锁事件列表
        """
        params = {
            'type': 'upcoming',
            'cryptoId': cmc_id,
            'page': str(page),
            'limit': str(limit),
            'enableSmallUnlocks': str(enable_small_unlocks).lower(),
        }
        try:
            logger.info(f"正在获取代币(ID:{cmc_id})的解锁事件数据")
            response = requests.get(cls.EVENT_URL, params=params)
            response.raise_for_status()
            data = response.json()
            if data['status']['error_message'] == 'SUCCESS':
                return data['data'].get('tokenEvent', [])
            else:
                raise Exception(f"CMC 事件API错误: {data['status']['error_message']}")
        except requests.exceptions.RequestException as e:
            logger.error(f"请求CMC事件API失败: {e}")
            raise

    @classmethod
    def update_full_events_for_token(cls, cmc_id, limit=10, enable_small_unlocks=True):
        """
        根据事件API获取并更新指定代币的所有解锁事件
        """
        token_unlock = TokenUnlock.objects.get(cmc_id=cmc_id)
        token_unlock.events.all().delete()
        page = 1
        total = 0
        while True:
            events = cls.fetch_events(cmc_id, page=page, limit=limit, enable_small_unlocks=enable_small_unlocks)
            if not events:
                break
            for ev in events:
                time_str = ev.get('time', '')
                try:
                    event_date = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
                except ValueError:
                    event_date = datetime.strptime(time_str, '%Y-%m-%dT%H:%M:%S.%fZ')
                    event_date = event_date.replace(tzinfo=timezone.utc)
                for alloc in ev.get('allocations', []):
                    UnlockEvent.objects.create(
                        token=token_unlock,
                        unlock_date=event_date,
                        unlock_amount=alloc.get('amount'),
                        unlock_percentage=ev.get('percentage'),
                        allocation_name=alloc.get('allocationName')
                    )
                    total += 1
            page += 1
        logger.info(f"已更新代币(ID:{cmc_id})的所有解锁事件，共{total}条")
        return total

    @classmethod
    def update_full_events_for_all(cls, limit=10, enable_small_unlocks=True):
        """
        遍历数据库中所有代币，更新其全部解锁事件
        """
        results = {}
        for token in TokenUnlock.objects.all():
            count = cls.update_full_events_for_token(token.cmc_id, limit=limit, enable_small_unlocks=enable_small_unlocks)
            results[token.cmc_id] = count
        return results
