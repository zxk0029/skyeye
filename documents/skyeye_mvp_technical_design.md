# SkyEye MVP 专项技术设计文档

## 1. 引言 (MVP焦点)

### 1.1. MVP目标
本文档旨在为SkyEye市场数据监听系统的MVP（Minimum Viable Product，最小可行产品）阶段提供详细的技术设计方案。MVP的核心目标是在**1周内**，快速交付一个具备核心功能的市场数据服务原型，以便：
*   验证核心技术路径的可行性（CEX和DEX数据接入、K线生成与服务）。
*   为后续迭代收集早期反馈。
*   向上层业务（如HailStone业务中台）展示初步的数据服务能力。

具体产出目标如下：
*   从 **1-2个核心CEX** (首选Binance) 采集实时交易数据。
*   从**以太坊链的Uniswap (V2/V3)** 和 **BNB Chain的PancakeSwap (V2/V3)** 采集实时Swap数据。
*   为上述已接入的数据源，实现 **1分钟、5分钟、1小时、1天周期K线** 的生成、存储与聚合（5m, 1h, 1d由1m聚合）。
*   提供一个基础的 **HTTP API**，用于查询上述交易对的各周期K线数据。
*   系统能在开发/测试环境中稳定运行。

### 1.2. MVP范围与明确的牺牲点
为确保1周内达成目标，MVP阶段将严格控制范围，并在多个方面进行简化和牺牲：

**MVP范围内**: 
*   **CEX接入**: 1-2个，仅采集Trades数据。
*   **DEX接入**: ETH Uniswap (V2/V3), BSC PancakeSwap (V2/V3)，仅采集Swap事件数据。
*   **K线数据**: 支持1m, 5m, 1h, 1d周期。5m, 1h, 1d 由1m聚合生成。
*   **API服务**: 基础HTTP GET接口查询K线。
*   **数据存储**: PostgreSQL存储K线，可选存储原始交易/Swap数据。
*   **核心中间件**: Celery + Redis (Broker/Backend)。
*   **部署**: 本地Docker Compose。

**MVP牺牲点 (暂不考虑或极简实现)**:
*   **数据源广度**: PRD中提及的其他CEX/DEX及公链。
*   **数据类型丰富度**: 订单簿、完整Ticker、市值、历史成交明细深度等。
*   **K线周期完整性**: PRD中提及的更长周期（周K、月K）或自定义周期。
*   **错误处理与系统健壮性**: 仅基础异常捕获。无复杂重试、备用源切换、数据质量校验、高可用设计。
*   **API高级功能**: 无gRPC，无复杂查询参数、分页、认证、限流。
*   **性能与扩展性**: 不针对高并发、大数据量优化。优先功能实现。
*   **监控与告警**: 无。
*   **历史数据回补**: 优先实时数据，历史数据回补不做重点或仅少量手动处理。
*   **UI界面**: 无。
*   详细的资产和市场元数据管理**: MVP阶段将通过数据库管理核心的交易所、资产和市场配置，但可能不包含所有详尽的元数据字段，高级动态管理功能（如通过UI配置）将后续迭代。

### 1.3. 预期的1周交付产出
*   可运行的后端服务代码库 (Python/Django)。
*   PostgreSQL数据库包含采集到的K线数据。
*   可供调用的HTTP K线查询API，并附带简单的API使用说明。
*   本MVP技术设计文档。

## 2. MVP系统架构

