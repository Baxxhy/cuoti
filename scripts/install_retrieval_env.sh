#!/usr/bin/env bash
set -euo pipefail

ENV_NAME="${RETRIEVAL_CONDA_ENV:-minddimension-retrieval}"
TORCH_FLAVOR="${RETRIEVAL_TORCH_FLAVOR:-auto}"

if ! conda env list | awk -v name="$ENV_NAME" '$1 == name { found=1 } END { exit !found }'; then
  conda create -n "$ENV_NAME" python=3.11 pip -y
fi

if [ "$TORCH_FLAVOR" = "auto" ]; then
  if command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi >/dev/null 2>&1; then
    TORCH_FLAVOR="cu128"
  else
    TORCH_FLAVOR="cpu"
  fi
fi

conda run --no-capture-output -n "$ENV_NAME" python -m pip install \
  --index-url "https://download.pytorch.org/whl/$TORCH_FLAVOR" 'torch==2.9.1'
conda run --no-capture-output -n "$ENV_NAME" python -m pip install \
  'transformers>=4.57,<5' 'tokenizers>=0.22,<0.23' \
  'FlagEmbedding>=1.4,<2' 'fastapi>=0.115' 'uvicorn[standard]>=0.34'

echo "retrieval_env=$ENV_NAME torch_flavor=$TORCH_FLAVOR ready"
