"""Two bounded real-model calls for a fixed labelled geometry photo.

No real student data. The deliberately rough diagram is not to scale; labels,
not visual angle estimates, are the observations to inspect.
"""

import json
import os
import re
import sys
import time
from pathlib import Path
from uuid import uuid4

import httpx
from PIL import Image, ImageDraw, ImageFont

PROJECT = Path(__file__).resolve().parents[1]
SOURCE = "在三角形ABC中，∠A=50°，∠B=60°，求∠C。"


def example():
    image = Image.new("RGB", (760, 580), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 32)
    draw.line([(240, 110), (110, 400), (610, 400), (240, 110)], fill="black", width=4)
    for point, position in [("A", (220, 63)), ("B", (70, 410)), ("C", (620, 405))]:
        draw.text(position, point, font=font, fill="black")
    for label, position in [
        ("∠A=50°", (295, 125)),
        ("∠B=60°", (110, 450)),
        ("∠C=80°", (450, 450)),
    ]:
        draw.text(position, label, font=font, fill="black")
    draw.text(
        (210, 530),
        "Sketch - not to scale",
        font=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 22),
        fill="black",
    )
    return image


def main(submit=False):
    os.umask(0o077)
    runtime = PROJECT / ".runtime"
    runtime.mkdir(exist_ok=True)
    report_path = runtime / "live-figure-check.json"
    base = "http://127.0.0.1:" + os.environ.get("CANGJIE_BACKEND_PORT", "8002")
    with httpx.Client(base_url=base + "/api/v1", timeout=240) as client:

        def call(method, url, **kwargs):
            response = client.request(method, url, **kwargs)
            if response.status_code not in (200, 202):
                raise RuntimeError("本地业务请求失败")
            return response.json()["data"]

        if submit:
            report = json.loads(report_path.read_text())
            credentials = json.loads((runtime / "live-figure-login.json").read_text())
            user = call("POST", "/auth/login", json=credentials)
        else:
            credentials = {
                "email": f"figure-check-{uuid4().hex}@example.test",
                "password": uuid4().hex,
            }
            user = call(
                "POST", "/auth/register", json={**credentials, "name": "固定图形核验"}
            )
            (runtime / "live-figure-login.json").write_text(
                json.dumps(credentials) + "\n"
            )
            report = {
                "kind": "fixed-geometry-photo-actual-pool",
                "student_trial": False,
                "results": [],
            }
        headers = {"Authorization": "Bearer " + user["access_token"]}

        def record(stage, passed):
            report["results"].append({"stage": stage, "passed": passed})
            report_path.write_text(
                json.dumps(report, ensure_ascii=False, indent=2) + "\n"
            )
            report_path.chmod(0o600)
            print(f"{stage}: " + ("通过" if passed else "未通过"), flush=True)

        def wait(id):
            deadline = time.monotonic() + 90
            while True:
                task = call("GET", "/learning-tasks/" + id, headers=headers)
                if task["status"] not in ("queued", "running"):
                    return task
                if time.monotonic() > deadline:
                    raise RuntimeError("任务等待超时")
                time.sleep(0.3)

        if not submit:
            q = call(
                "POST",
                "/questions/manual",
                headers=headers,
                json={
                    "subject": "数学",
                    "grade": "初二",
                    "question_type": "综合题",
                    "question_text": SOURCE,
                    "student_answer": "80°",
                    "student_steps": ["∠C=80°"],
                },
            )
            report["question_id"] = q["id"]
            analyzed = call(
                "POST", "/questions/" + q["id"] + "/analyze", headers=headers, json={}
            )
            report["analysis_answer"] = analyzed["final_answer"]
            answer = (
                re.sub(r"\s+", "", analyzed["final_answer"])
                .replace("$", "")
                .replace(r"\angle", "∠")
                .replace(r"^{\circ}", "°")
                .replace(r"^\circ", "°")
            )
            valid_answer = bool(
                re.fullmatch(r"(?:∠?C[=＝])?70(?:\.0+)?(?:°|度)?[。.]?", answer)
            )
            record("actual-analysis", valid_answer)
            if not valid_answer:
                raise RuntimeError("固定原题答案未通过核对")
            task = call(
                "POST",
                "/learning-tasks",
                headers=headers,
                json={"question_id": q["id"], "request_id": str(uuid4())},
            )
            task = wait(task["id"])
            report["task_id"] = task["id"]
            file = runtime / "figure-review-example.png"
            example().save(file, "PNG")
            with file.open("rb") as image:
                queued = call(
                    "POST",
                    "/learning-tasks/" + task["id"] + "/handwriting",
                    headers=headers,
                    data={
                        **{
                            key: str(task[key])
                            for key in ("version", "step_id", "input_fingerprint")
                        },
                        "request_id": str(uuid4()),
                    },
                    files={"file": ("figure.png", image, "image/png")},
                )
            task = wait(queued["id"])
            draft = task["student_view"].get("handwriting") or {}
            report["handwriting"] = draft
            passed = any(
                row["status"] == "conflicts"
                and "C" in row["label"]
                and "80" in row["label"]
                for row in draft.get("figure_review", [])
            )
            assert not task["learning_applied"]
            if not draft.get("image_url"):
                raise RuntimeError("缺少原图地址")
            original = client.get(base + draft["image_url"])
            assert original.status_code == 200 and original.content == file.read_bytes()
            record("actual-figure-review-and-original", passed)
            if not passed:
                raise RuntimeError("真实图形标注核对未通过")
        else:
            task = wait(report["task_id"])
            draft = task["student_view"].get("handwriting")
            call(
                "POST",
                "/learning-tasks/" + task["id"] + "/actions",
                headers=headers,
                json={
                    "kind": "answer",
                    "text": "70°",
                    "version": task["version"],
                    "step_id": task["step_id"],
                    "input_fingerprint": task["input_fingerprint"],
                    "request_id": str(uuid4()),
                    **(
                        {"handwriting_id": draft["id"], "handwriting_confirmed": True}
                        if draft
                        else {}
                    ),
                },
            )
            done = wait(task["id"])
            report["final_status"] = done["status"]
            history = call(
                "GET", "/learning-tasks/" + task["id"] + "/history", headers=headers
            )
            passed = (
                done["status"] == "completed"
                and not done["learning_applied"]
                and any(
                    item.get("verdict") == "confirmed_correct" and item.get("assisted")
                    for item in history["items"]
                )
            )
            record("actual-assisted-answer", passed)
            if not passed:
                raise RuntimeError("真实辅助作答核验未通过")


