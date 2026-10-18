"""Native figure observations: source checks, stored evidence and assisted grading."""

import io
import json
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import uuid4

from PIL import Image, ImageDraw
from smoke_cangjie_accounts import request
from smoke_cangjie_detail import fixture_insert


def task_figures(endpoint, env, query, token, other, state, create):
    from smoke_cangjie_learning_tasks import action, task_request, wait_task

    insert = fixture_insert(env, query)
    owner = request(endpoint, "GET", "/api/v1/auth/me", token=token)["id"]
    q = request(
        endpoint,
        "POST",
        "/api/v1/questions/manual",
        {
            "subject": "数学",
            "grade": "初二",
            "question_type": "综合题",
            "question_text": "在三角形ABC中，∠A=50°，∠B=60°，求∠C。",
            "student_answer": "80",
            "student_steps": ["∠C=80°"],
        },
        token=token,
    )
    insert("problem_analyses", question_id=q["id"], subject="数学", final_answer="70")
    task = wait_task(endpoint, create(q)["id"], token)
    output = io.BytesIO()
    image = Image.new("RGB", (100, 80), "white")
    ImageDraw.Draw(image).rectangle((20, 10, 40, 30), fill="red")
    image.save(output, "PNG")
    raw = output.getvalue()
    original_result = state.get("task_handwriting_result")
    state["task_handwriting_result"] = {
        "final_answer": "80",
        "steps": ["∠C=80°"],
        "transcription": "∠C=80°",
        "confidence": 0.9,
        "uncertain": False,
        "figure_observations": [
            {
                "relation": "angle_value",
                "points": ["A", "C", "B"],
                "value": "80",
                "basis": "label",
                "quote": "∠C=80°",
            }
        ],
    }

    def snapshot():
        return query(
            env,
            f"SELECT (SELECT COUNT(*) FROM cognitive_updates WHERE question_id='{q['id']}'),(SELECT COUNT(*) FROM review_plans WHERE question_id='{q['id']}'),(SELECT COUNT(*) FROM mastery_states WHERE user_id='{owner}'),(SELECT SUM(mastery_score) FROM mastery_states WHERE user_id='{owner}')",
        )

    def upload(account=token, expected=202):
        boundary = "figure-" + uuid4().hex
        fields = {key: task[key] for key in ("version", "step_id", "input_fingerprint")}
        fields["request_id"] = str(uuid4())
        body = b"".join(
            f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'.encode()
            for key, value in fields.items()
        )
        body += (
            f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="figure.png"\r\nContent-Type: image/png\r\n\r\n'.encode()
            + raw
            + f"\r\n--{boundary}--\r\n".encode()
        )
        try:
            response = urlopen(
                Request(
                    endpoint + f"/api/v1/learning-tasks/{task['id']}/handwriting",
                    data=body,
                    headers={
                        "Authorization": "Bearer " + account,
                        "Content-Type": "multipart/form-data; boundary=" + boundary,
                    },
                ),
                timeout=10,
            )
        except HTTPError as error:
            response = error
        with response:
            assert response.status == expected
            return json.load(response).get("data")

    try:
        before = snapshot()
        upload(other, 404)
        upload()
        recognized = wait_task(endpoint, task["id"], token)
        draft = recognized["student_view"]["handwriting"]
        assert draft["figure_review"][0]["status"] == "conflicts"
        assert draft["recognition"]["figure_observations"][0]["value"] == "80"
        photo = query(
            env,
            f"SELECT original_path FROM learning_task_images WHERE id='{draft['id']}'",
        )
        assert (Path(env["CANGJIE_MEDIA_ROOT"]) / photo).read_bytes() == raw
        trace = json.loads(
            query(
                env,
                f"SELECT trace FROM learning_task_steps WHERE task_id='{task['id']}' AND tool_name='inspect_figure'",
            )
        )
        assert trace["validation"] == "needs_review"
        assert (
            trace["evidence"]["classification"] == "model_observation"
            and not trace["evidence"]["student_confirmed"]
        )
        assert snapshot() == before
        supported, _ = action(endpoint, recognized, token, kind="hint")
        assert (
            supported["student_view"]["handwriting"]["figure_review"]
            == draft["figure_review"]
        )
        body = {
            "kind": "answer",
            "text": "70",
            "version": supported["version"],
            "step_id": supported["step_id"],
            "input_fingerprint": supported["input_fingerprint"],
            "request_id": str(uuid4()),
            "handwriting_id": draft["id"],
            "handwriting_confirmed": True,
        }
        task_request(
            endpoint,
            f"/api/v1/learning-tasks/{task['id']}/actions",
            token,
            {**body, "handwriting_recognition": draft["recognition"]},
            status=422,
        )
        task_request(
            endpoint,
            f"/api/v1/learning-tasks/{task['id']}/actions",
            token,
            body,
            status=202,
        )
        done = wait_task(endpoint, task["id"], token)
        assert done["status"] == "completed" and not done["learning_applied"]
        history = request(
            endpoint, "GET", f"/api/v1/learning-tasks/{task['id']}/history", token=token
        )
        assert any(
            item["verdict"] == "confirmed_correct" and item["assisted"]
            for item in history["items"]
        )
        assert snapshot() == before
        if env.get("CANGJIE_VERIFY_BROWSER") == "1":
            task = wait_task(endpoint, create(q)["id"], token)
            upload()
            preview = wait_task(endpoint, task["id"], token)
            assert preview["student_view"]["handwriting"]["figure_review"]
            env["QA_FIGURE_TASK_ID"] = preview["id"]
            env["QA_FIGURE_TOKEN"] = token
        print(
            "Cangjie task figures passed: typed source check, original bytes, private candidate provenance, retained review, client forgery rejected and no independent learning after assistance"
        )
    finally:
        if original_result is None:
            state.pop("task_handwriting_result", None)
        else:
            state["task_handwriting_result"] = original_result
