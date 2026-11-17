import json

from cuoti_backend import task_leases


def test_cancelled_or_replaced_lease_cannot_submit():
    task = {"status": "running", "lease_token": "current", "cancel_requested": False}
    assert task_leases.lease_valid(task, "current")
    assert not task_leases.lease_valid(task, "old")
    assert not task_leases.lease_valid({**task, "cancel_requested": True}, "current")
    assert not task_leases.lease_valid({**task, "status": "completed"}, "current")


def test_preparation_failure_preserves_photo_and_pending_action_scope(monkeypatch):
    calls = []
    monkeypatch.setattr(
        task_leases, "execute", lambda db, sql, params: calls.append((sql, params))
    )
    task_leases.fail_preparation(
        None,
        {"id": "task", "student_view": {"handwriting": {"image_url": "/photo.jpg"}}},
        "prepare_budget",
        limit=True,
    )
    view = json.loads(calls[0][1][0])
    assert view["handwriting"]["image_url"] == "/photo.jpg"
    assert view["secondary_actions"] == ["resume"]
    assert "status='pending'" in calls[1][0]
