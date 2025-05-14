# 主流DEX数据获取方式调研总结

本文档总结了对 SkyEye 项目一期（1.3.4节）计划接入的主流DEXs，其官方API、SDK或社区常用数据获取方式的调研结果，重点关注获取**当前价格**和**24小时交易量**的可行性。

## 1. Ethereum (以太坊) - Uniswap V2 & V3

*   **DEX名称**: Uniswap (V2 和 V3)
*   **链**: Ethereum
*   **主要数据获取方式**:
    *   **The Graph (推荐用于历史数据和聚合数据)**: Uniswap V2 和 V3 的交易对数据（价格、交易量、流动性等）被广泛索引在 The Graph 上。可以通过查询对应的 Subgraph (例如 Uniswap V2 Subgraph, Uniswap V3 Subgraph) 来获取数据。这是获取历史K线、24小时交易量等聚合数据的常用方式。
    *   **Uniswap SDKs (`@uniswap/sdk-core`, `@uniswap/v3-sdk`)**: 这些SDK主要用于与智能合约直接交互，例如计算当前兑换价格、执行交易、获取池子状态等。对于实时价格，SDK非常有用。但对于历史聚合数据（如24小时交易量），SDK本身不直接提供，通常需要结合链上事件或索引服务。
    *   **直接与智能合约交互 (通过RPC节点)**: 可以直接调用 Uniswap 交易对合约的方法（如 V2的 `getReserves`，V3的 `slot0` 和 `observe`）来计算当前价格。获取24小时交易量则需要监听和聚合 `Swap` 事件，非常复杂。
*   **关键数据点**:
    *   **当前价格**:
        *   通过 Uniswap SDK 计算。
        *   通过查询 The Graph Subgraph 获取交易对的最新价格。
        *   通过直接调用合约方法计算。
    *   **24小时交易量**:
        *   主要通过查询 The Graph Subgraph 获取（例如 `pairDayData` 或 `poolDayData` 实体）。
*   **费率限制与费用**:
    *   **The Graph**: 公共服务有免费查询额度和速率限制。超出限制或需要更高可靠性则需要使用付费服务。
    *   **RPC节点**: 如果直接与合约交互，会受限于所使用的以太坊RPC节点的请求频率和费用策略（如 Infura, Alchemy 有免费套餐和付费套餐）。
