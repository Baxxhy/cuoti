import json

import pytest

from app.providers.api_pool import ApiPoolUnavailable
from app.schemas import AnalysisOutput
from app.services.ai_pipeline import analyze_question, diagnose_steps
from app.services.diagnosis import equation_equivalent
from app.services.grading import _grade_by_rule, grade_answer
from app.services.math_tools import (
    compare_equivalence,
    locate_first_error,
    parse_math_expression,
    solve_text_equation,
)


class OfflineProvider:
    async def generate_structured(self, *_args, **_kwargs):
        raise ApiPoolUnavailable("offline")


@pytest.mark.parametrize(
    ("left", "right"),
    [
        ("2x + 2", "2(x+1)"),
        ("sqrt(4)", "2"),
        ("0.5", "1/2"),
    ],
)
def test_bounded_parser_supports_school_arithmetic(left, right):
    assert compare_equivalence(left, right) == (True, True)


@pytest.mark.parametrize(
    ("left", "right"),
    [
        ("$-9-a$", "-a-9"),
        (r"\(a^{2}-9\)", "(a-3)(a+3)"),
        (r"\[a^{2}\]", "a*a"),
        ("$$a^{2}$$", "a*a"),
    ],
)
def test_math_display_wrappers_preserve_symbolic_meaning(left, right):
    assert compare_equivalence(left, right) == (True, True)


@pytest.mark.asyncio
async def test_imported_simplification_answer_validates_the_complete_equation_chain():
    expected = "【答案】解: 原式 $=a^{2}-9-a^{2}-a$ $=-9-a$.\n\n【解析】先用平方差公式计算，再合并同类项。"
    result = await grade_answer(
        OfflineProvider(),
        question="化简: $(a-3)(a+3)-a(a+1)$",
        answer="-a-9",
        expected=expected,
        reference_solution=[],
        subject="数学",
        question_type="计算题",
    )
    assert result["verdict"] == "confirmed_correct"
    assert result["can_update_learning"]
    assert result["method"] == "sympy_equivalent"
    wrong = _grade_by_rule("-a+9", expected, "数学", "计算题")
    assert not wrong["correct"]
    assert wrong["method"] == "sympy_mismatch"


@pytest.mark.parametrize(
    "expected",
    [
        "【答案】解: 原式 $=a+9$ $=-9-a$.【解析】错误变形不能只取最后一个式子。",
        "【答案】第一问 $a+1$；第二问 $-a-9$。【解析】多问不能丢掉前一问。",
        "【答案】答案不是 $-a-9$。【解析】否定不能被丢弃。",
        "【答案】解: 原式 $=a/a-10-a$ $=-9-a$.",
        "【答案】解: 原式 $=2^{1000000}$ $=-9-a$.",
        "【答案】解: 原式 $=__import__('os')$ $=-9-a$.",
    ],
)
def test_expected_answer_extraction_keeps_uncertain_prose_and_unsafe_chains_unverified(expected):
    result = _grade_by_rule("-a-9", expected, "数学", "计算题")
    assert result["method"] == "math_unverified"
    assert not result["correct"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("answer", "expected"),
    [
        ("12", "【答案】(1) 2\n(2) 3【解析】多问"),
        ("12", "【答案】(1) 2 (2) 3【解析】多问"),
        ("6", "2\n3"),
        ("6", "2 3"),
        ("2xy", "(1)x (2)y"),
        ("x^4", "【答案】$x²²$【解析】指数不是四"),
        ("x^8", "x²³"),
    ],
)
async def test_numbered_answers_and_superscript_runs_cannot_change_math_meaning(answer, expected):
    result = await grade_answer(
        OfflineProvider(),
        question="计算",
        answer=answer,
        expected=expected,
        reference_solution=[],
        subject="数学",
        question_type="填空题",
    )
    assert result["verdict"] == "review_required"
    assert not result["can_update_learning"]


@pytest.mark.parametrize(
    "expression",
    [
        "__import__('builtins').sum([1, 2])",
        "().__class__",
        "[x for x in (1,2)]",
        "lambda: 1",
        "open('not-a-file')",
        "2**1000000",
        "exp(1000000)",
    ],
)
def test_external_expression_cannot_invoke_python_or_unbounded_operations(expression):
    with pytest.raises((ValueError, SyntaxError)):
        parse_math_expression(expression)
    assert compare_equivalence(expression, "3")[1] is False


@pytest.mark.parametrize(
    ("answer", "expected", "correct"),
    [
        ("0.5m/s", "5m/s", False),
        ("0.5m/s", "0.50m/s", True),
        ("1.25m", "12.5m", False),
        ("2mW", "2MW", False),
        ("1e-7m", "2e-7m", False),
    ],
)
def test_numeric_grading_preserves_decimal_point_and_unit_case(answer, expected, correct):
    assert _grade_by_rule(answer, expected, "物理", "填空题")["correct"] is correct


@pytest.mark.parametrize(
    ("answer", "expected", "correct"),
    [
        ("y=2", "x=2", False),
        ("x=1,y=2", "x=2", False),
        ("x=1,y=2", "y=2,x=1", True),
        ("2", "x=2", True),
        ("x=2", "2", True),
        ("x=1/2", "x=0.5", True),
        ("x=1,x=2", "x=1,x=2", True),
        ("不存在", "不存在", True),
    ],
)
def test_math_grading_compares_variables_and_all_answer_components(answer, expected, correct):
    assert _grade_by_rule(answer, expected, "数学", "填空题")["correct"] is correct


