#!/usr/bin/env bash
# Historical command alias; no compiler or Cangjie process is used.
set -euo pipefail
exec bash "$(dirname "${BASH_SOURCE[0]}")/question_bank.sh" "$@"
