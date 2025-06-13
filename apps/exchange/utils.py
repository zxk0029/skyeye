import asyncio
# import json # Removed as no longer used
from typing import Dict, List, Optional, Union, Any, Set

import ccxt
import ccxt.async_support as async_ccxt_module

from common.helpers import getLogger
# Removed CMC constants from this import as they are no longer used here

logger = getLogger(__name__)


def get_exchange_slug_map(only_active: bool = True, only_cex: bool = True) -> Dict[str, str]:
    """
    构建 slug/alias -> 主 slug 的映射表。
    - 支持 slug 唤起和 meta_data['ccxt_alias_ids'] 别名唤起。
    - 默认只查 active 且为 CEX 的交易所。
    - 返回 dict: {alias_or_slug: 主 slug}
    """
    try:
        from apps.exchange.models import Exchange

        qs = Exchange.objects.all()
        if only_active:
            qs = qs.filter(status='Active')
        if only_cex:
            qs = qs.filter(exchange_category='Cex')
        qs = qs.only('slug', 'meta_data')

        slug_map = {}
        for ex in qs:
            slug_map[ex.slug.lower()] = ex.slug  # 主 slug
            meta = ex.meta_data or {}
            for alias in (meta.get('ccxt_alias_ids') or []):
                slug_map[alias.lower()] = ex.slug
        return slug_map
    except Exception:
        return {}


async def check_exchange_capability(ccxt_module: Any, exchange_id: str, capability_name: str) -> Dict[str, Any]:
    """
    检查单个交易所对特定功能的支持情况。
    
    Args:
        ccxt_module: 要使用的ccxt模块 (如 ccxt.pro, ccxt.async_support)
        exchange_id: 交易所ID
        capability_name: 功能名称
        
    Returns:
        包含支持状态的字典
    """
    result = {
        'exchange_id': exchange_id,
        'support_status': 'unsupported_or_undefined',
        'error': None
    }

    client = None
    try:
        # 创建交易所实例
        client = getattr(ccxt_module, exchange_id)()

        # 检查功能支持情况
        if not (hasattr(client, 'has') and client.has):
            return result

        support_status = client.has.get(capability_name)

        # 根据支持状态分类
        if support_status is True:
            result['support_status'] = 'natively_supported'
        elif support_status == 'emulated':
            result['support_status'] = 'emulated_support'

    except ccxt.errors.NotSupported:
        pass
    except Exception as e:
        result['support_status'] = 'error'
        result['error'] = f"{type(e).__name__}: {str(e)}"
    finally:
        if client and hasattr(client, 'close'):
            try:
                await client.close()
            except Exception:
                pass

    return result


async def get_exchange_capability_support(ccxt_module: Any, capability_name: str, exchange_ids_to_check: Optional[List[str]] = None, max_concurrency: int = 200) -> Dict[str, Union[List[str], Dict[str, str]]]:
    """
    并发检查交易所对特定功能的支持情况。

    Args:
        ccxt_module: 要使用的ccxt模块 (如 ccxt.pro, ccxt.async_support)
        capability_name: 功能名称 (如 'fetchTickers', 'watchOrderBookForSymbols')
        exchange_ids_to_check: 可选的交易所ID列表。如果为None，检查ccxt_module中的所有交易所
        max_concurrency: 最大并发检查数量

    Returns:
        按功能支持情况分类的交易所字典
    """
    results = {
        'natively_supported': [],
        'emulated_support': [],
        'unsupported_or_undefined': [],
        'error_during_check': {}
    }

    # 确定要检查的交易所
    exchanges_to_iterate = exchange_ids_to_check or ccxt_module.exchanges
    valid_module_exchanges: Set[str] = set(ccxt_module.exchanges)

    # 过滤有效的交易所
    valid_exchanges = [ex for ex in exchanges_to_iterate if ex in valid_module_exchanges]

    # 添加无效交易所到错误列表
    for ex in exchanges_to_iterate:
        if ex not in valid_module_exchanges:
            results['error_during_check'][ex] = "Invalid exchange_id for the module"

    # 并发检查交易所支持情况
    semaphore = asyncio.Semaphore(max_concurrency)

    async def check_with_semaphore(exchange_id):
        async with semaphore:
            return await check_exchange_capability(ccxt_module, exchange_id, capability_name)

    # 执行所有检查任务
    # 两种方式实现并发:
    # 1. 使用Semaphore控制并发数量 - 适合需要限制并发请求数量的场景，避免API速率限制
    # tasks = [check_with_semaphore(ex) for ex in valid_exchanges]

    # 2. 直接并发所有任务 - 速度更快，但可能导致API速率限制或资源耗尽
    tasks = [check_exchange_capability(ccxt_module, ex, capability_name) for ex in valid_exchanges]

    all_results = await asyncio.gather(*tasks)

    # 处理结果
    for result in all_results:
        exchange_id = result['exchange_id']
        status = result['support_status']

        if status == 'natively_supported':
            results['natively_supported'].append(exchange_id)
        elif status == 'emulated_support':
            results['emulated_support'].append(exchange_id)
        elif status == 'error':
            results['error_during_check'][exchange_id] = result['error']
        else:
            results['unsupported_or_undefined'].append(exchange_id)

    # 对结果进行排序和去重
    for key in ['natively_supported', 'emulated_support', 'unsupported_or_undefined']:
        results[key] = sorted(list(set(results[key])))

    return results


