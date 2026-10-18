#!/usr/bin/env bash
set -euo pipefail
project_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$project_dir"
if [[ -f .env.cangjie ]]; then
  set -a
  source .env.cangjie
  set +a
fi
bash scripts/cangjie.sh build
exec "$project_dir/.venv/bin/python" scripts/prepare_cangjie_question_bank.py "$@"
