#!/usr/bin/env bash
set -euo pipefail

# 仅负责启动未运行的服务；不会停止、重启或清理任何已有进程。
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"
source scripts/service_checks.sh

BACKEND_LOG="${ZHIWEI_BACKEND_LOG:-/tmp/zhiwei-backend.log}"
FRONTEND_LOG="${ZHIWEI_FRONTEND_LOG:-/tmp/zhiwei-frontend.log}"
BACKEND_PID_FILE="${ZHIWEI_BACKEND_PID_FILE:-/tmp/zhiwei-backend.pid}"
FRONTEND_PID_FILE="${ZHIWEI_FRONTEND_PID_FILE:-/tmp/zhiwei-frontend.pid}"
CONDA_ENV_NAME="${CONDA_ENV:-minddimension}"
STARTUP_TIMEOUT="${ZHIWEI_STARTUP_TIMEOUT:-180}"
CONDA_BIN="${CONDA_EXE:-/root/miniconda3/bin/conda}"
PNPM_BIN="$(command -v pnpm || true)"

if [ -z "$PNPM_BIN" ]; then
  PNPM_BIN="$(find "$(getent passwd "$(id -u)" | cut -d: -f6)/.nvm/versions/node" -maxdepth 4 -path '*/bin/pnpm' 2>/dev/null | sort -V | tail -n 1)"
fi
if [ ! -x "$CONDA_BIN" ]; then
  echo "找不到 Conda：$CONDA_BIN" >&2
  exit 1
fi
if [ -z "$PNPM_BIN" ] || [ ! -x "$PNPM_BIN" ]; then
  echo "找不到 pnpm，请先安装 Node.js/pnpm" >&2
  exit 1
fi
export PATH="$(dirname "$PNPM_BIN"):$PATH"

if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi
BACKEND_PORT="${ZHIWEI_BACKEND_PORT:-8000}"
FRONTEND_PORT="${ZHIWEI_FRONTEND_PORT:-5173}"
BACKEND_URL="http://127.0.0.1:$BACKEND_PORT/api/v1/system/health"
FRONTEND_URL="http://127.0.0.1:$FRONTEND_PORT/"
export ZHIWEI_BACKEND_URL="http://127.0.0.1:$BACKEND_PORT"

pid_alive() {
  local pid_file="$1"
  [ -s "$pid_file" ] && kill -0 "$(cat "$pid_file")" 2>/dev/null
}

if zhiwei_backend_ready "$ZHIWEI_BACKEND_URL"; then
  echo "backend=already_running http://127.0.0.1:$BACKEND_PORT"
elif pid_alive "$BACKEND_PID_FILE"; then
  echo "backend=start_in_progress pid=$(cat "$BACKEND_PID_FILE") log=$BACKEND_LOG"
else
  setsid nohup env PYTHONPATH="$ROOT_DIR/backend" "$CONDA_BIN" run --no-capture-output -n "$CONDA_ENV_NAME" \
    python -m uvicorn app.main:app --host 0.0.0.0 --port "$BACKEND_PORT" \
    >>"$BACKEND_LOG" 2>&1 < /dev/null &
  echo $! >"$BACKEND_PID_FILE"
  echo "backend=started pid=$(cat "$BACKEND_PID_FILE") log=$BACKEND_LOG"
fi

if zhiwei_frontend_ready "${FRONTEND_URL%/}"; then
  echo "frontend=already_running http://127.0.0.1:$FRONTEND_PORT"
elif pid_alive "$FRONTEND_PID_FILE"; then
  echo "frontend=start_in_progress pid=$(cat "$FRONTEND_PID_FILE") log=$FRONTEND_LOG"
else
  # 轮询监听不占用大量 inotify watcher，源码修改仍会被 Vite 热更新。
  setsid nohup env CHOKIDAR_USEPOLLING=true CHOKIDAR_INTERVAL=1000 \
    "$PNPM_BIN" --dir frontend run dev:h5 -- --host 0.0.0.0 --port "$FRONTEND_PORT" --strictPort \
    >>"$FRONTEND_LOG" 2>&1 < /dev/null &
  echo $! >"$FRONTEND_PID_FILE"
  echo "frontend=started pid=$(cat "$FRONTEND_PID_FILE") log=$FRONTEND_LOG"
fi

startup_deadline=$((SECONDS + STARTUP_TIMEOUT))
while [ "$SECONDS" -lt "$startup_deadline" ]; do
  backend_ready=false
  frontend_ready=false
  zhiwei_backend_ready "$ZHIWEI_BACKEND_URL" && backend_ready=true
  zhiwei_frontend_ready "${FRONTEND_URL%/}" && frontend_ready=true
  if [ "$backend_ready" = true ] && [ "$frontend_ready" = true ]; then
    echo "services=ready frontend=$FRONTEND_PORT backend=$BACKEND_PORT mysql=3307"
    exit 0
  fi
  sleep 1
done

echo "services=starting backend=$backend_ready frontend=$frontend_ready" >&2
exit 1
