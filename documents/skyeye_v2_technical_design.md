# SkyEye V2 市场数据监听系统技术设计文档

## 1. 引言

### 1.1. 背景与目标

SkyEye市场数据监听系统（以下简称SkyEye V2）旨在构建一个全面、实时、可靠的加密货币市场数据采集、处理和服务的平台。该系统将从众多中心化交易所（CEX）和日益重要的去中心化交易所（DEX）高效采集关键市场数据（包括但不限于实时价格、历史K线、交易量、市值等），进行严格的标准化处理与聚合，并通过高性能API（优先gRPC）服务于上游业务系统，特别是作为"HailStone业务中台"的核心数据基础设施。

SkyEye V2的业务目标紧密围绕PRD V1.1中定义的核心价值：
*   **统一数据源**：建立统一的市场数据采集与管理平台，解决多业务线独立获取数据带来的口径不一、重复开发、资源浪费问题。
*   **高质量数据**：提供全面、准确、及时的市场数据，保障业务决策与交易执行的可靠性。
*   **提升效率与降低成本**：显著降低新数据源接入成本和外部API调用开销。
*   **标准化**：形成统一的市场数据标准，提升跨系统数据一致性。

本文档旨在详细阐述SkyEye V2的技术架构、模块设计、数据库结构、分期迭代计划及相关技术考量，作为项目后续开发、测试和运维的主要技术依据。

### 1.2. 文档目的
*   明确SkyEye V2的系统架构和技术方案。
*   指导开发团队进行模块设计和功能实现。
*   为项目管理提供分阶段的迭代计划和人力估算参考。
*   作为项目相关方沟通和评审的技术基础。

### 1.3. 名词解释
*   **CEX**: Centralized Exchange (中心化交易所)
*   **DEX**: Decentralized Exchange (去中心化交易所)
*   **PRD**: Product Requirement Document (产品需求文档)
*   **API**: Application Programming Interface (应用程序编程接口)
*   **gRPC**: Google Remote Procedure Call
*   **K线**: Candlestick chart, 包含开盘价(Open)、收盘价(Close)、最高价(High)、最低价(Low)和成交量(Volume)。
*   **Tick数据**: 指市场中每一笔成交或报价的明细数据。
*   **HailStone业务中台**: 本项目的主要服务对象和上游系统。

## 2. 系统架构设计 (SkyEye V2)

### 2.1. 整体架构图

```plantuml
@startuml
skinparam componentStyle uml2
skinparam linetype ortho
skinparam ranksep 30
skinparam nodesep 50
skinparam packageStyle rectangle

!includeurl https://raw.githubusercontent.com/tupadr3/plantuml-icon-font-sprites/master/devicons/python.puml
!includeurl https://raw.githubusercontent.com/tupadr3/plantuml-icon-font-sprites/master/devicons/django.puml
!includeurl https://raw.githubusercontent.com/tupadr3/plantuml-icon-font-sprites/master/devicons/redis.puml
!includeurl https://raw.githubusercontent.com/tupadr3/plantuml-icon-font-sprites/master/devicons/postgresql.puml
!includeurl https://raw.githubusercontent.com/tupadr3/plantuml-icon-font-sprites/master/font-awesome-5/server.puml
!includeurl https://raw.githubusercontent.com/tupadr3/plantuml-icon-font-sprites/master/font-awesome-5/database.puml
!includeurl https://raw.githubusercontent.com/tupadr3/plantuml-icon-font-sprites/master/font-awesome-5/cogs.puml
!includeurl https://raw.githubusercontent.com/tupadr3/plantuml-icon-font-sprites/master/font-awesome-5/exchange_alt.puml
!includeurl https://raw.githubusercontent.com/tupadr3/plantuml-icon-font-sprites/master/font-awesome-5/broadcast_tower.puml

rectangle "外部数据源" as ExternalSources #line.dashed {
  rectangle "中心化交易所 (CEXs)\nBinance, OKX, etc." as CEXs
  rectangle "去中心化交易所 (DEXs)\nUniswap, PancakeSwap, etc." as DEXs
}

package "SkyEye V2 系统 (基于Django演进)" {
  package "数据采集层 (DataFetcher)" <<$python>> {
    component "CEX Collector" as CexCollector <<$cogs>>
    component "DEX Collector" as DexCollector <<$cogs>>
  }

  package "数据缓冲与消息队列" {
    database "Redis (Cache & Buffer)" as RedisCache <<$redis>>
    queue "RabbitMQ / Kafka (Task Queue)" as MessageQueue <<$rabbitmq>>
  }

  package "数据处理层 (DataProcessor)" <<$python>> {
    component "Raw Data Handler" as RawHandler <<$cogs>>
    component "Standardizer" as Standardizer <<$cogs>>
    component "K-Line Generator" as KlineGen <<$cogs>>
    component "Indicator Calculator\n(Future)" as IndicatorCalc <<$cogs>>
  }

  package "数据存储层 (DataStorage)" {
    database "PostgreSQL (Master)" as MasterPostgres <<$postgresql>>
    database "PostgreSQL (Replica)" as ReplicaPostgres <<$postgresql>>
  }

  package "API服务层 (APIService)" <<$django>> {
    component "gRPC Service" as GrpcService <<$server>>
    component "HTTP Service (Internal/Legacy)" as HttpService <<$server>>
  }

  package "监控与告警 (Monitoring & Alerting)" {
    component "Metrics Collector" as Metrics
    component "Alerting Engine" as Alerter
  }
}

rectangle "上游系统" as UpstreamSystems #line.dashed {
  actor "HailStone 业务中台" as HailStonePlatform
}

' Data Flows
CEXs --> CexCollector : "API (REST/WebSocket)"
DEXs --> DexCollector : "节点RPC/Subgraph/API"

CexCollector --> RedisCache : "原始/准原始数据"
DexCollector --> RedisCache : "原始/准原始数据"

CexCollector --> MessageQueue : "采集任务/事件"
DexCollector --> MessageQueue : "采集任务/事件"

RedisCache --> RawHandler : "读取待处理数据"
MessageQueue --> RawHandler : "触发处理任务"

RawHandler --> MasterPostgres : "持久化原始数据 (raw_cex_trades, raw_dex_swaps)"
RawHandler --> Standardizer

Standardizer --> KlineGen
Standardizer --> MasterPostgres : "标准化Tick/价格 (market_ticks)"

KlineGen --> MasterPostgres : "各周期K线 (kline_1min, etc.)"
IndicatorCalc --> MasterPostgres : "技术指标 (future)"

MasterPostgres --> ReplicaPostgres : "主从复制"

ReplicaPostgres --> GrpcService : "数据查询"
ReplicaPostgres --> HttpService : "数据查询"

GrpcService --> HailStonePlatform
HttpService --> HailStonePlatform : "(可选)"

Metrics ..> CexCollector
Metrics ..> DexCollector
Metrics ..> RawHandler
Metrics ..> GrpcService
Alerter ..> Metrics : "触发告警"

note right of CexCollector : 现有 `exchange` 模块演进
note right of DexCollector : 新增模块，对接各公链
note right of RawHandler : Django Celery Worker / 独立进程
note right of MasterPostgres : 核心业务数据存储
note right of ReplicaPostgres : 读写分离，提升查询性能
@enduml
```

