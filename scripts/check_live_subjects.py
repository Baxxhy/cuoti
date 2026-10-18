"""Bounded actual-pool checks on three fixed public curriculum examples."""

import json
import os
import sys
import time
from pathlib import Path
from uuid import uuid4

import httpx

PROJECT = Path(__file__).resolve().parents[1]
CASES = [
    {
        "key": "quadratic",
        "subject": "数学",
        "grade": "初三",
        "question_text": "解方程：x^2-5x+6=0，写出所有实数解。",
        "student_answer": "x=2",
        "student_steps": ["(x-2)(x-3)=0", "x=2"],
    },
    {
        "key": "ohm",
        "subject": "物理",
        "grade": "初三",
        "question_text": "某导体两端电压为6 V，通过它的电流为0.2 A，求导体电阻。",
        "student_answer": "1.2 Ω",
        "student_steps": ["R=U*I", "R=6*0.2=1.2 Ω"],
    },
    {
        "key": "water",
        "subject": "化学",
        "grade": "初三",
        "question_text": "氢气与氧气点燃反应生成水，写出配平的化学方程式并注明反应条件。",
        "student_answer": "H2+O2=H2O",
        "student_steps": ["H2+O2=H2O"],
    },
]


def main():
    os.umask(0o077)
    runtime = PROJECT / ".runtime"
    runtime.mkdir(exist_ok=True)
    path = runtime / "live-subjects-check.json"
    report = {"kind": "fixed-subjects-actual-pool", "student_trial": False, "cases": []}

    def save():
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        path.chmod(0o600)

    with httpx.Client(
        base_url=f"http://127.0.0.1:{os.environ.get('CANGJIE_BACKEND_PORT', '8002')}/api/v1",
        timeout=240,
    ) as client:
        credentials = {
            "email": f"subjects-check-{uuid4().hex}@example.test",
            "password": uuid4().hex,
        }

        def request(method, url, body=None, token=None):
            response = client.request(
                method,
                url,
                json=body,
                headers={"Authorization": "Bearer " + token} if token else {},
            )
            if response.status_code not in (200, 202):
                raise RuntimeError(f"本地请求HTTP {response.status_code}")
            return response.json()["data"]

        user = request(
            "POST", "/auth/register", {**credentials, "name": "多学科固定样本核验"}
        )
        login = runtime / "live-subjects-login.json"
        login.write_text(json.dumps(credentials) + "\n")
        login.chmod(0o600)
        token = user["access_token"]
        report["user_id"] = user["id"]
        failed = False
        for case in CASES:
            entry = {"key": case["key"], "subject": case["subject"], "results": {}}
            report["cases"].append(entry)
            for stage in ("manual", "analyze", "diagnose", "read"):
                started = time.monotonic()
                try:
                    if stage == "manual":
                        question = request(
                            "POST",
                            "/questions/manual",
                            {key: value for key, value in case.items() if key != "key"},
                            token,
                        )
                        entry["question_id"] = question["id"]
                    else:
                        url = "/questions/" + entry["question_id"]
                        value = request(
                            "GET" if stage == "read" else "POST",
                            url if stage == "read" else url + "/" + stage,
                            None if stage == "read" else {},
                            token,
                        )
                        entry[stage] = value
                    entry["results"][stage] = {
                        "transport_passed": True,
                        "seconds": round(time.monotonic() - started, 2),
                    }
                    print(f"{case['key']} {stage}: 请求通过", flush=True)
                except (RuntimeError, httpx.HTTPError, ValueError, KeyError):
                    entry["results"][stage] = {"transport_passed": False}
                    failed = True
                    print(
                        f"{case['key']} {stage}: 请求失败，细节仅保留本地状态",
                        flush=True,
                    )
                    break
                finally:
                    save()
        report["transport_passed"] = not failed
        report["content_review"] = "pending"
        save()
        if failed:
            raise SystemExit(1)


