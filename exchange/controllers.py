#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import time
from django.conf import settings
from itertools import groupby
from operator import attrgetter
from typing import Any, Dict, List, Optional, Tuple
from common.helpers import dec, getLogger
from common.redis_client import global_redis, local_redis
from exchange.consts import (
    API_RESPONSE_KEY,
    EXCHANGE_ORDERBOOKS_KEY,
    EXCHANGE_TICKERS_KEY,
    NRDS_EXCHANGE_ORDERBOOKS_KEY,
    NRDS_EXCHANGE_TICKERS_KEY,
    NRDS_SYMBOL_MERGE_ORDERBOOKS_KEY,
    SYMBOL_MERGE_ORDERBOOKS_KEY,
    EXCHANGE_BLOCKING
)
from exchange.exceptions import OrderbookNotFound
from exchange.models import Exchange, Symbol
from exchange.types import Orderbook, OrderEntry


logger = getLogger(__name__)

EXCHANGE_BLOCKING_PERIOD = 60 * 5

def set_exchange_account_blocking(exg_name: str, api_account: str):
    key = EXCHANGE_BLOCKING % (exg_name, api_account)
    data = dict(blocking=True)
    value = json.dumps(data)
    global_redis().set(key, value, timeout = EXCHANGE_BLOCKING_PERIOD)


def get_exchange_account_blocking(exg_name: str, api_account: str):
    key = EXCHANGE_BLOCKING % (exg_name, api_account)
    value = global_redis().get(key)
    try:
        if value:
            data = json.loads(value)
            return data["blocking"]
        else:
            return False
    except (KeyError, ValueError):
        return False


def set_24ticker(
        exchange_name: str, symbol: str, data: Dict[str, Any], timeout: int = 120
) -> None:
    key = EXCHANGE_TICKERS_KEY % (exchange_name, symbol)
    zkey = NRDS_EXCHANGE_TICKERS_KEY % (exchange_name, symbol)
    if data["timestamp"] is None:
        tmstp = int(time.time())
    else:
        tmstp = int(data["timestamp"])
    assert int(time.time()) - 300 < tmstp < int(time.time()) + 300, f"incorrect tmstp {tmstp}"
    tiker_map = {json.dumps(data): tmstp}
    local_redis().zadd(zkey, tiker_map)
    local_redis().zremrangebyscore(zkey, 0, tmstp - 1200)
    global_redis().set(key, json.dumps(data), timeout=timeout)


def get_24ticker(
        exchange_name: str, symbol: str, timeout: int = 120
) -> Optional[Dict[str, Any]]:
    key = EXCHANGE_TICKERS_KEY % (exchange_name, symbol)
    data = global_redis().get(key)
    if data:
        ticker = json.loads(data)
        if time.time() - ticker["timestamp"] < timeout:
            return ticker
        else:
            return ticker
    else:
        return None


def get_history_24ticker(
        exchange_name: str, symbol: str, timestamp: int = 0, timeout: int = 120
):
    zkey = NRDS_EXCHANGE_TICKERS_KEY % (exchange_name, symbol)
    score_end = timestamp or int(time.time())
    score_start = score_end - 1200
    data = local_redis().zrevrangebyscore(zkey, score_start, score_end)
    if len(data) > 0:
        ticker = json.loads(data[len(data) - 1].decode())
        if time.time() - ticker["timestamp"] < timeout:
            return ticker
        else:
            return ticker
    else:
        return None


def get_orderbook(exchange_name: str, symbol_name: str) -> Orderbook:
    key = NRDS_EXCHANGE_ORDERBOOKS_KEY % (exchange_name, symbol_name)
    print(key)
    data = global_redis().get(key)
    print(data)
    if not data:
        raise OrderbookNotFound(f"{exchange_name} {symbol_name}")
    p = json.loads(data)
    p.setdefault("exchange", exchange_name)
    return Orderbook.from_json(p)


def get_history_orderbook(
        exchange_name: str, symbol: str, timestamp: int = 0
) -> Orderbook:
    return get_history_orderbook_lst(exchange_name, symbol, timestamp)[-1]


def get_history_orderbook_lst(
        exchange_name: str, symbol: str, timestamp: Optional[int] = None
) -> List[Orderbook]:
    key = NRDS_EXCHANGE_ORDERBOOKS_KEY % (exchange_name, symbol)
    score_start = (timestamp or int(time.time())) - 1200
    score_end = int(time.time())
    data = local_redis().zrangebyscore(key, score_start, score_end)
    if not data:
        raise OrderbookNotFound(f"{exchange_name}.{symbol}")
    data2ob = lambda _data: Orderbook.from_json(
        dict(
            exchange=exchange_name,
            **json.loads(_data.decode())
        )
    )
    return list(map(data2ob, data))


