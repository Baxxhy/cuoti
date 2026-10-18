#!/usr/bin/env bash
# 仅检查本项目服务，避免复用同一端口上其他项目的 HTTP 200 响应。
zhiwei_backend_ready() {
  local base_url="$1"
  curl --max-time 3 -fsS "$base_url/api/v1/system/health" >/dev/null 2>&1 || return 1
  curl --max-time 3 -fsS "$base_url/openapi.json" 2>/dev/null |
    python3 -c 'import json,sys; sys.exit(json.load(sys.stdin).get("info", {}).get("title") != "错题帮 API")' 2>/dev/null
}

zhiwei_frontend_ready() {
  curl --max-time 3 -fsS "$1/" 2>/dev/null | grep -q '<title>错题帮</title>'
}
