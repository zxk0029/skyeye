# SkyEye 本地开发环境启动指南

本文档提供 SkyEye 加密货币市场数据聚合平台的**本地开发环境**完整启动流程。

> 📋 **文档说明**
> - 本文档：本地开发环境设置和使用
> - 生产部署：请参考 `scripts/README.md` 中的生产部署部分
> - 项目架构：请参考 `CLAUDE.md`

## 项目概述

SkyEye 是一个基于 Django 的现代加密货币市场数据聚合平台，为 Savour DAO 生态系统提供实时和历史市场数据、代币经济分析、持仓跟踪和解锁计划等服务。

## 1. 环境要求

### 系统要求
- **Python**: 3.12+ (当前测试版本: 3.13.3)
- **Docker & Docker Compose**: 用于数据库和缓存服务
- **Git**: 版本控制和子模块管理
- **操作系统**: macOS, Linux, Windows (推荐 Unix-like 系统)

### 依赖服务
- **PostgreSQL**: 主从架构数据库 (端口 5430/5431)
- **Redis**: 多数据库缓存和任务队列 (端口 6379)
- **CoinMarketCap API**: 数据源 (需要 API 密钥)

## 2. 项目初始化

### 步骤 1: 克隆项目并准备环境

```bash
# 进入项目目录
cd /path/to/skyeye

# 创建虚拟环境 (推荐使用 uv)
uv venv .venv
source .venv/bin/activate

# 或使用传统方式
# python -m venv .venv
# source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate     # Windows
```

### 步骤 2: 安装依赖

```bash
# 使用 uv 安装依赖 (推荐)
uv pip install -r requirements.txt

# 或使用 pip
# pip install -r requirements.txt
```

### 步骤 3: 初始化子模块和编译 Protocol Buffers

```bash
# 初始化 git 子模块 (protobuf 定义)
git submodule update --init --recursive

# 编译 protobuf 文件
bash scripts/proto_compile.sh
```

## 3. 环境变量配置

### 方法一：使用自动化脚本（推荐）

项目提供了自动化环境设置脚本：

```bash
# 运行环境设置脚本
bash scripts/local/setup_env.sh
```

这个脚本会：
1. 从 `.env.production.example` 创建 `.env` 文件
2. 自动生成安全的 `SECRET_KEY`
3. 检查必要的环境变量配置
4. 运行环境验证

### 方法二：手动配置

如果需要手动配置，可以：

```bash
# 复制生产环境模板到开发环境
cp .env.production.example .env

# 编辑配置文件
nano .env
```

**重要配置项修改：**
```bash
# 开发环境设置
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# 时区和语言配置
CELERY_TIMEZONE=Asia/Shanghai  # 定时任务时区（可选，系统会自动检测）
LANGUAGE_CODE=zh-hans

# 数据库配置（Docker 默认配置）
POSTGRES_DB=skyeye
POSTGRES_USER=skyeye_user
POSTGRES_PASSWORD=123456
POSTGRES_HOST_MASTER=127.0.0.1
POSTGRES_PORT_MASTER=5430
POSTGRES_HOST_SLAVE=127.0.0.1
POSTGRES_PORT_SLAVE=5431

# Redis 配置（本地默认配置）
REDIS_URL=redis://localhost:6379/0
REDIS_CMC_URL=redis://localhost:6379/1
REDIS_TRADING_HOST=127.0.0.1
REDIS_TRADING_PORT=6379
REDIS_TRADING_DB=2

# 必须配置的 API 密钥
COINMARKETCAP_API_KEY=your-actual-cmc-api-key-here
```

**⚠️ 智能时区分离设计说明：**
- **数据存储时区**：固定使用UTC，确保数据一致性和跨时区兼容性
- **定时任务时区**：自动检测服务器本地时区，便于理解执行时间
- 自动检测支持：Linux系统文件、macOS、UTC偏移量等多种方式
- 如需手动指定定时任务时区，在 `.env` 中设置 `CELERY_TIMEZONE=Asia/Shanghai`
- ⚠️ **注意**：`.env` 中的 `TIME_ZONE` 环境变量已废弃，不再生效
- 详细配置说明请参考：[时区配置文档](docs/deployment/TIMEZONE_CONFIG.md)

**生成安全的 SECRET_KEY**

```bash
# 自动生成并更新 .env 文件中的 SECRET_KEY
bash scripts/utils/generate_secret_key.sh --update-env
```

