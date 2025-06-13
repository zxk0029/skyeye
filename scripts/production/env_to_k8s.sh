#!/bin/bash

# .env文件转换为Kubernetes ConfigMap和Secret的脚本
# 用途：将.env文件中的配置自动转换为K3s可用的ConfigMap和Secret

set -e

ENV_FILE="${1:-.env}"
NAMESPACE="${2:-skyeye}"
OUTPUT_DIR="${3:-./k8s-configs}"

echo "🔧 .env文件转K3s配置工具"
echo "=========================="
echo "  - 输入文件: $ENV_FILE"
echo "  - 命名空间: $NAMESPACE"
echo "  - 输出目录: $OUTPUT_DIR"
echo ""

# 检查.env文件是否存在
if [ ! -f "$ENV_FILE" ]; then
    echo "❌ 错误: 环境文件 '$ENV_FILE' 不存在"
    echo "💡 提示: 请先创建.env文件或指定正确的文件路径"
    echo "   例如: $0 .env.production skyeye"
    exit 1
fi

# 创建输出目录
mkdir -p "$OUTPUT_DIR"

# 定义敏感配置项 (将放入Secret)
SENSITIVE_KEYS=(
    "SECRET_KEY"
    "POSTGRES_PASSWORD"
    "REDIS_TRADING_PASSWORD"
    "COINMARKETCAP_API_KEY"
)

# 创建临时文件
CONFIGMAP_FILE="$OUTPUT_DIR/configmap-data.env"
SECRET_FILE="$OUTPUT_DIR/secret-data.env"

> "$CONFIGMAP_FILE"
> "$SECRET_FILE"

echo "🔍 分析.env文件..."

# 读取.env文件并分类
while IFS= read -r line || [ -n "$line" ]; do
    # 跳过注释和空行
    if [[ "$line" =~ ^[[:space:]]*# ]] || [[ -z "${line// }" ]]; then
        continue
    fi
    
    # 提取键值对
    if [[ "$line" =~ ^([^=]+)=(.*)$ ]]; then
        key="${BASH_REMATCH[1]}"
        value="${BASH_REMATCH[2]}"
        
        # 移除键和值的前后空格
        key=$(echo "$key" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
        value=$(echo "$value" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
        
        # 判断是否为敏感信息
        is_sensitive=false
        for sensitive_key in "${SENSITIVE_KEYS[@]}"; do
            if [[ "$key" == "$sensitive_key" ]]; then
                is_sensitive=true
                break
            fi
        done
        
        if [ "$is_sensitive" = true ]; then
            echo "$key=$value" >> "$SECRET_FILE"
            echo "  🔐 Secret: $key"
        else
            echo "$key=$value" >> "$CONFIGMAP_FILE"
            echo "  📝 ConfigMap: $key"
        fi
    fi
done < "$ENV_FILE"

echo ""
echo "📦 生成Kubernetes配置..."

# 生成ConfigMap YAML
if [ -s "$CONFIGMAP_FILE" ]; then
    cat > "$OUTPUT_DIR/configmap.yaml" << EOF
apiVersion: v1
kind: ConfigMap
metadata:
  name: skyeye-env-config
  namespace: $NAMESPACE
data:
$(while IFS= read -r line; do
    if [[ "$line" =~ ^([^=]+)=(.*)$ ]]; then
        key="${BASH_REMATCH[1]}"
        value="${BASH_REMATCH[2]}"
        # 处理特殊字符和多行值
        printf "  %s: %q\n" "$key" "$value"
    fi
done < "$CONFIGMAP_FILE")
EOF
    echo "✅ ConfigMap生成: $OUTPUT_DIR/configmap.yaml"
else
    echo "⚠️ 无ConfigMap数据"
fi

# 生成Secret YAML
if [ -s "$SECRET_FILE" ]; then
    cat > "$OUTPUT_DIR/secret.yaml" << EOF
apiVersion: v1
kind: Secret
metadata:
  name: skyeye-secrets
  namespace: $NAMESPACE
type: Opaque
data:
$(while IFS= read -r line; do
    if [[ "$line" =~ ^([^=]+)=(.*)$ ]]; then
        key="${BASH_REMATCH[1]}"
        value="${BASH_REMATCH[2]}"
        # Base64编码
        encoded_value=$(echo -n "$value" | base64 | tr -d '\n')
        printf "  %s: %s\n" "$key" "$encoded_value"
    fi
done < "$SECRET_FILE")
EOF
    echo "✅ Secret生成: $OUTPUT_DIR/secret.yaml"
else
    echo "⚠️ 无Secret数据"
fi

# 生成一键部署脚本
cat > "$OUTPUT_DIR/apply-configs.sh" << EOF
#!/bin/bash
# 一键应用.env配置到K3s集群
set -e

echo "🚀 应用SkyEye环境配置到K3s..."

# 创建命名空间
kubectl create namespace $NAMESPACE --dry-run=client -o yaml | kubectl apply -f -

# 应用ConfigMap
if [ -f "configmap.yaml" ]; then
    kubectl apply -f configmap.yaml
    echo "✅ ConfigMap应用完成"
fi

# 应用Secret
if [ -f "secret.yaml" ]; then
    kubectl apply -f secret.yaml
    echo "✅ Secret应用完成"
fi

echo "🎉 环境配置应用完成！"
echo ""
echo "📋 验证命令:"
echo "  kubectl get configmap skyeye-env-config -n $NAMESPACE -o yaml"
echo "  kubectl get secret skyeye-secrets -n $NAMESPACE"
EOF

chmod +x "$OUTPUT_DIR/apply-configs.sh"

# 生成验证脚本
cat > "$OUTPUT_DIR/verify-configs.sh" << EOF
#!/bin/bash
# 验证K3s中的环境配置
set -e

echo "🔍 验证SkyEye环境配置..."
echo ""

echo "📝 ConfigMap配置:"
kubectl get configmap skyeye-env-config -n $NAMESPACE -o jsonpath='{.data}' | jq '.' 2>/dev/null || \
kubectl get configmap skyeye-env-config -n $NAMESPACE -o yaml | grep -A 20 "data:"

echo ""
echo "🔐 Secret配置 (仅显示键名):"
kubectl get secret skyeye-secrets -n $NAMESPACE -o jsonpath='{.data}' | jq 'keys' 2>/dev/null || \
kubectl get secret skyeye-secrets -n $NAMESPACE -o yaml | grep -A 10 "data:" | grep ":" | awk '{print "  - " \$1}'

echo ""
echo "✅ 配置验证完成"
EOF

chmod +x "$OUTPUT_DIR/verify-configs.sh"

# 清理临时文件
rm -f "$CONFIGMAP_FILE" "$SECRET_FILE"

echo ""
echo "🎉 转换完成！"
echo "===================="
echo "📁 生成的文件:"
echo "  - $OUTPUT_DIR/configmap.yaml"
echo "  - $OUTPUT_DIR/secret.yaml"
echo "  - $OUTPUT_DIR/apply-configs.sh (一键部署)"
echo "  - $OUTPUT_DIR/verify-configs.sh (配置验证)"
echo ""
echo "📋 下一步操作:"
echo "  1. 检查生成的YAML文件"
echo "  2. 运行: cd $OUTPUT_DIR && ./apply-configs.sh"
echo "  3. 验证: cd $OUTPUT_DIR && ./verify-configs.sh"
echo ""
echo "💡 提示: 敏感信息已自动加密存储在Secret中"