@pytest.mark.asyncio
async def test_unrecognized_math_requires_review_without_changing_learning():
    result = await grade_answer(
        OfflineProvider(),
        question="填空",
        answer=r"\frac{1}{2}",
        expected="0.5",
        reference_solution=[],
        subject="数学",
        question_type="填空题",
    )
    assert result["verdict"] == "review_required"
    assert not result["can_update_learning"]


@pytest.mark.asyncio
async def test_unverified_math_does_not_erase_parentheses_when_comparing():
    result = await grade_answer(
        OfflineProvider(),
        question="化简",
        answer="(x+1)/(x+1)",
        expected="x+1/x+1",
        reference_solution=[],
        subject="数学",
        question_type="填空题",
    )
    assert not result["correct"]
    assert result["verdict"] == "review_required"


@pytest.mark.asyncio
async def test_offline_process_grading_does_not_treat_a_matching_last_answer_as_proof():
    result = await grade_answer(
        OfflineProvider(),
        question="求集合对的数量",
        answer="29+12+6=47\n但答案栏误写49",
        expected="49",
        reference_solution=[],
        subject="数学",
        question_type="填空题",
    )
    assert "误写49" in result["recognized_answer"]
    assert result["verdict"] == "review_required"
    assert not result["can_update_learning"]


def test_solving_condition_does_not_answer_a_different_question():
    assert solve_text_equation("已知2x+3=11，求x²") == ("", False)
    assert solve_text_equation("解方程：2x+3=11") == ("x=4", True)


@pytest.mark.parametrize(
    "text",
    [
        "解方程：(x-1)/(x-1)*x=1",
        "解方程：(x-1)**(-1)*(x-1)*x=1",
        "解方程：sqrt(x)**2=-1",
        "解方程：(x**(1/2))**2=-1",
    ],
)
def test_local_solver_does_not_lose_domain_restrictions(text):
    assert solve_text_equation(text) == ("", False)


@pytest.mark.asyncio
@pytest.mark.parametrize("answer", ["答案为1/2", "答案不是2"])
async def test_final_answer_extraction_keeps_fractions_and_negation(answer):
    result = await grade_answer(
        OfflineProvider(),
        question="计算",
        answer=answer,
        expected="2",
        reference_solution=[],
        subject="数学",
        question_type="填空题",
    )
    assert result["verdict"] != "confirmed_correct"
    assert not result["correct"]


def test_step_comparison_uses_the_complete_equation_and_variable():
    assert equation_equivalent("2x=8", "x=4")
    assert not equation_equivalent("x=2", "y=2")
    assert not equation_equivalent("1=2", "3=4")
    assert not equation_equivalent("__import__('builtins').sum([1,2])=3", "x=3")
    assert locate_first_error(["2x=8"], ["x=4"]) is None
    assert equation_equivalent("2x=8", "x=4", require_symbolic=True)
    assert not equation_equivalent("连接辅助线", "连接辅助线", require_symbolic=True)


@pytest.mark.asyncio
async def test_expression_question_retains_the_actual_requested_model_answer():
    class Provider:
        async def generate_structured(self, *_args, **_kwargs):
            return AnalysisOutput(
                subject="数学",
                problem_type="填空题",
                known_conditions=["2x+3=11"],
                goal="求x²",
                knowledge_points=["代数求值"],
                prerequisites=[],
                reference_steps=["x=4", "x²=16"],
                final_answer="16",
                answer_verified=False,
            )

    result = await analyze_question(Provider(), "已知2x+3=11，求x²", question_type="填空题")
    assert result.final_answer == "16"
    assert not result.answer_verified


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("question_text", "question_type", "expected"),
    [
        ("哪些是正数？", "多选题", "BC"),
        ("解方程：x+1=3", "单选题", "B"),
    ],
)
async def test_text_only_choice_analysis_includes_every_option_for_the_provider(
    question_text, question_type, expected
):
    options = [{"label": "A", "text": "-1"}, {"label": "B", "text": "2"}, {"label": "C", "text": "3"}]

    class Provider:
        async def generate_structured(self, prompt, _schema):
            context = json.loads(prompt.split("上下文：", 1)[1])
            assert context["question_text"] == question_text
            assert context["options"] == options
            return AnalysisOutput(subject="数学", final_answer=expected, reference_steps=["比较选项"])

    result = await analyze_question(Provider(), question_text, question_type=question_type, options=options)
    assert result.final_answer == expected
    assert not result.answer_verified


@pytest.mark.asyncio
async def test_offline_analysis_never_invents_a_standard_answer():
    with pytest.raises(ApiPoolUnavailable):
        await analyze_question(OfflineProvider(), "请分析这篇文章的主题", subject="语文")
    result = await analyze_question(OfflineProvider(), "解方程：2x+3=11")
    assert result.final_answer == "x=4"
    assert result.answer_verified


@pytest.mark.asyncio
async def test_offline_diagnosis_does_not_invent_confident_error_labels():
    with pytest.raises(ApiPoolUnavailable):
        await diagnose_steps(OfflineProvider(), "解方程", ["x=4"], ["x=4"])
