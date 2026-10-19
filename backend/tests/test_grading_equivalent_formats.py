"""Actual multi-blank answers must not depend on reference TeX formatting."""
import pytest

from app.providers.api_pool import ApiPoolUnavailable
from app.schemas import AnswerGradeOutput
from app.services.grading import grade_answer

QUESTION = r"在 $\frac{1}{5}$、$\frac{1}{6}$、$\frac{1}{10}$ 中，最大的是()，最小的是()。"
EXPECTED = r"$\frac{1}{5}$，$\frac{1}{10}$"

class Offline:
    async def generate_structured(self, *args, **kwargs):
        raise ApiPoolUnavailable("离线测试")

@pytest.mark.asyncio
@pytest.mark.parametrize('answer', ['1/5,1/10', '1/5，1/10', '0.2、0.1', '2/10;2/20', '1/5\n1/10'])
async def test_multiple_blanks_accept_equivalent_formats(answer):
    result = await grade_answer(Offline(), question=QUESTION, answer=answer, expected=EXPECTED,
                               subject='数学', question_type='填空题', reference_solution=[])
    assert result['verdict'] == 'confirmed_correct'
    assert result['can_update_learning'] is True

@pytest.mark.asyncio
@pytest.mark.parametrize('answer', ['1/10,1/5', '1/5', '1/5,1/10,1/6', '1/5,1/6'])
async def test_multiple_blanks_preserve_order_and_completeness(answer):
    result = await grade_answer(Offline(), question=QUESTION, answer=answer, expected=EXPECTED,
                               subject='数学', question_type='填空题', reference_solution=[])
    assert result['verdict'] == 'confirmed_incorrect'

class SemanticGrader:
    def __init__(self, *, correct=True, final='1/5,1/10', confidence=0.98):
        self.calls = 0
        self.correct, self.final, self.confidence = correct, final, confidence
    async def generate_structured(self, prompt, schema, system=''):
        self.calls += 1
        assert QUESTION in prompt and '学生作答' in prompt and '多空题' in prompt
        assert schema is AnswerGradeOutput
        return schema(correct=self.correct, score=100 if self.correct else 0,
                      recognized_final_answer=self.final, reason='已按最大值和最小值分别核对。',
                      confidence=self.confidence)

@pytest.mark.asyncio
async def test_short_natural_language_answer_uses_ai_then_checks_normalized_values():
    provider = SemanticGrader()
    result = await grade_answer(provider, question=QUESTION, answer='最大是五分之一，最小是十分之一',
                               expected=EXPECTED, subject='数学', question_type='填空题', reference_solution=[])
    assert provider.calls == 1
    assert result['grader'] == 'llm'
    assert result['verdict'] == 'confirmed_correct'
    assert result['can_update_learning'] is True
    assert any('SymPy' in item for item in result['evidence'])

@pytest.mark.asyncio
async def test_ai_cannot_confirm_wrong_order_or_low_confidence():
    for provider in [SemanticGrader(final='1/10,1/5'), SemanticGrader(confidence=0.7)]:
        result = await grade_answer(provider, question=QUESTION, answer='我认为最大为五分之一、最小为十分之一',
                                   expected=EXPECTED, subject='数学', question_type='填空题', reference_solution=[])
        assert result['verdict'] == 'review_required'
        assert result['can_update_learning'] is False

@pytest.mark.asyncio
async def test_short_unverified_answer_offline_stays_pending_instead_of_wrong():
    result = await grade_answer(Offline(), question=QUESTION, answer='最大是五分之一，最小是十分之一',
                               expected=EXPECTED, subject='数学', question_type='填空题', reference_solution=[])
    assert result['verdict'] == 'review_required'
    assert result['can_update_learning'] is False


@pytest.mark.asyncio
@pytest.mark.parametrize('answer,expected', [
    (r"\frac{1}{2}", '0.5'),
    (r"\frac{1}{\frac{5}{2}}", '2/5'),
    (r"\(\frac{1}{5}\),\(\frac{1}{10}\)", '0.2,0.1'),
    (r"$\sqrt{4}$", '2'),
])
async def test_safe_tex_presentation_normalization(answer, expected):
    result = await grade_answer(Offline(), question=QUESTION, answer=answer, expected=expected,
                               subject='数学', question_type='填空题', reference_solution=[])
    assert result['verdict'] == 'confirmed_correct'


@pytest.mark.asyncio
async def test_closed_math_answer_can_be_confirmed_by_high_confidence_ai_with_evidence():
    class SemanticEvidence(SemanticGrader):
        async def generate_structured(self, prompt, schema, system=''):
            result = await super().generate_structured(prompt, schema, system)
            return result.model_copy(update={'matched_key_steps': ['依照题目两个空的顺序，最大为五分之一，最小为十分之一。']})
    result = await grade_answer(SemanticEvidence(), question=QUESTION,
                               answer='最大为五分之一，最小为十分之一',
                               expected='最大为五分之一；最小为十分之一', subject='数学',
                               question_type='填空题', reference_solution=['同分子分数比较分母。'])
    assert result['grader'] == 'llm' and result['verdict'] == 'confirmed_correct'
    assert any('语义判题' in item for item in result['evidence'])
