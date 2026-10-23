#!/usr/bin/env bash
set -euo pipefail
for name in cuoti-delivery-app cuoti-delivery-qdrant; do
 if docker inspect "$name" >/dev/null 2>&1; then
  [[ $(docker inspect --format '{{index .Config.Labels "app"}}' "$name") == cuoti-delivery ]] || { echo '容器归属不符，拒绝停止'; exit 1; }
  docker stop -t 60 "$name"
 fi
done
echo '程序已停止，学习数据保留。'
