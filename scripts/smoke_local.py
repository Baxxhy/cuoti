#!/usr/bin/env python3
"""检查真实本地 API/MySQL 基础链；不触发远程 AI，不修改已有学生。"""
from __future__ import annotations

import os
import uuid

import httpx

BASE = os.environ.get("ZHIWEI_API_URL", f"http://127.0.0.1:{os.environ.get('ZHIWEI_BACKEND_PORT', '8000')}/api/v1").rstrip("/")


def data(response: httpx.Response):
    response.raise_for_status()
    payload = response.json()
    assert payload["success"] is True, response.url.path
    return payload["data"]


def main() -> int:
    with httpx.Client(base_url=BASE, timeout=30) as client:
        health = data(client.get("/system/health"))
        assert health["database"] == "mysql" and health["status"] == "healthy"
        assert client.get("/dashboard").status_code == 401

        email = f"smoke-{uuid.uuid4().hex}@minddimension.local"
        password = uuid.uuid4().hex
        registered = data(client.post("/auth/register", json={
            "email": email, "password": password, "name": "本地验收学生", "grade": "初二",
        }))
        logged_in = data(client.post("/auth/login", json={"email": email, "password": password}))
        assert logged_in["id"] == registered["id"]
        client.headers["Authorization"] = f"Bearer {logged_in['access_token']}"
        assert data(client.get("/auth/me"))["id"] == registered["id"]

        data(client.patch("/auth/me", json={"name": "已验证资料保存"}))
        assert data(client.get("/auth/me"))["name"] == "已验证资料保存"
        dashboard = data(client.get("/dashboard"))
        assert dashboard["weekly_questions"] == 0
        assert dashboard["today_reviews"] == 0
        assert dashboard["grade"] == "初二"
        assert dashboard["continue_learning"] is None
        for endpoint in ("/questions", "/reviews/today", "/reviews/history", "/papers"):
            assert data(client.get(endpoint)) == [], endpoint
        analytics = data(client.get("/analytics/overview"))
        assert analytics["summary"] == {
            "knowledge_count": 0, "misconception_count": 0, "evidence_count": 0,
        }
        assert client.get("/admin/workbench").status_code == 403
        assert client.get("/auth/me", headers={"Authorization": "Bearer invalid"}).status_code == 401
        question = data(client.post("/questions/manual", json={
            "question_text": "解方程：2x+3=11", "student_answer": "x=7", "subject": "数学", "grade": "初二",
            "student_steps": ["2x=11+3", "x=7"],
        }))
        qid = question["id"]
        detail = data(client.get(f"/questions/{qid}"))
        assert detail["question_text"] == "解方程：2x+3=11"
        assert detail["student_answer"] == "x=7" and detail["confirmed"] is True
        assert len(data(client.get("/questions"))) == 1
        journey = data(client.get(f"/questions/{qid}/journey"))
        assert journey["question_id"] == qid
        assert journey["stages"][0]["completed"] is True
        assert all(stage["completed"] is False for stage in journey["stages"][1:])
        assert journey["verification"]["verified"] is False
        assert journey["next_action"]["url"].endswith(qid)

        other = data(client.post("/auth/register", json={
            "email": f"smoke-isolation-{uuid.uuid4().hex}@minddimension.local", "password": uuid.uuid4().hex,
            "name": "数据隔离验收学生", "grade": "初二",
        }))
        other_headers = {"Authorization": f"Bearer {other['access_token']}"}
        assert client.get(f"/questions/{qid}", headers=other_headers).status_code == 404
        assert client.get(f"/questions/{qid}/journey", headers=other_headers).status_code == 404
        assert client.delete(f"/questions/{qid}", headers=other_headers).status_code == 404

        paper = data(client.post("/papers", json={"title": "本地验收练习", "question_ids": [qid]}))
        paper_id = paper["id"]
        assert len(data(client.get(f"/papers/{paper_id}"))["items"]) == 1
        assert client.get(f"/papers/{paper_id}", headers=other_headers).status_code == 404
        for kind, signature in (("question", b"%PDF-"), ("answer", b"%PDF-"), ("excel", b"PK")):
            export = data(client.post(f"/papers/{paper_id}/export", json={"kind": kind}))
            exported = client.get(f"/papers/{paper_id}/download", params={"kind": kind})
            exported.raise_for_status()
            assert exported.content.startswith(signature), kind
            media = client.get(httpx.URL(BASE).join(export["url"]))
            media.raise_for_status()
            assert media.content == exported.content, kind
            assert client.get(f"/papers/{paper_id}/download", params={"kind": kind},
                              headers=other_headers).status_code == 404
        assert data(client.delete(f"/papers/{paper_id}"))["deleted"] is True
        assert data(client.delete(f"/questions/{qid}"))["deleted"] is True
        assert data(client.get("/questions")) == []
        assert data(client.get("/papers")) == []
        print("local_smoke=passed database=mysql auth=passed profile=passed role_guard=passed")
        print("manual_question=passed journey=passed ownership=passed paper_exports=3 archive=passed")
        print("ai_calls=0 live_ai_coverage=not_run (run make verify-live-ai for the real model workflow)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