### 2.2. 核心组件职责

#### 2.2.1. DataFetcher (数据采集服务)
负责从各类CEX和DEX获取原始市场数据。将演进为更健壮和可扩展的服务。
*   **CEX数据采集模块**:
    *   基于现有`exchange`模块和CCXT库进行升级。
    *   支持WebSocket实时推送和REST API轮询。
    *   实现PRD中定义的连接管理、心跳、自动重连、错误处理和数据源切换逻辑。
    *   将采集到的原始数据（如trades, order book snapshots）推送到数据缓冲层，并异步通知数据处理层。
*   **DEX数据采集模块**:
    *   全新模块，针对不同公链（Ethereum, BNB Chain, Solana, Tron等）和DEX协议（Uniswap, PancakeSwap等）。
    *   通过连接公链节点RPC、调用DEX的智能合约、查询Subgraph或使用第三方DEX API等方式获取数据。
    *   重点采集交易对的交易事件（Swaps）、流动性池状态、价格预言机数据等。
    *   同样将原始数据推送到缓冲层并通知处理层。

#### 2.2.2. DataBuffer (数据缓冲层，如Redis + 消息队列)
*   **Redis**:
    *   用于临时缓存从DataFetcher接收到的高频原始数据，供DataProcessor快速消费。
    *   存储近期热数据、配置信息、分布式锁等。
    *   优化现有Redis使用，例如更细致的key设计，过期策略。
*   **消息队列 (RabbitMQ/Kafka/Celery+Redis)**:
    *   解耦DataFetcher和DataProcessor。DataFetcher将采集任务完成的事件或原始数据（的引用）放入队列。
    *   支持DataProcessor的分布式、异步处理。
    *   用于任务分发、失败重试、流量削峰填谷。

#### 2.2.3. DataProcessor (数据处理服务)
负责对原始数据进行清洗、校验、转换、聚合和计算。可作为独立的Django应用或Celery任务集群。
*   **原始数据处理与校验 (Raw Data Handler)**:
    *   从DataBuffer消费原始数据。
    *   进行基础的数据格式校验、去重、时间戳对齐。
    *   将校验后的原始数据持久化到PostgreSQL的原始数据表（如`raw_cex_trades`, `raw_dex_swaps`），确保数据的完整性和可追溯性。
*   **数据标准化 (Standardizer)**:
    *   将不同来源、不同格式的原始数据转换为统一的内部标准格式（如统一的交易对表示、价格精度、时间单位）。
    *   处理货币对转换、单位换算等。
    *   输出标准化的Tick数据或价格流，存入`market_ticks`等表。
*   **K线生成与聚合 (K-Line Generator)**:
    *   基于标准化的Tick数据或价格流，实时或准实时生成各周期的K线数据（1分钟，5分钟，15分钟，30分钟，1小时，4小时，1天，1周，1月等，按PRD要求）。
    *   确保K线数据的准确性（OHLCV）。
    *   实现PRD中定义的K线更新策略和历史数据回补逻辑。
    *   将生成的K线数据持久化到相应的K线表。
*   **技术指标计算 (Indicator Calculator)**: (远期规划)
    *   基于K线数据或其他标准化数据，计算常用的技术指标（如MA, EMA, MACD, RSI, BOLL等）。
    *   提供可配置的指标计算引擎。

#### 2.2.4. DataStorage (持久化存储层，如PostgreSQL)
采用PostgreSQL作为主持久化数据库，考虑主从复制架构以实现读写分离和高可用。
*   **原始市场数据表**: 存储从CEX/DEX采集的未经深度处理的原始交易、订单簿片段等数据。
*   **标准化行情数据表**: 存储经过清洗和标准化的Tick数据、价格数据。
*   **K线数据表**: 分表存储不同周期的K线数据，优化查询性能。
*   **其他辅助表**: 如资产信息、交易所信息、交易对信息（可从现有模型演进）。

