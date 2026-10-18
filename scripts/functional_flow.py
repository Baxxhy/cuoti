from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:8000/api/v1"


def unpack(response: httpx.Response):
    response.raise_for_status()
    body = response.json()
    assert body["success"], body
    return body["data"]


def wait_job(client: httpx.Client, headers: dict[str, str], job_id: str) -> dict[str, Any]:
    # Functional acceptance must not misclassify a slow, rate-limited AI pool as
    # a product failure. A terminal status still ends the wait immediately.
    for _ in range(900):
        job = unpack(client.get(BASE + "/jobs/" + job_id, headers=headers))
        if job["status"] in {"completed", "failed"}:
            return job
        time.sleep(1)
    raise AssertionError("processing job did not finish within 15 minutes")


def run_functional_case(
    client: httpx.Client, case: dict[str, Any], image_meta: dict[str, Any], email: str,
) -> dict[str, Any]:
    user = unpack(client.post(BASE + "/auth/register", json={"email": email, "name": case["name"], "grade": "初二", "password": "123456"}))
    headers = {"Authorization": f"Bearer {user['access_token']}"}
    pool_before = unpack(client.get(BASE + "/system/providers", headers=headers))
    image_path = ROOT / image_meta["image"]
    with image_path.open("rb") as stream:
        ingest = unpack(client.post(BASE + "/questions/ingest", headers=headers,
                                   files={"file": (image_path.name, stream, "image/jpeg")},
                                   data={"subject": case["subject"]}))
    job = wait_job(client, headers, ingest["job_id"])
    assert job["status"] == "completed", job
    question = unpack(client.get(BASE + f"/questions/{ingest['question_id']}", headers=headers))
    streams = {item["stream"] for item in question["ocr_runs"]}
    if "qwen_crop" not in streams:
        rerun = unpack(client.post(BASE + f"/questions/{question['id']}/ocr", headers=headers))
        question = rerun["question"]; streams = {item["stream"] for item in question["ocr_runs"]}
    assert {"original", "clean", "red_mask", "overlay"} <= {item["kind"] for item in question["assets"]}
    assert "qwen_crop" in streams
    confirmed = unpack(client.post(BASE + f"/questions/{question['id']}/confirm", headers=headers, json={
        "question_text": image_meta["question"], "student_answer": image_meta["student_answer"],
        "subject": image_meta["subject"], "formulas": image_meta["formulas"],
        "student_steps": [{"text": text, "confidence": 1, "source": "validation"}
                          for text in image_meta["student_steps"]],
        "teacher_marks": [{"comment": image_meta["teacher_comment"], "confidence": 1}],
        "knowledge_points": [case["name"].replace("错误", "")],
    }))
    assert confirmed["confirmed"]
    analysis = unpack(client.post(BASE + f"/questions/{question['id']}/analyze", headers=headers))
    diagnosis = unpack(client.post(BASE + f"/questions/{question['id']}/diagnose", headers=headers))
    assert analysis["reference_steps"] and diagnosis["evidence"]
    session = unpack(client.post(BASE + "/tutor/sessions", headers=headers, json={"question_id": question["id"]}))
    turn = unpack(client.post(BASE + f"/tutor/sessions/{session['id']}/turns", headers=headers,
                              json={"message": "我完全不会，也不知道从哪里开始"}))
    assert turn["branch"] == "completely_unknown"
    visualization = unpack(client.post(BASE + f"/tutor/sessions/{session['id']}/visualization", headers=headers,
                                       json={"type": case["visualization"], "values": {"delta": 3},
                                             "observation": "调整参数后，图形与底层关系同步变化。"}))
    teach_explanations = {
        "数学": "因为根据题目条件使用等价变形，所以每一步都要保持数学关系，最后得到结论。",
        "物理": "根据物理过程选择相应公式，因为要满足使用条件并检查单位，所以得到这个结论。",
        "历史": "根据材料中的史实和事件背景分析原因，因为前后事件存在因果关系，所以得到这个结论。",
    }
    teach = unpack(client.post(BASE + f"/tutor/sessions/{session['id']}/teach-back", headers=headers,
                               json={"explanation": teach_explanations[case["subject"]]}))
    assert teach["passed"]
    attempts = []
    for transfer in ("near", "far"):
        variant = unpack(client.post(BASE + f"/tutor/sessions/{session['id']}/variant", headers=headers,
                                     json={"transfer_type": transfer}))
        attempt = unpack(client.post(BASE + f"/variants/{variant['id']}/attempt", headers=headers,
                                     json={"answer": variant["answer"], "elapsed_seconds": 35, "hint_level": 0}))
        assert attempt["correct"]
        attempts.append(attempt["attempt"]["id"])
    finished = unpack(client.post(BASE + f"/tutor/sessions/{session['id']}/finish", headers=headers))
    review_attempt = unpack(client.post(BASE + f"/reviews/{finished['review']['id']}/attempt", headers=headers,
                                        json={"answer": analysis["final_answer"]}))
    review = unpack(client.post(BASE + f"/reviews/{finished['review']['id']}/grade", headers=headers,
                                json={"grade": "good", "attempt_id": review_attempt["attempt_id"]}))
    paper = unpack(client.post(BASE + "/papers", headers=headers,
                               json={"title": case["name"] + "专项卷", "question_ids": [question["id"]]}))
    export = unpack(client.post(BASE + f"/papers/{paper['id']}/export", headers=headers, json={"kind": "question"}))
    assert (ROOT / export["path"]).exists()
    dashboard = unpack(client.get(BASE + "/dashboard", headers=headers))
    analytics = unpack(client.get(BASE + "/analytics/overview", headers=headers))
    pool_after = unpack(client.get(BASE + "/system/providers", headers=headers))
    assert pool_after["last_status"] == "ok" and pool_after["last_entry"]
    return {"user_id": user["id"], "question_id": question["id"], "job_id": job["id"],
            "session_id": session["id"], "visualization_id": visualization["id"],
            "attempt_ids": attempts, "review_record_id": review["record"]["id"], "paper_id": paper["id"],
            "paper_item_count": 1, "export_path": str(ROOT / export["path"]), "streams": sorted(streams),
            "qwen_vision": True, "qwen_text": pool_after["last_entry"] != pool_before.get("last_entry")
            or bool(pool_after["recent_rotation"]), "dashboard_questions": dashboard["weekly_questions"],
            "analytics_knowledge": analytics["summary"]["knowledge_count"]}
