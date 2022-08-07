#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import functools
import random
import time
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
import ccxt.async_support as async_ccxt
from ccxt.async_support.base.exchange import (
    Exchange as ASYNCCCXTExchange,
)
from ccxt.base import errors as ccxt_exc
from ccxt.base.errors import ExchangeError
from ccxt.base.exchange import Exchange as CCXTExchange
from django.conf import settings
from eventlet import spawn
from eventlet.event import Event
from eventlet.queue import Empty, LightQueue
from common import exceptions
from common.helpers import getLogger
from common.redis_client import global_redis
from .consts import EXCHANGE_SYMBOL_MARKETS
from .models import Exchange, ExchangeAccount


logger = getLogger(__name__)


def del_token_bucket(key: str):
    fullkey = f'TOKENBUCKET/{key}'
    return global_redis().instance_local.delete(fullkey)

def token_bucket_key(acckeyid: Union[str, int]) -> str:
    return f'rlimit/{acckeyid}'

def consume_token_bucket(key: str) -> int:
    fullkey = f'TOKENBUCKET/{key}'
    return global_redis().instance_local.decr(fullkey)

def fill_token_bucket(key: str, cap: int=50):
    fullkey = f'TOKENBUCKET/{key}'
    rc = global_redis().instance_local
    remaining_cap = rc.get(fullkey)
    logger.info("token bucket of %s, remaining cap %s", key, remaining_cap)
    return rc.set(fullkey, cap)


class SelfRatelimit(ccxt_exc.ExchangeError):
    pass


class CCTask:
    task_done: Event
    func: Callable
    args: Tuple
    kwargs: Dict[str, Any]
    time_to_execute: float
    retry: int = 0
    ratelimit_retry: int

    def __init__(self, func: Callable, args: Tuple, kwargs: Dict[str, Any]):
        self.func = func  # type: ignore
        self.args = args
        self.kwargs = kwargs
        self.task_done = Event()
        self.time_to_execute = time.time()
        self.retry = 0
        self.ratelimit_retry = 0


def set_exchange_markets(exchange_name: str, markets: Dict[str, Any]):
    key = EXCHANGE_SYMBOL_MARKETS % exchange_name
    value = json.dumps(markets)
    global_redis().set(key, value, timeout=60 * 60)


def get_exchange_markets(exchange_name: str) -> Optional[Dict[str, Any]]:
    key = EXCHANGE_SYMBOL_MARKETS % exchange_name
    value = global_redis().get(key)
    if value:
        return json.loads(value)
    else:
        return None


def get_async_client(exchange_name: str) -> Optional[ASYNCCCXTExchange]:
    exchange_class = getattr(async_ccxt, exchange_name)
    exchange_client = exchange_class()
    select_proxy(exchange_client)
    print("exchange_clientexchange_clientexchange_clientexchange_clientexchange_client")
    print(exchange_client)
    print("exchange_clientexchange_clientexchange_clientexchange_clientexchange_client")
    return exchange_client


def select_proxy(exchange_client):
    if settings.C_PROXIES:
        selected = random.choice(settings.C_PROXIES)
        logger.info("async client %s selected proxy %s", exchange_client, selected)
        exchange_client.aiohttp_proxy = "http://%s" % selected


