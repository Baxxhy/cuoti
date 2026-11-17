#!/usr/bin/env bash
set -euo pipefail
project_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$project_dir"
if [[ -f .env.cangjie ]]; then
  set -a
  source .env.cangjie
  set +a
fi
export PYTHONPATH="$project_dir/backend-python:$project_dir/backend-algorithms${PYTHONPATH:+:$PYTHONPATH}"
exec "${CUOTI_PYTHON:-$project_dir/.venv/bin/python}" scripts/prepare_question_bank.py "$@"
