import asyncio
import json
import sys

import httpx
from app.providers.api_pool import ApiPoolProvider
from fastapi.testclient import TestClient
from service import create_app

SECRET = "teaching-test-" + "x" * 32
HEADERS = {"Authorization": "Bearer " + SECRET}


def test_teaching_brief_boundary_and_fallback(tmp_path):
    pool = tmp_path / "pool.json"
    pool.write_text(
        json.dumps(
            [
                {
                    "base_url": "http://teaching.test/v1",
                    "api_key": "fixture-private-key",
                    "model": "Qwen",
                }
            ]
        )
    )
    provider = ApiPoolProvider(pool)
    asyncio.run(provider._client.aclose())
    state = {"mode": "good", "calls": 0}

    def upstream(request):
        state["calls"] += 1
        body = json.loads(request.content)
        assert body["model"] == "Qwen"
        assert "倒数" in str(body["messages"])
        if state["mode"] == "fail":
            return httpx.Response(503, json={"error": "fixture-private-key"})
        output = {
            "topic": "倒数",
            "correct_answer": "错误答案",
            "key_explanation": "0没有倒数。",
            "option_explanations": [
                {"label": "B", "text": "0没有倒数。", "correct": True}
            ],
            "check": {
                "id": "targeted-check",
                "type": "single_choice",
                "title": "检查",
                "question": "哪个数没有倒数？",
                "options": [
                    {"value": "零", "label": "A"},
                    {"value": "一", "label": "B"},
                ],
                "correct_answers": ["零"],
                "hint": "乘积需要等于1。",
                "teaching": "0乘任何数都不等于1。",
            },
        }
        if state["mode"] == "invalid":
            output["key_explanation"] = {"bad": "shape"}
        if state["mode"] == "vague":
            output["check"]["question"] = "你知道了吗？"
        return httpx.Response(
            200, json={"choices": [{"message": {"content": json.dumps(output)}}]}
        )

    provider._client = httpx.AsyncClient(transport=httpx.MockTransport(upstream))
    app = create_app(secret=SECRET, pool_path=pool)
    app.state.provider = provider
    payload = {
        "operation": "teaching_brief",
        "text": "哪个数没有倒数？",
        "correct_answer": "B",
        "student_answer": "A",
        "question_type": "choice",
        "knowledge_points": ["倒数"],
        "options": [{"label": "A", "text": "1"}, {"label": "B", "text": "0"}],
    }
    with TestClient(app) as client:

        def compute(**extra):
            return client.post(
                "/v1/compute", headers=HEADERS, json={**payload, **extra}
            )

        result = compute().json()["result"]
        assert result["logical_model"] == "Qwen"
        brief = result["brief"]
        assert (
            brief["correct_answer"] == "B"
        )  # Trusted analysis answer beats model invention.
        assert brief["check"]["correct_answers"] == ["A"]
        assert brief["check"]["options"][0] == {"value": "A", "label": "A 零"}
        assert (
            not {"app.db", "app.models", "app.main", "app.config"} & sys.modules.keys()
        )
        for mode in ("vague", "invalid", "fail"):
            state["mode"] = mode
            response = compute()
            assert response.status_code == 200
            fallback = response.json()["result"]["brief"]
            assert fallback["correct_answer"] == "B"
            assert fallback["check"]["correct_answers"] == ["B"]
            assert "你知道了吗" not in fallback["check"]["question"]
            assert "fixture-private-key" not in response.text
        calls = state["calls"]
        for extra in (
            {"text": ""},
            {"correct_answer": "　"},
            {"knowledge_points": ["x"] * 101},
            {"diagnosis": []},
            {"question_id": "forbidden-business-field"},
        ):
            assert compute(**extra).status_code == 422
        assert state["calls"] == calls

    with TestClient(
        create_app(secret=SECRET, pool_path=tmp_path / "missing.json")
    ) as client:
        assert (
            client.post("/v1/compute", headers=HEADERS, json=payload).status_code == 503
        )
