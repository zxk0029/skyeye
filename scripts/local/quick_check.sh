#!/bin/bash
echo "🔍 SkyEye 系统状态检查"
echo "======================"

# 检查环境变量
echo "📋 1. 检查环境配置..."
source .venv/bin/activate && python scripts/check_env.py --quiet 2>/dev/null && echo "✅ 环境配置正常" || echo "❌ 环境配置异常"

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

# 5.1 市场数据 API - 分页查询
curl -s "http://localhost:8000/api/v1/cmc/market-data?page=1&page_size=1" | grep -q '"ok": true' && echo "  ✅ 市场数据 API (分页)" || echo "  ❌ 市场数据 API (分页)"

# 5.2 市场数据 API - 单个资产查询 (BTC)
curl -s "http://localhost:8000/api/v1/cmc/market-data?cmc_id=1" | grep -q '"ok": true' && echo "  ✅ 市场数据 API (单个资产)" || echo "  ❌ 市场数据 API (单个资产)"

# 5.3 市场数据 API - 多个资产查询 (BTC, ETH, DOGE)
curl -s "http://localhost:8000/api/v1/cmc/market-data?cmc_ids=1,1027,74" | grep -q '"ok": true' && echo "  ✅ 市场数据 API (多个资产)" || echo "  ❌ 市场数据 API (多个资产)"

# 5.4 代币经济模型 API
curl -s "http://localhost:8000/api/v1/cmc/token-allocations?cmc_id=24220" | grep -q '"ok": true' && echo "  ✅ 代币经济模型 API" || echo "  ❌ 代币经济模型 API"

# 5.5 代币解锁信息 API
curl -s "http://localhost:8000/api/v1/cmc/token-unlocks?page=1&page_size=1" | grep -q '"ok": true' && echo "  ✅ 代币解锁信息 API" || echo "  ❌ 代币解锁信息 API"

# 5.6 代币链上持仓 API
curl -s "http://localhost:8000/api/v1/cmc/holdings?cmc_id=6536" | grep -q '"ok": true' && echo "  ✅ 代币链上持仓 API" || echo "  ❌ 代币链上持仓 API"

# 5.7 K线数据 API - 单个资产
curl -s "http://localhost:8000/api/v1/cmc/klines?cmc_id=1027&hours=24" | grep -q '"ok": true' && echo "  ✅ K线数据 API (单个资产)" || echo "  ❌ K线数据 API (单个资产)"

# 5.8 K线数据 API - 分页查询
curl -s "http://localhost:8000/api/v1/cmc/klines?page=1&page_size=1&hours=24" | grep -q '"ok": true' && echo "  ✅ K线数据 API (分页)" || echo "  ❌ K线数据 API (分页)"

echo ""
echo "🎉 如果所有检查都显示 ✅，说明 SkyEye 系统运行正常！"
echo "📖 可以查看 OpenAPI 文档了解完整的 API 接口：skyeye-openapi.yaml"
echo ""
echo "📊 API 测试覆盖范围："
echo "   • 市场数据查询 (3种方式: 分页/单个/批量)"
echo "   • 代币经济模型查询"
echo "   • 代币解锁信息查询"
echo "   • 代币链上持仓查询"
echo "   • K线数据查询 (2种方式: 单个/分页)"