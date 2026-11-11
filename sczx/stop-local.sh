#!/usr/bin/env bash
set -euo pipefail
sczx_root="$(cd -- "$(dirname -- "$0")" && pwd)"
exec "$sczx_root/start-local.sh" stop "$@"
