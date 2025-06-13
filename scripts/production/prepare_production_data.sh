#!/bin/bash

# SkyEye 本地数据准备脚本
# 用途：在本地环境完整测试并准备生产环境的种子数据

set -e

echo "🧪 SkyEye 本地数据准备和测试"
echo "================================"

# 检查环境
if [ -z "$COINMARKETCAP_API_KEY" ]; then
    echo "❌ 错误: COINMARKETCAP_API_KEY 环境变量未设置"
    exit 1
fi

# 检查本地服务状态
echo "📋 1. 检查本地服务状态"
./scripts/manage_docker.sh status || {
    echo "🐳 启动本地 Docker 服务..."
    ./scripts/manage_docker.sh up
    sleep 10
}

# 等待数据库就绪
echo "⏳ 等待本地数据库就绪..."
timeout 30 bash -c 'until docker exec skyeye-db-master-1 pg_isready -U skyeye_user; do sleep 1; done'

# 检查Django服务
echo "🌐 检查Django服务..."
if ! curl -s -f http://localhost:8000 >/dev/null 2>&1; then
    echo "⚠️  Django服务未运行，请在另一个终端启动: uv run python manage.py runserver"
    echo "💡 等待Django服务启动后按回车继续..."
    read -p ""
fi

# 启动Celery服务
echo "⚙️ 2. 启动Celery服务"
./scripts/manage_celery.sh start || echo "Celery worker已运行"
./scripts/manage_celery.sh start-beat-db || echo "Celery beat已运行"
uv run python manage.py initialize_beat_tasks

sleep 3

# 检查当前数据状态
echo "📊 3. 检查当前数据状态"
ASSET_COUNT=$(uv run python manage.py shell -c "from apps.cmc_proxy.models import CmcAsset; print(CmcAsset.objects.count())" | tail -1)
KLINE_COUNT=$(uv run python manage.py shell -c "from apps.cmc_proxy.models import CmcKline; print(CmcKline.objects.count())" | tail -1)

echo "当前状态:"
echo "  - CmcAsset: $ASSET_COUNT 条"
echo "  - CmcKline: $KLINE_COUNT 条"

# 数据获取和测试流程
if [ "$ASSET_COUNT" -lt 5000 ]; then
    echo "🔄 4. 获取基础市场数据（CMC资产和行情）"
    echo "正在触发全量数据同步..."
    uv run python -c "from apps.cmc_proxy.tasks import daily_full_data_sync; daily_full_data_sync.delay()"
    
    echo "⏳ 等待数据获取完成（可能需要2-5分钟）..."
    for i in {1..30}; do  # 最多等待5分钟
        sleep 10
        CURRENT_COUNT=$(uv run python manage.py shell -c "from apps.cmc_proxy.models import CmcAsset; print(CmcAsset.objects.count())" | tail -1)
        echo "  进度: $CURRENT_COUNT 个资产已同步"
        if [ "$CURRENT_COUNT" -gt 5000 ]; then
            echo "✅ 基础数据获取完成"
            break
        fi
    done
else
    echo "✅ 基础数据充足，跳过获取步骤"
fi

# 获取K线数据
echo "📈 5. 获取K线历史数据"
if [ "$KLINE_COUNT" -lt 10000 ]; then
    echo "正在获取24小时K线数据..."
    uv run python manage.py update_cmc_klines --initialize --count=24 --run-once
    echo "✅ K线数据获取完成"
else
    echo "✅ K线数据充足，跳过获取步骤"
fi

# 获取其他业务数据
echo "💼 6. 获取代币相关业务数据"
echo "获取代币持仓数据..."
uv run python manage.py update_token_holdings --run-once 2>/dev/null || echo "代币持仓命令执行完成"

echo "获取代币解锁数据..."
uv run python manage.py update_token_unlocks --run-once 2>/dev/null || echo "代币解锁命令执行完成"

echo "获取代币分配数据..."
uv run python manage.py update_token_allocation --run-once 2>/dev/null || echo "代币分配命令执行完成"

# 功能测试
echo "🧪 7. 功能验证测试"
echo "测试核心API接口..."

# 测试市场数据API
echo -n "  - 市场数据API: "
if curl -s -f "http://localhost:8000/api/v1/cmc/market-data?page=1&page_size=1" | grep -q '"ok":true'; then
    echo "✅ 正常"
else
    echo "❌ 异常"
fi

# 测试K线数据API
echo -n "  - K线数据API: "
if curl -s -f "http://localhost:8000/api/v1/cmc/klines?cmc_id=1&limit=1" | grep -q '"ok":true'; then
    echo "✅ 正常"
