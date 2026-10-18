import asyncio
import json
import sys

import httpx
from app.providers.api_pool import ApiPoolProvider
from fastapi.testclient import TestClient
from service import create_app

SECRET = "variant-test-" + "x" * 32
HEADERS = {"Authorization": "Bearer " + SECRET}


def test_variant_generation_and_verified_fallback(tmp_path):
    pool = tmp_path / "pool.json"
    pool.write_text(
        json.dumps(
            [
                {
                    "base_url": "http://variant.test/v1",
                    "api_key": "private-fixture",
                    "model": "Qwen",
                }
            ]
        )
    )
    provider = ApiPoolProvider(pool)
    asyncio.run(provider._client.aclose())
    state = {"mode": "good"}

    def upstream(request):
        body = json.loads(request.content)
        assert body["model"] == "Qwen"
        if state["mode"] == "fail":
            return httpx.Response(503, json={"error": "private-fixture"})
        result = {
            "question_text": "解方程：3x+4=19",
            "answer": "x=5",
            "reference_solution": ["3x=15", "x=5"],
            "explanation": "等式两边先减4，再除以3。",
        }
        if state["mode"] == "wrong":
            result["answer"] = "x=99"
        if state["mode"] == "unrelated":
            result["question_text"] = "求菱形的面积。"
        if state["mode"] == "invalid":
            result["reference_solution"] = {"bad": "shape"}
        return httpx.Response(
            200, json={"choices": [{"message": {"content": json.dumps(result)}}]}
        )

    provider._client = httpx.AsyncClient(transport=httpx.MockTransport(upstream))
    app = create_app(secret=SECRET, pool_path=pool)
    app.state.provider = provider
    payload = {
        "operation": "generate_variant",
        "text": "一元一次方程：2x+3=11",
        "knowledge_points": ["一元一次方程"],
        "subject": "数学",
        "question_type": "综合题",
        "variant_references": [
            {"id": "reference-1", "question_text": "解方程：x+1=2", "answer": "x=1"}
        ],
    }
    with TestClient(app) as client:

        def compute(**extra):
            return client.post(
                "/v1/compute", headers=HEADERS, json={**payload, **extra}
            )

        result = compute().json()["result"]
        assert result["verified"] is True and result["variant"]["answer"] == "x=5"
        assert result["generation"]["retrieval_ids"] == ["reference-1"]
        assert result["generation"]["source"] == "qwen_with_retrieval"
        assert (
            not {
                "app.db",
                "app.models",
                "app.config",
                "app.services.practice_retrieval",
            }
            & sys.modules.keys()
        )
        for mode, reason in [
            ("wrong", "format_or_answer_invalid"),
            ("unrelated", "knowledge_mismatch"),
            ("invalid", "structured_output_invalid"),
            ("fail", "ai_pool_unavailable"),
        ]:
            state["mode"] = mode
            result = compute().json()["result"]
            assert result["verified"] is True
            assert result["variant"]["answer"] == "x=5"
            assert (
                result["generation"]["source"] == "knowledge_linear_equation_fallback"
            )
            assert result["generation"]["fallback_reason"] == reason
            assert "private-fixture" not in json.dumps(result)
        far = compute(transfer_type="far").json()["result"]
        assert "练习本" in far["variant"]["question_text"]
        assert far["verified"] is True
        assert compute(transfer_type="invalid").status_code == 422
        assert compute(text="").status_code == 422
        assert compute(variant_references=[{"id": "x"}]).status_code == 422
