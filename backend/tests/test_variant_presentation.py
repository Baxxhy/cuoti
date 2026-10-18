from types import SimpleNamespace

import pytest

from app.schemas import VariantOutput
from app.services.variants import build_knowledge_fallback, verify_knowledge_alignment, verify_variant


def test_unrelated_stem_cannot_pass_by_mentioning_topic_in_explanation():
    result = VariantOutput(
        question_text="菱形ABCD的顶点位于反比例函数上，求参数k。",
        answer="5",
        reference_solution=["求顶点坐标"],
        explanation="这道题继续检查一元一次方程的解法。",
    )
    assert not verify_knowledge_alignment(result, ["一元一次方程的解法"], "解方程：2x+3=11")


@pytest.mark.parametrize("transfer", ["near", "far"])
def test_linear_fallback_is_a_solvable_task_without_external_diagram(transfer):
    result, source = build_knowledge_fallback(
        "数学",
        transfer,
        "解方程：2x+3=11",
        "解答题",
        ["一元一次方程的解法"],
        [],
    )
    assert source == "knowledge_linear_equation_fallback"
    assert result.answer == "x=5"
    assert verify_variant(result, "数学")
    assert verify_knowledge_alignment(result, ["一元一次方程的解法"], "解方程：2x+3=11")
    assert "条件完成对应判断" not in result.question_text


@pytest.mark.parametrize("stem", ["如图，求三角形面积", "下图中求角度", "求<ImageHere>中阴影面积"])
def test_variant_cannot_require_a_missing_diagram(stem):
    result = VariantOutput(question_text=stem, answer="5", reference_solution=["求面积"])
    assert not verify_variant(result, "数学")


def test_legitimate_standalone_equation_remains_aligned():
    result = VariantOutput(question_text="解方程：4x-5=15", answer="x=5", reference_solution=["4x=20", "x=5"])
    assert verify_variant(result, "数学")
    assert verify_knowledge_alignment(result, ["一元一次方程的解法"], "解方程：2x+3=11")


@pytest.mark.asyncio
async def test_visualization_uses_analyzed_knowledge_when_ocr_has_none(monkeypatch):
    from app import main

    session = SimpleNamespace(question_id="q")
    question = SimpleNamespace(subject="数学", question_type="计算题", knowledge_points=[])
    analysis = SimpleNamespace(knowledge_points=["一元一次方程的解法"])

    class DB:
        async def get(self, *_args):
            return session

    async def context(*_args):
        return question, analysis, []

    monkeypatch.setattr(main, "tutor_learning_context", context)
    _, _, spec = await main.visualization_context("s", DB())
    assert spec["type"] == "equation_balance"
