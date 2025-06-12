#!/bin/bash

# SkyEye 生产环境配置准备脚本
# 用途：将开发环境的.env文件调整为适合K3s生产环境的配置

set -e

echo "🔧 SkyEye 生产环境配置准备"
echo "=========================="

ENV_FILE=".env"
BACKUP_FILE=".env.dev.backup"

# 检查.env文件是否存在
if [ ! -f "$ENV_FILE" ]; then
    echo "❌ 错误: 未找到 $ENV_FILE 文件"
    echo "💡 请先运行: bash scripts/setup_env.sh"
    exit 1
fi

# 备份当前的.env文件
echo "📦 备份当前配置到: $BACKUP_FILE"
cp "$ENV_FILE" "$BACKUP_FILE"

echo "🔍 当前环境检测..."
if grep -q "127.0.0.1\|localhost" "$ENV_FILE"; then
    echo "📋 检测到开发环境配置，准备调整为生产环境..."
    
    # 创建临时文件
    TEMP_FILE=$(mktemp)
    
    # 逐行处理.env文件
    while IFS= read -r line || [ -n "$line" ]; do
        # 跳过注释和空行，直接保留
        if [[ "$line" =~ ^[[:space:]]*# ]] || [[ -z "${line// }" ]]; then
            echo "$line" >> "$TEMP_FILE"
            continue
        fi
        
        # 处理配置项
        if [[ "$line" =~ ^([^=]+)=(.*)$ ]]; then
            key="${BASH_REMATCH[1]}"
            value="${BASH_REMATCH[2]}"
            
            case "$key" in
                "DEBUG")
                    echo "DEBUG=False" >> "$TEMP_FILE"
                    echo "  🔧 $key: True → False"
                    ;;
                "ALLOWED_HOSTS")
                    echo "ALLOWED_HOSTS=*" >> "$TEMP_FILE"
                    echo "  🔧 $key: 更新为通配符"
                    ;;
                "POSTGRES_HOST_MASTER")
                    echo "POSTGRES_HOST_MASTER=postgres-master-service" >> "$TEMP_FILE"
                    echo "  🔧 $key: localhost → postgres-master-service"
                    ;;
                "POSTGRES_HOST_SLAVE")
                    echo "POSTGRES_HOST_SLAVE=postgres-slave-service" >> "$TEMP_FILE"
                    echo "  🔧 $key: localhost → postgres-slave-service"
                    ;;
                "POSTGRES_PORT_MASTER")
                    echo "POSTGRES_PORT_MASTER=5432" >> "$TEMP_FILE"
                    echo "  🔧 $key: 5430 → 5432 (K3s标准端口)"
                    ;;
                "POSTGRES_PORT_SLAVE")
                    echo "POSTGRES_PORT_SLAVE=5432" >> "$TEMP_FILE"
                    echo "  🔧 $key: 5431 → 5432 (K3s标准端口)"
                    ;;
                "REDIS_URL")
                    echo "REDIS_URL=redis://redis-service:6379/0" >> "$TEMP_FILE"
                    echo "  🔧 $key: localhost → redis-service"
                    ;;
                "REDIS_CMC_URL")
                    echo "REDIS_CMC_URL=redis://redis-service:6379/1" >> "$TEMP_FILE"
                    echo "  🔧 $key: localhost → redis-service"
                    ;;
                "REDIS_TRADING_HOST")
                    echo "REDIS_TRADING_HOST=redis-service" >> "$TEMP_FILE"
                    echo "  🔧 $key: 127.0.0.1 → redis-service"
                    ;;
                "CELERY_BROKER_URL")
                    echo "CELERY_BROKER_URL=redis://redis-service:6379/0" >> "$TEMP_FILE"
                    echo "  🔧 $key: localhost → redis-service"
                    ;;
                "CELERY_RESULT_BACKEND")
                    echo "CELERY_RESULT_BACKEND=redis://redis-service:6379/0" >> "$TEMP_FILE"
                    echo "  🔧 $key: localhost → redis-service"
                    ;;
                *)
                    # 其他配置项保持不变
                    echo "$line" >> "$TEMP_FILE"
                    ;;
            esac
        else
            # 不符合key=value格式的行直接保留
            echo "$line" >> "$TEMP_FILE"
        fi
    done < "$ENV_FILE"
    
    # 替换原文件
    mv "$TEMP_FILE" "$ENV_FILE"
    echo "✅ 生产环境配置调整完成"
    
else
    echo "✅ 配置已经是生产环境格式"
fi

echo ""
echo "🔍 生产环境配置检查..."

# 检查必需的配置项
check_required_config() {
    local key=$1
    local description=$2
    local current_value=$(grep "^$key=" "$ENV_FILE" | cut -d'=' -f2- | tr -d '"')
    
    if [ -z "$current_value" ]; then
        echo "❌ $key: 未配置"
        return 1
    elif [[ "$current_value" == *"your-"* ]] || [[ "$current_value" == *"example"* ]] || [[ "$current_value" == *"changeme"* ]]; then
        echo "⚠️  $key: 仍为示例值，需要填入真实值"
        return 1
    else
        echo "✅ $key: 已配置"
        return 0
    fi
}

echo "📋 必需配置检查:"
needs_manual_config=0

if ! check_required_config "COINMARKETCAP_API_KEY" "CoinMarketCap API密钥"; then
    needs_manual_config=1
fi

if ! check_required_config "POSTGRES_PASSWORD" "数据库密码"; then
    needs_manual_config=1
fi

# 检查生产环境安全配置
echo ""
echo "📋 生产环境安全检查:"
debug_value=$(grep "^DEBUG=" "$ENV_FILE" | cut -d'=' -f2)
if [ "$debug_value" = "False" ]; then
    echo "✅ DEBUG: 已关闭"
else
    echo "⚠️  DEBUG: 建议设置为False"
    needs_manual_config=1
fi

secret_key=$(grep "^SECRET_KEY=" "$ENV_FILE" | cut -d'=' -f2)
if [ ${#secret_key} -ge 50 ]; then
    echo "✅ SECRET_KEY: 长度充足"
else
    echo "⚠️  SECRET_KEY: 长度不足，建议重新生成"
    needs_manual_config=1
fi

echo ""
if [ $needs_manual_config -eq 1 ]; then
    echo "⚠️  发现需要手动配置的项目"
    echo "📝 请编辑 $ENV_FILE 文件，完善以下配置:"
    echo "   nano $ENV_FILE"
    echo ""
    echo "🔑 重要提醒:"
    echo "   - COINMARKETCAP_API_KEY: 从 https://coinmarketcap.com/api/ 获取"
    echo "   - POSTGRES_PASSWORD: 设置强密码"
    echo "   - 如需重新生成SECRET_KEY: bash scripts/generate_secret_key.sh --update-env"
    echo ""
    echo "✅ 配置完成后，再次运行此脚本验证"
else
    echo "🎉 生产环境配置检查通过！"
    echo ""
    echo "📋 配置摘要:"
    echo "   - 数据库: postgres-*-service:5432"
    echo "   - Redis: redis-service:6379"
    echo "   - DEBUG: 已关闭"
    echo "   - API密钥: 已配置"
    echo ""
    echo "📁 文件:"
    echo "   - 生产配置: $ENV_FILE"
    echo "   - 开发备份: $BACKUP_FILE"
    echo ""
    echo "🚀 现在可以运行部署脚本:"
    echo "   ./scripts/production_deployment.sh skyeye_production_seed_*.sql"
fi