### 配置验证

```bash
# 运行环境配置检查
python scripts/utils/check_env.py

# 验证时区自动检测功能
python scripts/utils/check_timezone.py
```

## 4. 服务启动流程

### 步骤 1: 启动基础服务 (PostgreSQL + Redis)

```bash
# 启动 Docker Compose 服务
./scripts/local/manage_docker.sh up

# 检查服务状态
./scripts/local/manage_docker.sh status

# 查看服务日志 (可选)
./scripts/local/manage_docker.sh logs
```

**服务映射：**
- PostgreSQL Master: `localhost:5430`
- PostgreSQL Slave: `localhost:5431`
- Redis: `localhost:6379`

### 步骤 2: 数据库初始化

```bash
# 生成迁移文件
uv run python manage.py makemigrations

# 执行数据库迁移
uv run python manage.py migrate

# 创建超级用户 (可选，用于 Django Admin)
uv run python manage.py createsuperuser
```

### 步骤 3: 启动 Django 开发服务器

```bash
# 启动开发服务器
uv run python manage.py runserver

# 服务将在 http://localhost:8000 启动
```

### 步骤 4: 启动后台任务系统

打开新的终端窗口：

```bash
# 激活虚拟环境
source .venv/bin/activate

# 启动 Celery Worker (后台)
./scripts/local/manage_celery.sh start

# 启动 Celery Beat 调度器 (新终端)
./scripts/local/manage_celery.sh start-beat-db

# 初始化定时任务
uv run python manage.py initialize_beat_tasks
```

### 步骤 5: 启动监控服务 (可选)

```bash
# 启动 Flower 监控界面 (后台)
./scripts/local/manage_celery.sh flower-bg

# 访问监控界面: http://localhost:5555
```

## 5. 本地开发数据初始化

### 首次系统初始化（必须按顺序执行）

> ⚠️ **注意**: 以下是本地开发环境的数据初始化步骤
> 
> 🚀 **生产部署**: 请参考 [`scripts/README.md`](scripts/README.md) 中的生产部署指南

本地开发环境首次启动后，需要按以下顺序手动执行初始化命令获得基础数据：

```bash
# 步骤1: 全量市场数据同步（获取基础的资产和市场数据）
uv run python -c "from apps.cmc_proxy.tasks import daily_full_data_sync; daily_full_data_sync.delay()"

# 步骤2: 等待数据持久化完成（约1-2分钟）
# sync_cmc_data_task 每1秒自动将Redis数据同步到PostgreSQL
# 可以通过以下命令检查数据是否同步完成：
# uv run python manage.py shell -c "from apps.cmc_proxy.models import CmcAsset; print(f'已同步资产数量: {CmcAsset.objects.count()}')"

# 步骤3: 初始化K线数据（24小时历史数据）
uv run python manage.py update_cmc_klines --initialize

# 步骤4: 初始化代币相关数据（依赖基础CMC数据）
uv run python manage.py update_token_holdings
uv run python manage.py update_token_unlocks
uv run python manage.py update_token_allocation
```

**⚠️ 重要说明：**
- 步骤1执行后，需等待数据持久化完成再执行后续步骤
- 代币相关任务依赖于CMC基础数据，必须等基础数据同步完成后执行
- `--initialize` 参数用于K线数据的首次初始化，获取24小时历史数据

### 持续数据同步（自动执行）

系统启动后，以下任务将自动执行：
- **每2秒**: CMC API批量请求处理 (`process_pending_cmc_batch_requests`)
- **每1秒**: Redis 到 PostgreSQL 数据同步 (`sync_cmc_data_task`)  
- **每小时15分**: K线数据增量更新（最新1小时）(`update_cmc_klines`)
- **每日3:40**: 完整市场数据同步 (`daily_full_data_sync`)
- **每日4:00**: 代币持仓数据更新 (`update_token_holdings_daily_task`)
- **每日5:00**: 代币解锁数据更新 (`update_token_unlocks_task`)
- **每日6:00**: 代币分配数据更新 (`update_token_allocations_task`)

**⚠️ 时区分离设计注意事项：**
- **定时任务执行**：系统自动检测服务器时区，按本地时间执行
  - 例如：在中国服务器上，3:40表示本地凌晨3:40（而非UTC时间）
