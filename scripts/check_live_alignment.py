"""Regression for the actual diagnosed source and its previously wrong recommendation."""

import json
import os
from pathlib import Path

import httpx
from prepare_cangjie_question_bank import native

PROJECT = Path(__file__).resolve().parents[1]


def main():
    runtime = PROJECT / ".runtime"
    original = json.loads((runtime / "live-relevance-check.json").read_text())
    credentials = json.loads((runtime / "live-system-login.json").read_text())
    os.umask(0o077)
    report = {"kind": "actual-practice-alignment", "passed": False}

    def record(stage, **fields):
        report.update(stage=stage, **fields)
        path = runtime / "live-alignment-check.json"
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        path.chmod(0o600)
        print(json.dumps({"stage": stage, **fields}, ensure_ascii=False), flush=True)

    with httpx.Client(
        base_url="http://127.0.0.1:" + os.environ.get("CANGJIE_BACKEND_PORT", "8002"),
        timeout=300,
    ) as client:

        def data(response):
            report["last_http_status"] = response.status_code
            if response.status_code != 200:
                raise ValueError("local request failed")
            return response.json()["data"]

        try:
            user = data(client.post("/api/v1/auth/login", json=credentials))
            headers = {"Authorization": "Bearer " + user["access_token"]}
            source_id = original["source_id"]
            source = data(client.get("/api/v1/questions/" + source_id, headers=headers))
            assert source.get("analysis") and source.get("diagnosis")

            def snapshot():
                overview = data(
                    client.get("/api/v1/analytics/overview?days=30", headers=headers)
                )
                journey = data(
                    client.get(
                        "/api/v1/questions/" + source_id + "/journey", headers=headers
                    )
                )
                return {
                    "overview": overview,
                    "practice": journey["practice"],
                    "review": journey["review"],
                }

            before = snapshot()
            rejected = client.post(
                "/api/v1/practice/attempt",
                headers=headers,
                json={
                    "mistake_id": source_id,
                    "question_id": original["practice_id"],
                    "mode": "reinforce",
                    "student_answer": "A",
                },
            )
            assert rejected.status_code == 409 and snapshot() == before
            record("legacy-geometry-rejected", no_learning_change=True)
            selected = data(
                client.post(
                    "/api/v1/practice/recommend",
                    headers=headers,
                    json={"mistake_id": source_id, "mode": "reinforce", "debug": True},
                )
            )
            assert selected["question_id"] != original["practice_id"]
            assert selected["debug"]["target_knowledge_name"] == "一元一次方程"
            assert "answer" not in selected and "solution" not in selected
            report.update(source_id=source_id, selected_id=selected["question_id"])
            row = None
            for dataset in ("cmm-math", "cmmu"):
                after = ""
                while True:
                    rows = native(
                        {"operation": "export", "source": dataset, "after": after}
                    )
                    if not rows:
                        break
                    row = next(
                        (
                            item
                            for item in rows
                            if item["id"] == selected["question_id"]
                        ),
                        None,
                    )
                    if row:
                        break
                    after = rows[-1]["id"]
                if row:
                    break
            assert row and row["question_text"] == selected["stem"]
            report["selected_stem"] = selected["stem"]
            record(
                "aligned-recommendation",
                method=selected["debug"].get("alignment_method", "revalidated_cache"),
            )
            answer = row["answer"]
            text = (
                "、".join(map(str, answer)) if isinstance(answer, list) else str(answer)
            )
            graded = data(
                client.post(
                    "/api/v1/practice/attempt",
                    headers=headers,
                    json={
                        "mistake_id": source_id,
                        "question_id": selected["question_id"],
                        "mode": "reinforce",
                        "student_answer": text,
                        "duration_seconds": 30,
                    },
                )
            )
            report.update(
                grading_correct=graded.get("correct"),
                grading_decisive=graded.get("can_update_learning"),
                grading_verdict=graded.get("verdict"),
            )
            assert graded["correct"] is True and graded["can_update_learning"] is True
            after = snapshot()
            assert any(
                item["knowledge_point"] == "一元一次方程"
                for item in after["overview"]["mastery"]
            )
            old_other = [
                item
                for item in before["overview"]["mastery"]
                if item["knowledge_point"] != "一元一次方程"
            ]
            new_other = [
                item
                for item in after["overview"]["mastery"]
                if item["knowledge_point"] != "一元一次方程"
            ]
            assert old_other == new_other
            record(
                "aligned-attempt-completed",
                passed=True,
                correct=True,
                unrelated_mastery_unchanged=True,
            )
        except Exception:  # noqa: BLE001 - do not expose provider responses or local credentials
            record("failed", passed=False)
            raise RuntimeError("实际对齐核验未通过，请检查本地私有报告") from None


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError, ValueError):
        print("请先准备实际核验账号和旧错配复现记录；未输出凭据。")
        raise SystemExit(1) from None
