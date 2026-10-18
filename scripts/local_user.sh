#!/usr/bin/env bash
set -euo pipefail
project_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$project_dir"
# Same trusted local configuration as final.sh; never print its values.
if [[ -f .env.cangjie ]]; then
  set -a
  source .env.cangjie
  set +a
fi
exec "$project_dir/.venv/bin/python" scripts/local_user.py "$@"