### 2.1. 简化的MVP架构图
```plantuml
@startuml MVP Architecture
skinparam componentStyle uml2
skinparam linetype ortho
skinparam ranksep 20
skinparam nodesep 30

!includeurl https://raw.githubusercontent.com/tupadr3/plantuml-icon-font-sprites/master/devicons/python.puml
!includeurl https://raw.githubusercontent.com/tupadr3/plantuml-icon-font-sprites/master/devicons/django.puml
!includeurl https://raw.githubusercontent.com/tupadr3/plantuml-icon-font-sprites/master/devicons/redis.puml
!includeurl https://raw.githubusercontent.com/tupadr3/plantuml-icon-font-sprites/master/devicons/postgresql.puml
!includeurl https://raw.githubusercontent.com/tupadr3/plantuml-icon-font-sprites/master/font-awesome-5/cogs.puml

package "External Sources" {
  rectangle "CEX (e.g., Binance)" as CEX_SRC
  rectangle "DEX (ETH-Uniswap, BSC-PancakeSwap)" as DEX_SRC
}

package "SkyEye MVP System (Django based)" {
  package "Data Fetcher (Celery Tasks / Management Commands)" <<$python>> {
    component "CEX Trade Fetcher" as CEX_FETCHER
    component "DEX Swap Fetcher" as DEX_FETCHER
  }

  database "Redis (Celery Broker, Temp Buffer)" as REDIS <<$redis>>

  package "Data Processor (Celery Tasks)" <<$python>> {
    component "1-min K-Line Generator" as KLINE_GEN_1M <<$cogs>>
    component "Multi-Period K-Line Aggregator" as KLINE_AGG <<$cogs>>
  }

  database "PostgreSQL (Data Storage)" as POSTGRES <<$postgresql>> {
    rectangle "klines Table" as KLINE_TABLE
    rectangle "(Optional) raw_cex_trades Tables" as RAW_TABLES
  }

  package "API Service (Django HTTP)" <<$django>> {
    component "HTTP K-Line API" as HTTP_API
  }
}

actor "Developer / Tester" as USER

CEX_SRC --> CEX_FETCHER : "Fetch Trades (REST/WS)"
DEX_SRC --> DEX_FETCHER : "Fetch Swaps (RPC Events)"

CEX_FETCHER --> REDIS : "Push Raw Trade (Optional Buffer / Task Trigger)"
DEX_FETCHER --> REDIS : "Push Raw Swap (Optional Buffer / Task Trigger)"

REDIS --> KLINE_GEN_1M : "Consume Raw Data / Triggered by Celery"
KLINE_GEN_1M --> POSTGRES : "Write 1-min K-Lines to klines Table"

POSTGRES -- KLINE_AGG : "Read 1-min K-Lines from klines Table"
KLINE_AGG --> POSTGRES : "Write Aggregated K-Lines (5m,1h,1d) to klines Table"

POSTGRES <-- HTTP_API : "Read K-Lines from klines Table"
HTTP_API --> USER : "Serve K-Line Data (JSON)"

@enduml
```

### 2.2. MVP核心组件职责
*   **`DataFetcher-CEX-MVP` (CEX交易数据采集器)**
    *   实现方式: Django Management Command 或 Celery Beat定时任务。
    *   职责: 从数据库的 `markets` 表及关联的 `exchanges`, `assets` 表中读取状态为 `is_active` 的CEX类型市场配置，通过CCXT库连接指定CEX，轮询获取最新Trades数据。
    *   输出: 将获取的Trade数据（交易对、价格、数量、时间戳）直接触发1分钟K线生成任务，或先暂存Redis再由任务消费。
*   **`DataFetcher-DEX-MVP` (DEX Swap数据采集器)**
    *   实现方式: Django Management Command 或 Celery Beat定时任务 (可按链或交易所分组)。
    *   职责: 从数据库的 `markets` 表及关联的 `exchanges`, `assets` 表中读取状态为 `is_active` 的DEX类型市场配置（包含链信息、DEX类型、交易对合约地址等元数据），连接对应公链节点，监听目标DEX交易对的`Swap`事件。
    *   输出: 解析Swap事件，提取关键信息，直接触发1分钟K线生成任务，或先暂存Redis再由任务消费。
*   **`DataProcessor-MVP - 1-min K-Line Generator` (1分钟K线生成器)**
    *   实现方式: Celery Task。
    *   职责: 消费来自Fetcher的原始交易/Swap数据，实时计算形成1分钟OHLCV K线数据。
    *   输出: 将生成的1分钟K线数据写入PostgreSQL的`klines`表。
