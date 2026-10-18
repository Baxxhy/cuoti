#!/usr/bin/env python3
"""通过真实 AI 执行一条学习链；公开任务的答案由验收者独立输入。"""
from __future__ import annotations

import io
import json
import os
import sys
import time
import uuid
from pathlib import Path

import httpx
from PIL import Image, ImageDraw, ImageFont

BASE = os.environ.get("ZHIWEI_API_URL", f"http://127.0.0.1:{os.environ.get('ZHIWEI_BACKEND_PORT', '8000')}/api/v1").rstrip("/")


def data(response: httpx.Response):
    response.raise_for_status()
    return response.json()["data"]


def main() -> int:
    if not sys.stdin.isatty():
        raise SystemExit("真实 AI 验收需要交互终端，按公开题干独立作答：make verify-live-ai")
    client = httpx.Client(timeout=360)
    user = data(client.post(BASE + "/auth/register", json={
        "email": f"live-smoke-{uuid.uuid4().hex}@minddimension.local", "password": uuid.uuid4().hex,
        "name": "真实 AI 验收学生", "grade": "初一",
    }))
    headers = {"Authorization": f"Bearer {user['access_token']}"}
    provider_before = data(client.get(BASE + "/system/providers", headers=headers))
    print(f"live_run=user:{user['id']} model={provider_before['logical_model']}", flush=True)
    image = Image.new("RGB", (900, 600), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 36)
    draw.text((70, 70), "Solve: 2x + 3 = 11", fill="black", font=font)
    draw.text((90, 220), "2x = 11 + 3", fill="#18345c", font=font)
    draw.text((90, 300), "x = 7", fill="#18345c", font=font)
    draw.line((60, 210, 520, 210), fill="#dc2f2f", width=8)
    draw.text((550, 220), "sign!", fill="#dc2f2f", font=font)
    buf = io.BytesIO(); image.save(buf, format="JPEG")
    ingest = data(client.post(BASE + "/questions/ingest", headers=headers, files={"file": ("demo.jpg", buf.getvalue(), "image/jpeg")}, data={"subject": "数学"}))
    print(f"ingest=started question_id={ingest['question_id']}", flush=True)
    # 远端视觉模型遇到线路限流时可能较慢；smoke 只关心功能完成，不做性能门禁。
    for _ in range(900):
        try:
            job = data(client.get(BASE + "/jobs/" + ingest["job_id"], headers=headers))
        except httpx.TransportError:
            time.sleep(1)
            continue
        if job["status"] in {"completed", "failed"}:
            break
        time.sleep(1)
    assert job["status"] == "completed", job
    print("ingest=completed", flush=True)
    question = data(client.get(BASE + "/questions/" + ingest["question_id"], headers=headers))
    assert {"original", "clean", "red_mask", "overlay"}.issubset({a["kind"] for a in question["assets"]})
    data(client.post(BASE + f"/questions/{question['id']}/confirm", headers=headers, json={
        "question_text": "解方程：2x+3=11", "student_answer": "x=7", "subject": "数学",
        "grade": "初一", "question_type": "计算题", "knowledge_points": ["一元一次方程", "等价变形"],
        "student_steps": [{"text": "2x=11+3"}, {"text": "x=7"}],
    }))
    analysis = data(client.post(BASE + f"/questions/{question['id']}/analyze", headers=headers))
    assert analysis["verified"] is True, "固定方程必须通过规则校验"
    # 固定夹具由验收者预先计算：2x = 11 - 3 = 8，因此 x = 4。
    assert str(analysis["final_answer"]).replace(" ", "") == "x=4", analysis["final_answer"]
    diagnosis = data(client.post(BASE + f"/questions/{question['id']}/diagnose", headers=headers))
    assert diagnosis["first_error_step"] == 0, "首错应定位到把减 3 错写成加 3 的第一步"
    print(f"analysis=verified diagnosis={diagnosis['error_type']} first_error_step={diagnosis['first_error_step']}", flush=True)
    session = data(client.post(BASE + "/tutor/sessions", headers=headers, json={"question_id": question["id"]}))
    guidance = data(client.post(BASE + f"/tutor/sessions/{session['id']}/turns", headers=headers,
                                json={"message": "我把3移到了右边，应该怎样检查这一步？"}))
    assert guidance["message"].strip()
    visual = data(client.post(BASE + f"/tutor/sessions/{session['id']}/visualization", headers=headers, json={"type": "equation_balance", "values": {"delta": 3}, "observation": "两边同时减3仍然平衡"}))
    answers = []
    for _ in range(12):
        session = data(client.get(BASE + f"/tutor/sessions/{session['id']}", headers=headers))
        if session["stage"] == "finished":
            break
        if session["stage"] == "understanding" and session["stage_status"] == "passed":
            data(client.post(BASE + f"/tutor/sessions/{session['id']}/advance", headers=headers,
                             json={"target_stage": "teach_back"}))
            continue
        activity = session["activity"]
        assert activity, "尚未结束的教学阶段必须提供任务"
        print(f"\nstage={session['stage']} task={activity['question']}", flush=True)
        for option in activity.get("options", []):
            print(f"  {option['value']}: {option['label']}", flush=True)
        print("请根据公开题干独立作答（选择题填写选项标识，多选用逗号分隔）：", flush=True)
        answer = input().strip()
        assert answer, "验收答案不能为空"
        submitted = answer.split(",") if activity["type"] == "multiple_choice" else answer
        updated = data(client.post(BASE + f"/tutor/sessions/{session['id']}/activity/answer", headers=headers,
                                   json={"activity_id": activity["id"], "answer": submitted, "elapsed_seconds": 30}))
        answers.append({"stage": session["stage"], "question": activity["question"], "answer": submitted,
                        "result_stage": updated["stage"]})
        print(f"answer_saved stage={updated['stage']} feedback={updated.get('activity', {}).get('feedback', '') if updated.get('activity') else updated.get('completion_summary', '')}", flush=True)
    assert session["stage"] == "finished", "教学任务未在本条验收链内完成"
    finished = data(client.post(BASE + f"/tutor/sessions/{session['id']}/finish", headers=headers, json={}))
    journey = data(client.get(BASE + f"/questions/{question['id']}/journey", headers=headers))
    assert next(stage for stage in journey["stages"] if stage["key"] == "transfer")["completed"], "独立近迁移和远迁移须均通过"
    paper = data(client.post(BASE + "/papers", headers=headers, json={"title": "首错点专项练习", "question_ids": [question["id"]]}))
    exports = [data(client.post(BASE + f"/papers/{paper['id']}/export", headers=headers, json={"kind": kind})) for kind in ("question", "answer", "excel")]
    dashboard = data(client.get(BASE + "/dashboard", headers=headers))
    provider = data(client.get(BASE + "/system/providers", headers=headers))
    assert provider["recent_rotation"] != provider_before["recent_rotation"], "本次链路必须有真实 API 池调用记录"
    print(f"user_id={user['id']}")
    print(f"question_id={question['id']} assets={len(question['assets'])} job={job['status']}")
    print(f"diagnosis={diagnosis['error_type']} first_error_step={diagnosis['first_error_step']}")
    print(f"learning=finished independent_transfer=true visualization={visual['type']}")
    mastery_score = (
        finished["mastery"]["mastery_score"]
        if finished.get("mastery") else finished["session"]["mastery_score"]
    )
    print(f"mastery={mastery_score} reviews={dashboard['today_reviews']}")
    print("exports=" + ",".join(item["path"] for item in exports))
    print(f"provider_text={provider['text_entries']} provider_vision={provider['vision_entries']} rotations={len(set(provider['recent_rotation']))}")
    evidence = {
        "user_id": user["id"], "question_id": question["id"], "session_id": session["id"],
        "model": provider_before["logical_model"], "job_status": job["status"], "verified": analysis["verified"],
        "first_error_step": diagnosis["first_error_step"], "answers": answers,
        "journey": journey, "exports": [item["id"] for item in exports],
        "provider_calls_before": len(provider_before["recent_rotation"]),
        "provider_calls_recent": len(provider["recent_rotation"]), "provider_status": provider.get("last_status"),
    }
    report_path = Path("reports") / f"live-smoke-{question['id']}.json"
    report_path.parent.mkdir(exist_ok=True)
    report_path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"evidence={report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
