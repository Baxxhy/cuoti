"""Bounded actual-pool check using a fixed public equation, not a student trial."""

import json
import os
import time
from pathlib import Path
from uuid import uuid4

import httpx

PROJECT = Path(__file__).resolve().parents[1]


class CheckFailure(RuntimeError):
    pass


def main():
    base = f"http://127.0.0.1:{os.environ.get('CANGJIE_BACKEND_PORT', '8002')}/api/v1"
    results = []
    report = {
        "kind": "fixed-equation-actual-pool",
        "results": results,
        "student_trial": False,
    }
    path = PROJECT / ".runtime/live-system-check.json"
    os.umask(0o077)
    path.parent.mkdir(exist_ok=True)

    def record(stage, **fields):
        results.append({"stage": stage, **fields})
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        os.chmod(path, 0o600)
        print(json.dumps(results[-1], ensure_ascii=False), flush=True)

    with httpx.Client(timeout=180) as client:

        def request(method, url, payload=None, token=None):
            response = client.request(
                method,
                base + url,
                json=payload,
                headers={"Authorization": "Bearer " + token} if token else {},
            )
            if response.status_code not in (200, 202):
                raise CheckFailure(f"本机业务请求失败 HTTP {response.status_code}")
            body = response.json()
            return body.get("data", body)

        stage = "register"
        try:
            credentials = {
                "email": f"actual-check-{uuid4().hex}@example.test",
                "password": uuid4().hex,
            }
            user = request(
                "POST",
                "/auth/register",
                {
                    **credentials,
                    "name": "实际功能核验",
                    "grade": "初一",
                },
            )
            login_file = PROJECT / ".runtime/live-system-login.json"
            login_file.write_text(json.dumps(credentials) + "\n")
            os.chmod(login_file, 0o600)
            token = user["access_token"]
            report["user_id"] = user["id"]
            record(stage, passed=True)
            stage = "manual-question"
            question = request(
                "POST",
                "/questions/manual",
                {
                    "question_text": "解方程：2x+3=11",
                    "student_answer": "x=7",
                    "student_steps": ["2x=11+3", "x=7"],
                    "subject": "数学",
                    "grade": "初一",
                },
                token,
            )
            report["question_id"] = question["id"]
            record(stage, passed=True)
            stage = "actual-analysis"
            started = time.monotonic()
            analysis = request(
                "POST", f"/questions/{question['id']}/analyze", {}, token
            )
            answer = str(analysis["final_answer"]).replace(" ", "").replace("$", "")
            if answer not in ("x=4", "4", "x＝4") or not analysis.get("verified"):
                raise CheckFailure("实际分析未得到经过验证的x=4，需检查算法结果")
            record(
                stage, passed=True, elapsed_seconds=round(time.monotonic() - started, 2)
            )
            stage = "actual-diagnosis"
            started = time.monotonic()
            diagnosis = request(
                "POST", f"/questions/{question['id']}/diagnose", {}, token
            )
            if diagnosis.get("first_error_step") != 0:
                raise CheckFailure("首错步骤未定位到第一步，需检查实际诊断")
            record(
                stage, passed=True, elapsed_seconds=round(time.monotonic() - started, 2)
            )

            def wait_task(task_id):
                deadline = time.monotonic() + 65
                while time.monotonic() < deadline:
                    task = request("GET", "/learning-tasks/" + task_id, token=token)
                    if task["status"] not in ("queued", "running"):
                        return task
                    time.sleep(0.5)
                raise CheckFailure("学习任务未在核验等待窗口内返回状态")

            stage = "actual-task"
            created = request(
                "POST",
                "/learning-tasks",
                {"question_id": question["id"], "request_id": str(uuid4())},
                token,
            )
            task = wait_task(created["id"])
            report["task_id"] = task["id"]
            if task["status"] != "waiting_student":
                raise CheckFailure("实际任务未进入可作答状态")
            record(stage, passed=True, status=task["status"])
            stage = "repair-answer"
            request(
                "POST",
                f"/learning-tasks/{task['id']}/actions",
                {
                    "kind": "answer",
                    "text": "2x=8",
                    "version": task["version"],
                    "step_id": task["step_id"],
                    "input_fingerprint": task["input_fingerprint"],
                    "request_id": str(uuid4()),
                },
                token,
            )
            repaired = wait_task(task["id"])
            if (
                repaired["status"] not in ("waiting_student", "completed")
                or repaired["version"] <= task["version"]
            ):
                raise CheckFailure("实际订正未推进，需检查任务结果")
            history = request(
                "GET", f"/learning-tasks/{task['id']}/history", token=token
            )
            if not any(
                item.get("phase") == "repair"
                and item.get("verdict") == "confirmed_correct"
                for item in history.get("items", [])
            ):
                raise CheckFailure("订正历史没有确认正确的局部作答证据")
            record(
                stage,
                passed=True,
                verdict="confirmed_correct",
                status=repaired["status"],
                history_entries=len(history.get("items", [])),
            )
            stage = "retained-source"
            detail = request("GET", "/questions/" + question["id"], token=token)
            if (
                detail["student_answer"] != "x=7"
                or detail["student_steps"][0]["text"] != "2x=11+3"
            ):
                raise CheckFailure("原始作答不一致")
            record(stage, passed=True)
            report["passed"] = True
            path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        except (CheckFailure, httpx.HTTPError, ValueError, KeyError):
            report["passed"] = False
            record(stage, passed=False)
            raise CheckFailure(
                "实际功能核验未通过；失败阶段已记录，未输出上游报错或凭据"
            ) from None
    print("固定题实际核验通过；不代表全题型或真实学生效果。", flush=True)


if __name__ == "__main__":
    try:
        main()
    except CheckFailure as error:
        print(str(error), flush=True)
        raise SystemExit(1) from None
