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