class CCXTClient(object):
    api_account: str = ""
    exchange: Exchange
    running: bool = True
    _api_key: str = ""
    _secret: str = ""
    _password: str = ""
    _proxy: List[str] = []
    max_retry: int = 3
    exchange_client: Optional[CCXTExchange] = None
    ratelimit_key: str = ''

    @classmethod
    def from_account(cls, exchange: Exchange, api_account: str = "") -> "CCXTClient":
        testnet = "test" == api_account
        exacc = ExchangeAccount.objects.filter(
            exchange=exchange, name=api_account, testnet=testnet
        ).last()
        assert exacc is not None, f"{exchange.name}.{api_account} does not exist."

        ea_key = ExchangeAccount.objects.filter(
            exchangeaccount=exacc, status='ACTIVE').order_by("?").first()
        assert ea_key is not None, f"{exchange.name}.{api_account}.key does not exist."

        return CCXTClient(
            exchange=exchange,
            api_account=api_account,
            api_key=ea_key.api_key,
            secret=ea_key.get_secret(),
            password=ea_key.password,
            proxy=ea_key.proxy,
            testnet=exacc.testnet,
            ratelimit_key=token_bucket_key(ea_key.id),
        )

    @classmethod
    def public_client(cls, exchange: Exchange) -> "CCXTClient":
        testnet = False
        # testnet = True if settings.TEST_MODE else False
        return CCXTClient(
            exchange=exchange,
            api_account="",
            api_key="",
            secret="",
            password="",
            proxy=[],
            testnet=testnet,
        )

    def __init__(self,
                 exchange: Exchange,
                 api_account: str,
                 api_key: str,
                 secret: str,
                 proxy: List[str] = None,
                 password: str = "",
                 testnet: bool = False,
                 ratelimit_key: str='',
    ):
        self._api_key = api_key
        self._secret = secret
        self._proxy = proxy or []
        self._password = password
        self._testnet = testnet

        self._logger = getLogger("ccxtclient.{}".format(exchange.name))
        self.api_account = api_account
        self.exchange = exchange
        self.local_methods = ["retry_on_error", "load_markets"]

        self.refresh_client()
        # make a queue to serialize operations on a single exchange
        # infinite size
        self.running = True
        self.queue = LightQueue()

        spawn(self.process_tasks)

    def refresh_client(self):
        import ccxt
        user_agent = f"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.88 Safari/537.{random.randint(1, 100)}"
        if self.exchange.name == "huobipro":
            from .ccxt_exchanges.huobipro import huobipro  # type:ignore

            exchange_class = huobipro
        elif self.exchange.name == 'binance':
            from .ccxt_exchanges.binance import binance  # type:ignore
            exchange_class = binance
        elif self.exchange.name == "okex_option":
            from .ccxt_exchanges.okex_option import okex as okex_option  # type: ignore

            exchange_class = okex_option
        elif self.exchange.name == "okex":
            from .ccxt_exchanges.okex import okex  # type: ignore
            exchange_class = okex
        elif self.exchange.name == 'bybit':
            from .ccxt_exchanges.bybit import bybit  # type: ignore
            exchange_class = bybit
        else:
            exchange_class = getattr(ccxt, self.exchange.name)
        if self._api_key and self._secret:
            key_pairs = {
                "apiKey": self._api_key,
                "secret": self._secret,
                "password": self._password,
            }
            self.exchange_client = exchange_class(key_pairs)
        else:
            self.exchange_client = exchange_class()
        if self._testnet and "test" in self.exchange_client.urls:
            self.exchange_client.urls["api"] = self.exchange_client.urls["test"]
            if self.exchange.name == "okex":
                self.exchange_client.testnet = True
        self.exchange_client.enableRateLimit = True
        self.exchange_client.userAgent = user_agent

    def get_markets(self):
        markets = get_exchange_markets(exchange_name=self.exchange.name)
        if markets:
            self.exchange_client.markets = markets
        else:
            markets = self.exchange_client.load_markets()
            set_exchange_markets(exchange_name=self.exchange.name, markets=markets)

    def get_proxy(self):
        if self.exchange.name == "kkex":
            return None

        acc: Tuple[str, str] = (self.exchange.name, self.api_account)
        # proxies: List[str] = settings.ACCOUNT_PROXIES.get(
        #     acc, settings.PROXIES)

        proxies: List[str] = []
        if self._proxy:
            proxies = self._proxy
        elif not self.api_account:
            # not api_account means it's the public client
            proxies = settings.C_PROXIES
        # proxies: List[str] = [self._proxy] if self._proxy else settings.PROXIES
        if not proxies:
            return None

        # selected = random.randint(0, len(settings.PROXIES) - 1)
        selected = random.choice(proxies)
        logger.info("%s selected proxy %s", acc, selected)
        return {"http": selected, "https": selected}

    def __getattr__(self, name: str) -> Callable:
        if name not in self.local_methods:
            f = getattr(self.exchange_client, name)
        else:
            f = getattr(self, "_" + name)
        return functools.partial(self.add_task, f)

    def add_task(self, func, *args, **kwargs):
        if not self.running:
            self._logger.debug("ccxt client %s destroyed" % self)
            raise Exception("CCXT Client Destroyed")

        # task_done = eventlet.event.Event()
        # self.queue.put((task_done, func, args, kwargs))
        task = CCTask(func, args, kwargs)
        self.queue.put(task)

        err, result = task.task_done.wait()
        # if isinstance(result, Exception):
        if err:
            raise err
        return result

    def process_tasks(self):
        while True:
            queue_size = self.queue.qsize()
            if queue_size >= settings.WARNING_QUEUE_SIZE:
                self._logger.warning(
                    "queue size too high: %s for exchange %s"
                    " client %s" % (queue_size, self.exchange.name, id(self))
                )
            try:
                task = self.queue.get(block=True, timeout=2)
            except Empty:
                if not self.running:
                    self._logger.debug("ccxt client %s destroyed, stop tasks" % self)
                    break
                else:
                    continue

            assert isinstance(task, CCTask)
            if task.time_to_execute > time.time():
                self.queue.put(task)
                time.sleep(0.1)
            else:
                # FIXME, an interval value to avoid ddos
                self.execute_task(task)
                time.sleep(0.5)


    def consume(self):
        if self.ratelimit_key:
            r = consume_token_bucket(self.ratelimit_key)
            logger.info('consume %s to %s', self.ratelimit_key, r)
            if r < 0:
                raise SelfRatelimit("rate limit excceed, %s" % self.func)

    def execute_task(self, task: CCTask) -> None:
        # assign a proxy for this request
        proxies = self.get_proxy()
        if proxies:
            self.exchange_client.proxies = proxies  # type: ignore
        self.get_markets()

        try:
            self.consume()
            func = task.func
            resp = func(*task.args, **task.kwargs)
            task.task_done.send((None, resp))
        except SelfRatelimit as e:
            self._logger.warning(
                'rate limit exceeded %s', task.func, exc_info=True)
            task.ratelimit_retry += 1
            if task.ratelimit_retry > 10:
                task.task_done.send((e, None))
            else:
                # 再重新试一次
                task.time_to_execute = time.time() + 2
                self.queue.put(task)
        except (ccxt_exc.ExchangeError, ExchangeError) as e:
            self._logger.warning(
                "except exchange error func %s" % task.func, exc_info=True
            )
            if '-1013' in str(e):
                e = None
            task.task_done.send((e, None))
        except ccxt_exc.NetworkError as e:
            self._logger.warning(
                "network error on task %s, retry on 30 seconds, args %s kwargs %s"
                % (task.func, task.args, task.kwargs),
                exc_info=True,
            )
            task.retry += 1
            if task.retry > 1 or self.exchange.name == "savour":
                task.task_done.send((e, None))
            else:
                task.time_to_execute = time.time() + 10
                self.queue.put(task)
        except ccxt_exc.InvalidOrder as e:
            if '-1013' in str(e):
                logger.info(e)
                e = None
            task.task_done.send((e, None))
        except Exception as e:
            self._logger.warning(
                "request error on proxy %s for %s, args %s, kwargs %s"
                % (
                    self.exchange_client.proxies,  # type: ignore
                    task.func,
                    task.args,
                    task.kwargs,
                ),
                exc_info=True,
            )
            err = e
            task.task_done.send((err, None))

    def _retry_on_error(self, func_name: str, *args, **kwargs):
        func = getattr(self.exchange_client, func_name)

        # max_retry = 3
        retry_intervals = fib(settings.CRAWLING_INTERVAL, self.max_retry)
        retry = 0

        exc_cause: Optional[Exception] = None
        while retry <= self.max_retry:
            try:
                self._logger.info(
                    f'api stats exchange name {self.exchange_client.name} func_name {func_name} proxy {self.exchange_client.proxies }'
                )
                result = func(*args, **kwargs)
                return result
            except ccxt_exc.ExchangeError as e:
                # ExchangeError 表明即使重试也无法成功, 可以直接退出
                self._logger.warning(
                    "request %s on exhange %s error, %s"
                    % (func_name, self.exchange.name, e)
                )
                exc_cause = e
                # exceptions.notify_sentry()
                break
            except ccxt_exc.NetworkError as e:
                retry_interval = retry_intervals[retry]
                self._logger.warning(
                    "request %s on exchange %s failed: %s, retry after "
                    "%s seconds" % (func_name, self.exchange.name, e, retry_interval),
                    exc_info=True,
                )
                exc_cause = e
                time.sleep(retry_interval)
                if isinstance(e, ccxt_exc.NetworkError):
                    # use a new client instance, new proxy
                    self.refresh_client()
                    proxies = self.get_proxy()
                    if proxies:
                        self._logger.debug("got 1 proxy %s" % proxies)
                        self.exchange_client.proxies = proxies  # type: ignore
                retry += 1
                exceptions.notify_sentry()
                continue
        if exc_cause:
            msg = (
                "error %s request %s on exchange %s failed after %s retry, "
                "give up" % (exc_cause, func_name, self.exchange.name, self.max_retry)
            )
            self._logger.warning(msg)
            raise exceptions.CCXTException(message=msg) from exc_cause

    def destroy(self):
        self.running = False

    def _load_markets(self):
        return self._retry_on_error("load_markets")


