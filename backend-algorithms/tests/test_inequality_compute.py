from types import SimpleNamespace

import pytest
import sympy as sp
from inequality_compute import (
    format_solution,
    grade_inequality,
    inequality_alignment,
    solution_set,
    source_inequality,
    verify_inequality_repair,
)

QUESTION = "解不等式：x^2-5x+6≤0，写出解集。"
X = sp.Symbol("x")


def steps(*values):
    return [
        SimpleNamespace(id=f"step-{i}", text=value) for i, value in enumerate(values)
    ]


@pytest.mark.parametrize(
    "question,expected",
    [
        (QUESTION, sp.Interval(2, 3)),
        ("解不等式：-2x+6>0", sp.Interval.open(-sp.oo, 3)),
        (
            "解一元二次不等式：x^2-4>0",
            sp.Union(sp.Interval.open(-sp.oo, -2), sp.Interval.open(2, sp.oo)),
        ),
        ("解不等式：x^2+1<0", sp.S.EmptySet),
        ("解不等式：x^2>=0", sp.S.Reals),
        ("解不等式：x^2<=0", sp.FiniteSet(0)),
        ("解不等式：x^2-2<=0", sp.Interval(-sp.sqrt(2), sp.sqrt(2))),
    ],
)
def test_source_solution_sets_and_display_round_trip(question, expected):
    source = source_inequality(question)
    assert source is not None and source.solutions == expected
    assert solution_set(format_solution(source), source.variable) == expected


@pytest.mark.parametrize(
    "answer",
    [
        "2≤x≤3",
        "3>=x>=2",
        "[2,3]",
        "x∈[2,3]",
        "{x|2<=x<=3}",
        r"$x\in\left[2,3\right]$",
        r"$\{x\mid 2\leq x\leq3\}$",
        "x>=2 and x<=3",
    ],
)
def test_notation_is_compared_as_real_sets(answer):
    result = grade_inequality(QUESTION, answer, "[2,3]")
    assert result["verdict"] == "confirmed_correct" and result["can_update_learning"]
    assert result["recognized_answer"] == answer


@pytest.mark.parametrize(
    "answer", ["(2,3)", "[2,3)", "x≤2或x≥3", "x>=2", "x=2", "{2,3}"]
)
def test_missing_endpoints_extra_values_and_only_roots_are_wrong(answer):
    result = grade_inequality(QUESTION, answer, "[2,3]")
    assert result["verdict"] == "confirmed_incorrect" and result["decisive"]


@pytest.mark.parametrize(
    "question",
    [
        "已知x^2-5x+6≤0，求x的最大值",
        "解不等式：x^2-5x+6≤0，求最大值",
        "判断下列说法：x^2-5x+6≤0",
        "解不等式：x/(x-2)>0",
        "解不等式：sqrt(x)<=2",
        "解不等式：sin(x)>0",
        "解不等式：x^5-x>0",
        "解不等式：x+y>0",
        "解不等式：x^2-a>0",
        "解不等式：x^2>0，且x<1",
    ],
)
def test_conditions_other_goals_and_unsupported_domains_are_not_certified(question):
    assert source_inequality(question) is None


@pytest.mark.parametrize(
    "answer",
    [
        "[3,2]",
        "[-∞,2]",
        "[2,∞]",
        "y∈[2,3]",
        "{y|2<x<3}",
        "__import__('os')",
        "2<=x<=3\n错误过程",
        r"\letter x<3",
    ],
)
def test_ambiguous_domains_and_non_math_are_rejected(answer):
    with pytest.raises((ValueError, SyntaxError)):
        solution_set(answer, X)


def test_reference_must_match_source_before_any_learning_update():
    for reference in ("(2,3)", "x<2或x>3", "模型认为答案是2"):
        result = grade_inequality(QUESTION, "[2,3]", reference)
        assert result["verdict"] == "review_required" and result["conflict"]
        assert not result["can_update_learning"]


@pytest.mark.parametrize("variable", ["α", "t"])
def test_supported_single_letter_variable_survives_display_and_answer_parsing(variable):
    question = f"解不等式：{variable}^2-4≤0"
    source = source_inequality(question)
    shown = format_solution(source)
    assert solution_set(shown, source.variable) == source.solutions
    assert (
        grade_inequality(question, f"{{{variable}|-2≤{variable}≤2}}", shown)["verdict"]
        == "confirmed_correct"
    )