def retry_photo(refresh=False):
    runtime = PROJECT / ".runtime"
    path = runtime / "live-figure-check.json"
    report = json.loads(path.read_text())
    credentials = json.loads((runtime / "live-figure-login.json").read_text())
    base = "http://127.0.0.1:" + os.environ.get("CANGJIE_BACKEND_PORT", "8002")
    with httpx.Client(base_url=base + "/api/v1", timeout=240) as client:

        def data(response):
            if response.status_code not in (200, 202):
                raise RuntimeError("恢复请求失败")
            return response.json()["data"]

        user = data(client.post("/auth/login", json=credentials))
        headers = {"Authorization": "Bearer " + user["access_token"]}
        tasks = data(client.get("/learning-tasks", headers=headers))
        task = next(
            item for item in tasks if item["question_id"] == report["question_id"]
        )
        if task["status"] != "failed" and not (
            refresh and task["status"] in ("waiting_student", "needs_review")
        ):
            raise RuntimeError("固定样本不是待恢复失败任务")
        if refresh:
            with (runtime / "figure-review-example.png").open("rb") as image:
                data(
                    client.post(
                        "/learning-tasks/" + task["id"] + "/handwriting",
                        headers=headers,
                        data={
                            **{
                                key: str(task[key])
                                for key in ("version", "step_id", "input_fingerprint")
                            },
                            "request_id": str(uuid4()),
                        },
                        files={"file": ("figure.png", image, "image/png")},
                    )
                )
        else:
            data(
                client.post(
                    "/learning-tasks/" + task["id"] + "/actions",
                    headers=headers,
                    json={
                        "kind": "resume",
                        "text": "",
                        "version": task["version"],
                        "step_id": task["step_id"],
                        "input_fingerprint": task["input_fingerprint"],
                        "request_id": str(uuid4()),
                    },
                )
            )
        deadline = time.monotonic() + 90
        while True:
            task = data(client.get("/learning-tasks/" + task["id"], headers=headers))
            if task["status"] not in ("queued", "running"):
                break
            if time.monotonic() > deadline:
                raise RuntimeError("恢复等待超时")
            time.sleep(0.3)
        draft = task["student_view"].get("handwriting") or {}
        passed = any(
            row["status"] == "conflicts"
            and "C" in row["label"]
            and "80" in row["label"]
            for row in draft.get("figure_review", [])
        )
        if not draft.get("image_url"):
            raise RuntimeError("恢复后缺少原图")
        original = client.get(base + draft["image_url"])
        passed = (
            passed
            and original.status_code == 200
            and original.content == (runtime / "figure-review-example.png").read_bytes()
            and not task["learning_applied"]
        )
        report.update(task_id=task["id"], handwriting=draft)
        stage = (
            "actual-refreshed-figure-and-original"
            if refresh
            else "actual-resumed-figure-and-original"
        )
        report["results"].append({"stage": stage, "passed": passed})
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        path.chmod(0o600)
        print(
            stage + ": " + ("通过" if passed else "未通过"),
            flush=True,
        )
        if not passed:
            raise RuntimeError("恢复后的图形核验未通过")


if __name__ == "__main__":
    try:
        if sys.argv[1:] not in ([], ["--submit"], ["--retry"], ["--refresh-photo"]):
            raise RuntimeError("参数无效")
        if sys.argv[1:] == ["--retry"]:
            retry_photo()
        elif sys.argv[1:] == ["--refresh-photo"]:
            retry_photo(refresh=True)
        else:
            main(submit=bool(sys.argv[1:]))
    except (RuntimeError, ValueError, KeyError, httpx.HTTPError, OSError):
        print("实际图形核验失败，未输出凭据或上游响应。", flush=True)
        raise SystemExit(1) from None
