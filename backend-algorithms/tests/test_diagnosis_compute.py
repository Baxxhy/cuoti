import asyncio
import json
import sys

import httpx
from app.providers.api_pool import ApiPoolProvider
from fastapi.testclient import TestClient
from service import create_app
from test_service import HEADERS, SECRET, image_input


def test_diagnosis_alignment_counterfactual_and_failure(tmp_path):
    pool = tmp_path / "pool.json"
    pool.write_text(
        json.dumps(
            [
                {
                    "base_url": "http://diagnosis.test/v1",
                    "api_key": "private-fixture-key",
                    "model": "Qwen",
                }
            ]
        )
    )
    provider = ApiPoolProvider(pool)
    asyncio.run(provider._client.aclose())
    state = {"mode": "good", "images": 0, "repairs": 0}

    def upstream(request):
        body = json.loads(request.content)
        assert body["model"] == "Qwen"
        repair = "反事实验证器" in json.dumps(body, ensure_ascii=False)
        if repair:
            state["repairs"] += 1
        content = body["messages"][-1]["content"]
        if isinstance(content, list):
            state["images"] += sum(part["type"] == "image_url" for part in content)
        if state["mode"] == "fail" or (repair and state["mode"] == "repair_fail"):
            return httpx.Response(503, json={"error": "private-fixture-key"})
        if repair:
            result = {
                "corrected_first_step": "2*x=8",
                "repaired_steps": ["2*x=8", "x=4"],
                "reasoning": "修正移项后的数值",
                "confidence": 0.9,
            }
            if state["mode"] == "wrong_repair":
                result.update(
                    corrected_first_step="2*x=10", repaired_steps=["2*x=10", "x=5"]
                )
        else:
            result = {
                "first_error_step": 99,
                "first_error_text": "虚构步骤",
                "error_location": "第100步",
                "error_type": "unknown",
                "root_misconception": "移项时数值错误",
                "strategy_candidates": ["先计算 11-3"],
                "confidence": 0.8,
            }
            if state["mode"] == "invalid":
                result["first_error_step"] = []
            if state["mode"] == "invalid_probability":
                result["confidence"] = 1.5
        return httpx.Response(
            200, json={"choices": [{"message": {"content": json.dumps(result)}}]}
        )

    provider._client = httpx.AsyncClient(transport=httpx.MockTransport(upstream))
    app = create_app(secret=SECRET, pool_path=pool)
    app.state.provider = provider
    data = {
        "operation": "diagnose",
        "text": "解方程：2*x+3=11",
        "reference_steps": [
            {"id": "ref-0", "text": "2*x=8"},
            {"id": "ref-1", "text": "x=4"},
        ],
        "student_records": [
            {"id": "stu-0", "text": "2*x=10"},
            {"id": "stu-1", "text": "x=5"},
        ],
        "student_answer": "5",
    }
    with TestClient(app) as client:

        def compute(**extra):
            return client.post("/v1/compute", headers=HEADERS, json={**data, **extra})

        response = compute(images_base64=[image_input()])
        assert response.status_code == 200, response.text
        result = response.json()["result"]
        assert result["diagnosis"]["first_error_step"] == 0
        assert result["diagnosis"]["first_error_text"] == "2*x=10"
        assert result["diagnosis"]["recommended_strategy"] == "先计算 11-3"
        assert result["alignment"][0]["reference_step_id"] == "ref-0"
        assert result["alignment"][0]["student_step_id"] == "stu-0"
        assert result["alignment"][0]["is_first_error"] is True
        assert result["alignment"][1]["propagated"] is True
        assert result["counterfactual"]["root_cause_confirmed"] is True
        assert (
            result["counterfactual"]["verification_method"]
            == "qwen_proposal_sympy_check"
        )
        assert state["images"] == 1 and state["repairs"] == 1
        state["mode"] = "wrong_repair"
        wrong = compute(operation="counterfactual").json()["result"]
        assert "diagnosis" not in wrong
        assert wrong["counterfactual"]["root_cause_confirmed"] is False
        assert wrong["counterfactual"]["status"] == "inconclusive"
        state["mode"] = "repair_fail"
        fallback = compute().json()["result"]["counterfactual"]
        assert fallback["root_cause_confirmed"] is True
        assert fallback["verification_method"] == "reference_repair_sympy_check"
        state["mode"] = "good"
        repairs_before = state["repairs"]
        answer_only = compute(student_records=[]).json()["result"]
        assert answer_only["diagnosis"]["first_error_step"] is None
        assert (
            answer_only["diagnosis"]["first_error_text"]
            == answer_only["diagnosis"]["error_location"]
            == ""
        )
        assert answer_only["counterfactual"]["status"] == "not_needed"
        assert state["repairs"] == repairs_before
        assert all(
            not item["is_first_error"] and not item["propagated"]
            for item in answer_only["alignment"]
        )
        correct = compute(
            student_records=[{"id": "s0", "text": "2*x=8"}, {"id": "s1", "text": "x=4"}],
            student_answer="x=4",
        ).json()["result"]
        assert all(item["math_valid"] for item in correct["alignment"])
        assert correct["diagnosis"]["first_error_step"] is None
        assert correct["diagnosis"]["error_type"] == "exact"
        assert correct["diagnosis"]["root_misconception"] == ""
        assert correct["counterfactual"]["status"] == "not_needed"
        quadratic = compute(
            text="解方程：x^2-5x+6=0，写出所有实数解。",
            reference_steps=[
                {"id": "r0", "text": "观察方程，寻找两个数。"},
                {"id": "r1", "text": "确定这两个数为-2和-3。"},
                {"id": "r2", "text": "将左边因式分解为 (x-2)(x-3)=0。"},
            ],
            student_records=[
                {"id": "s0", "text": "(x-2)(x-3)=0"},
                {"id": "s1", "text": "x=2"},
            ],
            student_answer="x=2",
        ).json()["result"]
        assert quadratic["diagnosis"]["first_error_step"] == 1
        assert quadratic["diagnosis"]["error_type"] == "condition_omission"
        assert not quadratic["alignment"][0]["is_first_error"]
        assert quadratic["alignment"][0]["math_valid"]
        for invalid in (
            {"text": ""},
            {"student_records": [{"id": "s", "text": {}}]},
            {"reference_steps": [{"id": "r", "text": "x", "path": "/etc/passwd"}]},
        ):
            assert compute(**invalid).status_code == 422
        for mode in ("fail", "invalid", "invalid_probability"):
            state["mode"] = mode
            failed = compute()
            assert (
                failed.status_code == 503 and "private-fixture-key" not in failed.text
            )
        assert (
            not {"app.db", "app.models", "app.main", "app.config"} & sys.modules.keys()
        )
