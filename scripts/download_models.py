#!/usr/bin/env python3
"""预下载错题帮使用的语音和检索模型。"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend-algorithms"))


def download_voice() -> None:
    from learning_core.services.voice import VoiceProvider

    provider = VoiceProvider()
    provider._load_model()
    print(f"voice=ready model={provider.model_name} path={provider.model_dir}")


def download_retrieval() -> None:
    cache = Path(os.getenv("RETRIEVAL_MODEL_CACHE", ROOT / ".models/bge")).resolve()
    os.environ.setdefault("HF_HOME", str(cache))
    from huggingface_hub import snapshot_download

    models = (
        os.getenv("RETRIEVAL_EMBEDDING_MODEL", "BAAI/bge-m3"),
        os.getenv("RETRIEVAL_RERANKER_MODEL", "BAAI/bge-reranker-v2-m3"),
    )
    for model in models:
        path = snapshot_download(repo_id=model, cache_dir=cache, ignore_patterns=[".DS_Store", "*/.DS_Store"],)
        print(f"retrieval=ready model={model} path={path}")


async def main() -> None:
    parser = argparse.ArgumentParser(description="下载语音或 BGE 检索模型")
    parser.add_argument("--voice", action="store_true", help="下载 faster-whisper small")
    parser.add_argument("--retrieval", action="store_true", help="下载 BGE-M3 与 BGE reranker")
    args = parser.parse_args()
    if not any((args.voice, args.retrieval)):
        parser.error("请指定 --voice 或 --retrieval")
    if args.voice:
        await asyncio.to_thread(download_voice)
    if args.retrieval:
        await asyncio.to_thread(download_retrieval)


if __name__ == "__main__":
    asyncio.run(main())