#### 2.2.5. APIService (API服务层)
向上游系统（主要是HailStone业务中台）提供数据服务。
*   **gRPC接口**:
    *   主要的服务接口形式，提供高性能、低延迟的数据查询。
    *   接口定义遵循PRD，涵盖实时价格、历史K线、交易量、市值等。
    *   提供清晰的proto文件和API文档。
*   **HTTP接口**: (可选)
    *   用于内部管理、简单查询或兼容现有系统。
    *   可基于Django REST framework实现。

#### 2.2.6. Monitoring & Alerting (监控告警模块)
对整个数据链路的关键节点和指标进行监控，并及时发出告警。
*   **指标采集**: 采集数据源连接状态、数据采集频率/延迟、处理队列长度、API响应时间、系统资源使用率等。
*   **数据质量监控**: 监控数据缺失、异常值（如价格剧烈波动）、数据一致性等。
*   **告警引擎**: 根据预设阈值和规则，通过邮件、短信、IM等方式发送告警。
*   **可视化**: 结合Prometheus, Grafana等工具进行指标展示和仪表盘配置。

### 2.3. 数据流程
1.  **CEX数据**: CEX API -> CexCollector -> Redis (原始ticks/trades) & MessageQueue (通知) -> RawDataHandler (读取Redis, 持久化原始数据到Postgres) -> Standardizer -> KlineGen -> Postgres (K线表)。
2.  **DEX数据**: DEX (链上事件/API) -> DexCollector -> Redis (原始swaps/events) & MessageQueue (通知) -> RawDataHandler (读取Redis, 持久化原始数据到Postgres) -> Standardizer -> KlineGen -> Postgres (K线表)。
3.  **API查询**: HailStonePlatform -> gRPC Service -> ReplicaPostgres -> gRPC Response。

### 2.4. 技术选型
*   **语言**: Python 3.x (主力)
*   **核心框架**: Django (用于快速开发、ORM、Admin后台、部分API服务、Celery集成)
*   **异步/高并发**:
    *   Celery (配合Redis/RabbitMQ，用于分布式任务队列，处理DataProcessor中的大部分逻辑)
    *   Asyncio/AIOHTTP/FastAPI (可选，用于DataFetcher中与外部交易所进行高并发IO交互的部分，或独立的轻量级gRPC服务节点)
*   **CEX数据采集**: CCXT库
*   **DEX数据采集**: Web3.py (Ethereum及EVM兼容链), Solana.py, Tronpy等各链SDK，或直接与节点RPC交互。
*   **消息队列**: Redis (作为Celery Broker), RabbitMQ (更专业的选择)
*   **缓存**: Redis
*   **数据库**: PostgreSQL (支持JSONB、时序数据优化特性)
*   **API**:
    *   gRPC: `grpcio`, `grpcio-tools`
    *   HTTP: Django REST framework
*   **监控与告警**: Prometheus, Grafana, Sentry (错误追踪), ELK/EFK Stack (日志管理)
*   **容器化**: Docker, Docker Compose
*   **编排**: Kubernetes (K8s) (生产环境推荐)

### 2.5. 现有系统集成与演进策略
*   **`exchange`模块**: 作为CEX Collector的核心基础进行重构和增强，剥离部分非采集核心逻辑，强化其连接管理和数据获取能力。
*   **`backoffice.models.MgObPersistence`**: 其存储的聚合价格逻辑会被新的K线生成和标准化数据表替代。历史数据迁移需评估。
*   **`dex`模块**: 废弃现有不完整的实现，按照新的DEX Collector设计全新开发。
*   **数据模型**:
    *   `Asset`, `Exchange`, `Symbol`等基础模型可沿用并按需扩展字段（如增加DEX特有属性）。
    *   新增大量与原始数据、标准化数据、K线相关的表。
*   **Management Commands**: 现有`broker_crawler`和`mg_ob_persistence`的逻辑将被新的服务化组件（DataFetcher, DataProcessor）替代。命令可保留用于一次性任务或调试。
*   **`frontend` API**: 可逐步废弃或仅保留内部管理用途，核心服务能力迁移至gRPC。

## 3. 数据库设计 (SkyEye V2)

基于PRD和演进策略，数据库需要新增和调整以下核心表。所有表将包含`created_at`和`updated_at`字段。

### 3.1. 新增/修改核心数据表结构

#### 3.1.1. `assets` (资产信息 - 演进自 `exchange.Asset`)
*   `id` (PK)
*   `name` (VARCHAR, UNIQUE, e.g., "Bitcoin")
*   `symbol` (VARCHAR, UNIQUE, e.g., "BTC")
*   `asset_type` (VARCHAR, e.g., "crypto", "stablecoin", "utility_token")
*   `decimals` (INTEGER, 精度)
*   `logo_url` (VARCHAR)
*   `platform` (VARCHAR, e.g., "Ethereum", "BNB Chain", "Native" - 针对Token)
*   `contract_address` (VARCHAR, 针对Token)
*   `status` (VARCHAR, e.g., "active", "delisted")
*   ... (其他元数据)

