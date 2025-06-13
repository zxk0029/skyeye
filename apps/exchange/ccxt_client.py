#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from typing import Optional, Dict, Any

import aiohttp
import ccxt
import ccxt.async_support as async_ccxt
import ccxt.pro as ccxtpro

from common.helpers import getLogger

logger = getLogger(__name__)


def get_sync_client(exchange_name: str, extra_config: Optional[Dict] = None) -> Optional[object]:
    """
    Return a synchronous ccxt client.
    Suitable for scripts, management commands, and other non-async contexts.
    Args:
        exchange_name: Name of the exchange
        extra_config: Optional dictionary to override or add to default CCXT client config
    """
    try:
        config = {
            'timeout': 30000,
            'verbose': False,
            'enableRateLimit': True
        }
        if extra_config:
            config.update(extra_config)

        if not hasattr(ccxt, exchange_name):
            logger.error(f"CCXT sync exchange '{exchange_name}' not found.")
            return None
        exchange_class = getattr(ccxt, exchange_name)
        client = exchange_class(config)
        # logger.info(f"Created ccxt sync client: {exchange_name} (id: {client.id}) with config: {config}")
        return client
    except Exception as e:
        logger.error(f"Failed to create CCXT sync client: {exchange_name}: {e}", exc_info=True)
        return None


def get_async_client(exchange_name: str, client_type: str = "rest", extra_config: Optional[Dict] = None,
                     aiohttp_connector: Any = None) -> Optional[object]:
    """
    Return a ccxt.async_support (REST) or ccxt.pro (WebSocket) client according to client_type.
    REST client is for one-off requests, Pro client is for persistent WebSocket connections.
    Args:
        exchange_name: Name of the exchange
        client_type: 'rest' for ccxt.async_support, 'pro' for ccxt.pro
        extra_config: Optional dictionary to override or add to default CCXT client config
        aiohttp_connector: Optional custom aiohttp TCPConnector for DNS resolution customization
    """
    try:
        # Default base configuration
        config = {
            'timeout': 30000,  # Default timeout in milliseconds
            'verbose': False,  # CCXT internal verbose logging
            'enableRateLimit': True
        }

        # Merge extra_config, allowing it to override defaults
        if extra_config:
            config.update(extra_config)

        if client_type == "rest":
            if not hasattr(async_ccxt, exchange_name):
                logger.error(f"CCXT async_support (REST) exchange '{exchange_name}' not found.")
                return None
            exchange_class = getattr(async_ccxt, exchange_name)
            client = exchange_class(config)

            # 设置自定义aiohttp连接器（如果提供）
            if aiohttp_connector and hasattr(client, 'session'):
                # 关闭已存在的session
                if client.session:
                    try:
                        client.session.close()
                    except:
                        pass
                # 创建新的session并设置自定义连接器
                client.session = aiohttp.ClientSession(connector=aiohttp_connector)  # 直接使用aiohttp
                logger.debug(f"设置自定义aiohttp连接器到 {exchange_name} 客户端")

            return client
        elif client_type == "pro":
            if not hasattr(ccxtpro, exchange_name):
                logger.error(f"CCXT Pro (WebSocket) exchange '{exchange_name}' not found.")
                return None
            exchange_class = getattr(ccxtpro, exchange_name)
            client = exchange_class(config)

            # 设置自定义aiohttp连接器（如果提供）
            if aiohttp_connector and hasattr(client, 'session'):
                # 关闭已存在的session
                if client.session:
                    try:
                        client.session.close()
                    except:
                        pass
                # 创建新的session并设置自定义连接器
                client.session = aiohttp.ClientSession(connector=aiohttp_connector)  # 直接使用aiohttp
                logger.debug(f"设置自定义aiohttp连接器到 {exchange_name} Pro客户端")

            return client
        else:
            logger.error(f"Invalid client_type: '{client_type}', must be 'rest' or 'pro'.")
            return None
    except Exception as e:
        logger.error(f"Failed to create CCXT client: {exchange_name} (type: {client_type}): {e}", exc_info=True)
        return None


def get_client(exchange_name: str, sync_type: str = "sync", client_type: str = "rest",
               extra_config: Optional[Dict] = None, aiohttp_connector: Any = None) -> Optional[object]:
    """
    Unified function to get CCXT client based on sync_type and client_type.
    
    Args:
        exchange_name: Name of the exchange (e.g., 'binance', 'okx')
        sync_type: 'sync' for synchronous client, 'async' for asynchronous client
        client_type: Only used when sync_type='async', 'rest' for REST API, 'pro' for WebSocket
        extra_config: Optional dictionary to override or add to default CCXT client config
        aiohttp_connector: Optional custom aiohttp TCPConnector for DNS resolution customization
    
    Returns:
        CCXT client instance or None if creation fails
    """
    if sync_type == "sync":
        return get_sync_client(exchange_name, extra_config=extra_config)
    elif sync_type == "async":
        return get_async_client(exchange_name, client_type, extra_config=extra_config, aiohttp_connector=aiohttp_connector)
    else:
        logger.error(f"Invalid sync_type: '{sync_type}', must be 'sync' or 'async'.")
        return None

# 用法示例：
# # 同步客户端
# def sync_example():
#     client = get_client('binance', sync_type='sync')
#     if client:
#         print(client.fetch_markets())
#
# # 异步客户端
# async def async_example():
#     # REST 客户端
#     rest_client = get_client('binance', sync_type='async', client_type='rest')
#     if rest_client:
#         print(await rest_client.fetch_markets())
#         await rest_client.close()
#     
#     # WebSocket 客户端
#     pro_client = get_client('binance', sync_type='async', client_type='pro')
#     if pro_client:
#         # ... subscribe to streams etc. ...
#         await pro_client.close()
