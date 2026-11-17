#!/usr/bin/env bash
# Optional internal compute process; the unified backend runs it in-process.
set -euo pipefail
project_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$project_dir"
config_file=${CUOTI_ENV_FILE:-}
if [[ -z "$config_file" ]]; then
  if [[ -f .env.python ]]; then config_file=.env.python; else config_file=.env.cangjie; fi
fi
secret_root="$project_dir"
if [[ -f "$config_file" ]]; then
  secret_root=$(cd "$(dirname "$config_file")" && pwd)
  set -a
  source "$config_file"
  set +a
fi
if [[ -z ${CUOTI_ALGORITHM_SECRET:-${CANGJIE_ALGORITHM_SECRET:-}} ]]; then
  for secret_file in "$secret_root/.runtime/cuoti-algorithm-secret" "$secret_root/.runtime/cangjie-algorithm-secret"; do
    if [[ -f "$secret_file" ]]; then export CUOTI_ALGORITHM_SECRET=$(cat "$secret_file"); break; fi
  done
fi
export PYTHONPATH="$project_dir/backend-algorithms:$project_dir/backend-python${PYTHONPATH:+:$PYTHONPATH}"
exec "${CUOTI_PYTHON:-$project_dir/.venv/bin/python}" -m uvicorn service:create_app --factory \
  --host 127.0.0.1 --port "${CUOTI_ALGORITHM_PORT:-${CANGJIE_ALGORITHM_PORT:-8012}}" --no-access-log --log-level warning