class OrderbookDelayError(Exception):
    pass


def set_orderbook(exchange_name: str, symbol: str, data: Dict[str, Any]) -> None:
    assert all(key in data for key in ("source", "bids", "asks", "timestamp")), \
        f'{data} must have attribute ' \
        f'("source", "bids", "asks", "timestamp")'
    assert data["timestamp"], f'{data} attribute "timestamp" is None'
    key = EXCHANGE_ORDERBOOKS_KEY % (exchange_name, symbol)
    print("key11===", key)
    ts_new = data.get("timestamp", None)
    try:
        existing = global_redis().get(key)
        if existing:
            ob_data = json.loads(existing)
            ts_cur = ob_data.get("timestamp", None)
            if ts_cur and ts_new and ts_cur > ts_new:
                raise OrderbookDelayError
    except OrderbookDelayError:
        logger.info(f"{exchange_name}.{symbol}: {data['source']} data rejected.")
    else:
        ts_lag = time.time() * 1000 - ts_new
        logger.info(f"{exchange_name}.{symbol}: {data['source']} data accepted. ts_lag {ts_lag}")
        global_redis().set(key, json.dumps(data))  # timeout=None)
    zkey = NRDS_EXCHANGE_ORDERBOOKS_KEY % (exchange_name, symbol)
    tsmp = int(int(data["timestamp"]) / 1000)
    current = int(time.time())
    assert current - 300 < tsmp < current + 300, f"incorrect tsmp {tsmp}, current {current}"
    orderbook_map = {json.dumps(data): tsmp}
    print("set_orderbookset_orderbookset_orderbookset_orderbook")
    print(orderbook_map)
    print("set_orderbookset_orderbookset_orderbookset_orderbook")
    local_redis().zadd(zkey, orderbook_map)
    local_redis().zremrangebyscore(zkey, 0, tsmp - 1200)


def get_merged_orderbook(symbol_name: str) -> Orderbook:
    key = SYMBOL_MERGE_ORDERBOOKS_KEY % symbol_name
    dbdata = global_redis().get(key)
    if not dbdata:
        raise OrderbookNotFound(f"merged {symbol_name}")
    data: Dict[str, Any] = json.loads(dbdata)
    return Orderbook.from_json(data)


def set_merged_orderbook(symbol_name: str, orderbook: Orderbook) -> None:
    key = SYMBOL_MERGE_ORDERBOOKS_KEY % symbol_name
    global_redis().set(key, json.dumps(orderbook.as_json()))
    zkey = NRDS_SYMBOL_MERGE_ORDERBOOKS_KEY % symbol_name
    if orderbook.timestamp is None:
        tsmp = int(time.time())
    else:
        tsmp = int(int(orderbook.timestamp) / 1000)
    assert int(time.time()) - 300 < tsmp < int(time.time()) + 300, f"incorrect tsmp {tsmp}"
    merged_orderbook_map = {json.dumps(orderbook.as_json()): tsmp}
    local_redis().zadd(zkey, merged_orderbook_map)
    local_redis().zremrangebyscore(zkey, 0, tsmp - 1200)


def get_history_merged_orderbook(symbol_name: str, timestamp: int = 0) -> Orderbook:
    zkey = NRDS_SYMBOL_MERGE_ORDERBOOKS_KEY % symbol_name
    score_end = timestamp or int(time.time())
    score_start = score_end - 1200
    dbdata = local_redis().zrangebyscore(zkey, score_start, score_end)
    if len(dbdata) == 0:
        raise OrderbookNotFound(f"merged {symbol_name}")
    data: Dict[str, Any] = json.loads(dbdata[len(dbdata) - 1].decode())
    return Orderbook.from_json(data)


def get_perpetual_orderbook() -> Orderbook:
    for ex_name, symbol_name in [
        ("bitmex", "BTC/USD"),
        ("okex", "BTC-USD-SWAP"),
        ("huobipro", "BTC-USD"),
    ]:
        try:
            return get_orderbook(ex_name, symbol_name)
        except OrderbookNotFound:
            pass
    raise OrderbookNotFound(f"{ex_name} {symbol_name}")


