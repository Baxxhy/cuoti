#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"
source scripts/service_checks.sh
CONDA_ENV_NAME="${CONDA_ENV:-minddimension}"
CONDA_BIN="${CONDA_EXE:-$(command -v conda || true)}"
if [ -z "$CONDA_BIN" ]; then
  echo "找不到 Conda，请先加载 Conda 后再运行 make dev" >&2
  exit 1
fi
if ! command -v pnpm >/dev/null 2>&1; then
  USER_HOME_DIR="$(getent passwd "$(id -u)" | cut -d: -f6)"
  NVM_ROOT_DIR="${NVM_DIR:-$USER_HOME_DIR/.nvm}"
  PNPM_CANDIDATE="$(find "$NVM_ROOT_DIR/versions/node" -maxdepth 4 -path '*/bin/pnpm' 2>/dev/null | sort -V | tail -n 1)"
  if [ -z "$PNPM_CANDIDATE" ]; then
    echo "找不到 pnpm，请先安装 Node.js 并启用 pnpm" >&2
    exit 1
  fi
  export PATH="$(dirname "$PNPM_CANDIDATE"):$PATH"
fi
if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi
BACKEND_PORT="${ZHIWEI_BACKEND_PORT:-8000}"
FRONTEND_PORT="${ZHIWEI_FRONTEND_PORT:-5173}"
export ZHIWEI_BACKEND_URL="http://127.0.0.1:$BACKEND_PORT"
bash scripts/start_mysql.sh
bash scripts/start_retrieval.sh
if zhiwei_backend_ready "$ZHIWEI_BACKEND_URL"; then
  BACKEND_PID=""
  echo "backend=already_running $ZHIWEI_BACKEND_URL"
else
  PYTHONPATH=backend "$CONDA_BIN" run --no-capture-output -n "$CONDA_ENV_NAME" uvicorn app.main:app --host 0.0.0.0 --port "$BACKEND_PORT" &
  BACKEND_PID=$!
fi
if zhiwei_frontend_ready "http://127.0.0.1:$FRONTEND_PORT"; then
  FRONTEND_PID=""
  echo "frontend=already_running http://127.0.0.1:$FRONTEND_PORT"
else
  pnpm --dir frontend run dev:h5 -- --host 0.0.0.0 --port "$FRONTEND_PORT" --strictPort &
  FRONTEND_PID=$!
fi
if [ -n "$BACKEND_PID" ] || [ -n "$FRONTEND_PID" ]; then
  trap 'kill ${BACKEND_PID:-} ${FRONTEND_PID:-} 2>/dev/null || true' EXIT INT TERM
  wait
fi