#### 3.1.2. `exchanges` (交易所信息 - 演进自 `exchange.Exchange`)
*   `id` (PK)
*   `name` (VARCHAR, UNIQUE, e.g., "Binance")
*   `slug` (VARCHAR, UNIQUE, e.g., "binance")
*   `type` (VARCHAR, "CEX" or "DEX")
*   `website_url` (VARCHAR)
*   `logo_url` (VARCHAR)
*   `api_config` (JSONB, 存储API endpoint, 限频等信息)
*   `chain_id` (INTEGER, 如果是DEX，关联到支持的链)
*   `dex_protocol` (VARCHAR, e.g., "UniswapV2", "UniswapV3", "PancakeSwapV2" - 针对DEX)
*   `status` (VARCHAR, "active", "maintenance")
*   ... (其他元数据)

#### 3.1.3. `markets` (交易市场/交易对 - 演进自 `exchange.Symbol` 和 `exchange.ExchangeSymbolShip`)
*   `id` (PK)
*   `exchange_id` (FK, `exchanges.id`)
*   `base_asset_id` (FK, `assets.id`)
*   `quote_asset_id` (FK, `assets.id`)
*   `symbol_external` (VARCHAR, 交易所原始交易对名称, e.g., "BTCUSDT")
*   `symbol_internal` (VARCHAR, 系统内标准交易对名称, e.g., "BTC/USDT")
*   `market_type` (VARCHAR, e.g., "spot", "futures", "swap")
*   `status` (VARCHAR, "active", "inactive", "delisted")
*   `precision` (JSONB, 价格、数量等精度信息)
*   `limits` (JSONB, 最小/最大下单量等限制)
*   `raw_market_info` (JSONB, 交易所返回的原始市场信息)
*   `is_active_on_skyeye` (BOOLEAN, SkyEye是否采集此市场)
*   UNIQUE (`exchange_id`, `symbol_external`)

#### 3.1.4. `raw_cex_trades` (CEX原始成交数据)
*   `id` (BIGSERIAL PK)
*   `market_id` (FK, `markets.id`)
*   `trade_id_external` (VARCHAR, 交易所原始成交ID)
*   `price` (DECIMAL)
*   `quantity` (DECIMAL, 数量)
*   `amount` (DECIMAL, 成交额 quote_asset)
*   `side` (VARCHAR, "buy" or "sell")
*   `timestamp_exchange` (TIMESTAMPTZ, 交易所时间戳)
*   `timestamp_received` (TIMESTAMPTZ, 系统接收时间戳)
*   `raw_data` (JSONB, 原始报文)
*   INDEX (`market_id`, `timestamp_exchange`)

#### 3.1.5. `raw_dex_swaps` (DEX原始Swap数据)
*   `id` (BIGSERIAL PK)
*   `market_id` (FK, `markets.id`)
*   `transaction_hash` (VARCHAR, 链上交易哈希)
*   `log_index` (INTEGER)
*   `block_number` (BIGINT)
*   `block_timestamp` (TIMESTAMPTZ)
*   `pair_address` (VARCHAR, 交易对合约地址)
*   `sender_address` (VARCHAR)
*   `recipient_address` (VARCHAR)
*   `amount0_in` (DECIMAL)
*   `amount1_in` (DECIMAL)
*   `amount0_out` (DECIMAL)
*   `amount1_out` (DECIMAL)
*   `price_calculated` (DECIMAL, 计算得出的价格)
*   `raw_log_data` (JSONB, 原始log事件)
*   INDEX (`market_id`, `block_timestamp`)
*   UNIQUE (`transaction_hash`, `log_index`)

#### 3.1.6. `market_ticks_standardized` (标准化Tick/价格数据)
*   `id` (BIGSERIAL PK)
*   `market_id` (FK, `markets.id`)
*   `price` (DECIMAL)
*   `volume_24h` (DECIMAL, 可选，如果从tick聚合)
*   `timestamp` (TIMESTAMPTZ, 数据点时间)
*   `source_type` (VARCHAR, "cex_trade", "dex_swap", "cex_ticker_update")
*   `original_event_id` (BIGINT, 关联到原始数据表ID，可选)
*   INDEX (`market_id`, `timestamp`)

#### 3.1.7. `klines` (K线数据 - 统一表，通过周期区分)
*   `id` (BIGSERIAL PK)
*   `market_id` (FK, `markets.id`)
*   `interval` (VARCHAR, e.g., "1m", "5m", "1h", "1d", "1w", "1M")
*   `open_time` (TIMESTAMPTZ, K线开盘时间，唯一键的一部分)
*   `open_price` (DECIMAL)
*   `high_price` (DECIMAL)
*   `low_price` (DECIMAL)
*   `close_price` (DECIMAL)
*   `volume` (DECIMAL, 交易量 - base asset)
*   `quote_volume` (DECIMAL, 交易额 - quote asset)
*   `trade_count` (INTEGER, 成交笔数)
*   `is_final` (BOOLEAN, 该K线周期是否已结束不再更新)
*   UNIQUE (`market_id`, `interval`, `open_time`)

#### 3.1.8. `asset_market_caps` (市值数据)
*   `id` (BIGSERIAL PK)
*   `asset_id` (FK, `assets.id`)
*   `timestamp` (TIMESTAMPTZ)
*   `market_cap_usd` (DECIMAL)
*   `circulating_supply` (DECIMAL)
*   `total_supply` (DECIMAL)
*   `max_supply` (DECIMAL)
*   `source` (VARCHAR, e.g., "CoinMarketCap", "CoinGecko")
*   UNIQUE (`asset_id`, `timestamp`, `source`)

### 3.2. 对现有表 (`Asset`, `Exchange`, `Symbol`) 的调整
如3.1所述，现有核心模型将演进为新的`assets`, `exchanges`, `markets`表，增加更多字段以支持新需求。数据迁移方案需要详细规划。

## 4. 迭代计划

