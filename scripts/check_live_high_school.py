"""Three fixed authored curriculum examples through actual Cangjie/Qwen services.

Transport results and human content review are separate. Credentials/raw outputs
remain in private .runtime files; this is not a student trial or a benchmark.
"""

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
        "key": "quadratic-inequality",
        "subject": "数学",
        "grade": "高一",
        "question_type": "综合题",
        "question_text": "解不等式：x^2-5x+6≤0，写出解集。",
        "student_answer": "x≤2或x≥3",
        "student_steps": ["(x-2)(x-3)≤0", "x≤2或x≥3"],
        "review_expected": "2≤x≤3；第一步因式分解成立，第二步错误地取了两根外侧",
    },
    {
        "key": "english-subjunctive",
        "subject": "英语",
        "grade": "高一",
        "question_type": "单选题",
        "question_text": "Choose the correct form: If I ___ you, I would tell the truth.",
        "options": [
            {"label": "A", "text": "am"},
            {"label": "B", "text": "was"},
            {"label": "C", "text": "were"},
            {"label": "D", "text": "will be"},
        ],
        "student_answer": "A",
        "student_steps": ["主语是I，所以选择am。"],
        "review_expected": "C/were；与现在事实相反的假设使用虚拟语气，不能只按I匹配am",
    },
    {
        "key": "biology-meiosis",
        "subject": "生物",
        "grade": "高一",
        "question_type": "单选题",
        "question_text": "某二倍体生物体细胞染色体数为2n=8。一个初级精母细胞减数第一次分裂完成后，每个次级精母细胞中有多少条染色体？",
        "options": [
            {"label": "A", "text": "4"},
            {"label": "B", "text": "8"},
            {"label": "C", "text": "16"},
            {"label": "D", "text": "2"},
        ],
        "student_answer": "B",
        "student_steps": ["DNA已经复制，所以次级精母细胞还是8条染色体。"],
        "review_expected": "A/4；减数第一次分裂同源染色体分离，不能将DNA复制等同于染色体数加倍",
    },
]


