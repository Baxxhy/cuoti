from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.learning_api import ManualQuestion
from app.models import (
    DatasetPracticeAttempt,
    Diagnosis,
    ProcessingJob,
    Question,
    ReviewPlan,
    ReviewRecord,
    TutorSession,
)
from app.services.learning_journey import build_learning_journey

NOW = datetime(2026, 10, 13, 12, tzinfo=timezone.utc)


def question(**kwargs):
    return Question(
        id="question",
        user_id="student",
        title="方程",
        subject="数学",
        question_type="计算题",
        question_text="求 2x+3=7 的解",
        created_at=NOW,
        **kwargs,
    )


def session(**kwargs):
    return TutorSession(id="session", created_at=NOW, updated_at=NOW, **kwargs)


def test_empty_record_never_claims_mastery_and_routes_to_confirmation():
    data = build_learning_journey(question(confirmed=False), now=NOW)
    assert not any(s["completed"] for s in data["stages"])
    assert data["next_action"]["url"] == "/pages/ocr/ocr?id=question"
    assert data["practice"]["verified_attempts"] == 0
    assert data["verification"]["verified"] is False


def test_completed_assisted_session_is_not_independent_mastery():
    data = build_learning_journey(
        question(confirmed=True),
        sessions=[
            session(
                status="completed",
                state={
                    "understanding_passed": True,
                    "teach_back_passed": True,
                    "near_transfer": True,
                    "far_transfer": True,
                    "assisted": True,
                },
            )
        ],
        now=NOW,
    )
    assert data["stages"][2]["completed"] is True
    assert data["stages"][3]["completed"] is False


def test_independent_transfer_needs_both_successes_without_assistance():
    data = build_learning_journey(
        question(confirmed=True),
        sessions=[
            session(
                status="completed",
                state={
                    "near_transfer": True,
                    "far_transfer": True,
                },
            )
        ],
        now=NOW,
    )
    assert data["stages"][3]["completed"] is True
    assert data["stages"][4]["completed"] is False


def test_changed_question_does_not_reuse_old_learning_flags():
    data = build_learning_journey(
        question(confirmed=True),
        sessions=[
            session(
                status="completed",
                state={
                    "question_changed": True,
                    "understanding_passed": True,
                    "teach_back_passed": True,
                    "near_transfer": True,
                    "far_transfer": True,
                },
            )
        ],
        now=NOW,
    )
    assert data["stages"][2]["completed"] is False
    assert data["stages"][3]["completed"] is False
    assert any("不计入当前进度" in e["detail"] for e in data["events"])


def test_new_tutoring_session_preserves_valid_evidence_and_remains_next_action():
    earlier = session(
        status="completed",
        state={
            "understanding_passed": True,
            "teach_back_passed": True,
            "near_transfer": True,
            "far_transfer": True,
        },
    )
    current = TutorSession(
        id="current",
        created_at=NOW + timedelta(hours=1),
        updated_at=NOW + timedelta(hours=1),
        status="active",
        state={},
    )
    diagnosis = Diagnosis(id="diagnosis", created_at=NOW, root_misconception="移项符号")
    data = build_learning_journey(
        question(confirmed=True),
        diagnosis=diagnosis,
        sessions=[earlier, current],
        now=NOW + timedelta(hours=2),
    )
    assert data["stages"][2]["completed"] is True
    assert data["stages"][3]["completed"] is True
    assert data["next_action"]["url"] == "/pages/tutor/tutor?id=current"
    assert "曾有独立迁移证据" in data["summary"]


def test_separate_sessions_cannot_be_combined_into_complete_evidence():
    earlier = session(status="completed", state={"understanding_passed": True, "near_transfer": True})
    current = TutorSession(
        id="current",
        created_at=NOW + timedelta(hours=1),
        updated_at=NOW + timedelta(hours=1),
        status="completed",
        state={"teach_back_passed": True, "far_transfer": True},
    )
    data = build_learning_journey(question(confirmed=True), sessions=[earlier, current], now=NOW)
    assert data["stages"][2]["completed"] is False
    assert data["stages"][3]["completed"] is False