async def execute_exchange_method_async(exchange_id: str, method_name: str, params: Optional[Dict[str, Any]] = None, max_retries: int = 3, retry_delay_seconds: int = 5) -> Optional[Dict[str, Any]]:
    """
    使用ccxt.async_support安全地从指定交易所执行指定的方法，
    处理速率限制和重试逻辑。
    
    Args:
        exchange_id: 交易所ID
        method_name: 要执行的方法名称 (如 'fetchTickers', 'fetchOrderBook')
        params: 传递给方法的参数
        max_retries: 最大重试次数
        retry_delay_seconds: 重试延迟基准秒数(使用指数退避策略)
        
    Returns:
        方法执行结果，如果失败则返回None
    """
    # 检查交易所是否受支持
    if exchange_id not in async_ccxt_module.exchanges:
        return None

    client = None
    try:
        # 创建交易所客户端
        client = getattr(async_ccxt_module, exchange_id)({'enableRateLimit': True, 'timeout': 20000})

        # 检查是否支持指定方法
        if not (hasattr(client, 'has') and client.has and client.has.get(method_name)):
            return None

        # 获取要执行的方法
        method = getattr(client, method_name, None)
        if method is None:
            return None

        # 准备参数
        method_params = params or {}
        # 为yobit添加特殊处理 (仅针对fetchTickers方法)
        if method_name == 'fetchTickers' and exchange_id == 'yobit' and (
                params is None or params.get("all", False) is not False):
            method_params = {"all": True, **(params or {})}

        # 执行带重试的数据获取
        for attempt in range(max_retries + 1):  # +1 是因为第一次尝试也计数
            try:
                return await method(params=method_params)
            except ccxt.errors.RateLimitExceeded as e:
                if attempt == max_retries:
                    return None
                wait_time = retry_delay_seconds * (2 ** attempt)  # 指数退避
                await asyncio.sleep(wait_time)
            except (ccxt.errors.NetworkError, ccxt.errors.RequestTimeout) as e:
                if attempt == max_retries:
                    return None
                wait_time = retry_delay_seconds * (2 ** attempt)  # 指数退避
                await asyncio.sleep(wait_time)
            except Exception as e:
                return None
    finally:
        # 确保客户端正确关闭
        if client and hasattr(client, 'close'):
            try:
                await client.close()
            except Exception:
                pass

    return None


async def acquire_lock(redis_client, lock_key, timeout=10, identifier="1"):
    """
    获取分布式锁
    
    Args:
        redis_client: Redis客户端(支持原始redis客户端或AsyncRedisClient及其子类)
        lock_key: 锁的键名
        timeout: 锁的超时时间(秒)
        identifier: 锁的标识符
        
    Returns:
        bool: 是否成功获取锁
    """
    lock_acquired = await redis_client.set(lock_key, identifier, nx=True, ex=timeout)
    return bool(lock_acquired)


async def release_lock(redis_client, lock_key, identifier="1"):
    """
    释放分布式锁
    
    Args:
        redis_client: Redis客户端(支持原始redis客户端或AsyncRedisClient及其子类)
        lock_key: 锁的键名
        identifier: 锁的标识符
        
    Returns:
        bool: 是否成功释放锁
    """
    current = await redis_client.get(lock_key)
    if current == identifier:
        await redis_client.delete(lock_key)
        return True
    return False


if __name__ == '__main__':
    import time

    # 或者使用python manage.py shell -c "from apps.exchange.utils import get_exchange_slug_map; print(get_exchange_slug_map())"
    # import django

    # os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'skyeye.settings')
    # django.setup()

    # result = get_exchange_slug_map()
    # print(result)

    # 测试get_exchange_capability_support函数
    # s = time.time()
    # print("测试get_exchange_capability_support函数:")
    # print(asyncio.run(get_exchange_capability_support(ccxt_pro_module, 'watchOrderBookForSymbols')))
    # print(f"执行时间: {time.time() - s}秒")

    # 测试execute_exchange_method_async函数
    print("\n测试execute_exchange_method_async函数:")
    s = time.time()
    result = asyncio.run(execute_exchange_method_async('yobit', 'fetchTickers', None))
    print(f"获取到 {len(result) if result else 0} 个交易对的ticker数据")
    print(f"执行时间: {time.time() - s}秒")
