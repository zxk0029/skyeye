#!/usr/bin/env python
# -*- coding: utf-8 -*-

import asyncio
import socket
import sys
import time
from typing import Iterable, Optional, Set, List

from django.conf import settings

from common.decorators import retry_on
from common.helpers import search_limit, getLogger
from apps.exchange.consts import SLEEP_CONFIG
from apps.exchange.cache_ops import merge_orderbooks, set_24ticker, set_orderbook
from apps.exchange.models import Exchange, TradingPair
from apps.exchange.types import Orderbook
from apps.exchange.ccxt_client import get_client

HOSTNAME = socket.gethostname()

logger = getLogger(__name__)

class CrawlerService(object):
    symbols: Iterable[TradingPair]
    symbol_names: Set[str]
    exchange_name: str
    exchange_slug: str
    exchange_client: Optional[object]

    def __init__(self, exchange_obj: Exchange, proxy=None, testnet=False):
        self.exchange_name = exchange_obj.name
        self.exchange_slug = exchange_obj.slug
        self.exchange = exchange_obj
        self.proxy = proxy
        self.testnet = testnet
        self.exchange_client = None
        self._initialize_client()
        self.logger = getLogger(f'crawler.service.{self.exchange_slug}')
        self.symbols: List[TradingPair] = []
        self.symbol_names: Set[str] = set()

    def _initialize_client(self):
        try:
            client = get_client(self.exchange_slug, "async")
            if not client:
                logger.error(f"get_async_client returned None for {self.exchange_slug} (Name: {self.exchange_name})")
                self.exchange_client = None
                return

            if self.proxy:
                client.aiohttp_proxy = f"http://{self.proxy}"
                logger.info(f"Applied specific proxy {self.proxy} to client for {self.exchange_slug} (Name: {self.exchange_name})")
            
            if self.testnet:
                if hasattr(client, 'set_sandbox_mode'):
                    try:
                        client.set_sandbox_mode(True)
                        logger.info(f"Enabled sandbox mode for {self.exchange_slug} (Name: {self.exchange_name})")
                    except Exception as e_sandbox:
                        logger.warning(f"Failed to set sandbox mode for {self.exchange_slug} (Name: {self.exchange_name}): {e_sandbox}")
                elif 'test' in client.urls:
                     client.urls['api'] = client.urls['test']
                     logger.info(f"Switched to test API URL for {self.exchange_slug} (Name: {self.exchange_name})")
                else:
                    logger.warning(f"Testnet mode requested for {self.exchange_slug} (Name: {self.exchange_name}), but unsure how to configure. Client might not support it directly or needs specific options.")
            
            self.exchange_client = client
            logger.info(f"Successfully initialized and configured CCXT client for {self.exchange_slug} (Name: {self.exchange_name})")

        except Exception as e:
            logger.error(f"Failed to initialize CCXT client for {self.exchange_slug} (Name: {self.exchange_name}): {e}", exc_info=True)
            self.exchange_client = None

    def init_symbols_of_exchange(self):
        if self.exchange_name == 'platform':
            self.symbols = TradingPair.objects.filter(status='Active', symbol_display__in=settings.MERGE_SYMBOL_CONFIG.keys())
        else:
            self.symbols = self.exchange.symbols.filter(status='Active')
        self.symbol_names = set([sym.symbol_display for sym in self.symbols])

    def run(self, action_func):
        self.init_symbols_of_exchange()
        loop = asyncio.get_event_loop()
        func = getattr(self, action_func)
        loop.run_until_complete(func())

    @retry_on()
    async def fetch_24ticker(self, symbol: TradingPair) -> None:
        self.logger.debug(f"Attempting fetch_24ticker for {symbol.symbol_display}")
        assert self.exchange_client is not None, f'{self} attribute exchange_client is None'
        try:
            ticker = await self.exchange_client.fetch_ticker(symbol.symbol_display)
            self.logger.debug(f"API call successful for {symbol.symbol_display}. Ticker data: {ticker}")
            ticker["timestamp"] = time.time() * 1000
            set_24ticker(self.exchange_slug, symbol.symbol_display, ticker)
            self.logger.debug(f"set_24ticker completed for {symbol.symbol_display}")
        except Exception as e:
            self.logger.error(f"Error during fetch_ticker API call or processing for {symbol.symbol_display}", exc_info=True)
            raise

    @retry_on()
    async def fetch_orderbook(self, symbol: TradingPair, limit: int) -> None:
        if not limit:
            limit = settings.QUOTE_ORDERBOOK_LIMIT
        assert self.exchange_client is not None, f'{self} attribute exchange_client is None'
        if symbol.symbol_display in ['BTC-USD', 'ETH-USD']:
            params = {'market_type': 'swap'}
            data = await self.exchange_client.fetch_order_book(symbol.symbol_display, params=params)
        else:
            slimit = search_limit(limit)
            assert slimit >= limit, f'slimit {slimit} must be greater than limit {limit}'
            data = await self.exchange_client.fetch_order_book(symbol.symbol_display, limit=slimit)
        ob = Orderbook.from_json(data)
        ob.bids = ob.bids[:limit]
        ob.asks = ob.asks[:limit]
        ob.source = "crawler@{HOSTNAME}"
        set_orderbook(self.exchange_slug, symbol.symbol_display, ob.as_json())

    @retry_on()
    async def fetch_markets(self):
        markets = await self.exchange_client.fetch_markets()
        for data in markets:
            if data['symbol'] not in self.symbol_names:
                self.logger.debug('symbol %s is not related', data['symbol'])
                continue

    async def crawler_fetch_markets(self):
        while True:
            try:
                await self.fetch_markets()
                self.logger.debug('Crawler %s markets success', self.exchange_slug)
            except Exception as e:
                self.logger.error('Crawler %s markets fail.', self.exchange_slug, exc_info=True)
            await asyncio.sleep(SLEEP_CONFIG['crawler_fetch_markets'])

    async def crawler_fetch_24tickers(self):
        self.logger.info(f"Starting crawler_fetch_24tickers loop for exchange {self.exchange_slug} (Name: {self.exchange_name})")
        if not self.symbols:
            self.logger.warning("Symbols list is empty, crawler loop will not run.")
            return
        while True:
            self.logger.debug(f"Starting new ticker fetch cycle for symbols: {self.symbol_names}")
            for symbol in self.symbols:
                self.logger.debug(f"Processing symbol: {symbol.symbol_display}")
                try:
                    await self.fetch_24ticker(symbol)
                except Exception as e:
                    self.logger.error(f'Error processing symbol {symbol.symbol_display} in main loop.', exc_info=True)
            try:
                sleep_time = SLEEP_CONFIG['crawler_fetch_24tickers']
            except KeyError:
                self.logger.warning("'crawler_fetch_24tickers' not found in SLEEP_CONFIG, using default 60s")
                sleep_time = 60
            self.logger.debug(f"Ticker fetch cycle complete. Sleeping for {sleep_time} seconds.")
            await asyncio.sleep(sleep_time)

    async def crawler_fetch_orderbooks(self, limit: int = 15):
        cnt = 0
        while True:
            cnt += 1
            if cnt >= 10:
                self.exchange.refresh_from_db()
                cnt = 0
            if self.exchange.is_active:
                await self.fetch_symbols_orderbooks(limit)
            else:
                self.logger.error('exchange %s is not active', self.exchange_slug)
            await asyncio.sleep(SLEEP_CONFIG['crawler_fetch_orderbooks'])

    async def fetch_symbols_orderbooks(self, limit: int):
        for symbol in self.symbols:
            try:
                await self.fetch_orderbook(symbol, limit)
                self.logger.debug(
                    'Crawler %s %s fetch orderbooks succeed',
                    self.exchange_slug,
                    symbol.symbol_display
                )
            except Exception as e:
                self.logger.error(
                    'Crawler %s %s fetch orderbooks fail',
                    self.exchange_slug,
                    symbol.symbol_display, exc_info=True
                )
                sys.exit(1)

    async def merge_orderbooks(self, symbol: TradingPair):
        await merge_orderbooks(symbol)

    async def crawler_merge_orderbooks(self):
        while True:
            for symbol in self.symbols:
                try:
                    await self.merge_orderbooks(symbol)
                    self.logger.debug('%s orderbook is merged' % symbol.symbol_display)
                except Exception as e:
                    self.logger.error('%s orderbook merging failed' % symbol.symbol_display, exc_info=True)
            await asyncio.sleep(SLEEP_CONFIG['crawler_merge_orderbooks'])