*   **官方文档/链接**:
    *   Uniswap V2 Subgraph: [https://thegraph.com/hosted-service/subgraph/uniswap/uniswap-v2](https://thegraph.com/hosted-service/subgraph/uniswap/uniswap-v2)
    *   Uniswap V3 Subgraph: [https://thegraph.com/hosted-service/subgraph/uniswap/uniswap-v3](https://thegraph.com/hosted-service/subgraph/uniswap/uniswap-v3)
    *   Uniswap SDKs: [https://docs.uniswap.org/sdk/introduction](https://docs.uniswap.org/sdk/introduction)

## 2. BNB Chain (BSC) - PancakeSwap V2 & V3

*   **DEX名称**: PancakeSwap (V2 和 V3)
*   **链**: BNB Smart Chain (BSC)
*   **主要数据获取方式**:
    *   **The Graph (或类似索引服务)**: 与Uniswap类似，PancakeSwap的交易对数据（价格、交易量等）也通常通过其官方或社区维护的Subgraph进行索引和查询。
    *   **PancakeSwap SDK**: PancakeSwap也提供了SDK (例如 `@pancakeswap/sdk`, `@pancakeswap/v3-sdk`)，用于链上交互和价格计算。
    *   **直接与智能合约交互 (通过BSC RPC节点)**: 类似Uniswap，可以调用交易对合约方法获取数据。
*   **关键数据点**:
    *   **当前价格**:
        *   通过 PancakeSwap SDK 计算。
        *   通过查询其 Subgraph 获取。
    *   **24小时交易量**:
        *   主要通过查询其 Subgraph 获取。
*   **费率限制与费用**:
    *   与以太坊上的情况类似，取决于所使用的索引服务（如 The Graph 的BSC支持）或BSC RPC节点的策略。
*   **官方文档/链接**:
    *   PancakeSwap Documentation: [https://docs.pancakeswap.finance/](https://docs.pancakeswap.finance/)
    *   PancakeSwap Subgraphs: (通常可以在PancakeSwap文档或社区中找到链接，例如他们之前有托管在 The Graph 或 BitQuery 等平台上的 subgraph)

## 3. Tron (波场) - OpenOcean

*   **DEX名称**: OpenOcean (DEX聚合器)
*   **链**: Tron (以及其他多条链)
*   **主要数据获取方式**:
    *   **OpenOcean API**: OpenOcean 提供了官方API，用于获取报价、执行交易等。
*   **关键数据点**:
    *   **当前价格**: 可以通过其 "Quote API" 获取特定交易对的实时报价。
    *   **24小时交易量**: 需要查阅其API文档，看是否直接提供交易对的24小时汇总交易量，或者是否可以从历史交易数据中聚合。作为聚合器，它可能提供跨多个DEX的交易量数据。
*   **费率限制与费用**:
    *   其官方API通常会有速率限制。免费使用额度需要查阅其开发者文档。
*   **官方文档/链接**:
    *   OpenOcean API Documentation: [https://docs.openocean.finance/](https://docs.openocean.finance/) (之前调研时找到的链接)

## 4. Solana (索拉纳) - Jupiter Aggregator

*   **DEX名称**: Jupiter (DEX聚合器)
*   **链**: Solana
*   **主要数据获取方式**:
    *   **Jupiter API**: Jupiter 提供了非常全面和文档化的API。
*   **关键数据点**:
    *   **当前价格**:
        *   `Price API`: 可以直接获取代币的当前价格。
        *   `Quote API`: 获取执行交易的最佳报价，其中也包含价格信息。
    *   **24小时交易量**: 需要查阅Jupiter API文档，看是否提供交易对或代币的24小时交易量数据。
*   **费率限制与费用**:
    *   公共API会有速率限制，具体细节见其开发者文档。
*   **官方文档/链接**:
    *   Jupiter API Documentation: [https://docs.jup.ag/jupiter-api/](https://docs.jup.ag/jupiter-api/) (或类似的官方API文档入口)

## 5. TON (The Open Network) - Ston.fi

*   **DEX名称**: Ston.fi
*   **链**: TON (The Open Network)
*   **主要数据获取方式**:
    *   **Ston.fi Public HTTP API**: Ston.fi 提供了公开的HTTP API。
    *   **Ston.fi SDK (`@ston-fi/sdk`)**: JavaScript/TypeScript SDK，可用于与API或合约交互。
*   **关键数据点**:
    *   **当前价格**:
        *   API端点如 `/v1/jettons/:jetton_address/rates` 或 `/v1/assets` (可能包含价格)。
        *   `/export/pair/:address/chart_data` 或 `/export/jetton/:address/chart_data` 的最新点也反映价格。
    *   **24小时交易量**:
        *   `/export/pair/:address/chart_data` (如果提供OHLCV中的V是24小时交易量，或者可以聚合)。
        *   `/v1/pools/:pool_address` 或 `/v1/pools` 的池子统计数据中可能包含日交易量或可用于计算的数据。
*   **费率限制与费用**:
    *   作为公共API，预计会有速率限制。
*   **官方文档/链接**:
    *   (调研时发现其SDK文档和API端点主要通过其GitHub或社区资源找到，例如: [https://github.com/ston-fi](https://github.com/ston-fi))
    *   一个可能的API文档或Swagger UI入口: `https://api.ston.fi/docs` (需要验证)

## 6. Sui - Cetus Protocol

*   **DEX名称**: Cetus Protocol
*   **链**: Sui (也支持Aptos)
*   **主要数据获取方式**:
    *   **Cetus SDK (`@cetusprotocol/cetus-sui-clmm-sdk`)**: 用于与Sui上的Cetus协议交互。
    *   **Cetus API / Community Chart API**: 文档中曾提及这些API的存在，可能提供HTTP端点。
    *   **The Graph**: Cetus提到使用The Graph进行数据索引。
*   **关键数据点**:
    *   **当前价格**:
        *   通过SDK计算。
        *   通过其API或Subgraph查询。
    *   **24小时交易量**:
        *   通过其API或Subgraph查询。
*   **费率限制与费用**:
    *   取决于具体使用的API（Cetus官方API、社区API或The Graph）。
*   **官方文档/链接**:
    *   Cetus Protocol Documentation: [https://docs.cetus.zone/](https://docs.cetus.zone/)

## 7. Aptos - PancakeSwap

*   **DEX名称**: PancakeSwap
*   **链**: Aptos
*   **主要数据获取方式**:
    *   与BSC上的PancakeSwap类似，可能依赖于:
        *   **PancakeSwap提供的针对Aptos的Subgraph或API** (如果他们为Aptos链单独维护了索引服务)。
        *   **PancakeSwap Aptos SDK** (如果提供)。
        *   **通用的Aptos链上索引服务** (如果有索引PancakeSwap数据的话)。
*   **关键数据点**:
    *   **当前价格**:
        *   通过SDK计算。
        *   通过Aptos上的PancakeSwap Subgraph/API查询。
    *   **24小时交易量**:
        *   通过Aptos上的PancakeSwap Subgraph/API查询。
*   **费率限制与费用**:
    *   取决于所依赖的索引服务或Aptos RPC节点的策略。
*   **官方文档/链接**:
    *   PancakeSwap的官方文档中关于Aptos的部分。

**通用备注**:
*   对于许多DEX，特别是基于AMM模型的，**当前价格**通常可以通过SDK与链上智能合约交互（查询储备量、tick信息等）来实时计算。
*   **24小时交易量**这类历史聚合数据，直接从链上实时计算非常低效且成本高昂。因此，DEX通常依赖于链下索引服务（如The Graph、BitQuery或自建索引器）来处理和提供这类数据。
*   API的速率限制和费用是选择数据源时的重要考量因素。免费套餐通常有严格限制，大规模使用可能需要付费。
*   SDK虽然灵活，但直接的链上交互会消耗RPC调用次数，并且可能不适合获取大规模历史数据。
*   在选择具体方案时，应优先查找官方提供的、文档完善的API或推荐的Subgraph。

## 8. OKX DEX API (聚合器)

*   **服务名称**: OKX DEX API
*   **类型**: DEX 聚合器 API
*   **官方文档系列入口**: [https://web3.okx.com/zh-hans/build/dev-docs/dex-api/dex-market-price-reference](https://web3.okx.com/zh-hans/build/dev-docs/dex-api/dex-market-price-reference)

根据官方文档，OKX DEX的HTTP行情API（行情价格API部分）主要由以下五个核心接口构成，所有接口均以**单个代币合约地址 (`tokenContractAddress`)** 为查询中心，而非传统的交易对标识：

1.  **`GET /api/v5/dex/market/chains` (获取支持的链)**
    *   **文档**: (通常在此系列文档的"获取支持的链"部分，例如 [https://web3.okx.com/zh-hans/build/dev-docs/dex-api/dex-market-price-chains](https://web3.okx.com/zh-hans/build/dev-docs/dex-api/dex-market-price-chains))
    *   **功能**: 返回OKX DEX API支持的区块链列表及其对应的 `chainIndex` (链的数字ID)。

2.  **`POST /api/v5/dex/market/price` (获取价格)**
    *   **文档**: [https://web3.okx.com/zh-hans/build/dev-docs/dex-api/dex-market-price](https://web3.okx.com/zh-hans/build/dev-docs/dex-api/dex-market-price)
    *   **功能**: 批量获取一个或多个指定链上代币合约的最新价格。
    *   **请求**: POST方法，请求体为JSON数组，每个元素是包含 `chainIndex` 和 `tokenContractAddress` 的对象。
    *   **响应**: 返回每个代币的价格和时间戳。**此接口仅提供价格，不提供买卖盘、交易量等其他Ticker信息。**

3.  **`GET /api/v5/dex/market/trades` (获取交易)**
    *   **文档**: [https://web3.okx.com/zh-hans/build/dev-docs/dex-api/dex-market-trades](https://web3.okx.com/zh-hans/build/dev-docs/dex-api/dex-market-trades)
    *   **功能**: 获取指定链上单个代币合约的最新成交记录。
    *   **参数**: `chainIndex`, `tokenContractAddress`, `limit`等。
    *   **响应**: 包含成交ID、价格、数量（分解到具体代币）、美元价值、时间等。返回的是单个代币的交易历史，而非特定交易对的。 

4.  **`GET /api/v5/dex/market/candles` (获取K线)**
    *   **文档**: [https://web3.okx.com/zh-hans/build/dev-docs/dex-api/dex-market-candlesticks](https://web3.okx.com/zh-hans/build/dev-docs/dex-api/dex-market-candlesticks)
    *   **功能**: 获取指定链上单个代币合约的K线数据（OHLCV）。
    *   **参数**: `chainIndex`, `tokenContractAddress`, `bar` (周期, e.g., `1m`, `1Dutc`), `limit` (最大299)。
    *   **响应**: K线数据数组，每条K线包含 `ts` (时间戳), `o` (开), `h` (高), `l` (低), `c` (收), `vol` (以目标币种为单位的交易量), `volUsd` (以美元为单位的交易量), `confirm` (K线是否完结)。

5.  **`GET /api/v5/dex/market/historical-candles` (获取历史K线)**
    *   **文档**: [https://web3.okx.com/zh-hans/build/dev-docs/dex-api/dex-market-candlesticks-history](https://web3.okx.com/zh-hans/build/dev-docs/dex-api/dex-market-candlesticks-history)
    *   **功能**: 与获取K线类似，但用于获取更早周期的历史K线数据，支持分页。

*   **数据模型核心**: 所有这些行情接口都是以**单个代币合约地址 (`tokenContractAddress`)** 为查询依据。这意味着如果需要获取交易对A/B的数据：
    *   **交易对价格A/B**: 可能需要分别获取A代币相对于USD的价格和B代币相对于USD的价格，然后进行计算。
    *   **交易对交易量A/B**: API不直接提供。K线接口返回的是单个代币的总交易量（以自身或USD计价）。

*   **SkyEye核心数据获取策略**: 
    *   **获取当前价格 (单个代币)**:
        *   主要使用 `POST /api/v5/dex/market/price`，通过其批量能力一次获取多个代币（基于`chainIndex` 和 `tokenContractAddress`）的最新价格。
    *   **获取24小时交易量 (单个代币)**: 
        *   主要途径是通过 `GET /api/v5/dex/market/candles` (或历史K线接口) 请求参数 `bar=1Dutc`（或其他相应周期的UTC日K线），从返回的K线数据中使用 `vol` (以目标币种计) 或 `volUsd` (以美元计) 作为该单个代币的24小时交易量。
        *   这与特定交易对的24小时交易量概念不同，并且在1-5 RPS的限制下，为大量代币（如果每个交易对的两个币都需要查）获取日K线的调用成本较高。
    *   **获取历史K线/蜡烛图 (单个代币)**: 
        *   使用 `GET /api/v5/dex/market/candles` 或 `GET /api/v5/dex/market/historical-candles`。

*   **调用频率/费率**:
    *   **最新信息来源**: [https://web3.okx.com/zh-hans/build/dev-docs/dex-api/dex-api-fee](https://web3.okx.com/zh-hans/build/dev-docs/dex-api/dex-api-fee)
    *   根据最新文档，**非企业合作伙伴的速率限制为1到5个请求/每秒（RPS）。默认情况下，所有新注册的 API 访问限制为1 RPS。如果需要更高的速率，可以在开发者平台上提交请求将其提高到5 RPS。**
    *   此速率限制适用于整体API调用。
    *   这一相对严格的限制（尤其是默认1 RPS）使得 `POST /api/v5/dex/market/price` 的批量价格获取能力变得重要。对于K线等接口，如果不能有效批量（目前看K线接口是单个代币查询），则调用频率会是较大制约。

*   **身份验证**:
    *   根据API文档示例，调用这些行情接口时，请求头中可能需要包含 `OK-ACCESS-KEY`, `OK-ACCESS-SIGN`, `OK-ACCESS-PASSPHRASE`, `OK-ACCESS-TIMESTAMP` 等认证信息。具体要求需参照OKX最新的开发者文档关于API访问和认证的部分。

*   **初步评估与适用性**:
    *   OKX DEX API 在**批量获取多个代币的当前价格**方面有明确的接口支持，其广泛的链覆盖也是一个优势。
    *   能够提供**单个代币**的K线数据，包括以该代币或USD计价的交易量，这对于获取单个代币的24小时交易量（通过日K线）提供了一条途径。
    *   然而，API的设计核心是**单个代币合约**，**不直接提供以交易对为中心的完整Ticker信息**（如交易对的买卖盘、交易对的24小时交易量）。
    *   这意味着，如果SkyEye的核心需求是获取**交易对A/B的精确24小时交易量**或实时买卖盘，OKX DEX API无法直接满足，需要复杂的二次计算（例如从两个代币的交易数据推算）或依赖其他数据源。

*   **待确认的关键点 (基于当前理解)**:
    *   **`POST /api/v5/dex/market/price` 的实际批量上限**: 需要测试单次请求能有效处理多少个代币的价格查询，以评估在1-5 RPS限制下的整体效率。
    *   **交易对数据处理逻辑**: 如何基于这些以单个代币为中心的API来构建我们系统内部以交易对为核心的数据模型，特别是交易对的价格和交易对的24小时交易量。
    *   **K线接口 (`/candles`)的 `tokenContractAddress`**: 此地址是指交易对中的哪个币种？通常是基础币种，但API返回的 `vol` 是"以目标币种为单位"，`volUsd` 是"以美元为单位"。如果我们需要交易对A/B的交易量，这个接口返回的是A的交易量还是B的交易量，或者某个池子的交易量？文档描述为"币种合约地址"，暗示是单个代币。这需要明确。

*   **总结**: 
    *   OKX DEX API 提供了一套以**单个代币为中心**的行情数据接口，可以用来批量获取多链代币的**当前价格**，以及获取单个代币的**K线数据（包含该代币的交易量）**和成交历史。
    *   其主要价值在于价格的批量获取和多链覆盖。
    *   对于SkyEye系统所需的、以**交易对**为核心的完整Ticker信息（尤其是交易对的24小时总交易量和实时买卖盘），OKX DEX API的直接支持能力有限。获取这些数据将需要依赖更复杂的逻辑、二次计算，或者将OKX API作为数据源之一，并主要结合各DEX原生API/SDK或更专业的第三方数据服务进行设计。

### 8.1 OKX DEX API 支持的链及其代币数量 (截至脚本测试时)

通过 `okx_test.py` 脚本（具体调用 `/api/v5/dex/market/supported/chain` 获取链列表，然后对每条链调用 `/api/v5/dex/aggregator/all-tokens` 获取代币列表）测试，得到OKX DEX API支持的链及其上可查询到的代币数量汇总如下。请注意，代币数量为0可能表示该链上暂无OKX DEX聚合器支持的代币，或者查询时API未返回数据。

| 链名称 (Chain Name) | 链ID (Chain ID) | 支持的代币数量 (Token Count) |
|---------------------|---------------|--------------------------|
| Ethereum            | 1             | 1334                     |
| BNB Chain           | 56            | 699                      |
| Avalanche C         | 43114         | 191                      |
| Solana              | 501           | 191                      |
| Polygon             | 137           | 150                      |
| Fantom              | 250           | 148                      |
| Arbitrum            | 42161         | 133                      |
| Optimism            | 10            | 71                       |
| Base                | 8453          | 64                       |
| OKTC                | 66            | 61                       |
| Cronos              | 25            | 51                       |
| SUI                 | 784           | 26                       |
| TON                 | 607           | 26                       |
| TRON                | 195           | 24                       |
| Polygon zkEvm       | 1101          | 24                       |
| Blast               | 81457         | 23                       |
| Linea               | 59144         | 22                       |
| zkSync Era          | 324           | 20                       |
| Merlin              | 4200          | 19                       |
| Scroll              | 534352        | 18                       |
| X Layer             | 196           | 14                       |
| Conflux eSpace      | 1030          | 11                       |
| Mantle              | 5000          | 11                       |
| Manta Pacific       | 169           | 9                        |
| Sonic Mainnet       | 146           | 6                        |
| Zeta                | 7000          | 6                        |
| Bitlayer            | 200901        | 0                        |
| BOB Mainnet         | 60808         | 0                        |
| Mode                | 34443         | 0                        |
| opBNB               | 204           | 0                        |
| EthereumPoW         | 10001         | 0                        |
| IoTeX Network       | 4689          | 0                        |
| Taiko Mainnet       | 167000        | 0                        |
| B² Network          | 223           | 0                        |
| Berachain           | 80094         | 0                        |
| Gnosis              | 100           | 0                        |
| Starknet            | 9004          | 0                        |
| PulseChain          | 369           | 0                        |
| Sei EVM             | 1329          | 0                        |
| ApeChain            | 33139         | 0                        |
| Chiliz Chain        | 88888         | 0                        |
| Immutable zkEVM     | 13371         | 0                        |
| Aptos               | 637           | 0                        | 