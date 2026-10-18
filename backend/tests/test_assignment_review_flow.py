from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from app.models import (
    AssignmentAttempt,
    AssignmentStudent,
    Question,
    QuestionAssignment,
    TeacherQuestion,
    TeacherReviewTask,
    User,
)
from app.teacher_api import _sync_assignment_review, create_teacher_router


class ReviewDB:
    def __init__(self, rows, scalar_result):
        self.rows = {(type(row), row.id): row for row in rows}
        self.scalar_result = scalar_result
        self.added = []
        self.commits = 0

    async def get(self, model, key, **_kwargs):
        return self.rows.get((model, key))

    async def scalar(self, _statement):
        return self.scalar_result

    def add(self, row):
        self.added.append(row)

    async def flush(self):
        for index, row in enumerate(self.added):
            if not row.id:
                row.id = f"added-{index}"

    async def commit(self):
        self.commits += 1


def endpoint(path):
    router = create_teacher_router(object())
    return next(route.endpoint for route in router.routes if route.path == path)


@pytest.mark.asyncio
@pytest.mark.parametrize(("question_auto", "assignment_auto"), [(False, True), (True, False), (False, False)])
async def test_disabling_automatic_grading_preserves_work_without_calling_model(
    monkeypatch, question_auto, assignment_auto
):
    user = User(id="student", role="student")
    question = Question(id="question", user_id="teacher", subject="数学", question_type="综合题", options=[])
    assignment = QuestionAssignment(
        id="assignment",
        teacher_id="teacher",
        class_id="class",
        question_id=question.id,
        settings={"allow_auto_grade": assignment_auto},
    )
    link = AssignmentStudent(id="link", student_id=user.id, assignment_id=assignment.id, status="pending")
    meta = TeacherQuestion(
        id="meta",
        question_id=question.id,
        teacher_id="teacher",
        allow_auto_grade=question_auto,
        standard_answer="x=2",
        reference_steps=["x=3-1", "x=2"],
    )
    db = ReviewDB([question, assignment, link], meta)
    grader = AsyncMock(side_effect=AssertionError("automatic grading is disabled"))
    monkeypatch.setattr("app.teacher_api.grade_answer", grader)
    submit = endpoint("/api/v1/students/assignments/{student_assignment_id}/attempts")
    result = await submit(link.id, {"answer": "x=2", "steps": ["x=3-1", "x=2"]}, user, db)
    grader.assert_not_awaited()
    assert result["entered_review_queue"]
    assert result["grading"]["correct"] is None
    assert not result["grading"]["can_update_learning"]
    assert link.status == "review_pending"
    attempt = next(row for row in db.added if isinstance(row, AssignmentAttempt))
    task = next(row for row in db.added if isinstance(row, TeacherReviewTask))
    assert attempt.answer == "x=2" and attempt.steps == ["x=3-1", "x=2"]
    assert task.source_id == attempt.id == link.latest_attempt_id
    assert "auto_grade_disabled" in task.reason_codes
    assert db.commits == 1


@pytest.mark.parametrize(
    ("conclusion", "expected"),
    [
        ("confirmed_correct", "completed"),
        ("confirmed_incorrect", "completed"),
        ("partially_correct", "completed"),
        ("resubmit", "pending"),
        ("question_issue", "question_issue"),
        ("revoke", "review_pending"),
    ],
)
def test_teacher_decision_synchronizes_the_latest_student_task(conclusion, expected):
    attempt = AssignmentAttempt(id="attempt", status="review_pending")
    link = AssignmentStudent(id="link", latest_attempt_id=attempt.id, status="review_pending")
    _sync_assignment_review(attempt, link, conclusion)
    assert link.status == expected


def test_reviewing_an_older_attempt_cannot_finish_a_newer_submission():
    attempt = AssignmentAttempt(id="old", status="review_pending")
    link = AssignmentStudent(id="link", latest_attempt_id="new", status="review_pending")
    _sync_assignment_review(attempt, link, "confirmed_correct")
    assert attempt.status == "graded"
    assert link.status == "review_pending"