### 4.0 MVP极速迭代计划 (1周目标)

**背景**: 鉴于快速验证核心价值的业务需求，此MVP计划旨在1周内交付一个最小可行产品。此计划将优先保障核心数据链路的打通和关键功能的实现，部分次要功能、性能优化、扩展性及健壮性将在MVP成功验证后，在后续的"完整功能迭代计划"中逐步完善。

**核心理念**: "快速上线、快速验证、小步快跑"。

#### 4.0.1. MVP目标
*   在一周内，交付一个能从 **1-2个核心CEX** (例如Binance) 采集实时交易数据、从**以太坊链的Uniswap (V2/V3)** 和 **BNB Chain的PancakeSwap (V2/V3)** 采集实时Swap数据。
*   为上述已接入的数据源，实现 **1分钟、5分钟、1小时、1天周期K线** 的生成、存储与聚合。
*   提供一个基础的 **HTTP API**，用于查询上述交易对的各周期K线数据。
*   系统能在开发/测试环境中稳定运行。

#### 4.0.2. MVP重点与范围
*   **CEX数据采集与处理**:
    *   基于现有`exchange`模块（如果可复用部分代码），快速适配获取1-2个指定CEX的实时trades数据。
    *   实现1分钟K线的实时生成。
    *   基于1分钟K线数据，通过后台任务聚合生成5分钟、1小时、1天K线数据。
    *   K线数据（所有周期）存储于PostgreSQL。
*   **DEX数据采集与处理**:
    *   针对ETH-Uniswap和BSC-PancakeSwap，实现Swap事件的监听与解析。
    *   获取Swap数据后，实现1分钟K线的实时生成。
    *   基于1分钟K线数据，通过后台任务聚合生成5分钟、1小时、1天K线数据。
    *   K线数据（所有周期）存储于PostgreSQL。
*   **K线数据**:
    *   **支持周期**: 1分钟、5分钟、1小时、1天。
    *   **聚合方式**: 5分钟、1小时、1天K线均由已落库的1分钟K线数据聚合计算生成。
*   **API服务**:
    *   提供HTTP GET接口，允许按交易对和K线周期查询K线数据。
    *   接口能返回OHLCV数据。
*   **技术架构**:
    *   最大程度利用Django框架、Celery进行异步任务处理（K线生成与聚合）、PostgreSQL存储。
    *   DataFetcher (采集), DataProcessor (K线生成/聚合), DataStorage (DB), APIService (HTTP) 采用最直接的实现。
*   **日志与部署**:
    *   基础的运行日志。
    *   通过Docker Compose在本地环境部署。

#### 4.0.3. MVP阶段的简化与牺牲
为确保1周内达成目标，以下方面将做大幅简化或暂不考虑：
*   **数据源覆盖**: CEX仅1-2个，DEX仅ETH和BSC各1个核心协议。PRD中其他数据源暂不接入。
*   **数据类型**: 仅关注Trades (CEX) / Swaps (DEX) 用于生成K线。PRD中提及的订单簿、完整Ticker、市值数据等暂不处理。
*   **K线周期**: 仅支持1m, 5m, 1h, 1d。PRD中其他周期（如周K、月K等）暂不生成。
*   **错误处理与健壮性**: 仅做基础的异常捕获和日志记录。PRD中复杂的错误重试、备用数据源切换、数据质量深度校验等暂不实现。
*   **API**: 仅提供基础HTTP查询K线。不提供gRPC接口，不考虑复杂查询参数、分页、认证授权等。
*   **性能与扩展性**: 不针对高并发、大数据量做深度优化。系统部署和组件间的耦合度可能较高。
*   **监控与告警**: 暂不搭建专门的监控告警系统。
*   **历史数据回补**: MVP阶段优先保障实时数据流入和K线生成，历史数据的完整回补暂不作为主要目标，或仅做少量手动导入。
*   **UI界面**: 无任何前端用户界面。

#### 4.0.4. MVP关键任务与时间安排 (示例性，总计约5-7个工作日)

**前提**: 开发环境、PostgreSQL、Redis、Celery基础组件已就绪。团队成员对相关技术栈有一定经验。

*   **Day 1: CEX K线 MVP - 准备与1分钟K线**
    *   **任务1.1 (上午)**: 项目结构调整与CEX采集适配。
        *   快速评估和调整现有`exchange`模块代码，使其能独立运行并采集指定1-2个CEX的实时trades数据。
        *   数据暂存Redis或直接进入处理队列。
        *   设计简化的`klines`表结构（包含`market_symbol`, `interval`, `open_time`, `o`, `h`, `l`, `c`, `v`）。
    *   **任务1.2 (下午)**: CEX 1分钟K线生成与存储。
        *   实现Celery异步任务，从trades数据流实时计算1分钟OHLCV。
        *   将1分钟K线数据写入PostgreSQL的`klines`表。
        *   进行初步数据验证。
    *   **产出**: 能从1-2个CEX采集数据并生成、存储1分钟K线。

*   **Day 2: CEX K线 MVP - 多周期聚合与API**
    *   **任务2.1 (上午)**: CEX 多周期K线聚合。
        *   编写Celery定时任务（或基于1分钟K线生成后的回调触发），从已存储的1分钟K线聚合生成5分钟、1小时、1天K线。
        *   更新`klines`表数据。
    *   **任务2.2 (下午)**: CEX K线查询API。
        *   使用Django REST framework创建简单的HTTP GET接口，允许按`market_symbol`和`interval` (1m, 5m, 1h, 1d) 查询K线数据。
        *   进行API测试。
    *   **产出**: CEX部分的1m, 5m, 1h, 1d K线数据生成与API查询功能。

