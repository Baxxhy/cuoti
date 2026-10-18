"""Actual-pool upload check with a generated equation and byte-exact source."""

import hashlib
import io
import json
import os
import time
from pathlib import Path

import httpx
from PIL import Image, ImageDraw, ImageFont

PROJECT = Path(__file__).resolve().parents[1]


def main():
    runtime = PROJECT / ".runtime"
    credentials = json.loads((runtime / "live-system-login.json").read_text())
    base = "http://127.0.0.1:" + os.environ.get("CANGJIE_BACKEND_PORT", "8002")
    report = {"kind": "actual-image-source", "passed": False}
    os.umask(0o077)

    def record(stage, **fields):
        report.update(stage=stage, **fields)
        path = runtime / "live-image-check.json"
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        os.chmod(path, 0o600)
        print(json.dumps({"stage": stage, **fields}, ensure_ascii=False), flush=True)

    def body(response):
        if response.status_code != 200:
            raise ValueError("local request failed")
        return response.json()["data"]

    with httpx.Client(timeout=180) as client:
        try:
            user = body(client.post(base + "/api/v1/auth/login", json=credentials))
            headers = {"Authorization": "Bearer " + user["access_token"]}
            image = Image.new("RGB", (1000, 600), "white")
            draw = ImageDraw.Draw(image)
            font = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 42
            )
            for y, text in [
                (60, "Solve: 2x + 3 = 11"),
                (220, "2x = 11 + 3"),
                (310, "x = 7"),
            ]:
                draw.text((60, y), text, font=font, fill="black")
            stream = io.BytesIO()
            image.save(stream, format="PNG")
            original = stream.getvalue()
            item = body(
                client.post(
                    base + "/api/v1/questions/ingest",
                    headers=headers,
                    files={"file": ("actual-check.png", original, "image/png")},
                    data={"subject": "数学"},
                )
            )
            report["question_id"] = item["question_id"]
            record("accepted")
            if not item.get("job_id"):
                raise ValueError("missing job")
            end = time.monotonic() + 180
            while time.monotonic() < end:
                job = body(
                    client.get(base + "/api/v1/jobs/" + item["job_id"], headers=headers)
                )
                if job["status"] in ("completed", "failed", "cancelled"):
                    break
                time.sleep(1)
            if job["status"] != "completed":
                raise ValueError("processing not completed")
            record("processed", status=job["status"])
            question = body(
                client.get(
                    base + "/api/v1/questions/" + item["question_id"], headers=headers
                )
            )
            text = "".join(question.get("question_text", "").split())
            if not ("2x" in text and "11" in text):
                raise ValueError("OCR did not retain public equation")
            uploaded = next(
                asset
                for asset in question["assets"]
                if asset["kind"] == "uploaded_original"
            )
            working = next(
                asset for asset in question["assets"] if asset["kind"] == "original"
            )
            if uploaded["path"] == working["path"]:
                raise ValueError("processing source must be separate")
            response = client.get(base + uploaded["url"], headers=headers)
            expected = hashlib.sha256(original).hexdigest()
            if (
                response.status_code != 200
                or response.content != original
                or uploaded["sha256"] != expected
            ):
                raise ValueError("uploaded bytes were changed")
            if "image/png" not in response.headers.get("content-type", ""):
                raise ValueError("incorrect content type")
            record(
                "uploaded-original-preserved",
                passed=True,
                assets=len(question["assets"]),
            )
        except (httpx.HTTPError, ValueError, KeyError, StopIteration):
            record("failed", passed=False)
            raise RuntimeError("实际图片核验未通过，未输出上游报错或凭据") from None


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError, ValueError):
        print("图片核验未完成；请先运行固定题核验准备本地账号，再检查本地报告。")
        raise SystemExit(1) from None
