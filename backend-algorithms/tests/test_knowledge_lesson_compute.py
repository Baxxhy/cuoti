import json

import pytest

from knowledge_lesson_compute import LessonDraft, explain_knowledge


class Provider:
    def __init__(self, codes=None):
        self.calls = []
        self.codes = codes or ["equation"]

    async def generate_structured(self, prompt, model, **kwargs):
        self.calls.append(json.loads(prompt))
        return {
            "explanation": "等式两边同时加上同一个数，左右仍然相等。解方程时，要在两边做同样的运算。",
            "key_points": ["两边做同样的运算", "除数不能为零"],
            "check_question": "等式两边同时加3，等式还成立吗？",
            "source_codes": self.codes,
        }


def cards():
    return [{"code": "equation", "subject": "数学", "name": "等式的性质", "content": {
        "grade": "初一", "definition": "等式两边同时加上同一个数，等式仍成立。", "formulas": ["a=b"]
    }}]


@pytest.mark.asyncio
async def test_explanation_is_validated_source_bound_and_not_learning_evidence():
    provider = Provider()
    result = await explain_knowledge(provider, cards(), "数学", "初一", "为什么两边同时加3？")
    assert result["can_update_learning"] is False
    assert result["verification"] == "model_explanation"
    assert result["sources"][0]["code"] == "equation"
    assert len(result["sources"][0]["source_hash"]) == 64
    assert provider.calls[0]["student_question"] == "为什么两边同时加3？"


@pytest.mark.asyncio
async def test_followup_uses_bounded_conversation_as_context_not_evidence():
    provider = Provider()
    await explain_knowledge(provider, cards(), "数学", "初一", "再讲简单一些", [{"question": str(i), "explanation": "旧解释" * 1000} for i in range(5)])
    context = provider.calls[0]["recent_conversation"]
    assert [row["question"] for row in context] == ["2", "3", "4"]
    assert all(len(row["explanation"]) == 1400 for row in context)
    assert provider.calls[0]["sources"][0]["code"] == "equation"


@pytest.mark.asyncio
async def test_unknown_sources_are_rejected_and_missing_evidence_never_calls_model():
    provider = Provider(["invented"])
    with pytest.raises(ValueError, match="Unknown knowledge source"):
        await explain_knowledge(provider, cards(), "数学", "初一")
    empty_provider = Provider()
    with pytest.raises(ValueError, match="No usable curriculum evidence"):
        await explain_knowledge(empty_provider, cards(), "英语", "初一")
    assert empty_provider.calls == []


def test_output_limits_are_real_constraints():
    with pytest.raises(ValueError):
        LessonDraft(explanation="内容" * 20, key_points=["x" * 241], check_question="说明这一步的依据？", source_codes=["equation"])


@pytest.mark.asyncio
async def test_malformed_paragraph_field_retries_once_without_relaxing_schema():
    class MalformedFirst(Provider):
        async def generate_structured(self, prompt, model, **kwargs):
            result = await super().generate_structured(prompt, model, **kwargs)
            if len(self.calls) == 1:
                return {**result, "错误地作为字段名的第二段讲解": "额外内容"}
            return model.model_validate(result)

    provider = MalformedFirst()
    result = await explain_knowledge(provider, cards(), "数学", "初一", "为什么移项变号？")
    assert len(provider.calls) == 2
    assert "format_correction" in provider.calls[1]
    assert provider.calls[0]["sources"] == provider.calls[1]["sources"]
    assert provider.calls[0]["student_question"] == provider.calls[1]["student_question"]
    assert result["can_update_learning"] is False
    assert "错误地作为字段名的第二段讲解" not in result


@pytest.mark.asyncio
async def test_repeated_invalid_output_is_rejected_after_two_attempts():
    class Invalid(Provider):
        async def generate_structured(self, prompt, model, **kwargs):
            result = await super().generate_structured(prompt, model, **kwargs)
            return model.model_validate({**result, "unexpected": "must reject"})

    provider = Invalid()
    with pytest.raises(ValueError):
        await explain_knowledge(provider, cards(), "数学", "初一")
    assert len(provider.calls) == 2


@pytest.mark.asyncio
async def test_transport_timeout_does_not_start_a_format_retry():
    class Timeout(Provider):
        async def generate_structured(self, prompt, model, **kwargs):
            await super().generate_structured(prompt, model, **kwargs)
            raise TimeoutError()

    provider = Timeout()
    with pytest.raises(TimeoutError):
        await explain_knowledge(provider, cards(), "数学", "初一")
    assert len(provider.calls) == 1
