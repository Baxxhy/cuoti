from app.models import TeacherClassStudent, TeacherReviewTask
from app.teacher_api import _review_reasons


def test_uncertain_grading_enters_teacher_queue():
    reasons = _review_reasons(
        {"verdict": "probably_correct", "conflict": False},
        ocr_confidence=0.9,
        incomplete=False,
    )
    assert reasons == ["probably_correct"]


def test_decisive_grading_does_not_enter_teacher_queue():
    reasons = _review_reasons(
        {"verdict": "confirmed_correct", "conflict": False},
        ocr_confidence=0.98,
        incomplete=False,
    )
    assert reasons == []


def test_review_reasons_preserve_conflicting_and_low_confidence_evidence():
    reasons = _review_reasons(
        {"verdict": "review_required", "conflict": True},
        ocr_confidence=0.42,
        incomplete=True,
    )
    assert reasons == [
        "review_required",
        "rule_llm_conflict",
        "low_ocr_confidence",
        "incomplete_reference",
    ]


def test_class_membership_and_review_source_are_unique():
    class_constraints = {constraint.name for constraint in TeacherClassStudent.__table__.constraints}
    review_constraints = {constraint.name for constraint in TeacherReviewTask.__table__.constraints}
    assert "uq_teacher_class_student" in class_constraints
    assert "uq_teacher_review_source" in review_constraints