else
    echo "❌ 异常"
fi

# 测试代币相关API
echo -n "  - 代币分配API: "
if curl -s -f "http://localhost:8000/api/v1/cmc/token-allocations?cmc_id=1" | grep -q '"ok":true'; then
    echo "✅ 正常"
else
    echo "⚠️  数据为空或异常"
fi

echo -n "  - 代币解锁API: "
if curl -s -f "http://localhost:8000/api/v1/cmc/token-unlocks?cmc_id=1" | grep -q '"ok":true'; then
    echo "✅ 正常"
else
    echo "⚠️  数据为空或异常"
fi

echo -n "  - 代币持仓API: "
if curl -s -f "http://localhost:8000/api/v1/cmc/holdings?cmc_id=1" | grep -q '"ok":true'; then
    echo "✅ 正常"
else
    echo "⚠️  数据为空或异常"
fi

# 数据统计
echo "📊 8. 数据统计汇总"
uv run python manage.py shell -c "
from apps.cmc_proxy.models import CmcAsset, CmcMarketData, CmcKline
from apps.price_oracle.models import AssetPrice
from apps.token_economics.models import TokenAllocation
from apps.token_holdings.models import TokenHolder
from apps.token_unlocks.models import TokenUnlock

print('=' * 40)
print('本地测试数据统计:')
print('=' * 40)
print(f'📊 CmcAsset (资产): {CmcAsset.objects.count():,} 条')
print(f'📊 CmcMarketData (行情): {CmcMarketData.objects.count():,} 条')
print(f'📊 CmcKline (K线): {CmcKline.objects.count():,} 条')
try:
    print(f'📊 AssetPrice (价格): {AssetPrice.objects.count():,} 条')
except: pass
try:
    print(f'📊 TokenAllocation (分配): {TokenAllocation.objects.count():,} 条')
except: pass
try:
    print(f'📊 TokenHolder (持仓): {TokenHolder.objects.count():,} 条')
except: pass
try:
    print(f'📊 TokenUnlock (解锁): {TokenUnlock.objects.count():,} 条')
except: pass

if CmcKline.objects.count() > 0:
    avg_klines = CmcKline.objects.count() / max(CmcAsset.objects.count(), 1)
    print(f'📊 平均每个资产K线数: {avg_klines:.1f}')
print('=' * 40)
"

# 数据导出
echo "💾 9. 导出生产环境种子数据"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DUMP_FILE="skyeye_production_seed_${TIMESTAMP}.sql"

echo "正在导出核心业务数据到: $DUMP_FILE"

pg_dump -h localhost -p 5430 -U skyeye_user -d skyeye \
  --exclude-table=django_migrations \
  --exclude-table=django_admin_log \
  --exclude-table=django_session \
  --exclude-table=auth_* \
  --exclude-table=django_celery_beat_* \
  --exclude-table=django_content_type \
  --exclude-table=django_celery_results_* \
  --data-only --inserts \
  --file="$DUMP_FILE"

# 验证导出文件
if [ -f "$DUMP_FILE" ]; then
    FILE_SIZE=$(du -h "$DUMP_FILE" | cut -f1)
    echo "✅ 数据导出完成: $DUMP_FILE ($FILE_SIZE)"
    
    # 创建快速导入脚本
    cat > "import_${DUMP_FILE%.sql}.sh" << EOF
#!/bin/bash
# 生产环境数据导入脚本 - 自动生成于 $(date)
echo "导入 SkyEye 种子数据: $DUMP_FILE"
psql -U skyeye_user -d skyeye < "$DUMP_FILE"
echo "✅ 种子数据导入完成"
EOF
    chmod +x "import_${DUMP_FILE%.sql}.sh"
    echo "✅ 创建导入脚本: import_${DUMP_FILE%.sql}.sh"
else
    echo "❌ 数据导出失败"
    exit 1
fi

echo ""
echo "🎉 本地数据准备完成！"
echo "================================"
echo "📁 生产环境文件:"
echo "  - 数据文件: $DUMP_FILE"
echo "  - 导入脚本: import_${DUMP_FILE%.sql}.sh"
echo ""
echo "📋 下一步操作:"
echo "  1. 将数据文件上传到生产服务器"
echo "  2. 运行生产环境部署脚本: ./scripts/production_deployment.sh"
echo ""
echo "💡 提示: 数据可能是陈旧的，但生产环境的定时任务会自动更新为最新数据"