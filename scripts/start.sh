#!/usr/bin/env bash
# AI 图文生成系统 Linux 一键启动脚本
# 用法：bash scripts/start.sh
set -e

cd "$(dirname "$0")/.."   # 回到项目根目录
ROOT=$(pwd)
PY="$ROOT/backend/venv/bin/python"
CELERY="$ROOT/backend/venv/bin/celery"
UVICORN="$ROOT/backend/venv/bin/uvicorn"

echo "============================================"
echo "  AI 图文生成项目 一键启动（Linux）"
echo "============================================"

# 依赖检查
command -v redis-server >/dev/null 2>&1 || { echo "错误：未安装 redis-server（apt install redis-server）"; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "错误：未安装 python3"; exit 1; }

# [1/4] 启动 Redis（未运行时）
if redis-cli ping >/dev/null 2>&1; then
    echo "[1/4] Redis 已在运行"
else
    echo "[1/4] 启动 Redis ..."
    redis-server --daemonize yes
    sleep 1
fi

# [2/4] 创建虚拟环境并安装依赖（不存在时）
if [ ! -f "$PY" ]; then
    echo "创建 Python 虚拟环境并安装依赖 ..."
    python3 -m venv "$ROOT/backend/venv"
    "$ROOT/backend/venv/bin/pip" install -r "$ROOT/backend/requirements.txt"
fi

# [3/4] 启动 Celery worker
echo "[3/4] 启动 Celery worker ..."
(cd "$ROOT/backend" && "$CELERY" -A celery_app worker --loglevel=info --concurrency=2) &
WORKER_PID=$!

# [4/4] 启动 FastAPI
echo "[4/4] 启动 FastAPI ..."
(cd "$ROOT/backend" && "$UVICORN" main:app --host 0.0.0.0 --port 8000) &
API_PID=$!

echo ""
echo "============================================"
echo "  后端已启动：http://localhost:8000"
echo "  Celery worker PID：$WORKER_PID"
echo "  FastAPI PID：$API_PID"
echo "  前端：cd frontend && npm install && npm run dev"
echo "  停止：kill $WORKER_PID $API_PID"
echo "============================================"

# 等待任一进程退出（Ctrl+C 时一起结束）
trap "kill $WORKER_PID $API_PID 2>/dev/null" EXIT
wait