@pytest.mark.asyncio
async def test_manual_review_honors_assignment_mastery_setting_and_finishes_task(monkeypatch):
    user = User(id="teacher", role="teacher")
    task = TeacherReviewTask(
        id="task",
        student_id="student",
        class_id="class",
        question_id="question",
        source_id="attempt",
        version=1,
        status="pending",
        learning_applied=False,
        ai_result={},
        rule_result={},
    )
    attempt = AssignmentAttempt(
        id="attempt",
        assignment_student_id="link",
        student_id="student",
        question_id="question",
        status="review_pending",
    )
    link = AssignmentStudent(
        id="link",
        student_id="student",
        assignment_id="assignment",
        latest_attempt_id=attempt.id,
        status="review_pending",
    )
    assignment = QuestionAssignment(id="assignment", settings={"count_mastery": False})
    task.created_at = task.updated_at = datetime.now(timezone.utc)
    db = ReviewDB([attempt, link, assignment], task)
    monkeypatch.setattr("app.teacher_api._managed_student", AsyncMock())
    update = AsyncMock(side_effect=AssertionError("mastery updates are disabled"))
    monkeypatch.setattr("app.teacher_api._apply_learning", update)
    decide = endpoint("/api/v1/teachers/reviews/{task_id}/decision")
    result = await decide(
        task.id, {"version": 1, "conclusion": "confirmed_correct", "reason": "计算正确"}, user, db
    )
    update.assert_not_awaited()
    assert not result["result"]["allow_learning_update"]
    assert task.status == "resolved" and link.status == "completed" and attempt.status == "graded"
    assert db.commits == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "repeat", "required", "photo", "expected"),
    [
        ("pending", False, True, "", 422),
        (
            "pending",
            False,
            False,
            "/uploads/answers/other/assignment/link/handwriting-" + "a" * 32 + ".jpg",
            422,
        ),
        ("review_pending", True, False, "", 409),
        ("question_issue", True, False, "", 409),
        ("completed", False, False, "", 409),
    ],
)
async def test_assignment_rejects_missing_required_photo_foreign_photo_and_unavailable_repeat(
    monkeypatch, status, repeat, required, photo, expected
):
    from fastapi import HTTPException

    user = User(id="student", role="student")
    question = Question(id="question", user_id="teacher", subject="数学", question_type="计算题")
    assignment = QuestionAssignment(
        id="assignment", question_id=question.id, settings={"allow_repeat": repeat}
    )
    link = AssignmentStudent(id="link", student_id=user.id, assignment_id=assignment.id, status=status)
    meta = TeacherQuestion(
        id="meta", question_id=question.id, require_handwriting=required, allow_auto_grade=False
    )
    db = ReviewDB([question, assignment, link], meta)
    grader = AsyncMock(side_effect=AssertionError("invalid submission must not call AI"))
    monkeypatch.setattr("app.teacher_api.grade_answer", grader)
    submit = endpoint("/api/v1/students/assignments/{student_assignment_id}/attempts")
    with pytest.raises(HTTPException) as caught:
        await submit(link.id, {"answer": "x=4", "handwriting_image_url": photo}, user, db)
    assert caught.value.status_code == expected
    assert not db.added and db.commits == 0
    grader.assert_not_awaited()


@pytest.mark.asyncio
async def test_completed_assignment_allows_repeat_when_enabled(monkeypatch):
    user = User(id="student", role="student")
    question = Question(id="question", user_id="teacher", subject="数学", question_type="计算题")
    assignment = QuestionAssignment(id="assignment", question_id=question.id, settings={"allow_repeat": True})
    link = AssignmentStudent(
        id="link",
        student_id=user.id,
        assignment_id=assignment.id,
        status="completed",
        latest_attempt_id="old",
    )
    meta = TeacherQuestion(
        id="meta", question_id=question.id, require_handwriting=False, allow_auto_grade=False
    )
    db = ReviewDB([question, assignment, link], meta)
    submit = endpoint("/api/v1/students/assignments/{student_assignment_id}/attempts")
    result = await submit(link.id, {"answer": "x=4", "steps": ["2x=8"]}, user, db)
    assert result["entered_review_queue"] and link.status == "review_pending"
    assert link.latest_attempt_id != "old" and db.commits == 1


@pytest.mark.asyncio
async def test_required_photo_is_preserved_with_its_validated_recognition(monkeypatch, tmp_path):
    from app.services.answer_handwriting import settings

    monkeypatch.setattr(settings, "upload_dir", tmp_path)
    user = User(id="student", role="student")
    question = Question(id="question", user_id="teacher", subject="数学", question_type="计算题")
    assignment = QuestionAssignment(id="assignment", question_id=question.id, settings={})
    link = AssignmentStudent(id="link", student_id=user.id, assignment_id=assignment.id, status="pending")
    meta = TeacherQuestion(
        id="meta", question_id=question.id, require_handwriting=True, allow_auto_grade=False
    )
    relative = "answers/student/assignment/link/handwriting-" + "b" * 32 + ".jpg"
    original = tmp_path / relative
    original.parent.mkdir(parents=True)
    original.write_bytes(b"original image is unchanged")
    db = ReviewDB([question, assignment, link], meta)
    submit = endpoint("/api/v1/students/assignments/{student_assignment_id}/attempts")
    result = await submit(
        link.id,
        {
            "answer": "x=4",
            "handwriting_image_url": "/uploads/" + relative + "?signature=ignored",
            "handwriting_recognition": {"final_answer": "x=4", "steps": ["2x=8"], "confidence": 0.9},
        },
        user,
        db,
    )
    attempt = next(row for row in db.added if isinstance(row, AssignmentAttempt))
    assert result["entered_review_queue"]
    assert attempt.handwriting_asset_ref == "/uploads/" + relative
    assert attempt.grading_details["handwriting_recognition"]["confidence"] == 0.9
    assert original.read_bytes() == b"original image is unchanged"