*   **`DataProcessor-MVP - Multi-Period K-Line Aggregator` (多周期K线聚合器)**
    *   实现方式: Celery Beat定时任务 (例如每分钟执行一次，检查是否有可聚合的数据)。
    *   职责: 从`klines`表读取1分钟K线数据，聚合成5分钟、1小时、1天周期的K线数据。
    *   输出: 将聚合生成的K线数据写入（或更新）PostgreSQL的`klines`表。
*   **`DataStorage-MVP` (数据存储)**
    *   职责: 使用PostgreSQL存储K线数据。可选存储原始交易/Swap数据（用于调试或未来回补）。
*   **`APIService-MVP` (HTTP K线查询服务)**
    *   实现方式: Django View + Django REST framework (可选，或直接JsonResponse)。
    *   职责: 提供HTTP GET接口，根据请求参数（交易市场、周期等）从PostgreSQL查询K线数据并返回。

### 2.3. MVP数据流程图
1.  **CEX**: CEX API -> `CEX Trade Fetcher` -> (Optional Redis Buffer) -> `1-min K-Line Generator` (Celery) -> `klines` (1m) in PostgreSQL.
2.  **DEX**: DEX Node RPC -> `DEX Swap Fetcher` -> (Optional Redis Buffer) -> `1-min K-Line Generator` (Celery) -> `klines` (1m) in PostgreSQL.
3.  **Aggregation**: `klines` (1m) in PostgreSQL -> `Multi-Period K-Line Aggregator` (Celery Beat) -> `klines` (5m, 1h, 1d) in PostgreSQL.
4.  **API Query**: User/Client -> `HTTP K-Line API` (Django) -> `klines` in PostgreSQL -> JSON Response.

## 3. MVP数据库设计

### 3.1. 核心表结构 (PostgreSQL)

#### 3.1.1. `klines` (K线数据表)
此表用于存储所有周期的K线数据。
```sql
CREATE TABLE klines (
    id SERIAL PRIMARY KEY,
    market_identifier VARCHAR(100) NOT NULL, -- 例如: "BINANCE_BTC_USDT", "UNISWAP_ETH_USDC"
    interval VARCHAR(10) NOT NULL,          -- "1m", "5m", "1h", "1d"
    open_time TIMESTAMPTZ NOT NULL,         -- K线开盘时间 (UTC)
    open_price DECIMAL(38, 18) NOT NULL,
    high_price DECIMAL(38, 18) NOT NULL,
    low_price DECIMAL(38, 18) NOT NULL,
    close_price DECIMAL(38, 18) NOT NULL,
    volume DECIMAL(38, 18) NOT NULL,        -- 以基础资产计价的交易量
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_klines UNIQUE (market_identifier, interval, open_time)
);

CREATE INDEX idx_klines_market_interval_opentime ON klines (market_identifier, interval, open_time DESC);
```
*   `market_identifier`: 用于唯一标识一个交易市场，此标识符直接关联到 `markets.market_identifier` 字段，确保K线数据能准确映射到具体的市场配置。格式示例：`binance_btc_usdt`。
*   `DECIMAL(38, 18)`: 提供了足够的精度和范围，具体可根据实际资产调整。
*   MVP阶段，配合 `idx_klines_market_interval_opentime` 索引，单一表结构预计能满足查询性能需求。更长期的性能优化可参考3.3节的表分区策略。

#### 3.1.2. `raw_cex_trades` (CEX原始成交数据表 - 可选，用于调试)
```sql
-- 可选表，如果需要在MVP阶段持久化原始CEX数据
CREATE TABLE raw_cex_trades (
    id SERIAL PRIMARY KEY,
    exchange_name VARCHAR(50) NOT NULL,      -- e.g., "binance"
    symbol_external VARCHAR(50) NOT NULL,  -- e.g., "BTCUSDT"
    trade_id_external VARCHAR(100),
    price DECIMAL(38, 18) NOT NULL,
    quantity DECIMAL(38, 18) NOT NULL,
    timestamp_exchange TIMESTAMPTZ NOT NULL, -- 交易所时间戳 (UTC)
    fetched_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP, -- 系统获取时间
    raw_data JSONB -- 存储原始API响应，可选
);

CREATE INDEX idx_raw_cex_trades_exchange_symbol_time ON raw_cex_trades (exchange_name, symbol_external, timestamp_exchange DESC);
```

