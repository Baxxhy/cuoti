
from fastapi.testclient import TestClient

from service import create_app


def test_dialogue_computation_fallback_keeps_stage_and_uses_supplied_cards(tmp_path):
    secret = "dialogue-compute-" + "x" * 32
    app = create_app(secret=secret, pool_path=tmp_path / "missing.json")
    context = {
        "student_message": "我不会",
        "subject": "数学",
        "question_type": "综合题",
        "question_text": "解方程",
        "final_answer": "x=4",
        "reference_steps": ["2x=8", "x=4"],
        "turn_count": 1,
        "knowledge_points": ["一次方程"],
        "recent_turns": [{"role": "user", "content": "我不会"}],
    }
    headers = {"Authorization": "Bearer " + secret}
    with TestClient(app) as client:
        prepared = client.post(
            "/v1/compute",
            headers=headers,
            json={"operation": "tutor_dialogue_prepare", "dialogue_context": context},
        )
        assert prepared.status_code == 200, prepared.text
        preparation = prepared.json()["result"]
        assert (
            preparation["planner_status"] == "fallback"
            and preparation["plan"]["tool_name"] == "knowledge_search"
        )
        response = client.post(
            "/v1/compute",
            headers=headers,
            json={
                "operation": "tutor_dialogue_finish",
                "dialogue_context": context,
                "dialogue_preparation": preparation,
                "dialogue_cards": [
                    {
                        "code": "EQ",
                        "name": "一次方程",
                        "content": {"definition": "两边同做相同运算"},
                    }
                ],
            },
        )
        assert response.status_code == 200, response.text
        result = response.json()["result"]
        assert "知识卡 · 一次方程" in result["reply"]
        assert result["agent"]["verification"]["status"] == "verified"
        assert result["graph"]["mastery_proven"] is False
        assert app.state.provider is None


def test_dialogue_preserves_complete_long_formula_and_conditions(tmp_path, monkeypatch):
    explanation = (
        "先确认题目给出的条件。" * 12
        + r"当 $x\ne 0$ 时，$\frac{2x+3}{x}=2+\frac{3}{x}$。"
        + "请写出你认为等价的下一步，并说明分母不能为零的原因。"
    )

    async def guidance(*args, **kwargs):
        return explanation

    monkeypatch.setattr("dialogue_compute.generate_tutor_guidance", guidance)
    secret = "complete-content-" + "x" * 32
    app = create_app(secret=secret, pool_path=tmp_path / "missing.json")
    headers = {"Authorization": "Bearer " + secret}
    context = {"student_message": "我想检查这一步", "turn_count": 1}
    with TestClient(app) as client:
        preparation = client.post(
            "/v1/compute",
            headers=headers,
            json={"operation": "tutor_dialogue_prepare", "dialogue_context": context},
        ).json()["result"]
        result = client.post(
            "/v1/compute",
            headers=headers,
            json={
                "operation": "tutor_dialogue_finish",
                "dialogue_context": context,
                "dialogue_preparation": preparation,
            },
        )
        assert result.status_code == 200
        assert explanation in result.json()["result"]["reply"]


def test_explicit_answer_reveal_preserves_reference_instead_of_model_hint(tmp_path):
    from learning_core.providers.api_pool import ApiPoolUnavailable
    from learning_core.schemas import TutorGuidanceOutput

    class HintProvider:
        async def generate_structured(self, _prompt, schema, **_kwargs):
            if schema is TutorGuidanceOutput:
                return schema(reply="先观察等式两边的条件。")
            raise ApiPoolUnavailable("offline planner")

        async def close(self):
            pass

    secret = "answer-reveal-" + "x" * 32
    app = create_app(secret=secret, pool_path=tmp_path / "missing.json")
    headers = {"Authorization": "Bearer " + secret}
    context = {
        "student_message": "只要答案", "turn_count": 1, "final_answer": "x=4",
        "reference_steps": ["2x=8", "x=4"],
    }
    with TestClient(app) as client:
        app.state.provider = HintProvider()
        preparation = client.post(
            "/v1/compute", headers=headers,
            json={"operation": "tutor_dialogue_prepare", "dialogue_context": context},
        ).json()["result"]
        response = client.post(
            "/v1/compute", headers=headers,
            json={"operation": "tutor_dialogue_finish", "dialogue_context": context,
                  "dialogue_preparation": preparation},
        )
        assert response.status_code == 200
        assert "x=4" in response.json()["result"]["reply"]
        assert response.json()["result"]["graph"]["mastery_proven"] is False
        context["turn_count"] = 2
        context["recent_turns"] = [{"role": "assistant", "content": response.json()["result"]["reply"]}]
        repeated = client.post(
            "/v1/compute", headers=headers,
            json={"operation": "tutor_dialogue_finish", "dialogue_context": context,
                  "dialogue_preparation": preparation},
        )
        assert repeated.status_code == 200
        assert "x=4" in repeated.json()["result"]["reply"]
