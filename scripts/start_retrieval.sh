#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi
RETRIEVAL_ENV_NAME="${RETRIEVAL_CONDA_ENV:-minddimension-retrieval}"
QDRANT_CONTAINER_NAME="minddimension-qdrant"
QDRANT_STORAGE_PATH="$ROOT_DIR/data/qdrant_storage"
RETRIEVAL_IMPORT_PATH="$ROOT_DIR${RETRIEVAL_PYTHONPATH:+:$RETRIEVAL_PYTHONPATH}"

mkdir -p "$QDRANT_STORAGE_PATH" .models/bge
if docker container inspect "$QDRANT_CONTAINER_NAME" >/dev/null 2>&1; then
  docker start "$QDRANT_CONTAINER_NAME" >/dev/null
else
  docker run -d --name "$QDRANT_CONTAINER_NAME" --restart unless-stopped \
    -p 6333:6333 -p 6334:6334 -v "$QDRANT_STORAGE_PATH:/qdrant/storage" \
    qdrant/qdrant:latest >/dev/null
fi

if ! curl --max-time 3 -fsS http://127.0.0.1:8011/health >/dev/null 2>&1; then
  CONDA_BIN="${CONDA_EXE:-$(command -v conda || true)}"
  if [ -z "$CONDA_BIN" ] || ! env PYTHONPATH="$RETRIEVAL_IMPORT_PATH" "$CONDA_BIN" run -n "$RETRIEVAL_ENV_NAME" python -c 'import uvicorn.config, fastapi; from importlib.metadata import version; assert version("transformers").split(".")[0] == "4"' >/dev/null 2>&1; then
    echo "Conda 环境 $RETRIEVAL_ENV_NAME 缺少完整或兼容的服务依赖（需要 Transformers 4.x），请先修复环境（make install-retrieval）。已有模型和索引已保留。" >&2
    exit 1
  fi
  setsid nohup env RETRIEVAL_MODEL_CACHE="$(pwd)/.models/bge" PYTHONPATH="$RETRIEVAL_IMPORT_PATH" \
    "$CONDA_BIN" run --no-capture-output -n "$RETRIEVAL_ENV_NAME" \
    uvicorn scripts.retrieval_inference_server:app --host 127.0.0.1 --port 8011 \
    >/tmp/zhiwei-retrieval.log 2>&1 < /dev/null &
  echo $! >/tmp/zhiwei-retrieval.pid
fi

startup_deadline=$((SECONDS + ${RETRIEVAL_STARTUP_TIMEOUT:-180}))
while [ "$SECONDS" -lt "$startup_deadline" ]; do
  if curl --max-time 3 -fsS http://127.0.0.1:6333/ >/dev/null 2>&1 \
     && curl --max-time 3 -fsS http://127.0.0.1:8011/health >/dev/null 2>&1; then
    echo "retrieval=ready qdrant=http://127.0.0.1:6333 inference=http://127.0.0.1:8011"
    exit 0
  fi
  sleep 1
done
echo "retrieval=failed" >&2
exit 1
