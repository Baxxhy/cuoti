#!/usr/bin/env bash
set -euo pipefail
sczx_root="$(cd -- "$(dirname -- "$0")" && pwd)"
cd -- "$sczx_root"
for sczx_tool in python3 npm mysqld mysql mysqladmin; do
  command -v "$sczx_tool" >/dev/null || { echo "请先安装本地依赖：$sczx_tool" >&2; exit 1; }
done
python3 -m venv .venv
.venv/bin/python -m pip install -e backend-business
npm --prefix frontend ci
.venv/bin/python deploy/build_frontend.py
.venv/bin/python scripts/local.py init
printf '%s\n' '安装完成。运行 ./start-local.sh；账号见 backend-business/var/local/accounts.json。'