class AsyncCCXTClient(object):
    api_account: str = ""
    exchange: Exchange
    _api_key: str = ""
    _secret: str = ""
    _password: str = ""
    _proxy: List[str] = []

    def __init__(
        self,
        exchange: Exchange,
        api_account: str,
        api_key: str,
        secret: str,
        proxy: List[str] = None,
        password: str = "",
        testnet: bool = False,
    ):
        self._api_key = api_key
        self._secret = secret
        self._proxy = proxy or []
        self._password = password
        self._testnet = testnet

        self._logger = getLogger("ccxtclient.{}".format(exchange.name))
        self.api_account = api_account
        self.exchange = exchange
        self.refresh_client()

    @classmethod
    def from_account(
        cls, exchange: Exchange, api_account: str = ""
    ) -> "AsyncCCXTClient":
        testnet = "test" == api_account
        # testnet = True if settings.TEST_MODE else False
        # if testnet:
        #     api_account = 'test'
        # NOTE: status = "ACTIVE", enable = True, are by default
        exacc = ExchangeAccount.objects.filter(
            exchange=exchange,
            name=api_account,
            testnet=testnet,
        ).last()
        assert exacc is not None, f"{exchange.name}.{api_account} does not exist."

        ea_key = ExchangeAccount.objects.filter(
            exchangeaccount=exacc, status='ACTIVE').order_by("?").first()
        assert ea_key is not None, f"{exchange.name}.{api_account}.key does not exist."

        return AsyncCCXTClient(
            exchange=exchange,
            api_account=api_account,
            api_key=ea_key.api_key,
            secret=ea_key.get_secret(),
            password=ea_key.password,
            proxy=ea_key.proxy,
            testnet=exacc.testnet,
            ratelimit_key=f'rlimit/{ea_key.id}'
        )

    def refresh_client(self):
        import ccxt.async_support as ccxt

        if self.exchange.name == "huobipro":
            from .cex.async_support.huobipro import (
                huobipro as async_huobipro,
            )
            exchange_class = async_huobipro
        elif self.exchange.name == "okex":
            from .cex.async_support.okex import (
                okex as async_okex,
            )
            exchange_class = async_okex
        elif self.exchange.name == "bianace":
            from .cex.async_support.binance import (
                binance as async_binance,
            )
            exchange_class = async_binance
        else:
            exchange_class = getattr(ccxt, self.exchange.name)
        if self._api_key and self._secret:
            key_pairs = {
                "apiKey": self._api_key,
                "secret": self._secret,
                "password": self._password,
            }
            proxy = self.get_proxy()
            if proxy:
                key_pairs["aiohttp_proxy"] = proxy["https"]
            self.exchange_client = exchange_class(key_pairs)
        else:
            self.exchange_client = exchange_class()
        if self._testnet and "test" in self.exchange_client.urls:
            self.exchange_client.urls["api"] = self.exchange_client.urls["test"]
            if self.exchange.name == "okex":
                self.exchange_client.testnet = True
        self.exchange_client.enableRateLimit = True

    def __getattr__(self, name: str) -> Callable:
        logger.debug(f"access AsyncCCXTClient attribute: {name}")
        return getattr(self.exchange_client, name)

    def get_proxy(self):
        if self.exchange.name == "kkex":
            return None

        acc: Tuple[str, str] = (self.exchange.name, self.api_account)

        proxies: List[str] = []
        if self._proxy:
            proxies = self._proxy
        elif not self.api_account:
            proxies = settings.C_PROXIES
        if not proxies:
            return None

        selected = random.choice(proxies)
        logger.debug("%s selected proxy %s", acc, selected)
        return {"http": selected, "https": selected}


def fib(start: int, n: int) -> List[int]:
    result: List[int] = [start]
    a, b = 0, start
    for _ in range(0, n):
        a, b = b, a + b
        result.append(b)
    if n <= 0:
        return []
    return result

