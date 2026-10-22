from types import SimpleNamespace

from diagnosis_compute import StepRecord
from error_diagnosis import EvidenceWeights, assess_diagnosis


def assess(rows, students=None):
    return assess_diagnosis(
        students=students
        if students is not None
        else [StepRecord(id="s0", text="2*x=14")],
        references=[StepRecord(id="r0", text="2*x=8")],
        alignment=rows,
    )


def row(**extra):
    return {
        "index": 0,
        "student_step_id": "s0",
        "student_text": "2*x=14",
        "reference_step_id": "r0",
        "reference_text": "2*x=8",
        "alignment": "sign_error",
        "is_first_error": True,
        "math_valid": False,
        "verification_scope": "different_roots",
    } | extra


def test_verified_location_has_real_source_evidence_and_no_model_claim():
    result = assess([row()])
    assert result.verified and result.first_error_step == 0
    assert result.next_action == "repair"
    assert [item.source_id for item in result.evidence] == [
        "s0",
        "r0",
        "different_roots",
    ]
    assert result.candidates[0].score == 4
    assert result.score_kind == "uncalibrated_evidence_score"


def test_model_review_requires_concrete_question_even_with_reference():
    result = assess([row(verification_scope="model_review_requires_confirmation")])
    assert not result.verified and result.next_action == "confirm_work"
    assert "第 1 步" in result.question
    assert not any(item.verified for item in result.evidence)


def test_invented_ids_text_indices_and_exact_steps_never_establish_error():
    for extra in [
        {"student_step_id": "invented"},
        {"student_text": "invented"},
        {"index": 5},
        {"alignment": "exact"},
    ]:
        result = assess([row(**extra)])
        assert result.first_error_step is None and not result.verified
    result = assess([row(reference_step_id="invented")])
    assert not any(item.source == "reference_step" for item in result.evidence)


def test_missing_steps_cannot_locate_error():
    result = assess([row()], students=[])
    assert result.first_error_step is None and result.next_action == "confirm_question"


def test_choice_answer_is_work_without_inventing_a_step_or_rule_proof():
    reason = "可能把世界变得不同的愿景当作写作目的，忽略了作者呼吁帮助他人的意图。"
    result = assess_diagnosis(
        students=[],
        references=[],
        alignment=[],
        student_answer="B",
        diagnosis=SimpleNamespace(error_type="unknown", root_misconception=reason),
    )
    assert result.reason == reason
    assert result.first_error_step is None and not result.verified
    assert result.confidence_level == "needs_confirmation"
    assert result.next_action == "repair" and not result.question
    assert result.evidence[0].text == "B"
    assert result.evidence[0].source == "student_answer"


def test_existing_work_gets_actionable_analysis_even_if_model_reason_is_empty():
    for answer, students in [("B", []), (None, [StepRecord(id="s", text="x=7")])]:
        result = assess_diagnosis(
            students=students,
            references=[],
            alignment=[],
            student_answer=answer,
            diagnosis=SimpleNamespace(
                error_type="unknown", root_misconception="无法确定错因"
            ),
        )
        assert "检查本次作答" in result.reason
        assert result.confidence_level != "insufficient" and not result.question


def test_missing_work_still_requires_an_answer():
    result = assess([], students=[])
    assert result.confidence_level == "insufficient"
    assert "还没有你的作答" in result.reason


def test_unverified_prefix_blocks_first_error_certainty():
    result = assess(
        [
            row(index=1, student_step_id="s1"),
            row(
                is_first_error=False,
                math_valid=False,
                verification_scope="unverified_intermediate",
            ),
        ],
        students=[
            StepRecord(id="s0", text="解释文字"),
            StepRecord(id="s1", text="2*x=14"),
        ],
    )
    assert result.first_error_step == 1 and not result.verified


def test_supported_correct_work_does_not_create_diagnosis():
    result = assess(
        [row(is_first_error=False, alignment="equivalent", math_valid=True)]
    )
    assert result.verified and result.error_type == "exact"
    assert result.first_error_step is None


def test_weights_are_configurable_without_turning_scores_into_probability():
    result = assess_diagnosis(
        students=[StepRecord(id="s0", text="2*x=14")],
        references=[],
        alignment=[row()],
        weights=EvidenceWeights(rule=5),
    )
    assert result.candidates[0].score == 6


def test_knowledge_association_is_sourced_but_not_a_symbolic_proof():
    result = assess_diagnosis(
        students=[StepRecord(id="s0", text="2*x=14")],
        references=[],
        alignment=[row(verification_scope="model_review_requires_confirmation")],
        diagnosis=SimpleNamespace(root_misconception="等式的性质没有用对"),
        knowledge=[
            {
                "code": "equality",
                "name": "等式的性质",
                "role": "anchor",
                "definition": "等式两边同减同一个数仍相等。",
                "formulas": [],
                "source_hash": "fixture-source-hash",
            }
        ],
    )
    assert result.candidates[0].score == 1.5
    assert result.evidence[-1].source_id == "equality"
    assert not result.verified and not result.evidence[-1].verified


def test_contradictory_alignment_is_penalized_and_never_verified():
    result = assess([row(math_valid=True)])
    assert result.candidates[0].score == -2
    assert not result.verified and "矛盾" in result.reason