def recheck_math(correct=False):
    runtime = PROJECT / ".runtime"
    path = runtime / "live-subjects-check.json"
    report = json.loads(path.read_text())
    credentials = json.loads((runtime / "live-subjects-login.json").read_text())
    case = next(item for item in report["cases"] if item["key"] == "quadratic")
    with httpx.Client(
        base_url=f"http://127.0.0.1:{os.environ.get('CANGJIE_BACKEND_PORT', '8002')}/api/v1",
        timeout=240,
    ) as client:
        login = client.post("/auth/login", json=credentials)
        if login.status_code != 200:
            raise RuntimeError("实际样本账号无法登录")
        headers = {"Authorization": "Bearer " + login.json()["data"]["access_token"]}
        if correct:
            created = client.post(
                "/questions/manual",
                headers=headers,
                json={
                    "question_text": "解方程：2*x+3=11",
                    "subject": "数学",
                    "grade": "初一",
                    "student_answer": "x=4",
                    "student_steps": ["2*x=8", "x=4"],
                },
            )
            if created.status_code != 200:
                raise RuntimeError("正确作答样本创建失败")
            case = {
                "key": "correct-linear",
                "question_id": created.json()["data"]["id"],
            }
            analysis = client.post(
                "/questions/" + case["question_id"] + "/analyze",
                json={},
                headers=headers,
            )
            if analysis.status_code != 200:
                raise RuntimeError("正确作答样本分析失败")
        response = client.post(
            "/questions/" + case["question_id"] + "/diagnose", json={}, headers=headers
        )
        if response.status_code != 200:
            raise RuntimeError("实际样本重新诊断失败")
        value = response.json()["data"]
        passed = (
            value["first_error_step"] == 1
            and value["first_error_text"] == "x=2"
            and value["error_type"] == "condition_omission"
            and value["evidence"][0]["math_valid"] is True
            and value["evidence"][0]["is_first_error"] is False
            and value["counterfactual"]["root_cause_confirmed"] is True
        )
        if correct:
            passed = (
                value["error_type"] == "exact"
                and value["first_error_step"] is None
                and value["root_misconception"] == ""
                and all(
                    row["math_valid"] and not row["is_first_error"]
                    for row in value["evidence"]
                )
            )
            report["correct_case"] = case
            task = client.post(
                "/learning-tasks",
                headers=headers,
                json={"question_id": case["question_id"], "request_id": str(uuid4())},
            )
            if task.status_code != 202:
                raise RuntimeError("正确作答样本任务未受理")
            task_id = task.json()["data"]["id"]
            deadline = time.monotonic() + 60
            while True:
                current = client.get("/learning-tasks/" + task_id, headers=headers)
                if current.status_code != 200:
                    raise RuntimeError("正确作答任务无法读取")
                current = current.json()["data"]
                if current["status"] not in ("queued", "running"):
                    break
                if time.monotonic() > deadline:
                    raise RuntimeError("正确作答任务等待超时")
                time.sleep(0.3)
            passed = (
                passed
                and current["student_view"]["title"] == "独立完成这道题"
                and not current["learning_applied"]
            )
            case["task_id"] = task_id
            report["correct_case"] = case
        report.setdefault("rechecks", []).append(
            {"key": case["key"], "passed": passed, "diagnosis": value}
        )
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        path.chmod(0o600)
        print(
            f"{case['key']} 修复后真实诊断: {'通过' if passed else '未通过'}",
            flush=True,
        )
        if not passed:
            raise SystemExit(1)


if __name__ == "__main__":
    try:
        if sys.argv[1:] == ["--recheck-math"]:
            recheck_math()
        elif sys.argv[1:] == ["--check-correct"]:
            recheck_math(correct=True)
        elif not sys.argv[1:]:
            main()
        else:
            raise SystemExit(
                "用法：check_live_subjects.py [--recheck-math|--check-correct]"
            )
    except (httpx.HTTPError, RuntimeError, KeyError, ValueError, OSError):
        print("实际核验失败；未输出凭据或上游响应。", flush=True)
        raise SystemExit(1) from None