*   **Day 3-4: DEX K线 MVP - ETH & BSC (各1个核心DEX)**
    *   **任务3.1 (Day 3 上午)**: DEX数据采集框架与ETH-Uniswap接入。
        *   搭建基础的DEX Swap事件监听框架 (使用Web3.py)。
        *   实现监听以太坊链上Uniswap V2/V3的Swap事件，解析出必要信息 (交易对、价格、数量、时间戳)。
        *   原始Swap数据暂存Redis或直接进入处理队列。
    *   **任务3.2 (Day 3 下午)**: ETH-Uniswap 1分钟K线生成。
        *   复用或调整CEX的1分钟K线生成逻辑，适配DEX Swap数据。
        *   存入`klines`表。
    *   **任务3.3 (Day 4 上午)**: BSC-PancakeSwap接入与1分钟K线生成。
        *   参照ETH实现，快速接入BNB Chain上PancakeSwap V2/V3的Swap事件。
        *   实现1分钟K线生成并存储。
    *   **任务3.4 (Day 4 下午)**: DEX 多周期K线聚合与API整合。
        *   将DEX的1分钟K线纳入多周期（5m, 1h, 1d）聚合任务。
        *   扩展HTTP API，使其支持查询DEX的K线数据。
    *   **产出**: ETH-Uniswap和BSC-PancakeSwap的1m, 5m, 1h, 1d K线数据生成与API查询功能。DEX部分的任务量较大，3天内完成挑战较高，可能需要非常专注或适当调整范围。

*   **Day 5: 集成、测试、部署与文档**
    *   **任务5.1 (上午)**: 系统集成与整体测试。
        *   确保CEX和DEX数据流整体通畅。
        *   对API进行全面测试。
        *   修复发现的BUG。
    *   **任务5.2 (下午)**: 简易部署与文档。
        *   编写或更新Docker Compose配置，确保能在本地一键部署。
        *   编写极简的API使用说明和系统运行说明。
    *   **产出**: 一个可本地部署运行的MVP版本，附带基础说明文档。

#### 4.0.5. MVP人力与资源提示
*   **人力**: 至少1-2名经验丰富的全栈或后端工程师高度专注投入。
*   **资源**: 稳定的开发环境，可访问的CEX API Key，可用的以太坊和BNB Chain节点RPC端点（可以使用公共的，但速率限制可能影响开发测试效率）。
*   **说明**: 此MVP计划时间非常紧张，特别是DEX部分，对开发人员的技术熟练度和问题解决能力要求很高。上述天数安排是理想情况，实际操作中可能需要根据具体情况灵活调整任务优先级或略微延长。增加多周期K线聚合使得任务更为饱满。

### 4.1. **完整功能迭代计划 (Post-MVP)**
MVP验证成功后，可参考此前的三期迭代计划（核心架构搭建与CEX能力增强、DEX数据接入与API初步服务、功能完善、性能优化与监控告警）进行后续的系统建设和功能迭代。原计划中的任务和人力估算可作为进一步细化的基础。

#### 4.1.1. 第一期：核心架构演进与数据覆盖扩展 (原计划第一期修订)
##### 目标 
*   搭建SkyEye V2项目的基础骨架（基于Django），并对核心组件进行初步实现和演进。
*   在MVP基础上，进一步增强CEX数据采集的覆盖面和健壮性，满足PRD V1.1中对CEX的初期要求。
*   完善核心数据处理流程，包括更细致的数据标准化和K线生成规则。
*   扩展K线周期，并为后续的gRPC服务打下数据基础。
*   建立更完善的日志、监控和测试体系的雏形。

##### 关键任务 
*   **T1.1: 项目基础架构巩固与模块化**
    *   回顾MVP架构，进行必要的重构，提升模块化程度 (e.g., `fetchers`, `processors`, `storage`, `apis` 应用的职责明确)。
    *   完善开发、测试、预生产环境的Docker配置。
    *   对Celery的使用进行优化，考虑更健壮的消息队列中间件（如RabbitMQ）的引入评估。
*   **T1.2: `DataStorage` - 核心表结构演进**
    *   根据PRD，完善`assets`, `exchanges`, `markets`表结构，支持更丰富的元数据。
    *   设计并实现`market_ticks_standardized`表用于存储标准化后的价格/tick数据。
    *   优化`klines`表结构，考虑分区或索引策略以应对更多周期和更大数据量。
    *   规划数据迁移方案（如果MVP数据需要保留）。
*   **T1.3: `DataFetcher` - CEX模块能力全面增强**
    *   全面实现PRD 4.1.1中对CEX数据采集的要求：
        *   覆盖PRD V1.1初期定义的5个主流CEX (Binance, OKX, Huobi, Bybit, Bitget)。
        *   实现更精细的采集频率控制（如标准30秒，高活跃交易对可配置更短，低流动性可配置更长）。
        *   完善API错误处理、自动重连、超时管理。
        *   (初步) 实现PRD中提及的"备用数据源切换"的框架设计，并针对1-2个核心交易对进行简单实现。
    *   原始CEX交易数据、Ticker数据（如果PRD要求）持久化到`raw_cex_trades` (或新增`raw_cex_tickers`)。