- **数据存储**：统一使用UTC时间，确保数据一致性
  - 数据库中的时间戳都是UTC时间
  - API返回的时间也是UTC时间（客户端可转换为本地时间）
- 如需手动指定定时任务时区，在 `.env` 中设置 `CELERY_TIMEZONE=时区名称`
- 修改定时任务时区配置后，需要重启 Celery Beat：`./scripts/manage_celery.sh restart-beat`

## 6. 测试和验证

### 环境配置测试

```bash
# 运行环境检查脚本
python scripts/check_env.py
```

### 功能测试

项目包含一些专门的测试脚本：

```bash
# CMC 代理服务功能测试
uv run python -m apps.cmc_proxy.tests

# 注意：大部分 tests.py 文件只是占位符，实际测试通过 API 验证
```

### API 接口测试（基于 OpenAPI 文档验证）

根据 `skyeye-openapi.yaml` 定义的接口进行验证：

```bash
# 1. 【CMC】获取市场行情数据
# 分页查询所有资产
curl -s "http://localhost:8000/api/v1/cmc/market-data?page=1&page_size=5" | python -m json.tool

# 查询单个资产详情（比特币 ID=1）
curl -s "http://localhost:8000/api/v1/cmc/market-data?cmc_id=1" | python -m json.tool

# 批量查询多个资产（BTC、ETH、DOGE）
curl -s "http://localhost:8000/api/v1/cmc/market-data?cmc_ids=1,1027,74" | python -m json.tool

# 2. 【CMC】获取代币经济模型
curl -s "http://localhost:8000/api/v1/cmc/token-allocations?cmc_id=1" | python -m json.tool

# 3. 【CMC】获取代币解锁信息
curl -s "http://localhost:8000/api/v1/cmc/token-unlocks?cmc_id=1" | python -m json.tool

# 4. 【CMC】获取代币持仓信息
curl -s "http://localhost:8000/api/v1/cmc/holdings?cmc_id=1" | python -m json.tool

# 5. 【CMC】获取K线数据
curl -s "http://localhost:8000/api/v1/cmc/klines?cmc_id=1&interval=1h&limit=24" | python -m json.tool

# 6. 【CCXT】获取价格预言机数据
curl -s "http://localhost:8000/api/v1/ccxt/price" | python -m json.tool
```

**验证成功标准：**
- API 返回 `200` 状态码
- 响应格式符合 OpenAPI 文档定义
- 返回的数据结构包含 `ok: true` 和相应的 `result` 字段
- 市场数据包含价格、交易量等关键信息

### 后台任务状态检查

```bash
# 检查 Celery Worker 状态
./scripts/local/manage_celery.sh status

# 查看正在执行的任务
./scripts/local/manage_celery.sh active

# 查看计划中的任务
./scripts/local/manage_celery.sh scheduled

# 查看任务统计
./scripts/local/manage_celery.sh stats
```

## 7. 常用管理命令

### Docker 服务管理

```bash
# 启动所有服务
./scripts/local/manage_docker.sh up

# 停止所有服务
./scripts/local/manage_docker.sh down

# 停止服务并删除数据卷
./scripts/local/manage_docker.sh down-v

# 重启服务
./scripts/local/manage_docker.sh restart

# 查看日志
./scripts/local/manage_docker.sh logs [service_name]

# 进入容器执行命令
./scripts/local/manage_docker.sh exec db-master psql -U skyeye_user -d skyeye
```

### Celery 任务管理

```bash
# 启动/停止 Worker
./scripts/local/manage_celery.sh start      # 后台启动
./scripts/local/manage_celery.sh start-fg   # 前台启动
./scripts/local/manage_celery.sh stop       # 停止
./scripts/local/manage_celery.sh restart    # 重启

# 监控和调试
./scripts/local/manage_celery.sh status     # 状态检查
./scripts/local/manage_celery.sh active     # 活跃任务
./scripts/local/manage_celery.sh logs       # 查看日志
./scripts/local/manage_celery.sh flower     # 启动监控界面

# 任务管理
./scripts/local/manage_celery.sh purge      # 清空队列
```

## 8. 代码提交和部署

### 提交前检查清单

