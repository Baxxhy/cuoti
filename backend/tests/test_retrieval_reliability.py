from types import SimpleNamespace

import pytest

from app.services import practice_retrieval


@pytest.mark.asyncio
async def test_hybrid_queries_allow_the_cold_index_to_finish(monkeypatch):
    queries = []
    connection_options = {}

    class ColdIndexClient:
        def __init__(self, *, url, timeout=5):
            connection_options["timeout"] = timeout
            self.timeout = timeout

        def query_points(self, _collection, **kwargs):
            if self.timeout < 60:
                raise TimeoutError("cold index exceeded the default request timeout")
            queries.append(kwargs.get("using", "fused"))
            return SimpleNamespace(points=[SimpleNamespace(payload={"question_id": "matching-question"})])

    monkeypatch.setattr(practice_retrieval, "QdrantClient", ColdIndexClient)
    monkeypatch.setattr(practice_retrieval.bge_runtime, "embed", lambda _texts: ([[0.1, 0.2]], [{1: 0.5}]))
    fused, dense_ranks, sparse_ranks = await practice_retrieval.hybrid_ids("方程", "数学", "初一", "初中")
    assert connection_options["timeout"] == 60
    assert queries == ["dense", "sparse", "fused"]
    assert fused[0].payload["question_id"] == "matching-question"
    assert dense_ranks == sparse_ranks == {"matching-question": 1}
