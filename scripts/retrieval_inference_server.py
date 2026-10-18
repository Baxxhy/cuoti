#!/usr/bin/env python3
from __future__ import annotations

import os
from pathlib import Path
from threading import Lock

from fastapi import FastAPI
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[1]
CACHE = Path(os.getenv("RETRIEVAL_MODEL_CACHE", ROOT / ".models/bge")).resolve()
EMBEDDING_MODEL = os.getenv("RETRIEVAL_EMBEDDING_MODEL", "BAAI/bge-m3")
RERANKER_MODEL = os.getenv("RETRIEVAL_RERANKER_MODEL", "BAAI/bge-reranker-v2-m3")
BATCH_SIZE = int(os.getenv("RETRIEVAL_BATCH_SIZE", "16"))
MAX_LENGTH = int(os.getenv("RETRIEVAL_MAX_LENGTH", "512"))
os.environ.setdefault("HF_HOME", str(CACHE))
os.environ.setdefault("TRANSFORMERS_CACHE", str(CACHE))


def resolve_devices() -> tuple[str, str]:
    """Select a portable CPU/single-GPU/two-GPU layout unless explicitly configured."""
    import torch

    gpu_count = torch.cuda.device_count() if torch.cuda.is_available() else 0
    embedding = os.getenv("RETRIEVAL_EMBEDDING_DEVICE") or ("cuda:0" if gpu_count else "cpu")
    reranker = os.getenv("RETRIEVAL_RERANKER_DEVICE") or (
        "cuda:1" if gpu_count > 1 else "cuda:0" if gpu_count == 1 else "cpu"
    )
    return embedding, reranker


app = FastAPI(title="错题帮 BGE 检索服务")
lock = Lock()
embedder = None
reranker = None


class EmbedRequest(BaseModel):
    texts: list[str] = Field(min_length=1, max_length=512)


class RerankRequest(BaseModel):
    query: str
    documents: list[str] = Field(min_length=1, max_length=100)


@app.get("/health")
def health() -> dict:
    import torch
    embedding_device, reranker_device = resolve_devices()
    return {
        "status": "healthy", "cuda": torch.cuda.is_available(), "gpu_count": torch.cuda.device_count(),
        "embedding_model": EMBEDDING_MODEL, "reranker_model": RERANKER_MODEL,
        "embedding_device": embedding_device, "reranker_device": reranker_device,
        "embedding_loaded": embedder is not None, "reranker_loaded": reranker is not None,
    }


@app.post("/embed")
def embed(payload: EmbedRequest) -> dict:
    global embedder
    with lock:
        if embedder is None:
            from FlagEmbedding import BGEM3FlagModel
            embedding_device, _ = resolve_devices()
            embedder = BGEM3FlagModel(
                EMBEDDING_MODEL, use_fp16=embedding_device.startswith("cuda"),
                devices=[embedding_device], cache_dir=str(CACHE),
            )
        output = embedder.encode(
            payload.texts, batch_size=BATCH_SIZE, max_length=MAX_LENGTH,
            return_dense=True, return_sparse=True, return_colbert_vecs=False,
        )
    return {
        "dense": output["dense_vecs"].tolist(),
        "sparse": [{str(key): float(value) for key, value in row.items()}
                   for row in output["lexical_weights"]],
    }


@app.post("/rerank")
def rerank(payload: RerankRequest) -> dict:
    global reranker
    with lock:
        if reranker is None:
            from FlagEmbedding import FlagReranker
            _, reranker_device = resolve_devices()
            reranker = FlagReranker(
                RERANKER_MODEL, use_fp16=reranker_device.startswith("cuda"),
                devices=[reranker_device], cache_dir=str(CACHE),
            )
        scores = reranker.compute_score(
            [[payload.query, document] for document in payload.documents], normalize=True,
            batch_size=BATCH_SIZE, max_length=MAX_LENGTH,
        )
    if not isinstance(scores, list):
        scores = [scores]
    return {"scores": [float(score) for score in scores]}