```bash
# 1. 验证环境配置
python scripts/utils/check_env.py

# 2. 检查服务状态
./scripts/local/manage_docker.sh status
./scripts/local/manage_celery.sh status

# 3. 验证核心 API 响应（基于 OpenAPI 文档）
echo "检查市场数据 API..."
curl -s "http://localhost:8000/api/v1/cmc/market-data?page=1&page_size=1" | grep -q '"ok":true' && echo "✅ 市场数据 API 正常" || echo "❌ 市场数据 API 异常"

echo "检查价格预言机 API..."
curl -s "http://localhost:8000/api/v1/ccxt/price" | grep -q '"ok":true' && echo "✅ 价格预言机 API 正常" || echo "❌ 价格预言机 API 异常"

# 4. 检查数据同步状态
echo "检查 Celery 任务状态..."
./scripts/local/manage_celery.sh active

# 5. 功能测试（可选）
echo "运行 CMC 代理服务测试..."
uv run python -m apps.cmc_proxy.tests
```

### Git 提交流程

```bash
# 检查当前状态
git status
git diff

# 暂存变更
git add .

# 提交变更 (使用语义化提交信息)
git commit -m "feat: implement complete project setup

- Add comprehensive startup documentation
- Configure PostgreSQL master-slave architecture  
- Set up Redis multi-database caching
- Implement Celery distributed task processing
- Add API endpoints for market data aggregation
- Configure automatic data synchronization pipelines

🤖 Generated with Claude Code

Co-Authored-By: Claude <noreply@anthropic.com>"

# 推送到远程仓库
git push origin main
```

## 9. 故障排除

### 常见问题

**问题 1: Docker 服务启动失败**
```bash
# 检查端口占用
lsof -i :5430 -i :5431 -i :6379

# 清理 Docker 资源
docker system prune -f
./scripts/manage_docker.sh down-v
./scripts/manage_docker.sh up
```

**问题 2: Celery Worker 无法启动**
```bash
# 检查 Redis 连接
redis-cli ping

# 重置任务队列
./scripts/manage_celery.sh purge
./scripts/manage_celery.sh restart
```

**问题 3: 数据库连接错误**
```bash
# 检查数据库服务
./scripts/manage_docker.sh exec db-master pg_isready -U skyeye_user

# 重新运行迁移
uv run python manage.py migrate --run-syncdb
```

**问题 4: API 返回错误**
```bash
# 检查 Django 日志
tail -f logs/django.log

# 检查 CoinMarketCap API 密钥
curl -H "X-CMC_PRO_API_KEY: your-api-key" https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest?limit=1
```

### 日志文件位置

- **Django**: 控制台输出
- **Celery Worker**: `./logs/celery.log`
- **Flower**: `./logs/flower.log`
- **Docker 服务**: `docker logs <container_name>`

## 10. 重要配置说明

### 端口映射
- **Django 开发服务器**: 8000
- **PostgreSQL Master**: 5430
- **PostgreSQL Slave**: 5431  
- **Redis**: 6379
- **Flower 监控**: 5555

### 数据库配置
- **主数据库**: 处理所有写操作
- **从数据库**: 处理读操作 (通过 `ReadWriteRouter` 自动路由)
- **测试**: 从数据库镜像主数据库配置

### Redis 数据库分配
- **DB 0**: Django 缓存 + Celery 队列
- **DB 1**: CoinMarketCap 代理数据
- **DB 2**: 交易市场数据

### 必需的环境变量
- `SECRET_KEY`: Django 安全密钥 (自动生成)
- `POSTGRES_PASSWORD`: 数据库密码
- `COINMARKETCAP_API_KEY`: CMC API 密钥 ⚠️ **必须配置**

### 可选的环境变量
- `CELERY_TIMEZONE`: 定时任务时区设置 (自动检测服务器本地时区，可手动指定)

## 11. 生产部署注意事项

生产环境部署时需要额外考虑：

1. **安全配置**:
   - 设置 `DEBUG=False`
   - 配置合适的 `ALLOWED_HOSTS`
   - 使用强密码和密钥

2. **性能优化**:
   - 使用 Gunicorn/uWSGI 代替开发服务器
   - 配置 Nginx 反向代理
   - 启用数据库连接池

3. **监控和日志**:
   - 配置结构化日志记录
   - 设置性能监控
   - 配置错误报告

4. **备份策略**:
   - 定期数据库备份
   - Redis 数据持久化配置

## 12. 快速验证脚本

为了快速验证系统是否正常运行，可以使用以下综合检查脚本：

