"""Exercise native practice with actual local BGE/Qdrant and imported public data."""

import json
import os
from pathlib import Path

import httpx
from prepare_cangjie_question_bank import native

PROJECT = Path(__file__).resolve().parents[1]


def main():
    runtime = PROJECT / ".runtime"
    credentials = json.loads((runtime / "live-system-login.json").read_text())
    base = "http://127.0.0.1:" + os.environ.get("CANGJIE_BACKEND_PORT", "8002")
    report = {"kind": "actual-imported-practice", "passed": False}
    os.umask(0o077)

    def record(stage, **fields):
        report.update(stage=stage, **fields)
        output = runtime / "live-practice-check.json"
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        output.chmod(0o600)
        print(json.dumps({"stage": stage, **fields}, ensure_ascii=False), flush=True)

    def data(response):
        if response.status_code != 200:
            raise ValueError("local practice request failed")
        return response.json()["data"]

    with httpx.Client(timeout=300) as client:
        try:
            user = data(client.post(base + "/api/v1/auth/login", json=credentials))
            headers = {"Authorization": "Bearer " + user["access_token"]}
            question = data(
                client.post(
                    base + "/api/v1/questions/manual",
                    headers=headers,
                    json={
                        "question_text": "解方程：2x+3=11",
                        "subject": "数学",
                        "grade": "初中",
                        "title": "实际题库流程核验",
                    },
                )
            )
            report["mistake_id"] = question["id"]
            record("question-created")
            payload = {"mistake_id": question["id"], "mode": "reinforce"}
            selected = data(
                client.post(
                    base + "/api/v1/practice/recommend", headers=headers, json=payload
                )
            )
            assert selected["subject"] == "数学" and selected["stem"]
            assert not {"answer", "solution"} & selected.keys()
            original = None
            after = ""
            while True:
                rows = native({"operation": "export", "source": "cmmu", "after": after})
                if not rows:
                    break
                original = next(
                    (row for row in rows if row["id"] == selected["question_id"]), None
                )
                if original:
                    break
                after = rows[-1]["id"]
            assert original and original["question_text"] == selected["stem"]
            assert original["usable_for_auto_grade"] and original["has_answer"]
            for url in selected.get("images", []):
                response = client.get(base + url, headers=headers)
                assert response.status_code == 200 and response.headers.get(
                    "content-type", ""
                ).startswith("image/")
            report["practice_question_id"] = selected["question_id"]
            record("real-recommendation", images=len(selected.get("images", [])))
            answer = original["answer"]
            text = (
                "".join(str(value) for value in answer)
                if isinstance(answer, list)
                else str(answer)
            )
            attempt = {
                **payload,
                "question_id": selected["question_id"],
                "student_answer": text,
                "duration_seconds": 30,
            }
            graded = data(
                client.post(
                    base + "/api/v1/practice/attempt", headers=headers, json=attempt
                )
            )
            assert graded["correct"] is True
            duplicate = client.post(
                base + "/api/v1/practice/attempt", headers=headers, json=attempt
            )
            assert duplicate.status_code == 409
            record(
                "practice-completed", passed=True, correct=True, duplicate_blocked=True
            )
        except Exception:  # noqa: BLE001 - never expose upstream responses or local credentials
            record("failed", passed=False)
            raise RuntimeError(
                "实际题库核验未通过，请检查本地报告；未输出凭据或上游响应"
            ) from None


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError, ValueError):
        print("实际练习核验未完成；请先准备核验账号、题库和独立索引。")
        raise SystemExit(1) from None