def merge_order_list(old: List[OrderEntry], new: List[OrderEntry], reverse=False):
    output: List[OrderEntry] = []
    mixed = sorted(old + new, key=lambda ent: ent.price)
    for k, _ents in groupby(mixed, key=lambda ent: ent.price_str):
        ents = list(_ents)
        order = OrderEntry()
        order.price = dec(k)
        order.amount = dec(sum(e.amount for e in ents))
        output.append(order)
    return sorted(output, key=attrgetter("price"), reverse=reverse)


def save_merged_ob(symbol, orderbook, messages):
    toggle = True
    bids, asks = orderbook.bids, orderbook.asks
    while bids and asks and bids[0].price >= asks[0].price:
        bids, asks = (bids[1:], asks[:]) if toggle else (bids[:], asks[1:])
        toggle = not toggle
    bids_hidden = len(orderbook.bids) - len(bids)
    if bids_hidden:
        logger.warning(
            f"{bids_hidden} layers are hidden from bid-side merged orderbook."
        )
        messages['bids_hidden'] = bids_hidden
        orderbook.bids = bids
    asks_hidden = len(orderbook.asks) - len(asks)
    if asks_hidden:
        logger.warning(
            f"{asks_hidden} layers are hidden from ask-side merged orderbook."
        )
        messages['asks_hidden'] = asks_hidden
        orderbook.asks = asks
    if bids_hidden or asks_hidden:
        logger.warning(messages)
    else:
        logger.debug(messages)
    set_merged_orderbook(symbol.name, orderbook)


def merge_usds_orderbooks(symbol: Symbol):
    orderbook = Orderbook()
    symbols_dict = settings.EXCHANGE_FUTURES_SYMBOLS[symbol.quote_asset.name]

    # TODO: what if symbols_dict is empty
    groups = []
    for exchange_name, symbols in symbols_dict.items():
        try:
            ob = get_orderbook(exchange_name, symbols[0])
        except OrderbookNotFound:
            continue
        groups.append({
            'symbol': symbols[0],
            'timestamp': ob.timestamp,
            'source': ob.source,
            'exchange': ob.exchange,
            'detail': ob.as_json()
        })
        orderbook.bids = merge_order_list(orderbook.bids, ob.bids, reverse=True)
        orderbook.asks = merge_order_list(orderbook.asks, ob.asks)
    messages = {
        'groups': groups,
        'bids': [bid.as_json() for bid in orderbook.bids],
        'asks': [ask.as_json() for ask in orderbook.asks],
        'asks_hidden': 0,
        'bids_hidden': 0,
    }
    return orderbook, messages


def merge_orderbooks(symbol: Symbol):
    if symbol.name in ['BTC/USDS', 'ETH/USDS']:
        orderbook, messages = merge_usds_orderbooks(symbol)
    else:
        orderbook, messages = merge_usdt_orderbooks(symbol)
    save_merged_ob(symbol, orderbook, messages)


SPOT_EXG: Dict[str, Tuple[List, int]] = {}
SPOT_EXG_UPDATE_INTERVAL = 60


def merge_usdt_orderbooks(symbol: Symbol):
    global SPOT_EXG, SPOT_EXG_UPDATE_INTERVAL

    if symbol.name not in SPOT_EXG or SPOT_EXG[symbol.name][1] + SPOT_EXG_UPDATE_INTERVAL < time.time():
        exchanges = symbol.exchanges.filter(market_type="Cex", status="ACTIVE")[:]
        last_update = int(time.time())
        SPOT_EXG[symbol.name] = exchanges, last_update

    groups = []
    orderbook = Orderbook()
    exchange_names = settings.MERGE_SYMBOL_CONFIG[symbol.name].keys()
    for exchange in symbol.exchanges.filter(market_type="Cex", status="ACTIVE", name__in=exchange_names):
        try:
            ob = get_orderbook(exchange.name, symbol.name)
        except OrderbookNotFound:
            continue
        if symbol.category == "Spot":
            groups.append({
                'symbol': symbol.name,
                'timestamp': ob.timestamp,
                'source': ob.source,
                'exchange': ob.exchange,
                'detail': ob.as_json()

            })
            orderbook.bids = merge_order_list(orderbook.bids, ob.bids, reverse=True)
            orderbook.asks = merge_order_list(orderbook.asks, ob.asks)
    messages = {
        'groups': groups,
        'bids': [bid.as_json() for bid in orderbook.bids],
        'asks': [ask.as_json() for ask in orderbook.asks],
        'asks_hidden': 0,
        'bids_hidden': 0,
    }
    return orderbook, messages

