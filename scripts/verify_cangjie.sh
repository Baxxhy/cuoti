#!/usr/bin/env bash
set -euo pipefail
if [[ "${CANGJIE_VERIFY_BROWSER:-}" == "1" && -n "${CANGJIE_VERIFY_FOCUS:-}" ]]; then
  echo '完整浏览器验收不能启用聚焦模式；请清除 CANGJIE_VERIFY_FOCUS。' >&2
  exit 2
fi
project_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$project_dir"
db_socket=${CANGJIE_TEST_MYSQL_SOCKET:-$project_dir/.mysql-run/mysqld.sock}
mysql_admin=(mysql --socket="$db_socket" -uroot)
# Isolated, disposable database and account; never read the application's .env.
suffix=$(python -c 'import secrets; print(secrets.token_hex(6))')
export CANGJIE_DB_NAME="zhiwei_cangjie_test_$suffix"
export CANGJIE_DB_USER="cj_test_$suffix"
export CANGJIE_DB_PASSWORD=$(python -c 'import secrets; print(secrets.token_hex(24))')
export CANGJIE_DB_HOST=127.0.0.1
export CANGJIE_DB_PORT=${CANGJIE_TEST_MYSQL_PORT:-3307}
algorithm_tmp=$(mktemp -d /tmp/zhiwei-cangjie-algorithm.XXXXXX)
algorithm_pid=''
retrieval_pid=''
budget_pid=''
export CANGJIE_ALGORITHM_SECRET=$(python -c 'import secrets; print(secrets.token_hex(32))')
export CANGJIE_ALGORITHM_PORT=$(python -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1",0)); print(s.getsockname()[1]); s.close()')
export CANGJIE_ALGORITHM_URL="http://127.0.0.1:$CANGJIE_ALGORITHM_PORT"
# Recognition must fail explicitly during offline integration; never use the real pool.
export CANGJIE_API_POOL_PATH="$algorithm_tmp/missing-pool.json"
export CANGJIE_MEDIA_ROOT="$algorithm_tmp/media"
cleanup() {
  if [[ -n "$budget_pid" ]]; then
    kill "$budget_pid" 2>/dev/null || true
    wait "$budget_pid" 2>/dev/null || true
  fi
  if [[ -n "$retrieval_pid" ]]; then
    kill "$retrieval_pid" 2>/dev/null || true
    wait "$retrieval_pid" 2>/dev/null || true
  fi
  if [[ -n "$algorithm_pid" ]]; then
    kill "$algorithm_pid" 2>/dev/null || true
    wait "$algorithm_pid" 2>/dev/null || true
  fi
  rm -rf "$algorithm_tmp"
  "${mysql_admin[@]}" <<SQL
DROP DATABASE IF EXISTS \`$CANGJIE_DB_NAME\`;
DROP USER IF EXISTS '$CANGJIE_DB_USER'@'localhost';
SQL
}
trap cleanup EXIT
"${mysql_admin[@]}" <<SQL
CREATE DATABASE \`$CANGJIE_DB_NAME\` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER '$CANGJIE_DB_USER'@'localhost' IDENTIFIED WITH mysql_native_password BY '$CANGJIE_DB_PASSWORD';
GRANT ALL PRIVILEGES ON \`$CANGJIE_DB_NAME\`.* TO '$CANGJIE_DB_USER'@'localhost';
SQL
export CANGJIE_TEST_RETRIEVAL_STATE="$algorithm_tmp/retrieval.json"
export CANGJIE_TEST_RETRIEVAL_PORT=$(python -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1",0)); print(s.getsockname()[1]); s.close()')
export CANGJIE_QDRANT_URL="http://127.0.0.1:$CANGJIE_TEST_RETRIEVAL_PORT"
export CANGJIE_RETRIEVAL_INFERENCE_URL="$CANGJIE_QDRANT_URL"
printf '%s' '{"hits":[]}' > "$CANGJIE_TEST_RETRIEVAL_STATE"
"$project_dir/.venv/bin/python" scripts/cangjie_retrieval_fixture.py "$CANGJIE_TEST_RETRIEVAL_PORT" "$CANGJIE_TEST_RETRIEVAL_STATE" > "$algorithm_tmp/retrieval.log" 2>&1 &
retrieval_pid=$!
PYTHONPATH="$project_dir/backend:$project_dir/backend-algorithms" "$project_dir/.venv/bin/python" -m pytest -q backend-algorithms/tests
bash scripts/algorithms.sh > "$algorithm_tmp/service.log" 2>&1 &
algorithm_pid=$!
python - <<'PY'
import json, os, time
from urllib.error import URLError
from urllib.request import urlopen
deadline = time.monotonic() + 30
while True:
    try:
        with urlopen(os.environ['CANGJIE_ALGORITHM_URL'] + '/livez', timeout=1) as response:
            assert json.load(response)['service'] == 'zhiwei-algorithms'
        break
    except (URLError, TimeoutError):
        if time.monotonic() >= deadline:
            raise RuntimeError('独立算法服务启动超时') from None
        time.sleep(0.1)
PY
# Real algorithm responses pass through an isolated, test-only delay proxy.
export CANGJIE_TEST_BUDGET_STATE="$algorithm_tmp/budget.json"
export CANGJIE_TEST_BUDGET_EVENTS="$algorithm_tmp/budget-events.jsonl"
printf '%s' '{"rules":[]}' > "$CANGJIE_TEST_BUDGET_STATE"
budget_port=$(python -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1",0)); print(s.getsockname()[1]); s.close()')
"$project_dir/.venv/bin/python" scripts/cangjie_budget_fixture.py "$budget_port" "$CANGJIE_ALGORITHM_URL" "$CANGJIE_TEST_BUDGET_STATE" "$CANGJIE_TEST_BUDGET_EVENTS" > "$algorithm_tmp/budget.log" 2>&1 &
budget_pid=$!
export CANGJIE_ALGORITHM_URL="http://127.0.0.1:$budget_port"
python - "$budget_port" <<'PYPROXY'
import socket, sys, time
end=time.monotonic()+5
while True:
    try:
        with socket.create_connection(("127.0.0.1",int(sys.argv[1])),timeout=1): break
    except OSError:
        if time.monotonic()>end: raise RuntimeError("test proxy startup failed") from None
        time.sleep(0.05)
PYPROXY
bash scripts/cangjie.sh init-db
# A second initialization must refuse to overwrite the established schema.
if bash scripts/cangjie.sh init-db > /dev/null 2>&1; then
  echo '错误：数据库初始化覆盖保护未生效' >&2
  exit 1
fi
bash scripts/cangjie.sh test
"$project_dir/.venv/bin/python" scripts/smoke_cangjie.py
# Missing database configuration must report 503 rather than a false ready.
env -u CANGJIE_DB_NAME -u CANGJIE_DB_USER -u CANGJIE_DB_PASSWORD "$project_dir/.venv/bin/python" scripts/smoke_cangjie.py