#### 3.1.3. `raw_dex_swaps` (DEX原始Swap数据表 - 可选，用于调试)
```sql
-- 可选表，如果需要在MVP阶段持久化原始DEX数据
CREATE TABLE raw_dex_swaps (
    id SERIAL PRIMARY KEY,
    chain_name VARCHAR(50) NOT NULL,        -- e.g., "ethereum", "bsc"
    dex_name VARCHAR(50) NOT NULL,          -- e.g., "uniswap_v3", "pancakeswap_v2"
    pair_address VARCHAR(255) NOT NULL,
    transaction_hash VARCHAR(255) NOT NULL,
    log_index INTEGER NOT NULL,
    block_number BIGINT NOT NULL,
    block_timestamp TIMESTAMPTZ NOT NULL,   -- 区块时间戳 (UTC)
    token0_address VARCHAR(255) NOT NULL,   -- 通常是排序靠前的token
    token1_address VARCHAR(255) NOT NULL,
    amount0_delta DECIMAL(78, 0) NOT NULL,  -- token0 数量变化 (无小数位，原始单位)
    amount1_delta DECIMAL(78, 0) NOT NULL,  -- token1 数量变化 (无小数位，原始单位)
    -- `amountX_delta`：正数表示该token流出池子，负数表示该token流入池子。
    -- 价格可以通过 amount0_delta / amount1_delta (或反之) 并结合token精度计算。
    raw_log_data JSONB -- 存储原始log事件，可选
);

ALTER TABLE raw_dex_swaps ADD CONSTRAINT uq_raw_dex_swaps UNIQUE (transaction_hash, log_index);
CREATE INDEX idx_raw_dex_swaps_chain_dex_pair_time ON raw_dex_swaps (chain_name, dex_name, pair_address, block_timestamp DESC);
```
*   `amountX_delta` 使用 `DECIMAL(78,0)` 是为了存储 token 的原始 `uint256` 数量，不带小数位。

### 3.2. 核心配置数据管理 (数据库驱动)
为确保系统的可扩展性和动态管理能力，MVP阶段将采用数据库来存储和管理核心的交易所、资产及市场（交易对）配置信息。数据采集器等组件将从这些表中读取其工作所需的配置。

#### 3.2.1. `exchanges` (交易所/交易平台表)
存储交易所或DEX平台的基础信息。
```sql
CREATE TABLE exchanges (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,              -- 例如: "Binance", "Uniswap V3 Ethereum"
    slug VARCHAR(50) NOT NULL UNIQUE,        -- 例如: "binance", "uniswapv3_eth", 用于内部标识和market_identifier构建
    type VARCHAR(10) NOT NULL,               -- 'CEX' 或 'DEX'
    base_api_url VARCHAR(255) NULL,          -- CEX API的基地址 (可选)
    chain_name VARCHAR(50) NULL,             -- DEX所在的链 (例如: "ethereum", "bsc", 可选)
    is_active BOOLEAN DEFAULT TRUE NOT NULL, -- 是否启用此交易所/平台
    meta_data JSONB NULL                     -- 存储其他特定配置 (例如DEX的Factory地址, CEX的特殊参数等)
);
```

