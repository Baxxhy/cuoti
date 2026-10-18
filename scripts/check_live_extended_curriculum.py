"""Authored edge cases through the real business/model path; manual review required.

No private student data or model credentials are printed. Resume preserves results.
"""

import json
import os
import sys
import time
from pathlib import Path
from uuid import uuid4

import httpx

ROOT = Path(__file__).resolve().parents[1]
CASES = [
    (
        "fraction",
        "数学",
        "解方程：x/2+1=4",
        "x=6",
        ["x/2=3", "x=6"],
        "x=6；正确路径，不应判错",
    ),
    (
        "negative-inequality",
        "数学",
        "解不等式：-2x>6",
        "x>-3",
        ["x>-3"],
        "x<-3；首错0，除负数未变号",
    ),
    (
        "radical-extraneous",
        "数学",
        "解方程：sqrt(x+2)=x",
        "x=-1或x=2",
        ["x+2=x^2", "x=-1或x=2"],
        "仅x=2；首错1，-1是增根",
    ),
    (
        "rational-domain",
        "数学",
        "解方程：(x^2-1)/(x-1)=2",
        "x=1",
        ["x+1=2", "x=1"],
        "无解；x=1不在定义域，必须验根",
    ),
    (
        "absolute-roots",
        "数学",
        "解方程：abs(x-1)=2",
        "x=3",
        ["x-1=2", "x=3"],
        "x=-1或x=3；漏负分支，不可整题判对",
    ),
    (
        "decimal",
        "数学",
        "解方程：0.5x+0.2=1.7",
        "x=3",
        ["0.5x=1.5", "x=3"],
        "x=3；正确，不应判错",
    ),
    (
        "geometry-insufficient",
        "数学",
        "在三角形ABC中，仅知∠A=50°，求∠C的具体度数。",
        "∠C=80°",
        ["∠B=50°", "∠C=80°"],
        "条件不足；首错0，无依据假定B=50，不得编造唯一角度",
    ),
    (
        "speed-units",
        "物理",
        "汽车以72 km/h匀速行驶，求10秒内通过的路程（单位m）。",
        "720 m",
        ["s=vt", "s=72*10=720 m"],
        "200m；首错1，速度先换20m/s，公式s=vt正确",
    ),
    (
        "mass-conservation",
        "化学",
        "密闭容器中4g氢气与32g氧气恰好完全反应生成水，生成水的质量是多少？",
        "32g",
        ["水的质量等于氧气质量", "m(水)=32g"],
        "36g；首错0，守恒应加两反应物质量",
    ),
    (
        "english-correct",
        "英语",
        "Fill in the blank with the correct form of go: She ___ to school every day.",
        "goes",
        ["She是第三人称单数，every day表一般现在时，填goes。"],
        "goes；正确答案和解释，不应虚构错误",
    ),
    (
        "biology-correct",
        "生物",
        "植物进行光合作用时，吸收的气体和释放的气体分别是什么？",
        "二氧化碳和氧气",
        ["光合作用吸收二氧化碳，释放氧气。"],
        "二氧化碳、氧气；正确，不应判错",
    ),
    (
        "probability",
        "数学",
        "一个袋子有2个红球和3个白球，随机摸出1个球，摸到红球的概率是多少？",
        "2/3",
        ["红球2个，白球3个", "P=2/3"],
        "2/5；首错1，分母为总球数5",
    ),
]


