import pytest
from cuoti_backend import task_evidence
from cuoti_backend.protocol import ApiError


def test_exposure_and_actual_answer_gate(monkeypatch):
    calls = []
    monkeypatch.setattr(task_evidence, "execute", lambda *a: calls.append(a))

    def read(db, sql, params):
        if "SELECT subject" in sql and sql.startswith("SELECT subject"):
            return [{"subject": "数学"}]
        if "FROM learning_task_exposures" in sql:
            return [{"task_id": "one"}]
        return []

    monkeypatch.setattr(task_evidence, "rows", read)
    task = {
        "id": "one",
        "user_id": "user",
        "question_id": "question",
        "pending_action": {"kind": "answer"},
        "learning_applied": False,
    }
    result = {
        "status": "completed",
        "learning_eligible": True,
        "checkpoint": {"contrast": {"question": "2x=6"}, "contrast_passed": True},
        "attempt": {
            "phase": "contrast",
            "verdict": "confirmed_correct",
            "assisted": False,
            "grading": {"can_update_learning": True},
        },
    }
    assert task_evidence.learning_admission(None, task, result)
    assert not task_evidence.learning_admission(None, {**task, "id": "two"}, result)
    assert not task_evidence.learning_admission(
        None, {**task, "learning_applied": True}, result
    )
    with pytest.raises(ApiError):
        task_evidence.learning_admission(
            None, {**task, "pending_action": {"kind": "hint"}}, result
        )
    with pytest.raises(ApiError):
        task_evidence.learning_admission(
            None, task, {**result, "attempt": {**result["attempt"], "assisted": True}}
        )


@pytest.mark.parametrize(
    "assisted,verdict,interval",
    [
        (False, "confirmed_correct", 3),
        (True, "confirmed_correct", 1),
        (False, "confirmed_incorrect", 1),
    ],
)
def test_mastery_evidence_and_review(monkeypatch, assisted, verdict, interval):
    from cuoti_backend import learning_evidence, question_data
    from cuoti_backend.task_budget import TaskBudget

    applied, written = [], []
    monkeypatch.setattr(
        task_evidence,
        "rows",
        lambda db, sql, params: (
            [{"instant": "2026-11-17T00:00:00Z"}] if "DATE_FORMAT" in sql else []
        ),
    )
    monkeypatch.setattr(
        question_data,
        "select_rows",
        lambda *a: [
            {"id": "q", "subject": "数学", "knowledge_points": ["方程"], "options": []}
        ],
    )
    monkeypatch.setattr(
        learning_evidence, "apply_evidence", lambda *a, **kw: applied.append((a[4], kw))
    )
    monkeypatch.setattr(task_evidence, "execute", lambda *a: written.append(a))
    task = {
        "id": "task",
        "user_id": "user",
        "question_id": "q",
        "active_request": "request",
        "checkpoint": {"phase": "independent"},
        "pending_action": {"kind": "answer", "text": "3"},
    }
    result = {
        "checkpoint": {
            "workflow_version": "langgraph-learning-v1",
            "hints": {"independent": ["提示"] if assisted else []},
        },
        "attempt": {
            "phase": "independent",
            "verdict": verdict,
            "answer": "3",
            "assisted": assisted,
            "grading": {
                "can_update_learning": True,
                "verdict": verdict,
                "correct": verdict == "confirmed_correct",
            },
        },
    }
    assert task_evidence.apply_mastery(None, None, task, result, TaskBudget(), False)
    evidence, kwargs = applied[0]
    assert evidence["aemt_event"]["hint_used"] == assisted
    assert evidence["action_request_id"] == "request"
    assert kwargs["compute_timeout"] == 5
    assert written[0][2][-1] == interval
    result["checkpoint"]["revealed_phases"] = ["independent"]
    assert not task_evidence.apply_mastery(
        None, None, task, result, TaskBudget(), False
    )
    assert len(applied) == 1
    result["checkpoint"].pop("revealed_phases")
    monkeypatch.setattr(task_evidence, "rows", lambda *a: [{"id": "existing-evidence"}])
    assert not task_evidence.apply_mastery(None, None, task, result, TaskBudget(), False)
    assert len(applied) == 1
    result["attempt"]["answer"] = "伪造作答"
    with pytest.raises(ApiError):
        task_evidence.apply_mastery(None, None, task, result, TaskBudget(), False)
