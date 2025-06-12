#!/bin/bash

# SkyEye K3s 部署脚本
# 结合本地准备的种子数据进行K3s环境快速部署

set -e

echo "🚀 SkyEye K3s 环境部署"
echo "========================"

# 参数检查
SEED_DATA_FILE=""
NAMESPACE="${NAMESPACE:-skyeye}"
RELEASE_NAME="${RELEASE_NAME:-skyeye}"

if [ $# -eq 1 ]; then
    SEED_DATA_FILE="$1"
elif [ -f "skyeye_production_seed_*.sql" ]; then
    SEED_DATA_FILE=$(ls -t skyeye_production_seed_*.sql | head -1)
    echo "🔍 自动发现种子数据文件: $SEED_DATA_FILE"
fi

echo "📋 部署配置:"
echo "  - Namespace: $NAMESPACE"
echo "  - Release: $RELEASE_NAME"
echo "  - 种子数据: ${SEED_DATA_FILE:-无}"

# 检查K3s环境
echo "🔍 1. 检查K3s环境"
if ! kubectl cluster-info >/dev/null 2>&1; then
    echo "❌ 错误: 无法连接到K3s集群"
    exit 1
fi
echo "✅ K3s集群连接正常"

# 创建命名空间
echo "📁 2. 创建命名空间"
kubectl create namespace "$NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -
echo "✅ 命名空间 $NAMESPACE 准备就绪"

# 创建种子数据ConfigMap (如果有种子数据文件)
if [ -n "$SEED_DATA_FILE" ] && [ -f "$SEED_DATA_FILE" ]; then
    echo "📦 3. 创建种子数据ConfigMap"
    kubectl create configmap skyeye-seed-data \
        --from-file="skyeye_production_seed.sql=$SEED_DATA_FILE" \
        -n "$NAMESPACE" \
        --dry-run=client -o yaml | kubectl apply -f -
    echo "✅ 种子数据ConfigMap创建完成"
    
    # 更新values.yaml以启用种子数据
    if ! grep -q "configMapName.*skyeye-seed-data" k3s-values.yaml; then
        sed -i.bak 's/# configMapName: "skyeye-seed-data"/configMapName: "skyeye-seed-data"/' k3s-values.yaml
        sed -i.bak 's/# fileName: "skyeye_production_seed.sql"/fileName: "skyeye_production_seed.sql"/' k3s-values.yaml
        echo "📝 已更新k3s-values.yaml启用种子数据"
    fi
else
    echo "⚠️ 3. 未提供种子数据文件，将跳过数据预填充"
fi

# 检查依赖服务 (PostgreSQL, Redis)
echo "🗄️ 4. 检查依赖服务"
echo "检查PostgreSQL服务..."
if kubectl get service postgres-master-service -n "$NAMESPACE" >/dev/null 2>&1; then
    echo "✅ PostgreSQL服务已存在"
else
    echo "⚠️ PostgreSQL服务不存在，请先部署PostgreSQL"
    echo "💡 建议使用Helm部署: helm install postgres bitnami/postgresql-ha -n $NAMESPACE"
fi

echo "检查Redis服务..."
if kubectl get service redis-service -n "$NAMESPACE" >/dev/null 2>&1; then
    echo "✅ Redis服务已存在"
else
    echo "⚠️ Redis服务不存在，请先部署Redis"
    echo "💡 建议使用Helm部署: helm install redis bitnami/redis -n $NAMESPACE"
fi

# 创建Secret (如果不存在)
echo "🔐 5. 创建Secret"
if ! kubectl get secret skyeye-secrets -n "$NAMESPACE" >/dev/null 2>&1; then
    echo "请输入CoinMarketCap API密钥:"
    read -s CMC_API_KEY
    
    kubectl create secret generic skyeye-secrets \
        --from-literal=COINMARKETCAP_API_KEY="$CMC_API_KEY" \
        -n "$NAMESPACE"
    echo "✅ Secret创建完成"
else
    echo "✅ Secret已存在"
fi

# 构建和推送Docker镜像 (如果需要)
echo "🐳 6. 检查Docker镜像"
IMAGE_REPO=$(grep "repository:" k3s-values.yaml | awk '{print $2}' | tr -d '"')
IMAGE_TAG=$(grep "tag:" k3s-values.yaml | awk '{print $2}' | tr -d '"')
FULL_IMAGE="$IMAGE_REPO:$IMAGE_TAG"

echo "目标镜像: $FULL_IMAGE"
if docker images | grep -q "$IMAGE_REPO.*$IMAGE_TAG"; then
    echo "✅ 镜像已存在本地"
else
    echo "📦 构建Docker镜像..."
    docker build -t "$FULL_IMAGE" .
    echo "✅ 镜像构建完成"
fi

# 推送镜像到仓库 (如果需要)
if [[ "$IMAGE_REPO" == *"localhost"* ]] || [[ "$IMAGE_REPO" == *"k3d"* ]]; then
    echo "✅ 使用本地镜像仓库，无需推送"
else
    echo "📤 推送镜像到仓库..."
    docker push "$FULL_IMAGE" || echo "⚠️ 镜像推送失败，请检查仓库权限"
fi

# 部署应用
echo "🚀 7. 部署SkyEye应用"
helm upgrade --install "$RELEASE_NAME" ./charts \
    -f k3s-values.yaml \
    -n "$NAMESPACE" \
    --wait \
    --timeout=10m

echo "✅ 应用部署完成"

# 等待Pod就绪
echo "⏳ 8. 等待Pod就绪"
kubectl wait --for=condition=Ready pod -l app.kubernetes.io/name=app -n "$NAMESPACE" --timeout=300s
echo "✅ Pod就绪"

# 检查服务状态
echo "🔍 9. 检查服务状态"
echo "Pod状态:"
kubectl get pods -n "$NAMESPACE" -l app.kubernetes.io/name=app

echo -e "\n服务状态:"
kubectl get services -n "$NAMESPACE"

# 获取访问地址
echo -e "\n🌐 10. 获取访问信息"
NODE_PORT=$(kubectl get service "$RELEASE_NAME" -n "$NAMESPACE" -o jsonpath='{.spec.ports[0].nodePort}')
NODE_IP=$(kubectl get nodes -o jsonpath='{.items[0].status.addresses[?(@.type=="ExternalIP")].address}')
if [ -z "$NODE_IP" ]; then
    NODE_IP=$(kubectl get nodes -o jsonpath='{.items[0].status.addresses[?(@.type=="InternalIP")].address}')
fi

echo "访问地址: http://$NODE_IP:$NODE_PORT"
echo "API文档: http://$NODE_IP:$NODE_PORT/api/v1/"

# 功能验证
echo "🧪 11. 功能验证"
sleep 10  # 等待服务完全启动

echo "测试API响应..."
if curl -s -f "http://$NODE_IP:$NODE_PORT/api/v1/cmc/market-data?page=1&page_size=1" | grep -q '"ok":true'; then
    echo "✅ 市场数据API正常"
else
    echo "⚠️ 市场数据API异常，请检查日志"
fi

# 显示日志命令
echo -e "\n📋 12. 监控和调试命令"
echo "查看应用日志:"
echo "  kubectl logs -f deployment/$RELEASE_NAME -n $NAMESPACE"
echo "查看Celery Worker日志:"
echo "  kubectl logs -f deployment/$RELEASE_NAME-celery-worker -n $NAMESPACE"
echo "查看Celery Beat日志:"
echo "  kubectl logs -f deployment/$RELEASE_NAME-celery-beat -n $NAMESPACE"
echo "查看种子数据导入日志:"
echo "  kubectl logs job/$RELEASE_NAME-data-seed -n $NAMESPACE"

echo -e "\n进入容器调试:"
echo "  kubectl exec -it deployment/$RELEASE_NAME -n $NAMESPACE -- /bin/bash"

echo ""
echo "🎉 SkyEye K3s 部署完成！"
echo "========================"
echo "🌐 访问地址: http://$NODE_IP:$NODE_PORT"
echo "📊 监控: 可通过kubectl查看Pod和Service状态"
echo "🔄 数据同步: 定时任务将自动更新数据"