def test_pending_grades_are_not_counted_as_correct_evidence():
    practice = DatasetPracticeAttempt(
        id="attempt", created_at=NOW, correct=True, grading_details={"can_update_learning": False}
    )
    record = ReviewRecord(
        id="review",
        created_at=NOW,
        grade="pending",
        correct=True,
        grading_details={"can_update_learning": True},
    )
    data = build_learning_journey(question(confirmed=True), practices=[practice], reviews=[record], now=NOW)
    assert data["practice"] == {"attempts": 1, "verified_attempts": 0, "correct": 0, "pending": 1}
    assert data["review"]["completed"] == 0
    assert data["stages"][4]["completed"] is False


def test_review_actions_use_china_day_boundary_and_naive_mysql_dates():
    # 12:00 UTC is 20:00 China; 17:00 UTC belongs to tomorrow in China.
    diagnosis = Diagnosis(id="diagnosis", created_at=NOW, root_misconception="移项符号")
    tomorrow = ReviewPlan(
        id="tomorrow", due_at=(NOW + timedelta(hours=5)).replace(tzinfo=None), status="pending"
    )
    today = ReviewPlan(id="today", due_at=(NOW + timedelta(hours=2)).replace(tzinfo=None), status="pending")
    data = build_learning_journey(
        question(confirmed=True), diagnosis=diagnosis, plans=[tomorrow, today], now=NOW
    )
    assert data["review"]["due"] == 1
    assert data["next_action"]["url"] == "/pages/review/review?plan=today"


def test_ocr_in_progress_routes_to_the_persisted_job():
    data = build_learning_journey(
        question(confirmed=True), job=ProcessingJob(id="job", status="running"), now=NOW
    )
    assert data["next_action"]["url"] == "/pages/ocr/ocr?id=question&job=job"


@pytest.mark.parametrize(
    "payload",
    [
        {"question_text": "  "},
        {"question_text": "x", "student_steps": [""]},
        {"question_text": "x", "student_steps": ["x"] * 31},
    ],
)
def test_manual_question_rejects_empty_or_excessive_content(payload):
    with pytest.raises(ValidationError):
        ManualQuestion.model_validate(payload)


def test_manual_question_trims_user_input():
    data = ManualQuestion.model_validate({"question_text": "  求 x  ", "student_steps": [" x=2 "]})
    assert data.question_text == "求 x"
    assert data.student_steps == ["x=2"]


def test_changed_question_does_not_count_old_practice_or_review_evidence():
    changed = {"can_update_learning": True, "question_changed": True}
    practice = DatasetPracticeAttempt(id="attempt", created_at=NOW, correct=True, grading_details=changed)
    record = ReviewRecord(id="review", created_at=NOW, grade="good", correct=True, grading_details=changed)
    data = build_learning_journey(question(confirmed=True), practices=[practice], reviews=[record], now=NOW)
    assert data["practice"]["verified_attempts"] == 0
    assert data["practice"]["pending"] == 0
    assert data["review"]["completed"] == 0
    assert data["stages"][4]["completed"] is False


def test_only_current_unverified_practice_remains_pending_after_question_edit():
    attempts = [
        DatasetPracticeAttempt(
            id="historical",
            created_at=NOW,
            correct=False,
            grading_details={"can_update_learning": False, "question_changed": True},
        ),
        DatasetPracticeAttempt(
            id="current-pending",
            created_at=NOW,
            correct=False,
            grading_details={"can_update_learning": False},
        ),
        DatasetPracticeAttempt(
            id="current-verified", created_at=NOW, correct=True, grading_details={"can_update_learning": True}
        ),
    ]
    data = build_learning_journey(question(confirmed=True), practices=attempts, now=NOW)
    assert data["practice"] == {"attempts": 3, "verified_attempts": 1, "correct": 1, "pending": 1}
    assert any(
        event["id"] == "practice:historical" and "历史记录" in event["detail"] for event in data["events"]
    )
