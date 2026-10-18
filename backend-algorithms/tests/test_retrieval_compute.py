"""Cross-process comparison with retained retrieval and HTTP compute boundaries."""

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import retrieval_compute as retrieval
from fastapi.testclient import TestClient
from service import create_app


def snapshots():
    return [
        {
            "question": {
                "id": str(index),
                "subject": "数学",
                "grade": "七年级",
                "grade_band": "初中",
                "question_type": kind,
                "question_text": text,
                "options": [],
                "knowledge_points": ["一元一次方程"],
                "answer": answer,
                "solution": "移项并求解",
            },
            "source_dataset": "reference",
            "knowledge_points": [
                {"id": "kp", "name": "一元一次方程", "role": "primary"}
            ],
            "dense_rank": index,
            "sparse_rank": 3 - index,
            "fusion_rank": index,
            "fusion_score": 0.8,
        }
        for index, kind, text, answer in [
            (1, "填空题", "解方程 3x+4=19", "x=5"),
            (2, "综合题", "说明理由：求解 4x-7=9", "x=4"),
        ]
    ]


def test_reranker_matches_original_process(monkeypatch):
    rows = snapshots()
    code = """
import asyncio,json,sys
from dataclasses import asdict
from types import SimpleNamespace
from app.services import practice_retrieval as r
rows=json.load(sys.stdin)
r.bge_runtime.rerank=lambda query,documents:[0.6,0.7]
result={}
for mode in ("reinforce","variation"):
    candidates=[r.RetrievalCandidate(SimpleNamespace(**row["question"]),row["source_dataset"],row["knowledge_points"],row["dense_rank"],row["sparse_rank"],row["fusion_rank"],row["fusion_score"]) for row in rows]
    ranked=asyncio.run(r.rerank_candidates("query","解方程 2x+3=11","填空题",mode,candidates))
    result[mode]=[{**asdict(item),"question":vars(item.question)} for item in ranked]
print(json.dumps(result,ensure_ascii=False))
"""
    original = json.loads(
        subprocess.check_output(
            [sys.executable, "-c", code],
            input=json.dumps(rows).encode(),
            env={
                **os.environ,
                "PYTHONPATH": str(Path(__file__).resolve().parents[2] / "backend"),
            },
        )
    )
    monkeypatch.setattr(retrieval.bge_runtime, "rerank", lambda _q, _d: [0.6, 0.7])
    for mode in ("reinforce", "variation"):
        result = asyncio.run(
            retrieval.rank_snapshots(
                "query", "解方程 2x+3=11", "填空题", mode, rows, [], "practice"
            )
        )
        for item in result["ranked"]:
            item.pop("score_trace")
        assert result["ranked"] == original[mode]
    assert (
        asyncio.run(
            retrieval.rank_snapshots(
                "query",
                "解方程 2x+3=11",
                "填空题",
                "reinforce",
                rows,
                ["1", "2"],
                "practice",
            )
        )["ranked"]
        == []
    )
    assert (
        not {"app.db", "app.models", "app.config", "app.services.practice_retrieval"}
        & sys.modules.keys()
    )


def test_compute_search_and_revalidation(monkeypatch, tmp_path):
    calls = []
    closed = []

    class Index:
        def __init__(self, **_kwargs):
            pass

        def query_points(self, collection, **kwargs):
            calls.append((collection, kwargs))
            return SimpleNamespace(
                points=[
                    SimpleNamespace(payload={"question_id": "fixture-id"}, score=0.8)
                ]
            )

        def close(self):
            closed.append(True)

    monkeypatch.setattr(retrieval, "QdrantClient", Index)
    monkeypatch.setattr(
        retrieval.bge_runtime,
        "embed",
        lambda _texts: ([[0.1, 0.9]], [{3: 0.5, 1: 0.3}]),
    )
    secret = "retrieval-test-" + "x" * 32
    with TestClient(
        create_app(secret=secret, pool_path=tmp_path / "missing.json")
    ) as client:
        headers = {"Authorization": "Bearer " + secret}
        search = client.post(
            "/v1/compute",
            headers=headers,
            json={
                "operation": "retrieval_search",
                "retrieval_query": "方程",
                "subject": "数学",
                "grade": "七年级",
                "grade_band": "初中",
            },
        )
        assert (
            search.status_code == 200
            and search.json()["result"]["hits"][0]["dense_rank"] == 1
        )
        assert len(calls) == 3 and closed == [True]
        assert calls[1][1]["query"].indices == [1, 3]
        filters = calls[0][1]["query_filter"].model_dump()
        assert filters["must"][0]["match"]["value"] == "数学"
        assert {
            item["match"]["value"] for item in filters["min_should"]["conditions"]
        } == {"初一", "初中"}
        candidate = {
            "question_text": "解方程：3x+4=19",
            "answer": "x=5",
            "explanation": "移项后除以3",
            "reference_solution": ["3x=15", "x=5"],
        }
        payload = {
            "operation": "validate_variant",
            "text": "一元一次方程：2x+3=11",
            "subject": "数学",
            "knowledge_points": ["一元一次方程"],
            "variant_candidate": candidate,
        }
        assert (
            client.post("/v1/compute", headers=headers, json=payload).json()["result"][
                "valid"
            ]
            is True
        )
        payload["variant_candidate"] = {**candidate, "answer": "x=99"}
        assert (
            client.post("/v1/compute", headers=headers, json=payload).json()["result"][
                "valid"
            ]
            is False
        )
        assert client.post("/v1/compute", json=payload).status_code == 401