#### 3.2.2. `assets` (资产/币种表)
存储资产（如BTC, ETH, USDT）的元数据信息。
```sql
CREATE TABLE assets (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(50) NOT NULL UNIQUE,      -- 标准化的大写资产符号 (例如: "BTC", "ETH", "USDT")
    name VARCHAR(100) NULL,                  -- 资产全名 (例如: "Bitcoin", "Ethereum", "Tether")
    decimals INTEGER NULL,                   -- 资产精度 (用于链上资产的数值换算)
    asset_type VARCHAR(20) DEFAULT 'crypto' NOT NULL, -- 例如: 'crypto', 'fiat'
    chain_name VARCHAR(50) NULL,             -- 资产所在的链 (如果适用, 例如 USDT-ERC20 vs USDT-TRC20)
    contract_address VARCHAR(255) NULL,      -- 链上资产的合约地址 (可选, 对于特定链上的token)
    is_active BOOLEAN DEFAULT TRUE NOT NULL  -- 是否启用此资产
);
```

#### 3.2.3. `markets` (市场/交易对表)
存储具体的交易对及其在特定交易所/平台上的配置信息。
```sql
CREATE TABLE markets (
    id SERIAL PRIMARY KEY,
    exchange_id INTEGER NOT NULL REFERENCES exchanges(id) ON DELETE CASCADE,
    base_asset_id INTEGER NOT NULL REFERENCES assets(id) ON DELETE RESTRICT,
    quote_asset_id INTEGER NOT NULL REFERENCES assets(id) ON DELETE RESTRICT,
    market_identifier VARCHAR(150) NOT NULL UNIQUE, -- 系统内部全局唯一的市场标识符 (建议格式: exchange.slug_BASEASSET.SYMBOL_QUOTEASSET.SYMBOL)
    external_symbol_api VARCHAR(50) NULL,        -- 该市场在交易所API中使用的原始符号 (例如 "BTCUSDT", "ETH-USDC")
    precision_price INTEGER NULL,                -- 价格精度的小数位数 (可选)
    precision_amount INTEGER NULL,               -- 数量精度的小数位数 (可选)
    is_active BOOLEAN DEFAULT TRUE NOT NULL,     -- 是否监控此市场
    meta_data JSONB NULL                         -- 存储该市场的特定配置 (例如DEX交易对的合约地址、费率层级等)
);

-- 确保同一交易所下，基础资产和计价资产的组合是唯一的
CREATE UNIQUE INDEX uq_market_exchange_base_quote ON markets (exchange_id, base_asset_id, quote_asset_id);
```

**关于 `market_identifier`**: 
此字段是系统中K线等市场数据的核心关联键。建议在创建`markets`表记录时，由系统根据 `exchanges.slug`, `base_asset.symbol`, `quote_asset.symbol` 等信息组合生成，并确保其全局唯一性。
例如：`binance_btc_usdt`, `uniswapv3_eth_weth_usdc`。

### 3.3. 未来可扩展性考虑
MVP阶段优先保证核心功能的快速实现。对于系统未来的发展和数据量的增长，数据库层面可以考虑以下优化策略：

*   **读写分离 (Read Replicas)**: 为提升高并发读取性能和系统可用性，未来可以为PostgreSQL配置主从复制。Django的`settings.DATABASES`支持多数据库配置，可以结合数据库路由（Database Routers）实现读操作导向从库，写操作在主库。
*   **表分区 (Table Partitioning)**: 针对`klines`表可能累积大量历史数据的情况，未来可以采用PostgreSQL的表分区技术。例如，可以考虑按`open_time`字段进行范围分区（如按月或按季度分区），或者根据`market_identifier`的特征进行列表或哈希分区。这将有助于提高大数据量下的查询效率、索引管理和数据维护（如历史数据归档或删除）的性能。

MVP阶段暂不实现这些高级配置，但架构设计上应兼容这些优化方向。

## 4. MVP中间件

### 4.1. PostgreSQL
*   **用途**: 核心数据存储，用于持久化`klines`表，以及可选的`raw_cex_trades`和`raw_dex_swaps`表。
*   **版本**: 12+ 推荐。
*   **配置**: MVP阶段使用本地Docker容器运行即可。

