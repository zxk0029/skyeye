#!/usr/bin/env python
# -*- coding: utf-8 -*-

import asyncio
import sys
import time
from typing import Iterable, Optional, Set

from django.conf import settings

from common.decorators import retry_on
from common.helpers import search_limit, getLogger
from exchange import ccxt_client
from exchange.consts import SLEEP_CONFIG
from exchange.controllers import merge_orderbooks, set_24ticker, set_orderbook
from exchange.models import Exchange, Symbol
from exchange.types import Orderbook


import socket
HOSTNAME = socket.gethostname()


class CrawlerService(object):
    symbols: Iterable[Symbol]
    symbol_names: Set[str]
    exchange_name: str
    exchange_client: Optional[ccxt_client.ASYNCCCXTExchange]

    def __init__(self, exchange_name: str):
        self.exchange_name = exchange_name
        if self.exchange_name != 'platform':
            self.exchange = Exchange.objects.get(name=exchange_name)
        else:
            self.exchange = None
        self.logger = getLogger('crawler.service.{}'.format(self.exchange_name))
        self.symbols: Iterable[Symbol] = []
        self.symbol_names: Set[str] = set()
        self.exchange_client = ccxt_client.get_async_client(exchange_name)

    def init_symbols_of_exchange(self):
        if self.exchange_name == 'platform':
            self.symbols = Symbol.objects.filter(status='ACTIVE', name__in=settings.MERGE_SYMBOL_CONFIG.keys())
        else:
            self.symbols = self.exchange.symbols.filter(status='ACTIVE')
        self.symbol_names = [sym.name for sym in self.symbols]

    def run(self, action_func):
        self.init_symbols_of_exchange()
        loop = asyncio.get_event_loop()
        func = getattr(self, action_func)
        loop.run_until_complete(func())

    @retry_on()
    async def fetch_24ticker(self, symbol: Symbol) -> None:
        assert self.exchange_client is not None, f'{self} attribute exchange_client is None'
        ccxt_client.select_proxy(self.exchange_client)
        ticker = await self.exchange_client.fetch_ticker(symbol.name)
        ticker["timestamp"] = time.time()
        set_24ticker(self.exchange_name, symbol.name, ticker)

    @retry_on()
    async def fetch_orderbook(self, symbol: Symbol, limit: int) -> None:
        if not limit:
            limit = settings.QUOTE_ORDERBOOK_LIMIT
        assert self.exchange_client is not None, f'{self} attribute exchange_client is None'
        ccxt_client.select_proxy(self.exchange_client)
        if symbol.name in ['BTC-USD', 'ETH-USD']:
            params = {'market_type': 'swap'}
            data = await self.exchange_client.fetch_order_book(
                symbol.name, params=params)
        else:
            slimit = search_limit(limit)
            assert slimit >= limit, f'slimit {slimit} must be greater than limit {limit}'
            data = await self.exchange_client.fetch_order_book(
                symbol.name,
                limit=slimit
            )
        ob = Orderbook.from_json(data)
        ob.bids = ob.bids[:limit]
        ob.asks = ob.asks[:limit]
        ob.source = "crawler@{HOSTNAME}"
        set_orderbook(self.exchange_name, symbol.name, ob.as_json())

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
                self.logger.debug('Crawler %s markets success', self.exchange_name)
            except Exception as e:
                self.logger.error('Crawler %s markets fail.', self.exchange_name, exc_info=True)
            await asyncio.sleep(SLEEP_CONFIG['crawler_fetch_markets'])

    async def crawler_fetch_24tickers(self):
        while True:
            for symbol in self.symbols:
                try:
                    await self.fetch_24ticker(symbol)
                    self.logger.debug('Crawler %s %s fetch 24tickers success' % (self.exchange_name, symbol.name))
                except Exception as e:
                    self.logger.error('Crawler %s %s fetch 24tickers fail.' % (self.exchange_name, symbol.name),
                                      exc_info=True)
            sleep_time = SLEEP_CONFIG['crawler_fetch_24tickers']
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
                self.logger.error('exchange %s is not active', self.exchange_name)
            await asyncio.sleep(SLEEP_CONFIG['crawler_fetch_orderbooks'])

    async def fetch_symbols_orderbooks(self, limit: int):
        for symbol in self.symbols:
            try:
                await self.fetch_orderbook(symbol, limit)
                self.logger.debug(
                    'Crawler %s %s fetch orderbooks succeed',
                    self.exchange_name,
                    symbol.name
                )
            except Exception as e:
                self.logger.error(
                    'Crawler %s %s fetch orderbooks fail',
                    self.exchange_name,
                    symbol.name, exc_info=True
                )
                sys.exit(1)

    async def merge_orderbooks(self, symbol):
        merge_orderbooks(symbol)

    async def crawler_merge_orderbooks(self):
        while True:
            for symbol in self.symbols:
                try:
                    await self.merge_orderbooks(symbol)
                    self.logger.debug('%s orderbook is merged' % symbol.name)
                except Exception as e:
                    self.logger.error('%s orderbook merging failed' % symbol.name, exc_info=True)
            await asyncio.sleep(SLEEP_CONFIG['crawler_merge_orderbooks'])
