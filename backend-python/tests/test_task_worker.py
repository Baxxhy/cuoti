from hashlib import sha256
from types import SimpleNamespace

import pytest
from cuoti_backend import task_worker
from cuoti_backend.protocol import ApiError


def test_handwriting_input_binds_original_bytes_and_rejects_corruption(monkeypatch):
    raw = b"original-student-photo"
    image = {"original_path": "uploads/answer.png", "sha256": sha256(raw).hexdigest()}
    monkeypatch.setattr(task_worker, "select_rows", lambda *a: [image])
    task = {
        "id": "task",
        "input_fingerprint": "version",
        "pending_action": {"kind": "recognize_handwriting", "handwriting_id": "image"},
    }
    media = SimpleNamespace(read=lambda path: raw)
    action = task_worker.compute_action(None, media, task)
    import base64

    assert base64.b64decode(action["image_base64"]) == raw
    assert "image_base64" not in task["pending_action"]
    image["sha256"] = "0" * 64
    with pytest.raises(ApiError, match="原图校验失败"):
        task_worker.compute_action(None, media, task)
    monkeypatch.setattr(task_worker, "select_rows", lambda *a: [])
    with pytest.raises(ApiError, match="不属于当前任务版本"):
        task_worker.compute_action(None, media, task)


def test_poller_stops_cleanly_after_one_leased_task(monkeypatch):
    from contextlib import nullcontext
    from threading import Event

    from cuoti_backend import task_leases

    finished, calls = Event(), []
    service = SimpleNamespace(
        database=SimpleNamespace(session=lambda: nullcontext(None))
    )
    worker = task_worker.LearningTaskWorker(service)
    monkeypatch.setattr(task_leases, "recoverable_ids", lambda db: ["task"])

    def run(service, id):
        calls.append(id)
        worker.stopping.set()
        finished.set()

    monkeypatch.setattr(task_worker, "run_task", run)
    worker.start()
    assert finished.wait(2)
    worker.close()
    assert calls == ["task"] and not worker.thread.is_alive()


def test_app_lifespan_starts_and_joins_enabled_worker():
    from cuoti_backend.config import Settings
    from cuoti_backend.main import create_app
    from fastapi.testclient import TestClient

    app = create_app(Settings(learning_task_worker_enabled=True))
    with TestClient(app) as client:
        worker = app.state.learning_task_worker
        assert worker.thread.is_alive()
        assert client.get("/livez").status_code == 200
    assert not worker.thread.is_alive()