def test_factorization_is_correct_and_wrong_range_is_the_second_step():
    rows, complete = inequality_alignment(
        QUESTION,
        steps("观察开口、找零点、画图等参考说明"),
        steps("(x-2)(x-3)≤0", "x≤2或x≥3"),
        "x≤2或x≥3",
    )
    assert not complete and len(rows) == 2
    assert rows[0]["math_valid"] and not rows[0]["is_first_error"]
    assert rows[1]["is_first_error"] and rows[1]["student_step_id"] == "step-1"
    assert rows[1]["alignment"] == "invalid_transformation"


def test_boundary_equations_and_partial_necessary_bounds_are_valid_intermediates():
    rows, complete = inequality_alignment(
        QUESTION,
        [],
        steps("(x-2)(x-3)=0", "x=2", "x=3", "x>=2", "x<=3", "2<=x<=3"),
        "[2,3]",
    )
    assert complete and all(row["math_valid"] for row in rows)
    assert rows[0]["verification_scope"] == "boundary_zeros"
    assert rows[3]["alignment"] == "necessary_condition"
    assert not any(row["is_first_error"] for row in rows)
    rows, complete = inequality_alignment(QUESTION, [], steps("x>=2"), "x>=2")
    assert not complete and rows[0]["is_first_error"]


def test_unknown_prose_does_not_become_a_wrong_step_or_a_proven_prefix():
    rows, complete = inequality_alignment(
        QUESTION, [], steps("先讨论图形", "(x-2)(x-3)≤0", "x≤2或x≥3"), "x≤2或x≥3"
    )
    assert not complete
    assert rows[0]["alignment"] == "unknown" and rows[1]["math_valid"]
    assert not any(row["is_first_error"] for row in rows)


def test_counterfactual_requires_source_set_and_original_correct_prefix():
    students = steps("(x-2)(x-3)≤0", "x≤2或x≥3")
    rows, _ = inequality_alignment(QUESTION, [], students, students[-1].text)
    good = {
        "corrected_step": "2<=x<=3",
        "repaired_steps": [students[0].text, "2<=x<=3"],
    }
    assert verify_inequality_repair(QUESTION, [], students, rows, good)[
        "root_cause_confirmed"
    ]
    for bad in (
        {**good, "repaired_steps": ["x^2-5x+6≤0", "2<=x<=3"]},
        {"corrected_step": "2<x<3", "repaired_steps": [students[0].text, "2<x<3"]},
        {**good, "corrected_step": "2<x<3"},
        {**good, "repaired_steps": [students[0].text, "x" * 301]},
    ):
        assert not verify_inequality_repair(QUESTION, [], students, rows, bad)[
            "root_cause_confirmed"
        ]


def test_large_polynomials_are_rejected_before_expansion(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("must not expand")

    monkeypatch.setattr(sp, "Poly", forbidden)
    assert source_inequality("解不等式：((x+1)^20+1)^20>0") is None


@pytest.mark.parametrize("answer", ["x^2-5x+6≤0", "(x-2)(x-3)≤0", "{x|x^2-5x+6≤0}"])
def test_repeating_the_constraint_is_valid_work_but_not_a_solved_answer(answer):
    result = grade_inequality(QUESTION, answer, "[2,3]")
    assert result["verdict"] == "review_required" and not result["can_update_learning"]
    assert "取值范围" in result["feedback"]
    rows, complete = inequality_alignment(QUESTION, [], steps(answer), answer)
    assert rows[0]["math_valid"] and not rows[0]["is_first_error"]
    assert not complete


def test_isolated_algebraic_bounds_are_solved_answers():
    result = grade_inequality(
        "解不等式：x^2-2≤0", "-sqrt(2)≤x≤sqrt(2)", "[-sqrt(2),sqrt(2)]"
    )
    assert result["verdict"] == "confirmed_correct"
    rows, complete = inequality_alignment(
        "解不等式：x^2-2≤0", [], steps("-sqrt(2)≤x≤sqrt(2)"), "[-sqrt(2),sqrt(2)]"
    )
    assert complete and rows[0]["math_valid"]
