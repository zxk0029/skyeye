# -*- coding: utf-8 -*-

import os

from django.conf import settings

EXCHANGE_MARKETS_KEY = 'crawler:%s:markets'

EXCHANGE_TICKERS_KEY = 'crawler:%s:%s:tickers'
NRDS_EXCHANGE_TICKERS_KEY = 'new:redis:crawler:%s:%s:tickers'

EXCHANGE_ORDERBOOKS_KEY = 'crawler:%s:%s:orderbooks'
NRDS_EXCHANGE_ORDERBOOKS_KEY = 'new:redis:crawler:%s:%s:orderbooks'

HIST_VOLA_KEY = 'crawler:%s:histvolatilti'

SYMBOL_MERGE_ORDERBOOKS_KEY = 'crawler:%s:merge_orderbooks'
NRDS_SYMBOL_MERGE_ORDERBOOKS_KEY = 'new:redis:crawler:%s:merge_orderbooks'

SYMBOL_PRICE_KEY = 'crawler:%s:%s:price'
API_RESPONSE_KEY = 'crawler:%s:api_name'

EXPIRE_TIME_INTERVAL = 5

# unit second
SLEEP_CONFIG = {
    "crawler_fetch_24tickers": 30,
    "crawler_fetch_markets": 60,
    "crawler_fetch_orderbooks": 3,
    "crawler_merge_orderbooks": 2
}

SLEEP_CONFIG.update(settings.CRAWLER_SLEEP_CONFIG)

EXCHANGE_FUNDING_RATE_KEY = 'crawler:funding_rate:%s'

# 稳定币监控相关常量
STABLECOIN_PRICE_KEY = 'stablecoin:price:%s'
STABLECOIN_LAST_UPDATE_KEY = 'stablecoin:last_update:%s'

# 稳定币监控间隔和过期时间（秒）
STABLECOIN_PRICE_MONITOR_INTERVAL = 600  # 每60秒更新一次
STABLECOIN_PRICE_EXPIRE_TIME = 300  # 数据5分钟过期

# 重试配置
STABLECOIN_MAX_RETRIES = 3
STABLECOIN_RETRY_DELAY = 5  # 秒

# 批处理大小
STABLECOIN_DB_BATCH_SIZE = 500  # 数据库批处理大小
REDIS_PIPELINE_BATCH_SIZE = 1000  # Redis批处理大小

# 交易所批处理大小 - 根据不同交易所API限制优化
EXCHANGE_TICKERS_BATCH_SIZE = {
    'default': 200,
    'binance': 400,
    'okx': 400,
    'kucoin': 400,
    'bybit': 400,
    'huobi': 400,
    'gateio': 400,
    'bitget': 400,
    'mexc': 400,
    'hitbtc': 400,
    'bingx': 400,
    'poloniex': 400,
    'latoken': 400,
    'bitmart': 400,
    'lbank': 200,
    'xt': 400,
    'yobit': 400
}

# 交易所特殊配置
EXCHANGE_SPECIAL_CONFIG = {
    'yobit': {
        'needs_all_param': True,  # 需要使用params={"all": True}参数
        'timeout': 120  # 更长的超时时间
    },
    'ascendex': {
        'needs_authentication': True  # 需要认证才能获取所有交易对
    }
}

# 稳定币符号列表
# STABLECOIN_SYMBOLS = ['USDT', 'USDC', 'DAI', 'USD', 'TUSD', 'USDP', 'FRAX', 'LUSD', 'PYUSD', 'SUSD', 'MIM', 'DOLA', 'ALUSD', 'CUSD']
STABLECOIN_SYMBOLS = [
    # 主流稳定币 - 最稳定，流动性最好
    'USDT',  # Tether - 市值最大
    'USDC',  # USD Coin - 合规性好
    'USD',
    'DAI',  # MakerDAO - 去中心化

    # 次级稳定币 - 相对稳定，有一定市场份额
    'USDS',
    'TUSD',  # TrueUSD
    'USDP',  # Pax Dollar（原PAX）
    'FRAX',  # Frax - 部分算法
    'LUSD',  # Liquity USD
    'PYUSD',  # PayPal USD - 新兴但背景强

    # 特定生态稳定币 - 在特定场景有用
    'SUSD',  # Synthetix
    'MIM',  # Magic Internet Money
    'DOLA',  # Inverse Finance
    'ALUSD',  # Alchemix USD
    'CUSD',  # Celo Dollar
]

# 交易所优先级列表
EXCHANGE_PRIORITY = [
    'binance',
    'bybit',
    'coinbase',
    # 'upbit', # 多数交易对是以韩元为报价
    'okx',
    'bitget',
    'mexc',
    'gate',
    'kucoin',
    'cryptocom',
    'htx',
    'kraken',
    'lbank',
    'bitmart',
    'ascendex',
    'poloniex',
    'bingx',
    'latoken',
    'yobit',
    'coinex',
    'xt',
    'phemex',
    'probit',
    'bigone',
    'hitbtc'
]

EXCHANGE_BLOCKING = 'exchange:%s:%s'
EXCHANGE_SYMBOL_MARKETS = 'exchange_markets:%s'  # 'exchange_markets:bitmex'

PENALTY_UNFINISHED_ORDERS = 'penalty_unfinished_orders'
LAST_USDT_USDS_TIMESTAMP = 'last_usdt_usds_timestamp'

# 交易所特定配置：交易所ID -> 监控间隔(秒)
EXCHANGE_SPECIFIC_INTERVALS = {
    'yobit': 60,  # 1分钟
    'mexc': 10,  # 10秒钟
    'gate': 10,  # 10秒钟
    'latoken': 10,  # 10秒钟
    'bitmart': 10,  # 10秒钟
    'ascendex': 10,  # 10秒钟
}