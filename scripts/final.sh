#!/usr/bin/env bash
# Foreground supervisor: Ctrl+C stops only the process groups started here.
set -euo pipefail
project_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$project_dir"
if [[ -f .env.cangjie ]]; then
  set -a
  source .env.cangjie
  set +a
fi
if [[ ${1:-start} == check ]]; then
  exec "$project_dir/.venv/bin/python" scripts/check_final.py
fi
if [[ ${1:-start} != start ]]; then
  echo '用法：bash scripts/final.sh [start|check]' >&2
  exit 2
fi
if [[ -z ${CANGJIE_DB_PASSWORD:-} || ${CANGJIE_DB_PASSWORD:-} == replace-with-your-local-database-password ]]; then
  echo '先按 .env.cangjie.example 配置独立 MySQL；启动器不会创建或覆盖数据库。' >&2
  exit 1
fi
export CANGJIE_BACKEND_PORT=${CANGJIE_BACKEND_PORT:-8002}
export CANGJIE_ALGORITHM_PORT=${CANGJIE_ALGORITHM_PORT:-8012}
export CANGJIE_ALGORITHM_URL="http://127.0.0.1:$CANGJIE_ALGORITHM_PORT"
export ZHIWEI_FRONTEND_PORT=${ZHIWEI_FRONTEND_PORT:-5174}
export ZHIWEI_BACKEND_URL="http://127.0.0.1:$CANGJIE_BACKEND_PORT"
mkdir -p .runtime
if [[ -z ${CANGJIE_ALGORITHM_SECRET:-} ]]; then
  secret_file="$project_dir/.runtime/cangjie-algorithm-secret"
  (
    umask 077
    exec 9<>"$secret_file"
    flock -x 9
    if [[ ! -s "$secret_file" ]]; then openssl rand -hex 48 >&9; fi
  )
  export CANGJIE_ALGORITHM_SECRET=$(cat "$secret_file")
fi
# Refuse occupied ports before launching; do not attach to unrelated old services.
"$project_dir/.venv/bin/python" - <<'PY'
import os, socket
for name in ('CANGJIE_BACKEND_PORT', 'CANGJIE_ALGORITHM_PORT', 'ZHIWEI_FRONTEND_PORT'):
    with socket.socket() as probe:
        try:
            probe.bind(('127.0.0.1', int(os.environ[name])))
        except OSError:
            raise SystemExit(f'{name} 已被占用，请停止旧服务或调整端口') from None
PY
bash scripts/cangjie.sh build
children=()
cleanup() {
  trap - EXIT INT TERM
  for child in "${children[@]}"; do kill -TERM -- "-$child" 2>/dev/null || true; done
  for child in "${children[@]}"; do wait "$child" 2>/dev/null || true; done
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
setsid bash scripts/algorithms.sh &
children+=("$!")
setsid bash scripts/cangjie.sh run-built &
children+=("$!")
setsid npm --prefix frontend run dev:h5 -- --port "$ZHIWEI_FRONTEND_PORT" --strictPort &
children+=("$!")
echo "最终架构已启动；前端 http://127.0.0.1:$ZHIWEI_FRONTEND_PORT。Ctrl+C 停止本次服务。"
echo '另一个终端运行 make check-final 检查就绪；不会隐式初始化库或调用模型。'
wait -n "${children[@]}"