```bash
#!/bin/bash
# 创建快速验证脚本
cat > quick_check.sh << 'EOF'
#!/bin/bash
echo "🔍 SkyEye 系统状态检查"
echo "======================"

# 检查环境变量
echo "📋 1. 检查环境配置..."
python scripts/check_env.py --quiet 2>/dev/null && echo "✅ 环境配置正常" || echo "❌ 环境配置异常"

# 检查 Docker 服务
echo "🐳 2. 检查 Docker 服务..."
./scripts/manage_docker.sh status | grep -q "Up" && echo "✅ Docker 服务正常" || echo "❌ Docker 服务异常"

# 检查 Django 服务
echo "🌐 3. 检查 Django 服务..."
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000 | grep -q "200\|404" && echo "✅ Django 服务正常" || echo "❌ Django 服务异常"

# 检查 Celery Worker
echo "⚙️ 4. 检查 Celery Worker..."
./scripts/manage_celery.sh status | grep -q "OK" && echo "✅ Celery Worker 正常" || echo "❌ Celery Worker 异常"

# 检查核心 API（基于 OpenAPI 文档）
echo "🔌 5. 检查核心 API..."
curl -s "http://localhost:8000/api/v1/cmc/market-data?page=1&page_size=1" | grep -q '"ok":true' && echo "✅ 市场数据 API 正常" || echo "❌ 市场数据 API 异常"

echo ""
echo "🎉 如果所有检查都显示 ✅，说明 SkyEye 系统运行正常！"
echo "📖 可以查看 OpenAPI 文档了解完整的 API 接口：skyeye-openapi.yaml"
EOF

chmod +x quick_check.sh
```

**使用方法：**
```bash
# 运行快速检查
./quick_check.sh
```

## 13. 下一步操作建议

系统启动成功后，建议按以下顺序进行：

1. **首次数据初始化**：
   ```bash
   # 按正确顺序执行初始化命令
   uv run python manage.py daily_full_data_sync
   
   # 等待1-2分钟数据持久化，然后验证基础数据
   uv run python manage.py shell -c "from apps.cmc_proxy.models import CmcAsset; print(f'已同步资产数量: {CmcAsset.objects.count()}')"
   
   # 初始化K线和代币数据
   uv run python manage.py update_cmc_klines --initialize
   uv run python manage.py update_token_holdings
   uv run python manage.py update_token_unlocks  
   uv run python manage.py update_token_allocation
   
   # 验证 API 数据
   curl -s "http://localhost:8000/api/v1/cmc/market-data?cmc_id=1" | python -m json.tool
   ```

2. **监控服务**：
   - 访问 Flower 监控界面：http://localhost:5555
   - 查看 Celery 任务执行情况

3. **API 文档**：
   - 参考 `skyeye-openapi.yaml` 了解完整的 API 接口
   - 测试不同的查询参数和响应格式

4. **生产部署**：
   - 参考 `.env.production.example` 配置生产环境
   - 使用 Gunicorn/uWSGI 替代开发服务器
   - 配置 Nginx 反向代理和负载均衡

---

## 支持和贡献

如有问题或建议，请提交 Issue 或 Pull Request。更多详细信息请参考项目中的 `CLAUDE.md` 文件。

---

## 🚀 生产环境部署

本文档仅涵盖**本地开发环境**的设置。如需部署到生产环境，请参考：

### 📖 生产部署文档
- **脚本说明**: [`scripts/README.md`](scripts/README.md) - 详细的生产部署指南
- **一键部署**: `./scripts/production/production_deployment.sh` - 自动检测环境并部署

### 🔄 生产部署流程
```bash
# 1. 本地数据准备
./scripts/production/prepare_production_data.sh

# 2. 生产环境配置调整  
bash scripts/production/prepare_production_env.sh

# 3. 一键生产部署（支持Docker和K3s）
./scripts/production/production_deployment.sh skyeye_production_seed_*.sql
```

### 🎯 支持的部署环境
- **Docker Compose**: 传统容器化部署
- **K3s/Kubernetes**: 云原生容器编排
- **自动检测**: 脚本自动选择合适的部署方式

---

## 📚 文档导航

**重要文件参考：**
- **本地开发**: `STARTUP_GUIDE.md` (本文档)
- **生产部署**: [`scripts/README.md`](scripts/README.md)
- **项目架构**: `CLAUDE.md`
- **API文档**: `skyeye-openapi.yaml`
- **环境配置**: `.env.production.example`

**文档版本**: 2.0  
**最后更新**: 2025年6月12日