def main(resume=False, recheck_math=False, tasks=False, intermediate=False):
    os.umask(0o077)
    runtime = PROJECT / ".runtime"
    runtime.mkdir(exist_ok=True)
    path, login_path = (
        runtime / "live-high-school-check.json",
        runtime / "live-high-school-login.json",
    )
    report = (
        json.loads(path.read_text())
        if resume
        else {
            "kind": "three-authored-high-school-examples",
            "student_trial": False,
            "logical_model": "Qwen",
            "physical_model_version": "unknown",
            "content_review": "pending",
            "cases": [],
        }
    )

    def save():
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        path.chmod(0o600)

    with httpx.Client(
        base_url=f"http://127.0.0.1:{os.environ.get('CANGJIE_BACKEND_PORT', '8002')}/api/v1",
        timeout=240,
    ) as client:

        def request(method, url, body=None, token=None):
            response = client.request(
                method,
                url,
                json=body,
                headers={"Authorization": "Bearer " + token} if token else {},
            )
            if response.status_code not in (200, 202):
                raise RuntimeError(f"本地业务请求HTTP {response.status_code}")
            return response.json()["data"]

        if resume:
            credentials = json.loads(login_path.read_text())
            user = request("POST", "/auth/login", credentials)
        else:
            credentials = {
                "email": f"high-school-check-{uuid4().hex}@example.test",
                "password": uuid4().hex,
            }
            user = request(
                "POST", "/auth/register", {**credentials, "name": "高中固定样本核验"}
            )
            login_path.write_text(json.dumps(credentials) + "\n")
            login_path.chmod(0o600)
        token = user["access_token"]
        failed = False
        for case in CASES:
            if recheck_math and case["key"] != "quadratic-inequality":
                continue
            entry = next(
                (row for row in report["cases"] if row["key"] == case["key"]), None
            )
            if entry is None:
                entry = {"key": case["key"], "sample": case, "results": {}}
                report["cases"].append(entry)
            entry["sample"] = case
            if recheck_math:
                entry.setdefault("previous_runs", []).append(
                    {
                        key: entry.get(key)
                        for key in ("analyze", "diagnose", "read", "results")
                    }
                )
                entry["results"] = {"manual": entry["results"]["manual"]}
                report["content_review"] = "pending"
            for stage in ("manual", "analyze", "diagnose", "read"):
                if entry["results"].get(stage, {}).get("transport_passed"):
                    continue
                if entry["results"].get(stage, {}).get("transport_passed") is False:
                    entry.setdefault("previous_transport_failures", []).append(stage)
                started = time.monotonic()
                try:
                    if stage == "manual":
                        question = request(
                            "POST",
                            "/questions/manual",
                            {
                                key: value
                                for key, value in case.items()
                                if key not in ("key", "review_expected")
                            },
                            token,
                        )
                        entry["question_id"] = question["id"]
                    else:
                        url = "/questions/" + entry["question_id"]
                        entry[stage] = request(
                            "GET" if stage == "read" else "POST",
                            url if stage == "read" else url + "/" + stage,
                            None if stage == "read" else {},
                            token,
                        )
                    entry["results"][stage] = {
                        "transport_passed": True,
                        "seconds": round(time.monotonic() - started, 2),
                    }
                    print(f"{case['key']} {stage}: 请求通过", flush=True)
                except (RuntimeError, httpx.HTTPError, ValueError, KeyError):
                    entry["results"][stage] = {"transport_passed": False}
                    failed = True
                    print(f"{case['key']} {stage}: 请求失败，内容尚未核对", flush=True)
                    break
                finally:
                    save()
        report["transport_passed"] = not failed
        save()
        if failed:
            raise SystemExit(1)

        def wait_task(task_id):
            deadline = time.monotonic() + 70
            while time.monotonic() < deadline:
                current = request("GET", "/learning-tasks/" + task_id, token=token)
                if current["status"] not in ("queued", "running"):
                    return current
                time.sleep(0.4)
            raise RuntimeError("任务等待超时")

        if tasks:
            if report["content_review"] != "fixed_expected_reviewed":
                raise RuntimeError("请先按固定期望核对样本内容")
            answers = {
                "quadratic-inequality": "[2,3]",
                "english-subjunctive": "C",
                "biology-meiosis": "A",
            }

            for entry in report["cases"]:
                if entry.get("task_result", {}).get("passed"):
                    continue
                if not entry.get("task_id"):
                    task = request(
                        "POST",
                        "/learning-tasks",
                        {
                            "question_id": entry["question_id"],
                            "request_id": str(uuid4()),
                        },
                        token,
                    )
                    entry["task_id"] = task["id"]
                    save()
                task = wait_task(entry["task_id"])
                if task["status"] != "waiting_student":
                    raise RuntimeError("任务不在预期作答状态")
                request(
                    "POST",
                    "/learning-tasks/" + task["id"] + "/actions",
                    {
                        "kind": "answer",
                        "text": answers[entry["key"]],
                        "version": task["version"],
                        "step_id": task["step_id"],
                        "input_fingerprint": task["input_fingerprint"],
                        "request_id": str(uuid4()),
                    },
                    token,
                )
                final = wait_task(task["id"])
                history = request(
                    "GET", "/learning-tasks/" + task["id"] + "/history", token=token
                )
                original = request(
                    "GET", "/questions/" + entry["question_id"], token=token
                )
                preserved = (
                    original["student_answer"] == entry["sample"]["student_answer"]
                    and [s["text"] for s in original["student_steps"]]
                    == entry["sample"]["student_steps"]
                )
                passed = (
                    final["status"] == "completed"
                    and any(
                        row.get("verdict") == "confirmed_correct"
                        and row.get("phase") == "independent"
                        for row in history["items"]
                    )
                    and preserved
                )
                entry["task_result"] = {
                    "passed": passed,
                    "status": final["status"],
                    "learning_applied": final["learning_applied"],
                    "history": history["items"],
                    "original_preserved": preserved,
                }
                save()
                print(
                    f"{entry['key']} actual-task: {'通过' if passed else '未通过'}",
                    flush=True,
                )
                if not passed:
                    raise SystemExit(1)
            report["task_flow_passed"] = True
            save()

        if intermediate:
            entry = next(
                row for row in report["cases"] if row["key"] == "quadratic-inequality"
            )
            if report.get("intermediate_check", {}).get("passed"):
                print("intermediate-answer: 已有通过记录，未重复提交", flush=True)
                return
            created = request(
                "POST",
                "/learning-tasks",
                {"question_id": entry["question_id"], "request_id": str(uuid4())},
                token,
            )
            task = wait_task(created["id"])
            report["intermediate_check"] = {"task_id": task["id"], "passed": False}
            save()

            def send(current, kind, text=""):
                request(
                    "POST",
                    "/learning-tasks/" + current["id"] + "/actions",
                    {
                        "kind": kind,
                        "text": text,
                        "version": current["version"],
                        "step_id": current["step_id"],
                        "input_fingerprint": current["input_fingerprint"],
                        "request_id": str(uuid4()),
                    },
                    token,
                )
                return wait_task(current["id"])

            reviewed = send(task, "answer", "(x-2)(x-3)≤0")
            if (
                reviewed["status"] != "needs_review"
                or reviewed["learning_applied"]
                or "取值范围" not in reviewed["student_view"]["feedback"]
            ):
                raise RuntimeError("中间变形未正确进入需补充解集状态")
            resumed = send(reviewed, "resume")
            if resumed["status"] != "waiting_student":
                raise RuntimeError("任务恢复未回到作答状态")
            done = send(resumed, "answer", "[2,3]")
            history = request(
                "GET", "/learning-tasks/" + done["id"] + "/history", token=token
            )["items"]
            verdicts = [row.get("verdict") for row in history]
            passed = (
                done["status"] == "completed"
                and "review_required" in verdicts
                and "confirmed_correct" in verdicts
                and not done["learning_applied"]
            )
            report["intermediate_check"].update(
                passed=passed,
                reviewed_status=reviewed["status"],
                final_status=done["status"],
                learning_applied=done["learning_applied"],
                history=history,
            )
            save()
            print(
                "intermediate-answer: " + ("通过" if passed else "未通过"), flush=True
            )
            if not passed:
                raise SystemExit(1)


if __name__ == "__main__":
    try:
        if sys.argv[1:] not in (
            [],
            ["--resume"],
            ["--recheck-math"],
            ["--tasks"],
            ["--check-intermediate"],
        ):
            raise SystemExit(
                "用法：check_live_high_school.py [--resume|--recheck-math|--tasks|--check-intermediate]"
            )
        main(
            resume=bool(sys.argv[1:]),
            recheck_math=sys.argv[1:] == ["--recheck-math"],
            tasks=sys.argv[1:] == ["--tasks"],
            intermediate=sys.argv[1:] == ["--check-intermediate"],
        )
    except (httpx.HTTPError, RuntimeError, KeyError, ValueError, OSError):
        print("高中固定样本核验失败，未输出凭据或上游响应。", flush=True)
        raise SystemExit(1) from None
