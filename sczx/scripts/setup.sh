#!/usr/bin/env bash
set -euo pipefail
sczx_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
sczx_python="${SCZX_PYTHON:-python3}"
"$sczx_python" -m venv "$sczx_dir/.venv"
"$sczx_dir/.venv/bin/python" -m pip install -r "$sczx_dir/requirements.lock"
npm --prefix "$sczx_dir/frontend" ci --ignore-scripts --no-audit --no-fund --cache "$sczx_dir/.runtime/npm-cache"
printf '%s\n' '安装完成。按 README 配置独立 MySQL 和 .env 后启动。'
