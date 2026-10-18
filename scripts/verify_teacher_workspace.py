#!/usr/bin/env python3
from __future__ import annotations

import json

import httpx

BASE = "http://127.0.0.1:8000/api/v1"


def login(client: httpx.Client, email: str) -> dict[str, str]:
    response = client.post("/auth/login", json={"email": email, "password": "123456"})
    response.raise_for_status()
    token = response.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


def main() -> int:
    with httpx.Client(base_url=BASE, timeout=30) as client:
        teacher_headers = login(client, "teacher@minddimension.local")
        student_headers = login(client, "e2e@minddimension.local")
        dashboard = client.get("/teachers/dashboard", headers=teacher_headers)
        queue = client.get("/teachers/reviews", headers=teacher_headers)
        student_denied = client.get("/teachers/dashboard", headers=student_headers)
        foreign_class_hidden = client.get("/teachers/classes/not-a-managed-class", headers=teacher_headers)
        assert dashboard.status_code == 200, dashboard.text
        assert queue.status_code == 200, queue.text
        assert student_denied.status_code == 403, student_denied.text
        assert foreign_class_hidden.status_code == 404, foreign_class_hidden.text
        payload = dashboard.json()
        assert {
            "pending_reviews", "today_mistakes", "overdue_students", "unfinished_assignments",
            "weak_points", "frequent_errors", "attention_students",
        } <= set(payload)
        report = {
            "passed": True,
            "dashboard": dashboard.status_code,
            "review_queue": queue.status_code,
            "student_denied": student_denied.status_code,
            "foreign_class_hidden": foreign_class_hidden.status_code,
        }
        print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
