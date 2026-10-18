import asyncio

from grading_compute import UnavailableGradingProvider, angular_answer, grade_answer


def grade(
    answer,
    expected=r"$\angle C=70^{\circ}$",
    question="在三角形ABC中，∠A=50°，∠B=60°，求∠C。",
):
    return asyncio.run(
        grade_answer(
            UnavailableGradingProvider(),
            question=question,
            subject="数学",
            question_type="综合题",
            answer=answer,
            expected=expected,
            reference_solution=[],
        )
    )


def test_standard_degree_notation_does_not_require_identical_latex():
    for value in ("70°", "70度", r"$70^\circ$", "∠C=70°", "∠ACB=70°"):
        result = grade(value)
        assert (
            result["verdict"] == "confirmed_correct" and result["can_update_learning"]
        )
        assert result["recognized_answer"] == value
        assert result["expected_answer"] == r"$\angle C=70^{\circ}$"
    assert grade("80°")["verdict"] == "confirmed_incorrect"


def test_unknown_or_different_angle_names_do_not_turn_equal_numbers_into_proof():
    assert grade("∠A=70°")["verdict"] != "confirmed_correct"
    assert (
        grade("∠A=70°", expected="70°", question="求这个角的度数。")["verdict"]
        != "confirmed_correct"
    )
    assert angular_answer("70° + javascript") is None
    assert angular_answer("弧度1.22") is None
    assert angular_answer("80°\n70°") is None
    assert grade("∠C=80°\n∠C=70°")["verdict"] != "confirmed_correct"
