"""Durable handwriting: upload receipt, original bytes, transcription and confirmation."""

import io
import json
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import uuid4

from PIL import Image
from smoke_cangjie_accounts import request


def task_images(
    endpoint, env, query, token, other, state, create_question, create, started, release
):
    from smoke_cangjie_learning_tasks import action, task_request, wait_task

    question = create_question(23)
    task = wait_task(endpoint, create(question)["id"], token)
    task, _ = action(endpoint, task, token, text="2x=20")
    owner = request(endpoint, "GET", "/api/v1/auth/me", token=token)["id"]
    before = query(
        env, f"SELECT COUNT(*) FROM cognitive_updates WHERE user_id='{owner}'"
    )
    output = io.BytesIO()
    Image.new("RGB", (100, 60), "red").save(output, format="PNG")
    original = output.getvalue()

    def upload(current, *, account=token, req=None, expected=202, raw=original):
        fields = {
            key: current[key] for key in ("version", "step_id", "input_fingerprint")
        }
        fields["request_id"] = req or str(uuid4())
        boundary = "task-photo-" + uuid4().hex
        body = b"".join(
            f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode()
            for k, v in fields.items()
        )
        body += (
            f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="original.png"\r\nContent-Type: image/png\r\n\r\n'.encode()
            + raw
            + f"\r\n--{boundary}--\r\n".encode()
        )
        try:
            response = urlopen(
                Request(
                    endpoint + f"/api/v1/learning-tasks/{current['id']}/handwriting",
                    data=body,
                    headers={
                        "Authorization": "Bearer " + account,
                        "Content-Type": "multipart/form-data; boundary=" + boundary,
                    },
                ),
                timeout=5,
            )
        except HTTPError as error:
            response = error
        with response:
            payload = json.load(response)
            assert response.status == expected, (response.status, payload)
        return payload.get("data")

    def submit(current, image, confirmed=True, expected=202, answer="x=10"):
        body = {
            "kind": "answer",
            "text": answer,
            "version": current["version"],
            "step_id": current["step_id"],
            "input_fingerprint": current["input_fingerprint"],
            "request_id": str(uuid4()),
            "handwriting_id": image,
            "handwriting_confirmed": confirmed,
        }
        return task_request(
            endpoint,
            f"/api/v1/learning-tasks/{current['id']}/actions",
            token,
            body,
            status=expected,
        )

    state["task_handwriting_result"] = {
        "final_answer": "x=14",
        "steps": ["x=14"],
        "transcription": "x=14",
        "uncertain": True,
        "confidence": 0.4,
    }
    upload(task, account=other, expected=404)
    upload(task, raw=b"fake PNG", expected=422)
    upload(task | {"version": task["version"] - 1}, expected=409)
    request_id = str(uuid4())
    accepted_at = time.monotonic()
    queued = upload(task, req=request_id)
    assert time.monotonic() - accepted_at < 2
    assert queued["status"] in {"queued", "running"}
    recognized = wait_task(endpoint, task["id"], token)
    assert recognized["student_view"].get("handwriting"), (
        query(env, f"SELECT exit_reason FROM learning_tasks WHERE id='{task['id']}'"),
        state["errors"],
    )
    draft = recognized["student_view"]["handwriting"]
    assert draft["suggested_text"] == "x=14" and draft["recognition"]["uncertain"]
    assert recognized["student_view"]["title"] == "独立完成这道题"
    assert not recognized["learning_applied"]
    assert (
        query(env, f"SELECT COUNT(*) FROM cognitive_updates WHERE user_id='{owner}'")
        == before
    )
    assert upload(task, req=request_id)["version"] == recognized["version"]
    upload(task, req=request_id, raw=original + b"changed", expected=409)
    from urllib.parse import urlsplit

    with urlopen(
        endpoint
        + urlsplit(draft["image_url"]).path
        + "?"
        + urlsplit(draft["image_url"]).query
    ) as response:
        assert response.read() == original
    assert (
        query(
            env,
            f"SELECT COUNT(*) FROM learning_task_images WHERE task_id='{task['id']}'",
        )
        == "1"
    )
    submit(recognized, draft["id"], confirmed=False, expected=422)
    submit(recognized, str(uuid4()), expected=422)
    recognized, _ = action(endpoint, recognized, token, kind="visualize")
    assert recognized["student_view"]["handwriting"]["id"] == draft["id"]
    failed_observation = str(uuid4())
    query(
        env,
        f"ALTER TABLE learning_task_steps ADD CONSTRAINT photo_visual_rollback CHECK (task_id<>'{task['id']}' OR request_id<>'{failed_observation}')",
    )
    try:
        task_request(
            endpoint,
            f"/api/v1/learning-tasks/{task['id']}/actions",
            token,
            {
                "kind": "observe_visualization",
                "text": "先核对两边",
                "visual_values": {"delta": 1},
                "version": recognized["version"],
                "step_id": recognized["step_id"],
                "input_fingerprint": recognized["input_fingerprint"],
                "request_id": failed_observation,
            },
            status=202,
        )
        recognized = wait_task(endpoint, task["id"], token)
        assert (
            recognized["status"] == "failed"
            and recognized["student_view"]["handwriting"]["id"] == draft["id"]
        )
    finally:
        query(env, "ALTER TABLE learning_task_steps DROP CHECK photo_visual_rollback")
    recognized, _ = action(endpoint, recognized, token, kind="resume")
    assert recognized["student_view"]["handwriting"]["id"] == draft["id"]
    assert recognized["student_view"]["visualization"]["values"] == {"delta": 0}
    recognized, _ = action(endpoint, recognized, token, kind="close_visualization")
    assert recognized["student_view"]["handwriting"]["id"] == draft["id"]
    submitted = submit(recognized, draft["id"])
    contrast = wait_task(endpoint, submitted["id"], token)
    assert contrast["student_view"]["title"] == "换个条件，再试一次"
    submit(contrast, draft["id"], expected=409, answer="x=13")
    saved = query(
        env,
        f"SELECT JSON_EXTRACT(result,'$.attempt.handwriting.text_edited') FROM learning_task_actions WHERE task_id='{task['id']}' AND kind='answer' ORDER BY created_at DESC LIMIT 1",
    )
    assert saved == "true"
    # Target only the next request; existing successful OCR rows must remain valid.
    rollback_request = str(uuid4())
    query(
        env,
        f"ALTER TABLE learning_task_steps ADD CONSTRAINT photo_rollback CHECK (task_id<>'{task['id']}' OR request_id<>'{rollback_request}' OR tool_name<>'recognize_handwriting')",
    )
    state["task_handwriting_result"] = {
        "final_answer": "x=13",
        "steps": ["x=13"],
        "transcription": "x=13",
        "uncertain": False,
        "confidence": 0.9,
    }
    try:
        upload(contrast, req=rollback_request)
        failed = wait_task(endpoint, task["id"], token)
        assert failed["status"] == "failed"
    finally:
        query(env, "ALTER TABLE learning_task_steps DROP CHECK photo_rollback")
    restored, _ = action(endpoint, failed, token, kind="resume")
    assert restored["student_view"]["handwriting"]["suggested_text"] == "x=13"
    assert (
        query(
            env,
            f"SELECT COUNT(*) FROM learning_task_images WHERE task_id='{task['id']}'",
        )
        == "2"
    )
    assert (
        query(env, f"SELECT COUNT(*) FROM cognitive_updates WHERE user_id='{owner}'")
        == before
    )
    done = wait_task(
        endpoint,
        submit(restored, restored["student_view"]["handwriting"]["id"], answer="x=13")[
            "id"
        ],
        token,
    )
    assert done["status"] == "completed" and done["learning_applied"]
    history = request(
        endpoint, "GET", f"/api/v1/learning-tasks/{task['id']}/history", token=token
    )
    assert sum(bool(item["handwriting_image_url"]) for item in history["items"]) >= 3
    assert "image_base64" not in json.dumps(
        history
    ) and "original_path" not in json.dumps(history)
    text_fallback = wait_task(endpoint, create(create_question(29))["id"], token)
    upload(text_fallback, raw=original[:12])
    text_fallback = wait_task(endpoint, text_fallback["id"], token)
    assert (
        text_fallback["status"] == "failed"
        and "use_text" in text_fallback["student_view"]["secondary_actions"]
    )
    text_fallback, _ = action(endpoint, text_fallback, token, kind="use_text")
    assert (
        text_fallback["status"] == "waiting_student"
        and text_fallback["student_view"]["input_kind"] == "text"
    )
    assert not text_fallback["student_view"].get("handwriting")
    interrupted = []
    for constant, ending in ((31, "cancelled"), (33, "stale")):
        candidate_question = create_question(constant)
        candidate = wait_task(endpoint, create(candidate_question)["id"], token)
        state["mode"] = "block"
        started.clear()
        release.clear()
        try:
            upload(candidate)
            assert started.wait(5)
            if ending == "cancelled":
                task_request(
                    endpoint,
                    f"/api/v1/learning-tasks/{candidate['id']}/cancel",
                    token,
                    {},
                )
            else:
                request(
                    endpoint,
                    "PATCH",
                    f"/api/v1/questions/{candidate_question['id']}",
                    {"question_text": "解方程：2x+3=41"},
                    token=token,
                )
        finally:
            state["mode"] = "good"
            release.set()
        assert wait_task(endpoint, candidate["id"], token)["status"] == ending
        interrupted.append(candidate["id"])
    state.pop("task_handwriting_result", None)
    print(
        "Cangjie task handwriting passed: async receipts, original bytes, strict owner/step, idempotent upload, editable OCR confirmation, audit rollback, same-image resume and scoped grading"
    )

    recovery = wait_task(endpoint, create(create_question(27))["id"], token)
    recovery, _ = action(endpoint, recovery, token, text="2x=24")
    upload(recovery)
    recovery = wait_task(endpoint, recovery["id"], token)
    for identifier in interrupted:
        assert (
            query(
                env,
                f"SELECT COUNT(*) FROM learning_task_images WHERE task_id='{identifier}' AND recognition IS NOT NULL",
            )
            == "0"
        )
    return recovery