### 4.2. Redis
*   **用途**:
    1.  **Celery Broker**: 作为Celery任务队列的消息中间件，负责任务的分发。
    2.  **Celery Backend**: 存储Celery任务的执行结果和状态 (可选，但推荐用于调试)。
    3.  **可选 - 临时数据缓冲**: DataFetcher采集到的原始数据可以先快速写入Redis List或Stream，然后由Celery任务异步消费处理。这可以轻微解耦采集和处理，但会增加少量复杂度。MVP初期也可以是Fetcher直接触发Celery任务。
*   **版本**: 5+ 推荐。
*   **配置**: MVP阶段使用本地Docker容器运行即可。

### 4.3. Celery
*   **用途**:
    1.  **异步K线生成**: 将从CEX/DEX获取的原始数据通过Celery任务异步处理，生成1分钟K线。这避免了数据采集过程的阻塞。
    2.  **异步K线聚合**: 通过Celery Beat定时调度任务，定期从数据库读取1分钟K线，聚合成5分钟、1小时、1天周期的K线。
*   **配置**: Django项目集成Celery。需要定义Celery App，配置Broker (Redis)，定义Tasks。
*   **Worker**: 运行一个或多个Celery worker进程来执行任务。
*   **Beat**: 运行Celery Beat服务来调度周期性聚合任务。

## 5. MVP DEX接入方案 (ETH Uniswap & BSC PancakeSwap)

### 5.1. 通用策略
*   **库**: `Web3.py` (Python与以太坊及EVM兼容链交互的主要库)。
*   **连接**: 通过HTTP/WebSocket Provider连接到对应公链的RPC节点。
    *   **RPC节点**: MVP阶段可以使用公共RPC节点 (如 Infura, Alchemy, Ankr, BSC官方公共节点)。**需注意**: 公共节点通常有速率限制，可能影响高频轮询或大量历史事件获取。长期或高频使用建议考虑付费节点或自建节点。
    *   示例公共节点:
        *   Ethereum: `https://mainnet.infura.io/v3/YOUR_INFURA_PROJECT_ID`
        *   BSC: `https://bsc-dataseed.binance.org/`
*   **事件监听**: 核心是监听目标DEX交易对（流动性池）合约的`Swap`事件。因为`Swap`事件直接反映了交易的发生和价格的变动。
*   **价格计算**: 从`Swap`事件的参数中，可以获取两种token的流入/流出量。价格 P_token0/token1 = amount1_delta / amount0_delta (需注意正负号和token顺序，并结合token的decimals进行转换)。
*   **数据提取**: 从`Swap`事件和关联的区块信息中提取：
    *   交易对合约地址 (Pair Address)
    *   参与交易的Token地址 (token0, token1)
    *   Token的流入/流出量 (amount0In/Out, amount1In/Out 或 amount0/1Delta)
    *   交易发起方 (sender/origin)
    *   交易接收方 (recipient/to - 通常是交易对合约本身或router)
    *   交易哈希 (Transaction Hash)
    *   日志索引 (Log Index)
    *   区块号 (Block Number)
    *   区块时间戳 (Block Timestamp)
*   **起始区块处理**: 首次启动或中断后重启时，需要记录上次处理到的区块号，从该区块号继续监听，避免数据丢失或重复处理。MVP阶段此机制可简化。

### 5.2. 以太坊 - Uniswap (V2/V3)
*   **RPC节点**: 参考5.1。
*   **核心交易对示例**: (WETH/USDC, WETH/DAI, WBTC/WETH等)
    *   Uniswap V2: Pair合约地址直接代表交易对。 e.g., WETH/USDC Pair: `0xB4e16d0168e52d35CaCD2c6185b44281Ec28C9Dc`
    *   Uniswap V3: Pool合约地址代表交易对，通常还带有费率层级。 e.g., WETH/USDC 0.05% Pool: `0x88e6A0c2dDD26FEEb64F039a2c41296FcB3f5640`
