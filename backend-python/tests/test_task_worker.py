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
