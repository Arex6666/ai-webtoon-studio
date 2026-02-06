#!/bin/bash
# AI Webtoon Studio 开发启动脚本
# 使用方法: ./scripts/start-dev.sh

echo "🚀 启动 AI Webtoon Studio 开发环境..."

# 检查 Python 虚拟环境
if [ ! -d "apps/api/venv" ]; then
    echo "📦 创建 Python 虚拟环境..."
    cd apps/api
    python3 -m venv venv
    cd ../..
fi

# 启动所有服务
echo "🔌 启动后端 API..."
cd apps/api
source venv/bin/activate
pip install -r requirements.txt > /dev/null 2>&1
uvicorn app.main:app --reload --port 8000 &
API_PID=$!

echo "⚙️ 启动 Celery Worker..."
celery -A app.celery_app:celery_app worker --loglevel=info &
CELERY_PID=$!

cd ../..

echo "🎨 启动前端..."
cd apps/web
npm install > /dev/null 2>&1
npm run dev &
WEB_PID=$!

cd ../..

echo ""
echo "✨ 所有服务已启动！"
echo ""
echo "  📝 后端 API:    http://localhost:8000"
echo "  📚 API 文档:    http://localhost:8000/docs"
echo "  🎨 前端:        http://localhost:3000"
echo ""
echo "按 Ctrl+C 停止所有服务"

# 等待中断信号
trap "kill $API_PID $CELERY_PID $WEB_PID 2>/dev/null; exit" SIGINT SIGTERM
wait