*   **`Swap` 事件**: 
    *   **Uniswap V2 Pair `Swap` Event ABI**: `event Swap(address indexed sender, uint amount0In, uint amount1In, uint amount0Out, uint amount1Out, address indexed to);`
    *   **Uniswap V3 Pool `Swap` Event ABI**: `event Swap(address indexed sender, address indexed recipient, int256 amount0, int256 amount1, uint160 sqrtPriceX96, uint128 liquidity, int24 tick);`
        *   V3的`amount0`和`amount1`是delta值，正数表示该token流出池子，负数表示流入池子。
*   **数据解析与价格计算**: 
    *   V2: 价格 = amount1Out / amount0In 或 amount0Out / amount1In (取决于哪个In/Out非零)。需结合token decimals。
    *   V3: 价格 = abs(amount1 / amount0)。`sqrtPriceX96`也可以用来计算价格，但直接用amount delta更直接反映单笔交易价格。需结合token decimals。
*   **Fetcher实现**: 使用`web3.eth.filter`配合`'logs'`参数，指定`address` (Pair/Pool地址) 和`topics` (Swap事件的keccak256哈希)。轮询获取新日志。

### 5.3. BNB Chain - PancakeSwap (V2/V3)
*   **RPC节点**: 参考5.1。
*   **核心交易对示例**: (WBNB/BUSD, WBNB/CAKE等)
    *   PancakeSwap V2 Pair地址结构类似Uniswap V2。e.g., WBNB/BUSD: `0x58F876857a02D6762E0101bb5C46A8c1ED44Dc16`
    *   PancakeSwap V3 Pool地址结构类似Uniswap V3。e.g., WBNB/USDT 0.05% Pool: `0x36696167b9671475ce400d989f4898409951feb4`
*   **`Swap` 事件**: PancakeSwap V2和V3的`Swap`事件签名和结构与对应版本的Uniswap非常相似。
    *   **PancakeSwap V2 Pair `Swap` Event ABI**: `event Swap(address indexed sender, uint amount0In, uint amount1In, uint amount0Out, uint amount1Out, address indexed to);`
    *   **PancakeSwap V3 Pool `Swap` Event ABI**: `event Swap(address indexed sender, address indexed recipient, int256 amount0, int256 amount1, uint160 sqrtPriceX96, uint128 liquidity, int24 tick);`
*   **数据解析与价格计算**: 同Uniswap V2/V3相应版本。
*   **Fetcher实现**: 同Uniswap V2/V3相应版本，但连接BSC RPC节点。

### 5.4. 简化的错误处理和重连机制 (MVP阶段)
*   **RPC请求错误**: 基本的try-except捕获网络错误、RPC返回错误，记录日志并跳过当前轮询周期。
*   **数据解析错误**: 记录日志，标记问题数据，避免影响主流程。
*   **重连**: Fetcher主循环中可加入简单的延时重试逻辑。不实现复杂的状态管理和指数退避。

## 6. MVP API设计 (HTTP)

### 6.1. 端点
`GET /api/mvp/klines`

### 6.2. 请求参数
*   `market_identifier`: `string`, **必填**. 市场唯一标识符 (e.g., "BINANCE_BTC_USDT", "ETHEREUM_UNISWAPV3_WETH_USDC_0X88E6").
*   `interval`: `string`, **必填**. K线周期 ("1m", "5m", "1h", "1d").
*   `startTime`: `integer`, 可选. Unix时间戳 (秒), K线开盘时间的开始范围 (包含).
*   `endTime`: `integer`, 可选. Unix时间戳 (秒), K线开盘时间的结束范围 (包含).
*   `limit`: `integer`, 可选. 返回K线条数上限 (e.g., 默认500, 最大2000).

### 6.3. 响应格式 (JSON)
成功响应 (`200 OK`):
```json
[
  {
    "t": 1672531200, // open_time (Unix timestamp, seconds, UTC)
    "o": "20000.00", // open_price
    "h": "20010.50", // high_price
    "l": "19990.75", // low_price
    "c": "20005.25", // close_price
    "v": "10.534"    // volume
  },
  {
    "t": 1672531260,
    "o": "20005.25",
    "h": "20015.00",
    "l": "20000.00",
    "c": "20012.80",
    "v": "12.700"
  }
  // ... more kline data,按时间升序排列
]
```

