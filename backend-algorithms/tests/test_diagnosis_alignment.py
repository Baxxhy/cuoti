from types import SimpleNamespace

from diagnosis_alignment import (
    polynomial_alignment,
    source_equation,
    verify_polynomial_repair,
)


def steps(*values):
    return [
        SimpleNamespace(id=f"s-{index}", text=value)
        for index, value in enumerate(values)
    ]


def test_short_valid_derivation_does_not_inherit_reference_prose_errors():
    refs = steps(
        "观察方程 x^2-5x+6=0，寻找两个数。",
        "确定这两个数为 -2 和 -3。",
        "将方程因式分解为 (x-2)(x-3)=0。",
        "根据零乘积性质分别求解。",
    )
    result, complete = polynomial_alignment(
        "解方程：x^2-5x+6=0，写出所有实数解。",
        refs,
        steps("(x-2)(x-3)=0", "x=2"),
        "x=2",
    )
    assert len(result) == 2 and not complete
    assert result[0]["math_valid"] and not result[0]["is_first_error"]
    assert result[1]["is_first_error"]
    assert result[1]["alignment"] == "condition_omission"
    assert result[1]["student_step_id"] == "s-1"


def test_all_branches_with_complete_answer_are_valid_without_missing_prose_steps():
    result, complete = polynomial_alignment(
        "解方程：x^2-5x+6=0",
        steps("先因式分解，再求解，最后检查。"),
        steps("(x-2)(x-3)=0", "x=2", "x=3"),
        "x=2 或 x=3",
    )
    assert complete and len(result) == 3
    assert all(row["math_valid"] and not row["is_first_error"] for row in result)
    assert result[-1]["verification_scope"] == "branch_root"


def test_wrong_root_and_later_equivalent_form_do_not_erase_first_error():
    result, complete = polynomial_alignment(
        "解方程：2*x+3=11",
        steps("2*x=8", "x=4"),
        steps("2*x=10", "x=5", "x=4"),
        "x=4",
    )
    assert not complete
    assert result[0]["is_first_error"] and result[0]["reference_step_id"] == "s-0"
    assert result[1]["propagated"] and not result[2]["propagated"]


def test_valid_steps_do_not_verify_a_different_final_answer():
    _, complete = polynomial_alignment(
        "解方程：2*x+3=11", steps("x=4"), steps("x=4"), "x=5"
    )
    assert not complete


def test_multiple_roots_written_on_one_line_are_a_valid_complete_step():
    result, complete = polynomial_alignment(
        "解方程：x^2-5x+6=0",
        steps("分别求解两个因式。"),
        steps("(x-2)(x-3)=0", "x=2 或 x=3"),
        "2,3",
    )
    assert complete and all(row["math_valid"] for row in result)
    assert not any(row["is_first_error"] for row in result)


def test_unsupported_domains_goals_and_prose_are_not_symbolically_certified():
    for source in (
        "已知 2*x+3=11，求 x^2",
        "解方程：x/x=1",
        "解方程：sqrt(x)=2",
        "解方程：x^5-x=0",
        "解方程：x+1=2，求 x^2",
    ):
        assert source_equation(source) is None
    assert (
        polynomial_alignment(
            "解方程：2*x+3=11", steps("x=4"), steps("我认为 x=4"), "x=4"
        )
        is None
    )


def test_repair_requires_all_roots_and_preserves_preceding_correct_work():
    text = "解方程：x^2-5x+6=0"
    students = steps("(x-2)(x-3)=0", "x=2")
    refs = steps("x^2-5x+6=0")
    alignment, _ = polynomial_alignment(text, refs, students, "x=2")
    candidate = {
        "corrected_step": "x=2 或 x=3",
        "repaired_steps": [students[0].text, "x=2 或 x=3"],
    }
    assert verify_polynomial_repair(text, refs, students, alignment, candidate)[
        "root_cause_confirmed"
    ]
    for changed in (
        {**candidate, "repaired_steps": ["x^2-5x+6=0", "x=2 或 x=3"]},
        {
            **candidate,
            "corrected_step": "x=2",
            "repaired_steps": [students[0].text, "x=2"],
        },
        {**candidate, "repaired_steps": [students[0].text, "x=2 或 x=4"]},
    ):
        assert not verify_polynomial_repair(text, refs, students, alignment, changed)[
            "root_cause_confirmed"
        ]