*   **T1.4: `DataProcessor` - 数据处理与K线生成优化**
    *   优化Celery worker的任务分配和并发控制。
    *   完善数据清洗、标准化流程，确保数据一致性。
    *   K线生成逻辑增强：
        *   确保1分钟K线生成的准确性和实时性。
        *   全面实现从1分钟K线聚合生成更多周期K线（如PRD要求的5m, 15m, 30m, 1h, 4h, 1d），并确保存储。
        *   研究并初步实现PRD 4.1.1中定义的"数据内容异常处理"（如极端离群值检测与标记）的基础框架。
*   **T1.5: `APIService` - gRPC服务准备与内部API演进**
    *   调研并确定gRPC在Django项目中的集成方案 (e.g., `django-grpc-framework`)。
    *   定义核心数据对象和服务的初步`.proto`文件 (主要围绕K线查询)。
    *   现有内部测试用HTTP API根据新的数据表和K线周期进行调整。
*   **T1.6: 日志、监控与测试增强**
    *   引入Prometheus + Grafana进行核心服务指标监控的初步搭建 (采集任务成功率、队列长度、DB性能等)。
    *   完善单元测试和集成测试覆盖率。

##### 交付物 
*   一个经过初步重构和优化的SkyEye V2后端服务。
*   满足PRD初期要求的CEX数据采集能力（覆盖范围、频率、基础错误处理）。
*   支持多周期K线 (1m, 5m, 15m, 30m, 1h, 4h, 1d) 的生成与存储。
*   演进后的数据库表结构。
*   初步的gRPC服务定义和内部API更新。
*   基础的监控指标和更完善的测试覆盖。
*   更新的技术文档。

##### 预估人力 
*   （待后续讨论确定）

#### 4.1.2. 第二期：DEX数据接入与gRPC API初步服务
##### 目标 
*   重点攻克DEX数据采集，按照PRD V1.1要求，覆盖初期计划的公链及其核心DEX协议。
*   将DEX的交易数据全面纳入数据处理和多周期K线生成流程。
*   正式对外提供第一版gRPC API服务，满足HailStone业务中台对CEX和DEX核心市场数据（价格、K线）的查询需求。
*   扩展数据存储能力以适应DEX数据的特性。

##### 关键任务 
*   **T2.1: `DataFetcher` - DEX模块全面建设**
    *   基于MVP的DEX采集经验，构建更通用和可扩展的DEX Collector框架。
    *   按照PRD要求，完成初期计划的公链覆盖 (Ethereum, BNB Chain, Tron, Solana, TON, Sui, Aptos)，每条链至少支持1-2个核心DEX协议的Swap事件监听和历史数据回补。
        *   例如：ETH (Uniswap V2/V3, Sushiswap), BSC (PancakeSwap V2/V3), Tron (SunSwap), Solana (Raydium, Orca)等。
    *   实现对不同链节点RPC的稳定连接和高效查询。
    *   原始DEX Swap数据、流动性池数据（如果需要）持久化到`raw_dex_swaps` (或新增相关表)。
    *   处理DEX数据采集中的特殊问题，如链重组、RPC节点延迟、数据解析复杂性等。
*   **T2.2: `DataProcessor` - DEX数据处理与K线整合**
    *   完善DEX Swap数据的清洗、校验、价格计算（考虑多路径、滑点影响因素的简化模型）。
    *   确保DEX数据能准确、及时地生成1分钟K线，并聚合到其他所需周期 (5m, 15m, 30m, 1h, 4h, 1d)。
    *   解决CEX与DEX数据在时间戳、交易对表示等方面的对齐问题。
*   **T2.3: `APIService` - gRPC服务正式上线V1**
    *   完善`.proto`文件定义，涵盖PRD要求的核心查询功能：
        *   按交易对、K线周期查询历史K线 (OHLCV)。
        *   查询指定交易对的最新价格/Tick。
        *   (可选) 查询资产列表、交易所列表、市场列表等元数据。
    *   全面实现gRPC服务端逻辑，确保从PostgreSQL副本高效读取数据。
    *   编写清晰的API文档 (如使用Swagger/OpenAPI生成工具配合gRPC Gateway)。
    *   提供客户端调用示例或SDK雏形。
    *   进行API的性能测试和安全性评估（基础）。
*   **T2.4: `DataStorage` - 数据库优化与扩展**
    *   针对DEX数据特点（如更多的交易对、不同的数据结构）优化表设计和索引。
    *   评估并实施PostgreSQL的主从复制和读写分离策略，确保查询API的性能。
*   **T2.5: 测试与文档完善**
    *   针对DEX数据链路和gRPC API进行全面的集成测试和端到端测试。
    *   完善所有新增模块的技术文档和API用户手册。

##### 交付物 
*   支持PRD初期要求的CEX和DEX数据源的采集、处理和多周期K线生成。
*   第一版正式可用的gRPC API服务，满足核心数据查询需求。
*   经过优化的数据存储方案。
*   较完整的测试报告和技术文档。

##### 预估人力 
*   （待后续讨论确定）

#### 4.1.3. 第三期：功能完善、性能优化与监控告警
##### 目标 
*   全面覆盖PRD V1.1中定义的所有功能需求，包括但不限于更广泛的数据源覆盖、所有K线周期的精确生成、市值数据采集、高级错误处理机制等。
*   构建完整、强大的数据监控与告警体系，保障系统稳定性和数据质量。
*   对系统进行全面的性能优化和压力测试，确保满足生产环境要求。
*   提升系统的可运维性、安全性和文档完备性。

##### 关键任务 
*   **T3.1: `DataFetcher` - 全覆盖与高级特性**
    *   完成PRD V1.1中剩余的所有CEX和DEX数据源的接入。
    *   全面实现并测试CEX备用数据源切换逻辑 (PRD 4.1.1)。
    *   实现PRD 4.1.1中要求的市值数据采集功能，设计并实现`asset_market_caps`表。
    *   (可选) 根据需求，采集更丰富的数据类型，如CEX的订单簿深度数据、DEX的流动性池详细信息等。
