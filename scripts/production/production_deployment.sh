#!/bin/bash

# SkyEye 统一生产环境部署脚本
# 支持：Docker Compose + K3s/Kubernetes 环境
# 用途：使用本地准备的种子数据快速启动生产环境

set -e

echo "🚀 SkyEye 生产环境部署"
echo "======================="

# 检测部署环境
DEPLOYMENT_MODE="docker"
if command -v kubectl >/dev/null 2>&1 && kubectl cluster-info >/dev/null 2>&1; then
    DEPLOYMENT_MODE="k3s"
    echo "🔍 检测到K3s/Kubernetes环境"
elif command -v docker-compose >/dev/null 2>&1 || command -v docker >/dev/null 2>&1; then
    echo "🔍 检测到Docker环境"
else
    echo "❌ 错误: 未检测到支持的部署环境 (Docker或K3s)"
    exit 1
fi

# 参数检查
SEED_DATA_FILE=""
if [ $# -eq 1 ]; then
    SEED_DATA_FILE="$1"
elif [ -f "skyeye_production_seed_*.sql" ]; then
    SEED_DATA_FILE=$(ls -t skyeye_production_seed_*.sql | head -1)
    echo "🔍 自动发现种子数据文件: $SEED_DATA_FILE"
else
    echo "❌ 使用方法: $0 [种子数据文件.sql]"
    echo "💡 或者将种子数据文件放在当前目录"
    exit 1
fi

if [ ! -f "$SEED_DATA_FILE" ]; then
    echo "❌ 错误: 种子数据文件 '$SEED_DATA_FILE' 不存在"
    exit 1
fi

# K3s特定参数
if [ "$DEPLOYMENT_MODE" = "k3s" ]; then
    NAMESPACE="${NAMESPACE:-skyeye}"
    RELEASE_NAME="${RELEASE_NAME:-skyeye}"
    echo "📋 K3s配置:"
    echo "  - Namespace: $NAMESPACE"
    echo "  - Release: $RELEASE_NAME"
fi

# 检查环境配置文件
echo "📋 1. 检查环境配置"
ENV_FILE=".env"
if [ ! -f "$ENV_FILE" ]; then
    echo "❌ 错误: 未找到环境配置文件: $ENV_FILE"
    echo "💡 提示: 请先运行以下命令生成.env文件:"
    echo "   bash scripts/setup_env.sh"
    echo "   然后编辑 .env 文件，填入生产环境的实际配置值"
    exit 1
else
    echo "✅ 找到环境配置文件: $ENV_FILE"
    
    # 检查是否为开发环境配置
    if grep -q "127.0.0.1\|localhost" "$ENV_FILE"; then
        echo "⚠️  检测到开发环境配置（localhost/127.0.0.1）"
        echo "💡 建议先运行生产环境配置准备脚本:"
        echo "   bash scripts/prepare_production_env.sh"
        echo ""
        read -p "是否继续使用当前配置进行部署？(y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            echo "🔄 请先准备生产环境配置，然后重新运行部署"
            exit 0
        fi
    fi
fi

# 验证环境配置
if [ "$DEPLOYMENT_MODE" = "docker" ]; then
    # Docker模式：加载.env文件到环境变量
    set -a  # 自动导出变量
    source "$ENV_FILE"
    set +a
    
    python scripts/utils/check_env.py || {
        echo "❌ 环境配置检查失败，请检查 $ENV_FILE 文件"
        exit 1
    }
elif [ "$DEPLOYMENT_MODE" = "k3s" ]; then
    # K3s模式：生成ConfigMap和Secret
    echo "🔧 转换.env为K3s配置..."
    ./scripts/production/env_to_k8s.sh "$ENV_FILE" "$NAMESPACE" "./k8s-configs"
fi

echo "✅ 环境配置验证通过"

# 环境特定的部署逻辑
if [ "$DEPLOYMENT_MODE" = "k3s" ]; then
    # K3s部署逻辑
    echo "🚀 2. K3s环境部署"
    
    # 创建命名空间
    kubectl create namespace "$NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -
    echo "✅ 命名空间 $NAMESPACE 准备就绪"
    
    # 应用环境配置 (ConfigMap和Secret)
    echo "📦 应用环境配置..."
    cd k8s-configs && ./apply-configs.sh && cd ..
    echo "✅ 环境配置应用完成"
    
    # 创建种子数据ConfigMap
    echo "📦 创建种子数据ConfigMap"
    kubectl create configmap skyeye-seed-data \
        --from-file="skyeye_production_seed.sql=$SEED_DATA_FILE" \
        -n "$NAMESPACE" \
        --dry-run=client -o yaml | kubectl apply -f -
    echo "✅ 种子数据ConfigMap创建完成"
    
    # 部署应用
    echo "🚀 部署SkyEye应用"
    helm upgrade --install "$RELEASE_NAME" ./charts \
        -f values.yaml \
        --set dataSeed.enabled=true \
        --set dataSeed.configMapName=skyeye-seed-data \
        --set dataSeed.fileName=skyeye_production_seed.sql \
        -n "$NAMESPACE" \
        --wait \
        --timeout=10m
    
    # 等待Pod就绪
    kubectl wait --for=condition=Ready pod -l app.kubernetes.io/name=app -n "$NAMESPACE" --timeout=300s
    echo "✅ 应用部署完成"
    
else
    # Docker部署逻辑
    echo "🐳 2. 启动基础服务"
    ./scripts/local/manage_docker.sh up || {
        echo "❌ Docker 服务启动失败"
        exit 1
    }

    # 等待数据库就绪
    echo "⏳ 等待数据库服务就绪..."
    timeout 60 bash -c 'until docker exec skyeye-db-master-1 pg_isready -U skyeye_user; do sleep 2; done' || {
        echo "❌ 数据库服务启动超时"
        exit 1
    }
    echo "✅ 数据库服务就绪"

    # 数据库迁移
    echo "🗄️ 3. 执行数据库迁移"
    uv run python manage.py makemigrations --dry-run
    uv run python manage.py migrate
    echo "✅ 数据库迁移完成"

    # 导入种子数据
    echo "📥 4. 导入种子数据"
    echo "正在导入: $SEED_DATA_FILE"
    FILE_SIZE=$(du -h "$SEED_DATA_FILE" | cut -f1)
    echo "文件大小: $FILE_SIZE"

    # 执行数据导入
    if docker exec -i skyeye-db-master-1 psql -U skyeye_user -d skyeye < "$SEED_DATA_FILE"; then
        echo "✅ 种子数据导入成功"
    else
        echo "❌ 种子数据导入失败"
        exit 1
    fi
fi

# 验证导入的数据
echo "📊 验证导入的数据..."
uv run python manage.py shell -c "
from apps.cmc_proxy.models import CmcAsset, CmcMarketData, CmcKline
print(f'导入验证:')
print(f'  CmcAsset: {CmcAsset.objects.count():,} 条')
print(f'  CmcMarketData: {CmcMarketData.objects.count():,} 条')
print(f'  CmcKline: {CmcKline.objects.count():,} 条')
if CmcAsset.objects.count() < 1000:
    print('⚠️  警告: 资产数量较少，可能导入不完整')
else:
    print('✅ 数据导入验证通过')
"

# 启动应用服务
echo "🔧 5. 启动应用服务"

# 启动Django (在生产环境建议使用 Gunicorn)
echo "启动 Django 服务..."
if command -v gunicorn >/dev/null 2>&1; then
    echo "使用 Gunicorn 启动生产服务..."
    nohup uv run gunicorn skyeye.wsgi:application \
        --bind 0.0.0.0:8000 \
        --workers 4 \
        --timeout 30 \
        --keep-alive 2 \
        --max-requests 1000 \
        --max-requests-jitter 100 \
        > logs/gunicorn.log 2>&1 &
    echo "✅ Gunicorn 服务已启动 (PID: $!)"
else
    echo "使用 Django 开发服务器..."
    nohup uv run python manage.py runserver 0.0.0.0:8000 > logs/django.log 2>&1 &
    echo "✅ Django 服务已启动 (PID: $!)"
fi

# 等待Django服务启动
echo "⏳ 等待Django服务启动..."
for i in {1..30}; do
    if curl -s -f http://localhost:8000 >/dev/null 2>&1; then
        echo "✅ Django 服务启动完成"
        break
    fi
    sleep 2
done

# 启动Celery服务
echo "启动 Celery 服务..."
./scripts/manage_celery.sh start
./scripts/manage_celery.sh start-beat-db

# 初始化定时任务
echo "初始化定时任务..."
uv run python manage.py initialize_beat_tasks
echo "✅ Celery 服务启动完成"

# 等待服务稳定
sleep 5

# 功能验证
echo "🔍 6. 生产环境功能验证"
echo "测试核心API接口..."

# 测试市场数据API
echo -n "  - 市场数据API: "
if curl -s -f "http://localhost:8000/api/v1/cmc/market-data?page=1&page_size=1" | grep -q '"ok":true'; then
    echo "✅ 正常"
else
    echo "❌ 异常"
    echo "    检查Django日志: tail logs/django.log"
fi

# 测试K线数据API
echo -n "  - K线数据API: "
if curl -s -f "http://localhost:8000/api/v1/cmc/klines?cmc_id=1&limit=1" | grep -q '"ok":true'; then
    echo "✅ 正常"
else
    echo "❌ 异常"
fi

# 测试价格Oracle API
echo -n "  - 价格Oracle API: "
if curl -s -f "http://localhost:8000/api/v1/ccxt/price" | grep -q '"ok":true'; then
    echo "✅ 正常"
else
    echo "⚠️  数据为空或异常"
fi

# 检查Celery状态
echo -n "  - Celery Worker: "
if ./scripts/manage_celery.sh status | grep -q "OK"; then
    echo "✅ 正常"
else
    echo "❌ 异常"
fi

# 启动监控服务
echo "🖥️ 7. 启动监控服务"
./scripts/manage_celery.sh flower-bg
echo "✅ Flower 监控服务已启动"

# 显示系统状态
echo "📊 8. 系统状态总览"
echo "服务状态:"
echo "  🌐 Web服务: http://localhost:8000"
echo "  📊 监控面板: http://localhost:5555"
echo "  🐳 Docker服务: $(docker ps --format 'table {{.Names}}\t{{.Status}}' | grep skyeye | wc -l) 个容器运行中"
echo ""

# 显示定时任务状态
echo "⏰ 定时任务配置:"
echo "  - 每2秒: 批量请求处理"
echo "  - 每1秒: Redis数据同步"
echo "  - 每小时15分: K线数据更新"
echo "  - 每日3:00: 全量数据刷新"
echo ""

# 显示数据更新状态
echo "🔄 数据更新说明:"
echo "  - 当前数据: 来自本地测试环境 (可能陈旧)"
echo "  - 自动更新: 定时任务将在几小时内更新为最新数据"
echo "  - 手动触发: uv run python -c \"from apps.cmc_proxy.tasks import daily_full_data_sync; daily_full_data_sync.delay()\""
echo ""

echo "🎉 生产环境部署完成！"
echo "================================"
echo "🌐 API 地址: http://localhost:8000/api/v1/"
echo "📖 API 文档: skyeye-openapi.yaml"
echo "📊 监控地址: http://localhost:5555"
echo ""
echo "📋 日志文件:"
echo "  - Django: logs/django.log 或 logs/gunicorn.log"
echo "  - Celery: logs/celery.log"
echo "  - Flower: logs/flower.log"
echo ""
echo "🔧 管理命令:"
echo "  - 查看服务状态: ./scripts/manage_docker.sh status"
echo "  - 查看Celery状态: ./scripts/manage_celery.sh status"
echo "  - 重启服务: ./scripts/manage_celery.sh restart"
echo ""
echo "💡 建议: 观察几小时后检查数据是否已自动更新为最新"