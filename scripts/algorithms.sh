#!/usr/bin/env bash
set -euo pipefail
project_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
export PYTHONPATH="$project_dir/backend:$project_dir/backend-algorithms"
if [[ -z ${CANGJIE_ALGORITHM_SECRET:-} ]]; then
  echo '请设置独立的 CANGJIE_ALGORITHM_SECRET（至少 32 字符）' >&2
  exit 1
fi
exec "$project_dir/.venv/bin/python" -m uvicorn service:create_app --factory \
  --host 127.0.0.1 --port "${CANGJIE_ALGORITHM_PORT:-8012}" --no-access-log --log-level warning
