# SkyEye 加密货币市场数据聚合平台

<div align="center">
  <a href="https://github.com/SavourDao/skyeye/releases/latest">
    <img alt="Version" src="https://img.shields.io/github/tag/savour-labs/skyeye.svg" />
  </a>
  <a href="https://github.com/SavourDao/skyeye/blob/main/LICENSE">
    <img alt="License: Apache-2.0" src="https://img.shields.io/github/license/savour-labs/skyeye.svg" />
  </a>
</div>

SkyEye 是一个基于 Django 的现代加密货币市场数据聚合平台，为 Savour DAO 生态系统提供实时和历史市场数据、代币经济分析、持仓跟踪和解锁计划等服务。

**系统要求**: [Python 3.12+](https://www.python.org/)

## 🚀 快速开始

### 本地开发环境
```bash
# 1. 环境初始化
bash scripts/local/setup_env.sh

# 2. 启动服务
./scripts/local/manage_docker.sh up
./scripts/local/manage_celery.sh start

# 3. 启动Django
uv run python manage.py runserver
```

### 生产环境部署
```bash
# 1. 数据准备
./scripts/production/prepare_production_data.sh

# 2. 一键部署（自动检测Docker/K3s）
./scripts/production/production_deployment.sh skyeye_production_seed_*.sql
```

## 📚 文档导航

| 文档 | 用途 | 适用场景 |
|------|------|----------|
| [STARTUP_GUIDE.md](STARTUP_GUIDE.md) | 本地开发环境完整指南 | 开发、调试、测试 |
| [scripts/README.md](scripts/README.md) | 脚本说明和生产部署指南 | 生产部署、运维 |
| [CLAUDE.md](CLAUDE.md) | 项目架构和开发指南 | 代码开发、架构理解 |
| [skyeye-openapi.yaml](skyeye-openapi.yaml) | API接口文档 | 接口调用、集成 |

## 🏗️ 项目架构

- **数据收集**: CoinMarketCap API → Redis缓存 → PostgreSQL存储
- **任务处理**: Celery分布式任务队列
- **API服务**: Django REST API + gRPC服务
- **部署方式**: Docker Compose / K3s

## 📁 目录结构

```
skyeye/
├── apps/                 # Django应用模块
│   ├── cmc_proxy/       # CoinMarketCap数据代理
│   ├── price_oracle/    # 价格预言机
│   ├── token_*/        # 代币相关业务模块
│   └── api_router/     # API路由
├── scripts/             # 工具脚本
│   ├── local/          # 本地开发脚本
│   ├── production/     # 生产部署脚本
│   └── utils/          # 通用工具脚本
├── charts/             # Helm部署配置
└── skyeye/            # Django项目配置
```

## 🔧 核心功能

- **实时数据**: CoinMarketCap市场数据实时同步
- **历史数据**: K线图表和历史价格数据
- **代币分析**: 代币经济模型、持仓分析、解锁计划
- **高可用**: 主从数据库、Redis集群、分布式任务
- **API服务**: REST API + gRPC双协议支持

## 🛠️ 技术栈

- **后端**: Django 5.x, Python 3.12+
- **数据库**: PostgreSQL (主从架构)
- **缓存**: Redis (多数据库)
- **任务队列**: Celery + Redis
- **容器化**: Docker, K3s/Kubernetes
- **监控**: Flower (Celery监控)

## 📊 API接口

| 接口 | 功能 | 文档 |
|------|------|------|
| `/api/v1/cmc/market-data` | 市场行情数据 | [OpenAPI](skyeye-openapi.yaml) |
| `/api/v1/cmc/klines` | K线图表数据 | [OpenAPI](skyeye-openapi.yaml) |
| `/api/v1/cmc/token-*` | 代币相关数据 | [OpenAPI](skyeye-openapi.yaml) |
| gRPC服务 | 高性能数据查询 | [Protobuf](external/dapplink-proto/) |

## 🔐 环境配置

```bash
# 生成配置文件
bash scripts/local/setup_env.sh

# 主要配置项
COINMARKETCAP_API_KEY=your-api-key    # 必须配置
POSTGRES_PASSWORD=secure-password     # 数据库密码
SECRET_KEY=auto-generated             # 自动生成
```

## 🚀 部署环境

### 支持的部署方式
- **本地开发**: Docker Compose
- **生产环境**: K3s/Kubernetes 或 Docker Compose
- **自动检测**: 脚本自动选择最合适的部署方式

### 环境要求
- Python 3.12+
- Docker & Docker Compose
- uv包管理器
- CoinMarketCap API密钥

## 📈 监控和日志

- **Celery监控**: http://localhost:5555 (Flower)
- **Django Admin**: http://localhost:8000/admin
- **API文档**: 基于OpenAPI 3.0规范
- **日志**: 结构化日志，支持不同级别

## 🔍 详细设置指南

详细的本地开发环境设置步骤，请参考：
- **完整指南**: [STARTUP_GUIDE.md](STARTUP_GUIDE.md)
- **脚本说明**: [scripts/README.md](scripts/README.md)

## 📞 支持

- **文档**: 查看相关文档文件
- **Issues**: GitHub Issues
- **API文档**: OpenAPI规范文件

## 🤝 贡献指南

1. 阅读 [CLAUDE.md](CLAUDE.zh-CN.md) 了解项目架构
2. 参考 [STARTUP_GUIDE.md](STARTUP_GUIDE.md) 设置开发环境
3. 查看 [scripts/README.md](scripts/README.md) 了解工具脚本
4. 提交Pull Request前请运行完整测试

---

**快速链接**:
[本地开发](STARTUP_GUIDE.md) | [生产部署](scripts/README.md) | [项目架构](CLAUDE.zh-CN.md) | [API文档](skyeye-openapi.yaml)

## 开发流程

### 1. Fork仓库

Fork skyeye到你的GitHub

### 2. 克隆仓库

```bash
git clone git@github.com:your-username/skyeye.git
cd skyeye
```

### 3. 创建新分支并提交代码

```bash
git checkout -b feature-name

# 开发代码...

git add .
git commit -m "feat: your feature description"
git push origin feature-name
```

### 4. 提交PR

在你的GitHub上创建PR并提交到skyeye仓库

### 5. 代码审查

经过skyeye代码维护者审查通过后，代码将被合并到skyeye仓库。
