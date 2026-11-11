#!/usr/bin/env bash
set -euo pipefail
sczx_root="$(cd -- "$(dirname -- "$0")" && pwd)"
sczx_python="${SCZX_LOCAL_PYTHON:-$sczx_root/.venv/bin/python}"
if [[ ! -x "$sczx_python" ]]; then
  echo '请先运行 ./install-local.sh 安装本地依赖。' >&2
  exit 1
fi
exec "$sczx_python" "$sczx_root/scripts/local.py" "${@:-start}"
