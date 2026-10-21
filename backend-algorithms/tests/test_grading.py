import asyncio
import json

import httpx
from fastapi.testclient import TestClient

from learning_core.providers.api_pool import ApiPoolProvider
from service import create_app

SECRET = "grading-test-" + "x" * 32
HEADERS = {"Authorization": "Bearer " + SECRET}


def test_grading_without_model_pool(tmp_path):
    app = create_app(secret=SECRET, pool_path=tmp_path / "missing.json")
    with TestClient(app) as client:

        def compute(**extra):
            return client.post(
                "/v1/compute",
                headers=HEADERS,
                json={
                    "operation": "grade_answer",
                    "text": "解方程 x+1=2",
                    "answer": "x=1",
                    "expected": "x=1",
                    "question_type": "short_answer",
                    **extra,
                },
            )

        correct = compute().json()["result"]
        assert correct["correct"] and correct["can_update_learning"]
        wrong = compute(answer="x=3").json()["result"]
        assert not wrong["correct"] and wrong["can_update_learning"]
        multiple = compute(
            answer=["B", "A"],
            expected=["A", "B"],
            options=[{"value": "A", "label": "选项A"}],
        ).json()["result"]
        assert multiple["correct"] and multiple["method"] == "option_exact"
        uncertain = compute(
            answer="我认为因为这些条件，所以可以得到上述结论。",
            expected="某结论",
            subject="语文",
            question_type="subjective",
        ).json()["result"]
        assert not uncertain["can_update_learning"]
        assert compute(expected=None).status_code == 422
        assert compute(text="").status_code == 422


def test_grading_process_review_and_conflict(tmp_path):
    pool = tmp_path / "pool.json"
    pool.write_text(
        json.dumps(
            [
                {
                    "base_url": "http://grading.test/v1",
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
        assert json.loads(request.content)["model"] == "Qwen"
        if state["mode"] == "fail":
            return httpx.Response(503, json={"error": "private-fixture"})
        good = state["mode"] == "good"
        result = {
            "correct": good,
            "score": 100 if good else 0,
            "recognized_final_answer": "x=1",
            "reason": "过程已核对。",
            "confidence": 0.95,
        }
        return httpx.Response(
            200, json={"choices": [{"message": {"content": json.dumps(result)}}]}
        )

    provider._client = httpx.AsyncClient(transport=httpx.MockTransport(upstream))
    app = create_app(secret=SECRET, pool_path=pool)
    app.state.provider = provider
    with TestClient(app) as client:

        def compute():
            return client.post(
                "/v1/compute",
                headers=HEADERS,
                json={
                    "operation": "grade_answer",
                    "text": "解方程 x+1=2",
                    "answer": "x=2-1\nx=1",
                    "expected": "x=1",
                    "question_type": "subjective",
                    "subject": "数学",
                },
            ).json()["result"]

        result = compute()
        assert result["correct"] and result["can_update_learning"]
        state["mode"] = "conflict"
        result = compute()
        assert result["conflict"] and not result["can_update_learning"]
        state["mode"] = "fail"
        result = compute()
        assert (
            result["verdict"] == "review_required" and not result["can_update_learning"]
        )
        assert "private-fixture" not in json.dumps(result)


def test_short_answer_uses_qwen_pool_and_verifies_semantic_normalization(tmp_path):
    pool = tmp_path / "pool.json"
    pool.write_text(json.dumps([{"base_url": "http://semantic.test/v1", "api_key": "fixture-only", "model": "Qwen"}]))
    provider = ApiPoolProvider(pool)
    asyncio.run(provider._client.aclose())
    calls = []
    def upstream(request):
        payload = json.loads(request.content)
        assert payload["model"] == "Qwen"
        calls.append(payload)
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps({
            "correct": True, "score": 100, "recognized_final_answer": "1/5,1/10",
            "reason": "最大值和最小值分别正确，不受分数写法影响。", "confidence": 0.98,
        })}}]})
    provider._client = httpx.AsyncClient(transport=httpx.MockTransport(upstream))
    app = create_app(secret=SECRET, pool_path=pool)
    app.state.provider = provider
    with TestClient(app) as client:
        response = client.post("/v1/compute", headers=HEADERS, json={
            "operation": "grade_answer", "text": "比较1/5、1/6、1/10，求最大值和最小值。",
            "answer": "最大是五分之一，最小是十分之一", "expected": r"$\frac{1}{5}$，$\frac{1}{10}$",
            "subject": "数学", "question_type": "填空题",
        })
        assert response.status_code == 200
        result = response.json()["result"]
        assert result["grader"] == "llm" and result["verdict"] == "confirmed_correct"
        assert result["can_update_learning"] and len(calls) == 1
