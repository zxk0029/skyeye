# SkyEye 架构澄清问题清单

为了更好地理解现有 SkyEye 系统并绘制准确的架构图，请您补充以下信息。这将直接影响后续架构图的准确性和实用性。

## 关于数据存储与处理

1.  **Redis 使用场景**：
    *   `skyeye_analysis.md` 提到 Redis DB 2 用于存储历史订单簿 (`new:redis:crawler:...:orderbooks`) 和历史Ticker (`new:redis:crawler:...:tickers`)，以及内存缓存（Django Default Cache，`global_redis`）用于存储最新订单簿和Ticker。
        *   **问题1.1**: "内存缓存 (Django Default Cache, 通过`global_redis()`访问)" 在默认配置下实际是内存缓存还是也指向了某个Redis实例（如DB 0）？`global_redis` 回退到 `local_redis` (DB 2) 的具体触发条件是什么？
        * A：数据是存到redis中，然后处理后，放到postgreSQL里
        *   **问题1.2**: `new:redis:crawler:...:tickers` 和 `crawler:...:tickers` (最新Ticker) 的数据，分析报告中多次提到"目前未被使用"或"API不使用Redis缓存数据"。这些Ticker数据是否有其他潜在用途或计划中的用途？如果完全未使用，采集它们的目的是什么？
        * A：暂时未使用上，可能后续有其他计划。目前只使用了broker_crawler，从多个交易所获取行情数据
        *   **问题1.3**: 除了缓存行情数据，Redis（无论是DB 2还是其他DB）是否还用于其他功能，例如：分布式锁、任务队列（如Celery backend）、会话存储、Django的其他缓存（非默认缓存）等？
        * A：只缓存行情数据

2.  **PostgreSQL 使用**：
    *   `skyeye_analysis.md` 提到 `backoffice_mgobpersistence` 表存储处理后的价格，作为 `/api/v1/market_price` 的数据源。
        *   **问题2.1**: 当前 PostgreSQL 是单实例部署，还是已经配置了主从复制结构？目标架构图中有"主 postgres"和"从 postgres"。
        * A：应该是单实例部署，没有配置主从复制结构
        *   **问题2.2**: `mg_ob_persistence` 命令在处理数据时，聚合逻辑具体是怎样的？分析提到"似乎未使用它来合并多个交易所数据后再计算，而是对每个交易所单独计算并存储"，这是否准确？如果是，那么"聚合价格"具体指什么？
        * A： `mg_ob_persistence` 命令应该是存的单个交易所数据，没有进行聚合。`merged_ob_persistence`进行了多交易所的数据聚合，聚合策略是处理交叉盘/锁定盘。exchange/controllers.py的save_merged_ob函数有处理逻辑。不过这个聚合数据，HailStone 业务中台暂时没有使用

## 关于核心命令与服务

3.  **Management Commands (`broker_crawler`, `mg_ob_persistence`)**：
    *   **问题3.1**: 这两个命令是如何部署和运行的？是作为常驻进程（例如使用 `supervisor` 或类似工具管理），还是通过 `cron` 或其他调度系统定期执行？它们的执行频率和资源消耗大致如何？
    * A：这个不太清楚，是通过K3S部署的，我没看到相关配置
    *   **问题3.2**: `broker_crawler` 采集数据时，除了CCXT，是否有其他数据源或特殊的数据获取逻辑（比如特定交易所的私有API）？
    * A：当前只采集了CCXT

4.  **gRPC 服务 (`sevices/grpc_server.py`)**：
    *   **问题4.1**: `skyeye_analysis.md` 中提到 `sevices/grpc_server.py` 可能包含gRPC服务。这个gRPC服务目前的功能是什么？是否已经有客户端在实际调用它？它提供的数据是来源于PostgreSQL、Redis，还是两者都有？
    * A："HailStone 业务中台"会通过grpc服务来获取行情价格，数据是来源于PostgreSQL。PostgreSQL的数据来源于redis
    *   **问题4.2**: 这个gRPC服务与目标架构图中由 `ReplicaPostgres` 提供数据给 `GrpcApiService` 的模型是否一致，或者有何差异？
    * A: 当前系统没有从库，直接从主库提供数据给grpc服务

## 关于API与外部交互

5.  **HTTP API (`frontend`模块)**：
    *   **问题5.1**: 除了 `/api/v1/market_price`，`frontend` 模块是否还提供了其他重要的、被外部系统调用的HTTP API接口？
    * A：frontend模块我也不太清楚。frontend/urls.py 我看只有这一个文件里面有内容，定义了三个接口
    *   **问题5.2**: 现有API的认证和授权机制是怎样的（如果有的话）？
    * A：应该是没有，或者是使用的Django自带的认证

6.  **外部依赖与交互**：
    *   **问题6.1**: 目标架构图中的"HailStone 业务中台"是Skyeye的唯一上游消费者吗？还是有其他系统也在使用Skyeye的数据（通过API或其他方式）？
    * A：是的。只有HailStone在使用skyeye的数据，通过grpc的方式。proto文件在这个路径下面：external/dapplink-proto/dapplink。只使用了"chaineye" "common" "market" "wallet"这四个proto文件
    *   **问题6.2**: Skyeye系统本身是否有依赖其他的内部微服务或外部第三方服务（除了交易所API本身）？
    * A：不依赖其他服务

## 关于部署与运维（可选，但有助于理解整体）

7.  **部署拓扑**：
    *   **问题7.1**: Skyeye项目当前是如何部署的？是单体应用部署在单台服务器，还是有多个实例通过负载均衡提供服务？
    * A：是通过k3s部署的。由运维人员执行。具体怎么执行我，我也不清楚
    *   **问题7.2**: 日志是如何收集和管理的？是否有集中的日志系统？
    * A：目前应该是没有，后续可以添加。目前只打印了日志，使用的Django的setting.py里面的LOGGING配置日志打印信息
    *   **问题7.3**: 监控和告警机制是怎样的？
    * A：目前没有，后续需要添加

---