def main():
    os.umask(0o077)
    folder = ROOT / ".runtime/extended-curriculum"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "report.json"
    report = (
        json.loads(path.read_text())
        if path.exists()
        else {"cases": [], "manual_review": "pending", "student_trial": False}
    )
    if sys.argv[1:] == ["--recheck"]:
        for entry in report["cases"]:
            entry.setdefault("previous_runs", []).append(
                {
                    key: entry.pop(key)
                    for key in (
                        "analyze",
                        "diagnose",
                        "transport_error",
                        "task_id",
                        "task_result",
                    )
                    if key in entry
                }
            )
        report["manual_review"] = "pending"
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    elif sys.argv[1:] not in ([], ["--tasks"]):
        raise SystemExit("用法：check_live_extended_curriculum.py [--recheck|--tasks]")
    login = folder / "login.json"
    with httpx.Client(base_url="http://127.0.0.1:8002/api/v1", timeout=300) as client:

        def call(method, url, body=None):
            for attempt in range(3):
                response = client.request(method, url, json=body)
                if response.status_code in (200, 202):
                    return response.json()["data"]
                report.setdefault("request_failures", []).append(
                    {
                        "method": method,
                        "stage": url.rsplit("/", 1)[-1],
                        "status": response.status_code,
                        "attempt": attempt + 1,
                    }
                )
                path.write_text(json.dumps(report, ensure_ascii=False, indent=2))
                if response.status_code == 503 and attempt < 2:
                    print("模型请求503：保留失败记录，稍后补测。", flush=True)
                    time.sleep(30 * (attempt + 1))
                    continue
                raise RuntimeError(str(response.status_code))

        if login.exists():
            user = call("POST", "/auth/login", json.loads(login.read_text()))
        else:
            credentials = {
                "email": f"extended-{uuid4().hex}@example.test",
                "password": uuid4().hex,
            }
            user = call(
                "POST", "/auth/register", {**credentials, "name": "边界题型核验"}
            )
            login.write_text(json.dumps(credentials))
        client.headers["Authorization"] = "Bearer " + user["access_token"]
        for key, subject, text, answer, steps, expected in CASES:
            entry = next((row for row in report["cases"] if row["key"] == key), None)
            if entry is None:
                entry = {
                    "key": key,
                    "expected": expected,
                    "input": {
                        "subject": subject,
                        "grade": "初三",
                        "question_text": text,
                        "student_answer": answer,
                        "student_steps": steps,
                    },
                }
                report["cases"].append(entry)
            try:
                if "question_id" not in entry:
                    entry["question_id"] = call(
                        "POST", "/questions/manual", entry["input"]
                    )["id"]
                for stage in ("analyze", "diagnose"):
                    if stage not in entry:
                        entry[stage] = call(
                            "POST", f"/questions/{entry['question_id']}/{stage}", {}
                        )
                        path.write_text(
                            json.dumps(report, ensure_ascii=False, indent=2)
                        )
                entry.pop("transport_error", None)
                print(key + ": 请求完成，待逐题核对", flush=True)
            except (httpx.HTTPError, RuntimeError, ValueError, KeyError) as error:
                status = (
                    str(error)
                    if isinstance(error, RuntimeError)
                    else "transport_or_schema"
                )
                entry["transport_error"] = status
                print(key + ": 请求失败 " + status + "，已登记", flush=True)
            path.write_text(json.dumps(report, ensure_ascii=False, indent=2))

        if sys.argv[1:] == ["--tasks"]:

            def wait(task_id):
                deadline = time.monotonic() + 180
                while time.monotonic() < deadline:
                    task = call("GET", "/learning-tasks/" + task_id)
                    if task["status"] not in ("queued", "running"):
                        return task
                    time.sleep(0.5)
                raise RuntimeError("任务未完成")

            for key, answer in {
                "speed-units": "200 m",
                "mass-conservation": "36g",
                "probability": "2/5",
            }.items():
                entry = next(row for row in report["cases"] if row["key"] == key)
                if entry.get("task_result", {}).get("passed"):
                    continue
                if "diagnose" not in entry:
                    raise RuntimeError("样本诊断尚未完成")
                if "task_id" not in entry:
                    entry["task_id"] = call(
                        "POST",
                        "/learning-tasks",
                        {
                            "question_id": entry["question_id"],
                            "request_id": str(uuid4()),
                        },
                    )["id"]
                    path.write_text(json.dumps(report, ensure_ascii=False, indent=2))
                task = wait(entry["task_id"])
                if task["status"] == "waiting_student":
                    call(
                        "POST",
                        f"/learning-tasks/{task['id']}/actions",
                        {
                            "kind": "answer",
                            "text": answer,
                            "version": task["version"],
                            "step_id": task["step_id"],
                            "input_fingerprint": task["input_fingerprint"],
                            "request_id": str(uuid4()),
                        },
                    )
                    task = wait(task["id"])
                history = call("GET", f"/learning-tasks/{task['id']}/history")["items"]
                original = call("GET", "/questions/" + entry["question_id"])
                preserved = (
                    original["student_answer"] == entry["input"]["student_answer"]
                    and [s["text"] for s in original["student_steps"]]
                    == entry["input"]["student_steps"]
                )
                passed = (
                    task["status"] == "completed"
                    and preserved
                    and any(
                        row.get("phase") == "independent"
                        and row.get("verdict") == "confirmed_correct"
                        for row in history
                    )
                )
                entry["task_result"] = {
                    "passed": passed,
                    "status": task["status"],
                    "original_preserved": preserved,
                    "history": history,
                }
                path.write_text(json.dumps(report, ensure_ascii=False, indent=2))
                print(
                    key
                    + (
                        ": 实际独立作答闭环通过"
                        if passed
                        else ": 实际任务未通过，已登记"
                    ),
                    flush=True,
                )
                if not passed:
                    raise SystemExit(1)


if __name__ == "__main__":
    main()
