import asyncio

import pytest

from learning_core.providers.api_pool import ApiPoolUnavailable
from learning_core.schemas import VariantOutput
from practice_generation import PracticeReview, generate_practice


class Offline:
    async def generate_structured(self, *args, **kwargs):
        raise ApiPoolUnavailable("offline")


def test_linear_exercise_survives_offline_and_is_solvable():
    result = asyncio.run(
        generate_practice(
            Offline(),
            "数学",
            "near",
            "解方程：2x+3=11\n选项：[]\n年级：初一",
            "综合题",
            ["一元一次方程"],
        )
    )
    assert result["verified"]
    assert result["generation"]["source"] == "sympy_checked_practice"
    from variant_compute import verify_variant

    assert verify_variant(VariantOutput.model_validate(result["variant"]), "数学")


def test_generic_advice_is_never_served_as_similar_question():
    result = asyncio.run(
        generate_practice(
            Offline(), "历史", "near", "分析辛亥革命的历史意义", "综合题", ["辛亥革命"]
        )
    )
    assert result["verified"] is False


@pytest.mark.parametrize("approved", [True, False])
def test_model_exercise_requires_independent_review(approved):
    class Provider:
        async def generate_structured(self, prompt, schema):
            if schema is PracticeReview:
                return PracticeReview(
                    same_skill=True,
                    answer_correct=approved,
                    self_contained=True,
                    grade_appropriate=True,
                )
            return VariantOutput(
                question_text="辛亥革命推翻了哪个朝代的统治？",
                answer="清朝",
                reference_solution=["辛亥革命推翻清朝统治"],
                explanation="辛亥革命结束了清朝的统治。",
            )

    result = asyncio.run(
        generate_practice(
            Provider(),
            "历史",
            "near",
            "辛亥革命推翻了什么统治？",
            "综合题",
            ["辛亥革命"],
        )
    )
    assert result["verified"] is approved


def test_internal_endpoint_works_without_pool_for_checked_math(tmp_path):
    from fastapi.testclient import TestClient

    from service import create_app

    secret = "practice-service-test-" + "x" * 32
    app = create_app(secret=secret, pool_path=tmp_path / "missing.json")
    with TestClient(app) as client:
        response = client.post(
            "/v1/compute",
            headers={"Authorization": "Bearer " + secret},
            json={
                "operation": "generate_practice",
                "subject": "数学",
                "text": "解方程：2x+3=11",
                "question_type": "综合题",
                "transfer_type": "near",
                "knowledge_points": ["一元一次方程"],
            },
        )
        assert response.status_code == 200
        assert response.json()["operation"] == "generate_practice"
        assert response.json()["result"]["verified"]


def test_local_next_question_changes_even_when_randomness_repeats(monkeypatch):
    import practice_generation

    monkeypatch.setattr(practice_generation.secrets, "randbelow", lambda _: 0)
    first = asyncio.run(
        generate_practice(Offline(), "数学", "near", "解方程：2x+3=11", "综合题", [])
    )
    second = asyncio.run(
        generate_practice(
            Offline(),
            "数学",
            "near",
            "解方程：2x+3=11\n选项：[]\n此前练习：" + first["variant"]["question_text"],
            "综合题",
            [],
        )
    )
    assert first["variant"]["question_text"] != second["variant"]["question_text"]