### 6.4. 基础错误响应
*   `400 Bad Request`: 参数错误 (如缺少必要参数、参数格式不对)。
    ```json
    {
      "error": "Missing required parameter: market_identifier"
    }
    ```
*   `404 Not Found`: 未找到指定市场或该市场无此周期数据。
    ```json
    {
      "error": "No kline data found for market_identifier X and interval Y"
    }
    ```
*   `500 Internal ServerError`: 服务器内部错误。
    ```json
    {
      "error": "An internal server error occurred"
    }
    ```

## 7. MVP开发与部署要点

### 7.1. 开发顺序建议
1.  **环境搭建**: Docker, PostgreSQL, Redis, Django项目初始化, Celery集成。
2.  **CEX模块**: 
    *   `DataFetcher-CEX-MVP`: 采集Binance trades。
    *   `1-min K-Line Generator`: 处理CEX trades生成1分钟K线并入库。
    *   `Multi-Period K-Line Aggregator`: 从CEX的1分钟K线聚合多周期K线。
    *   `APIService-MVP`: 提供CEX K线查询API。
    *   此部分可优先完成，因CCXT库相对成熟，可较快见到成果。
3.  **DEX模块 (可并行，或在CEX稳定后)**:
    *   `DataFetcher-DEX-MVP` for ETH-Uniswap: 采集Swap事件。
    *   调整`1-min K-Line Generator`支持Uniswap Swap数据。
    *   整合进`Multi-Period K-Line Aggregator`。
    *   API扩展支持Uniswap K线查询。
    *   再复制并调整逻辑以支持BSC-PancakeSwap。
4.  **集成与测试**: 确保所有组件协同工作。

### 7.2. 核心配置表与`market_identifier`
数据库中的 `markets.market_identifier` 字段是关键。它作为系统全局唯一的市场引用，连接K线数据到具体的市场配置。应在创建 `markets` 记录时生成此标识符（例如基于 `exchange.slug`, `base_asset.symbol`, `quote_asset.symbol`），并确保其能够清晰地映射回交易所、基础资产和计价资产。`klines` 表中的 `market_identifier` 将直接使用此值。

### 7.3. DEX事件处理的幂等性
虽然MVP简化错误处理，但DEX事件监听最好能记录已处理的`transaction_hash`和`log_index`组合，或至少是`block_number`，以避免因重启或RPC问题导致的重复处理。MVP阶段如果过于复杂，可以暂时牺牲，但需记录为技术债。

### 7.4. 部署
*   项目将提供`Dockerfile`以便于构建容器化镜像。
*   本地开发和测试可使用Docker Compose等工具快速启动依赖服务 (PostgreSQL, Redis) 和应用。
*   最终的生产环境部署将由运维团队通过K3s集群完成，具体的K3s部署配置和管理由运维团队负责。
*   开发团队需确保应用本身是"云原生友好"的，例如：
    *   配置可以通过环境变量注入。
    *   应用是无状态的或状态通过外部服务（如Redis, PostgreSQL）管理。
    *   日志输出到标准输出/标准错误流。

### 7.5. MVP测试关注点
*   数据流打通**: CEX/DEX原始数据能否正确流向K线生成器，数据源配置能否从数据库正确加载。
*   1分钟K线准确性**: 随机抽查几个1分钟K线的OHLCV是否与原始数据大致对应。
*   K线聚合逻辑**: 5m, 1h, 1d K线是否由正确的1m K线聚合而成。
*   API可用性**: API能否根据参数正确返回K线数据，格式是否符合预期。
*   服务稳定性**: 基本的长时间运行（几小时）是否会出现明显错误或崩溃。
*   资源消耗**: 初步观察CPU、内存使用情况，有无明显泄漏（不做严格profile）。

