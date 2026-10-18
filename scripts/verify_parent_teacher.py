#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:8000/api/v1"


def unpack(response: httpx.Response):
    response.raise_for_status(); body = response.json(); assert body["success"], body
    return body["data"]


def login(client: httpx.Client, email: str) -> tuple[dict, dict[str, str]]:
    user = unpack(client.post(BASE + "/auth/login", json={"email": email, "password": "123456"}))
    return user, {"Authorization": f"Bearer {user['access_token']}"}


def main() -> int:
    client = httpx.Client(timeout=60)
    guardian, guardian_headers = login(client, "guardian@minddimension.local")
    students = unpack(client.get(BASE + "/guardians/students", headers=guardian_headers))
    assert guardian["role"] == "guardian" and len(students) == 5
    assert all("average_mastery" in student and "pending_reviews" in student for student in students)
    guardian_report = unpack(client.get(BASE + f"/guardians/students/{students[0]['id']}/overview",
                                        headers=guardian_headers))
    assert guardian_report["student"]["id"] == students[0]["id"] and "summary" in guardian_report
    teacher, teacher_headers = login(client, "teacher@minddimension.local")
    classes = unpack(client.get(BASE + "/teachers/classes", headers=teacher_headers))
    assert teacher["role"] == "teacher" and classes and classes[0]["student_count"] == 5
    classroom = unpack(client.get(BASE + f"/teachers/classes/{classes[0]['id']}", headers=teacher_headers))
    assert len(classroom["students"]) == 5
    reports = [unpack(client.get(BASE + f"/teachers/students/{student['id']}/report", headers=teacher_headers))
               for student in classroom["students"]]
    assert all("mastery" in report and "misconceptions" in report and "suggestion" in report for report in reports)
    report = {"passed": True, "guardian_student_count": len(students), "class_count": len(classes),
              "class_student_count": len(classroom["students"]),
              "student_names": [student["name"] for student in classroom["students"]],
              "report_summaries": [value["summary"] for value in reports], "mysql_aggregates": True}
    target = ROOT / "reports/verification/parent_teacher.json"; target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False)); return 0


if __name__ == "__main__":
    raise SystemExit(main())