*   **T3.2: `DataProcessor` - K线策略完善与高级数据处理**
    *   精确实现PRD 4.1.1中所有K线周期的生成与更新策略，特别是周K、月K、季度K、年K的准确计算和最终化标记 (`is_final`字段)。
    *   全面实现并优化PRD 4.1.1中定义的数据内容异常处理机制 (极端离群值检测、数据中断处理等)。
    *   (可选) 引入更复杂的数据校验和清洗规则，提升数据质量。
    *   (可选) 根据PRD需求，开始技术指标计算 (Indicator Calculator) 模块的设计与初步实现 (如MA, EMA)。
*   **T3.3: `APIService` - gRPC服务增强与生态建设**
    *   根据HailStone业务中台的反馈和进一步需求，扩展gRPC接口功能，如更灵活的查询参数、聚合查询、数据推送/订阅机制（如果需要）。
    *   完善API版本管理策略。
    *   考虑API的认证授权机制，如使用OAuth2/JWT。
    *   提供更完善的客户端SDK (多语言可选) 和开发者文档。
*   **T3.4: `Monitoring & Alerting` - 全面监控告警系统搭建**
    *   基于Prometheus/Grafana/Alertmanager，建立覆盖数据链路各关键节点的全面监控仪表盘。
    *   配置针对数据采集失败、数据延迟过大、处理队列积压、API错误率超标、系统资源瓶颈等关键事件的告警规则和通知机制。
    *   开发或集成数据质量监控工具，定期对数据完整性、准确性、一致性进行自动化巡检和报告。
    *   ELK/EFK日志管理平台搭建，便于日志查询和问题定位。
*   **T3.5: 系统性能优化与压力测试**
    *   对整个系统进行端到端的性能瓶颈分析，重点优化DataFetcher的并发采集能力、DataProcessor的数据吞吐量、DataStorage的读写性能以及APIService的响应延迟和并发处理能力。
    *   进行模拟生产环境的压力测试，评估系统在高负载下的稳定性、可靠性和可扩展性，找出并解决性能瓶颈。
    *   数据库查询优化、缓存策略调优、异步任务处理优化等。
*   **T3.6: 安全加固、代码审计与运维体系建设**
    *   进行全面的安全评估和加固，包括API接口安全、依赖库漏洞扫描、数据存储加密、访问控制等。
    *   组织内部或外部代码审计。
    *   完善运维手册、应急预案、备份恢复策略、版本发布流程等。
*   **T3.7: 文档最终化与知识库沉淀**
    *   完成所有技术文档、API文档、用户手册、运维手册的最终审校和发布。
    *   建立项目知识库，沉淀设计文档、问题解决方案、经验教训等。

##### 交付物 
*   一个功能完整、性能达标、安全可靠、具备全面监控告警能力的SkyEye V2生产级系统。
*   全面满足PRD V1.1核心功能需求的市场数据服务。
*   完善的API、SDK及各类技术与运维文档。
*   压力测试报告和安全审计报告。

##### 预估人力 
*   （待后续讨论确定）

**注**: 上述Post-MVP的迭代计划和人力估算为基于PRD的较完整实现所做的初步规划。在MVP成功验证后，应根据实际业务优先级、资源情况以及MVP阶段的经验教训，对每一期的具体范围、任务和排期进行更详细的评审和调整。

## 5. 风险与挑战
*   **DEX数据源的多样性和复杂性**: 不同公链、不同DEX协议的数据获取方式差异大，维护成本高。
*   **数据量巨大**: 实时市场数据量非常庞大，对存储、处理和查询性能要求高。
*   **数据质量保障**: 外部数据源可能存在错误、延迟或中断，需要强大的校验和容错机制。
*   **实时性要求**: 部分场景对数据延迟要求极高，需要优化整个数据链路。
*   **第三方API依赖**: CEX的API限频、变更或不稳定可能影响服务。
*   **团队技术储备**: 需要团队成员对加密货币、区块链技术、相关开发工具有较好理解。
*   **项目初期范围蔓延**: 需严格控制每期目标，避免不必要的功能扩展。

## 6. 部署架构建议
*   **开发/测试环境**: Docker, Docker Compose。
*   **生产环境**:
    *   应用服务 (Django/Celery/gRPC) 容器化部署在Kubernetes集群，便于弹性伸缩和滚动更新。
    *   PostgreSQL采用云服务商提供的RDS (如AWS RDS for PostgreSQL, Google Cloud SQL for PostgreSQL) 或自建高可用集群。
    *   Redis采用云服务商提供的缓存服务 (如AWS ElastiCache, Google Memorystore) 或自建高可用集群。
    *   消息队列 (RabbitMQ/Kafka) 也推荐使用云服务或K8s上部署高可用集群。
    *   监控组件 (Prometheus, Grafana) 可部署在K8s集群内。
    *   使用负载均衡器 (如Nginx Ingress Controller, ALB/NLB) 对外暴露API服务。
    *   CI/CD流水线 (Jenkins, GitLab CI, GitHub Actions) 实现自动化构建、测试和部署。

## 7. 附录
*   PRD V1.1 (链接或嵌入)
*   详细API接口定义 (.proto文件，OpenAPI规范等) - 后续补充
*   数据库ER图 - 后续补充
*   关键配置项说明 - 后续补充 