"""Real Cangjie upload -> Python algorithms -> simulated Qwen -> MySQL pipeline."""

import base64
import hashlib
import io
import json
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from uuid import uuid4

from PIL import Image, ImageDraw
from smoke_cangjie_accounts import request
from smoke_cangjie_analysis import analysis
from smoke_cangjie_assignments import assignments
from smoke_cangjie_diagnosis import diagnoses
from smoke_cangjie_journey import journey
from smoke_cangjie_learning_tasks import learning_tasks
from smoke_cangjie_papers import papers
from smoke_cangjie_practice import practice
from smoke_cangjie_retrieval import retrieval
from smoke_cangjie_reviews import reviews
from smoke_cangjie_system_admin import system_admin
from smoke_cangjie_tutor import tutor_start
from smoke_cangjie_tutor_completion import tutor_completion
from smoke_cangjie_tutor_dialogue import tutor_dialogue
from smoke_cangjie_variant_attempt import variant_attempts
from smoke_cangjie_visualizations import visualizations
from smoke_cangjie_voice import voice_pipeline


def ingest(endpoint, env, query):
    pool = Path(env["CANGJIE_API_POOL_PATH"])
    assert pool.name == "missing-pool.json" and pool.parent.name.startswith(
        "zhiwei-cangjie-algorithm."
    )
    root = Path(env["CANGJIE_MEDIA_ROOT"])
    image = Image.new("RGB", (100, 80), "white")
    ImageDraw.Draw(image).rectangle((20, 10, 40, 30), fill="red")
    stream = io.BytesIO()
    image.save(stream, "PNG")
    png = stream.getvalue()
    state = {"mode": "fail", "calls": 0, "errors": []}
    started, release = threading.Event(), threading.Event()
    recognition = {
        "subject": "数学",
        "grade": "初一",
        "question_type": "calculation",
        "question_text": "解方程：2x+3=11",
        "student_answer": "x=4",
        "student_steps": [
            {"index": 1, "text": "2x = 8"},
            {"index": 2, "text": " x=4 "},
        ],
        "teacher_annotations": [{"type": "comment", "text": "检查步骤"}],
        "question_figures": [
            {
                "role": "diagram",
                "bbox": [0.5, 0.5, 0.9, 0.9],
                "description": "原题示意图",
            }
        ],
        "student_working_figures": [
            {
                "role": "student_working_figure",
                "bbox": [0.1, 0.5, 0.4, 0.9],
                "description": "学生草图",
            }
        ],
        "teacher_annotation_regions": [
            {
                "role": "teacher_annotation_region",
                "bbox": [0.2, 0.125, 0.41, 0.39],
                "description": "红色批注",
            }
        ],
        "has_answer": True,
        "has_working": True,
        "has_teacher_annotation": True,
        "recognition_confidence": 0.9,
    }

    class Upstream(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *_):
            pass

        def do_POST(self):
            try:
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                assert body["model"] == "Qwen"
                content = body["messages"][-1]["content"]
                review_grader = (
                    "中学作业判题老师" in body["messages"][0]["content"]
                    and isinstance(content, str)
                    and "题目：解方程：3x+2=17\n" in content
                )
                pictures = (
                    [
                        part["image_url"]["url"].split(",", 1)[1]
                        for part in content
                        if part["type"] == "image_url"
                    ]
                    if isinstance(content, list)
                    else []
                )
                if (
                    review_grader
                    or state.get("analysis")
                    or state.get("diagnosing")
                    or state.get("teaching")
                    or state.get("dialogue")
                    or state.get("learning_task")
                    or state.get("variant")
                ):
                    state["analysis_images"] = len(pictures)
                else:
                    assert len(pictures) == 1
                for encoded in pictures:
                    with Image.open(io.BytesIO(base64.b64decode(encoded))) as source:
                        if "手写作答转写器" in body["messages"][0][
                            "content"
                        ] and not state.get("handwriting"):
                            assert 0 < source.width * source.height <= 25_000_000
                        else:
                            assert source.size == state.get("image_size", (100, 80))
                        assert any(
                            r > 140 and r > g * 1.4 and r > b * 1.4
                            for r, g, b in source.convert("RGB").getdata()
                        ), "must use original, not cleaned image"
                selected_result = (
                    state["analysis_result"] if state.get("analysis") else recognition
                )
                if state.get("diagnosing"):
                    prompt = json.dumps(body, ensure_ascii=False)
                    selected_result = (
                        state["repair_result"]
                        if "反事实验证器" in prompt
                        else state["diagnosis_result"]
                        if "错因体系" in prompt
                        else state["analysis_result"]
                    )
                if state.get("teaching"):
                    selected_result = state["teaching_result"]
                if state.get("variant"):
                    selected_result = state["variant_result"]
                if state.get("handwriting"):
                    selected_result = state["handwriting_result"]
                if state.get("dialogue"):
                    system_prompt = body["messages"][0]["content"]
                    if "教学任务规划器" in system_prompt:
                        perception = json.loads(content.split("\nJSON Schema:\n", 1)[0])
                        assert "foreign memory must not appear" not in json.dumps(
                            perception["long_term_memory"]
                        )
                        selected_result = {
                            **state["dialogue_plan"],
                            "memory_source_ids": perception["long_term_memory"][
                                "source_ids"
                            ][:3],
                        }
                    else:
                        assert "中学个性化教师" in system_prompt
                        state["dialogue_images"] = len(pictures)
                        selected_result = state["dialogue_reply"]
                if not state.get("handwriting") and any(
                    name in body["messages"][0]["content"]
                    for name in ("手写作答转写器", "手写与图形标注转写器")
                ):
                    selected_result = state.get(
                        "task_handwriting_result",
                        {
                            "final_answer": "x=4",
                            "steps": ["2x=8", "x=4"],
                            "transcription": "2x=8\nx=4",
                            "confidence": 0.7,
                            "uncertain": True,
                        },
                    )
                elif state.get("learning_task"):
                    memory_refs = []
                    if (
                        state.get("task_memory_probe")
                        and "中学学习规划器" in body["messages"][0]["content"]
                    ):
                        raw_context = content.split("上下文：", 1)[1].split(
                            "\nJSON Schema:\n", 1
                        )[0]
                        memory_context = json.loads(raw_context)
                        state["task_memory_context"] = memory_context
                        kind = state.get("task_memory_kind")
                        memory_refs = [
                            item["ref"]
                            for item in memory_context.get("memory_snapshot", {}).get(
                                "entries", []
                            )
                            if item["kind"] == kind
                        ][:1]
                        if state.get("task_memory_foreign"):
                            memory_refs = ["self_check:foreign"]
                    selected_result = {
                        "goal": "补充相关知识依据",
                        "tool_name": "visualization"
                        if state.get("task_visual_plan")
                        else "knowledge_search",
                        "decision_summary": "先查课程卡片，没有证据就回到等式关系",
                        "memory_refs": memory_refs,
                    }
                    if state.get("task_illegal_plan"):
                        selected_result["tool_name"] = "delete_database"
                if review_grader:
                    # A fixed process-grading protocol reply, not a general mock grader.
                    answer = content.split("学生作答：", 1)[1].split("\n请判断", 1)[0]
                    assert answer in {"x=4", "x=5", "3x=15\nx=5"}, (
                        "unexpected review fixture answer"
                    )
                    correct = answer != "x=4"
                    selected_result = {
                        "correct": correct,
                        "score": 100 if correct else 0,
                        "recognized_final_answer": "x=5" if correct else "x=4",
                        "reason": "等式两边同时减2，再除以3，答案正确。"
                        if correct
                        else "3x=15应得到x=5，请检查除法。",
                        "matched_key_steps": ["3x=15", "x=5"] if correct else [],
                        "error_points": [] if correct else ["最终答案有误"],
                        "confidence": 0.99,
                    }
                state["calls"] += 1
                if state["mode"] == "block":
                    started.set()
                    assert release.wait(15)
                if state["mode"] == "fail" or (
                    state.get("restart_only_handwriting")
                    and "手写作答转写器" not in body["messages"][0]["content"]
                    and not review_grader
                ):
                    status, result = 503, {"error": "simulated unavailable"}
                else:
                    status, result = (
                        200,
                        {
                            "choices": [
                                {
                                    "message": {
                                        "content": json.dumps(
                                            selected_result,
                                            ensure_ascii=False,
                                        )
                                    }
                                }
                            ]
                        },
                    )
            except Exception as error:  # noqa: BLE001 -- Record fixture-thread failures for main-thread assertions.
                state["errors"].append(
                    f"{type(error).__name__}@{traceback.extract_tb(error.__traceback__)[-1].lineno}"
                )
                status, result = 500, {"error": "fixture failure"}
            raw = json.dumps(result).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Upstream)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    handed_off = False

    def close_upstream():
        release.set()
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    pool.write_text(
        json.dumps(
            [
                {
                    "base_url": f"http://127.0.0.1:{server.server_port}/v1",
                    "api_key": "fixture-model-key",
                    "model": "Qwen",
                }
            ]
        )
    )
    account = request(
        endpoint,
        "POST",
        "/api/v1/auth/register",
        {
            "email": f"ingest-{uuid4().hex}@example.test",
            "password": "test-password-123",
            "name": "上传测试",
        },
    )
    token = account["access_token"]

    def upload(
        raw=png,
        deferred=False,
        filename='../../手机; "原图".png',
        expected=200,
        authenticated=True,
        content_type=None,
        body_override=None,
    ):
        boundary = "cangjie-boundary-" + uuid4().hex
        escaped = filename.replace("\\", "\\\\").replace('"', '\\"')
        body = (
            f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{escaped}"\r\nContent-Type: image/png\r\n\r\n'.encode()
            + raw
            + f'\r\n--{boundary}\r\nContent-Disposition: form-data; name="defer_processing"\r\n\r\n{str(deferred).lower()}\r\n--{boundary}--\r\n'.encode()
        )
        headers = {
            "Content-Type": content_type
            or f'multipart/form-data; boundary="{boundary}"'
        }
        if authenticated:
            headers["Authorization"] = "Bearer " + token
        try:
            response = urlopen(
                Request(
                    endpoint
                    + "/api/v1/questions/ingest?"
                    + urlencode({"subject": "物理"}),
                    data=body if body_override is None else body_override,
                    headers=headers,
                ),
                timeout=20,
            )
        except HTTPError as error:
            response = error
        with response:
            payload = json.load(response)
            assert response.status == expected, (response.status, payload)
        return payload["data"] if expected == 200 else payload

    def detail(item):
        return request(
            endpoint, "GET", "/api/v1/questions/" + item["question_id"], token=token
        )

    def wait_job(item, status):
        deadline = time.monotonic() + 20
        while True:
            job = request(
                endpoint, "GET", "/api/v1/jobs/" + item["job_id"], token=token
            )
            if job["status"] in {"failed", "completed", "cancelled"}:
                assert job["status"] == status, job
                return job
            assert time.monotonic() < deadline, job
            time.sleep(0.05)

    try:
        if env.get("CANGJIE_VERIFY_FOCUS") in {"practice-evidence", "review-recovery"}:
            other = request(
                endpoint,
                "POST",
                "/api/v1/auth/register",
                {
                    "email": f"practice-other-{uuid4().hex}@example.test",
                    "password": "test-password-123",
                    "name": "练习隔离测试",
                },
            )
            state["mode"] = "good"
            if env.get("CANGJIE_VERIFY_FOCUS") == "review-recovery":
                reviews(endpoint, env, query, token, other["access_token"], state)
            else:
                practice(endpoint, env, query, token, other["access_token"], state)
            assert not state["errors"], state["errors"]
            return None
        if env.get("CANGJIE_VERIFY_FOCUS") in {
            "task-images",
            "task-figures",
            "task-visuals",
            "task-sources",
            "task-memory",
            "task-budget",
            "task-contract",
        }:
            other = request(
                endpoint,
                "POST",
                "/api/v1/auth/register",
                {
                    "email": f"task-image-other-{uuid4().hex}@example.test",
                    "password": "test-password-123",
                    "name": "照片隔离测试",
                },
            )
            recovery = learning_tasks(
                endpoint,
                env,
                query,
                token,
                other["access_token"],
                state,
                started,
                release,
            )
            assert not state["errors"], state["errors"]
            handed_off = True
            return {
                "close_upstream": close_upstream,
                "learning_task_id": recovery,
                "token": token,
            }
        upload(authenticated=False, expected=401)
        upload(raw=b"", expected=422)
        upload(raw=b"not an image", expected=422)
        upload(content_type="application/json", expected=422)
        upload(body_override=b"broken", expected=422)
        upload(raw=b"x" * (15 * 1024 * 1024 + 1), expected=413)
        assert (
            query(
                env, f"SELECT COUNT(*) FROM questions WHERE user_id='{account['id']}'"
            )
            == "0"
        )
        deferred = upload(deferred=True)
        assert deferred["status"] == "awaiting_crop" and deferred["job_id"] is None
        saved = detail(deferred)
        assert saved["subject"] == "物理" and saved["title"] == '../../手机; "原图".png'
        assert len(saved["assets"]) == 2 and state["calls"] == 0
        original = next(
            asset for asset in saved["assets"] if asset["kind"] == "original"
        )
        assert original["path"] == f"uploads/{deferred['question_id']}/original.jpg"
        uploaded = next(
            asset for asset in saved["assets"] if asset["kind"] == "uploaded_original"
        )
        assert uploaded["path"] == f"uploads/{deferred['question_id']}/uploaded.png"
        assert (root / uploaded["path"]).read_bytes() == png
        assert uploaded["sha256"] == hashlib.sha256(png).hexdigest()
        with urlopen(endpoint + uploaded["url"]) as response:
            assert response.headers.get_content_type() == "image/png"
            assert response.read() == png
        raw = (root / original["path"]).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == original["sha256"]
        with urlopen(endpoint + original["url"]) as response:
            assert response.read() == raw
        # Filename and declared MIME cannot select the stored upload type.
        # JPEG metadata and WebP source bytes survive standardization exactly.
        for format_name, extension in (("JPEG", "jpg"), ("WEBP", "webp")):
            encoded = io.BytesIO()
            if format_name == "JPEG":
                exif = Image.Exif()
                exif[274] = 6
                exif[270] = "retain-upload-metadata"
                image.save(encoded, format_name, exif=exif)
            else:
                image.save(encoded, format_name)
            source_bytes = encoded.getvalue()
            extra = detail(
                upload(raw=source_bytes, deferred=True, filename="untrusted.png")
            )
            uploaded_extra = next(
                asset
                for asset in extra["assets"]
                if asset["kind"] == "uploaded_original"
            )
            assert uploaded_extra["path"].endswith("uploaded." + extension)
            assert (root / uploaded_extra["path"]).read_bytes() == source_bytes
            with urlopen(endpoint + uploaded_extra["url"]) as response:
                assert response.read() == source_bytes
                assert response.headers.get_content_type() == (
                    "image/jpeg" if extension == "jpg" else "image/webp"
                )
        before = {file for file in root.rglob("*") if file.is_file()}
        query(
            env,
            "ALTER TABLE questions ADD CONSTRAINT ingest_failure CHECK (title <> 'fail-upload')",
        )
        try:
            upload(filename="fail-upload", expected=503)
            assert {file for file in root.rglob("*") if file.is_file()} == before
        finally:
            query(env, "ALTER TABLE questions DROP CHECK ingest_failure")
        if env.get("CANGJIE_VERIFY_FOCUS") == "original-upload":
            assert not state["errors"]
            print(
                "Cangjie original uploads passed: PNG/JPEG EXIF/WebP exact bytes, MIME sniff, signed download and two-file transaction rollback"
            )
            return None
        failed = upload()
        wait_job(failed, "failed")
        assert (
            detail(failed)["status"] == "partial" and len(detail(failed)["assets"]) == 2
        )
        retry_path = f"/api/v1/jobs/{failed['job_id']}/retry"
        request(endpoint, "POST", retry_path, expected=401)
        request(
            endpoint, "POST", f"/api/v1/jobs/{uuid4()}/retry", token=token, expected=404
        )
        other = request(
            endpoint,
            "POST",
            "/api/v1/auth/register",
            {
                "name": "重试权限",
                "email": f"retry-{uuid4()}@example.com",
                "password": "Retry-Password-123",
            },
        )
        request(endpoint, "POST", retry_path, token=other["access_token"], expected=404)
        active_id = str(uuid4())
        query(
            env,
            f"INSERT INTO processing_jobs (id,question_id,kind,status,progress,created_at,updated_at) VALUES ('{active_id}','{failed['question_id']}','ocr','pending',0,UTC_TIMESTAMP(),UTC_TIMESTAMP())",
        )
        resumed = request(endpoint, "POST", retry_path, token=token)
        assert resumed["id"] == active_id and resumed["resumed"] is True
        query(env, f"DELETE FROM processing_jobs WHERE id='{active_id}'")
        query(
            env, f"UPDATE processing_jobs SET kind='ocr' WHERE id='{failed['job_id']}'"
        )
        request(endpoint, "POST", retry_path, token=token, expected=422)
        query(
            env,
            f"UPDATE processing_jobs SET kind='ingest' WHERE id='{failed['job_id']}'",
        )
        state["mode"] = "block"
        started.clear()
        release.clear()
        calls_before = state["calls"]
        try:
            with ThreadPoolExecutor(max_workers=2) as executor:
                responses = list(
                    executor.map(
                        lambda _: request(
                            endpoint,
                            "POST",
                            retry_path,
                            token=token,
                            expected=(200, 409),
                        ),
                        range(2),
                    )
                )
            assert sum(isinstance(item, dict) for item in responses) == 1
            assert 409 in responses
            assert started.wait(10)
        finally:
            release.set()
        wait_job(failed, "completed")
        assert state["calls"] == calls_before + 1
        request(endpoint, "POST", retry_path, token=token, expected=409)
        assert detail(failed)["status"] == "needs_confirmation"
        state["mode"] = "good"
        good = upload()
        wait_job(good, "completed")
        result = detail(good)
        assert result["status"] == "needs_confirmation" and result["confirmed"] is False
        assert (
            result["question_text"] == recognition["question_text"]
            and result["student_answer"] == "x=4"
        )
        assert [step["step_index"] for step in result["student_steps"]] == [0, 1]
        assert result["student_steps"][1]["normalized_text"] == "x=4"
        assert all(step["user_confirmed"] is False for step in result["student_steps"])
        assert len(result["teacher_marks"]) == 1 and len(result["assets"]) == 8
        assert (
            result["ocr"]["model_name"] == "Qwen"
            and result["ocr"]["status"] == "completed"
        )
        for asset in result["assets"]:
            assert (
                hashlib.sha256((root / asset["path"]).read_bytes()).hexdigest()
                == asset["sha256"]
            )
        source_asset = next(
            asset for asset in result["assets"] if asset["kind"] == "original"
        )
        source_upload = next(
            asset for asset in result["assets"] if asset["kind"] == "uploaded_original"
        )
        assert (root / source_upload["path"]).read_bytes() == png
        assert (root / source_asset["path"]).read_bytes() == raw
        assert (root / original["path"]).read_bytes() == raw
        cropped_item = upload(deferred=True)
        crop_api = f"/api/v1/questions/{cropped_item['question_id']}/crop"
        full_box = {"box": [0, 0, 1, 1]}
        request(endpoint, "POST", crop_api, full_box, expected=401)
        request(
            endpoint,
            "POST",
            crop_api,
            full_box,
            token=other["access_token"],
            expected=404,
        )
        for invalid in (
            {},
            {"box": [0, 0, 0, 1]},
            {"box": [0, 0, 2, 1]},
            {"box": [0, 0, 1]},
            {"box": [0, "NaN", 1, 1]},
        ):
            request(endpoint, "POST", crop_api, invalid, token=token, expected=422)
        state["mode"] = "block"
        started.clear()
        release.clear()
        calls_before = state["calls"]
        try:
            with ThreadPoolExecutor(max_workers=2) as executor:
                crops = list(
                    executor.map(
                        lambda _: request(
                            endpoint, "POST", crop_api, full_box, token=token
                        ),
                        range(2),
                    )
                )
            assert crops[0]["job_id"] == crops[1]["job_id"]
            assert sum(item.get("resumed", False) for item in crops) == 1
            assert started.wait(10)
            request(
                endpoint,
                "POST",
                crop_api,
                {"box": [0, 0, 0.5, 0.5]},
                token=token,
                expected=409,
            )
        finally:
            release.set()
        wait_job(crops[0], "completed")
        assert state["calls"] == calls_before + 1
        created_crop = next(item for item in crops if not item.get("resumed"))
        assert (
            created_crop["geometry"]["width"] == 100
            and created_crop["original_preserved"] is True
        )
        with urlopen(endpoint + created_crop["url"]) as response:
            assert hashlib.sha256(response.read()).hexdigest() == created_crop["sha256"]
        state["mode"] = "good"
        state["image_size"] = (50, 40)
        changed_crop = request(
            endpoint, "POST", crop_api, {"box": [0, 0, 0.5, 0.5]}, token=token
        )
        wait_job(changed_crop, "completed")
        assert (
            changed_crop["id"] == created_crop["id"]
            and changed_crop["path"] != created_crop["path"]
        )
        assert changed_crop["bbox"] == [0, 0, 0.5, 0.5]
        assert (
            changed_crop["geometry"]["width"] == 50
            and changed_crop["geometry"]["height"] == 40
        )
        assert (
            root / f"uploads/{cropped_item['question_id']}/original.jpg"
        ).read_bytes() == raw
        before_crops = set(
            (root / f"uploads/{cropped_item['question_id']}/crops").glob("*")
        )
        query(
            env,
            f"ALTER TABLE questions ADD CONSTRAINT crop_failure CHECK (id <> '{cropped_item['question_id']}' OR status <> 'processing')",
        )
        try:
            request(endpoint, "POST", crop_api, full_box, token=token, expected=503)
            assert (
                set((root / f"uploads/{cropped_item['question_id']}/crops").glob("*"))
                == before_crops
            )
            assert (
                next(
                    item
                    for item in detail(cropped_item)["assets"]
                    if item["kind"] == "crop"
                )["path"]
                == changed_crop["path"]
            )
        finally:
            query(env, "ALTER TABLE questions DROP CHECK crop_failure")
        request(
            endpoint,
            "DELETE",
            f"/api/v1/questions/{cropped_item['question_id']}",
            token=token,
        )
        request(endpoint, "POST", crop_api, full_box, token=token, expected=404)
        state["image_size"] = (100, 80)
        print(
            "Cangjie crop passed: geometry, original preservation, concurrent reuse, changed bounds, rollback and archive"
        )
        # Prepare a crop fixture for independent OCR/reprocess coverage.
        recognition_base = f"/api/v1/questions/{deferred['question_id']}"
        for operation in ("ocr", "reprocess"):
            path = recognition_base + "/" + operation
            request(endpoint, "POST", path, expected=401)
            request(endpoint, "POST", path, token=other["access_token"], expected=404)
            request(endpoint, "POST", path, token=token, expected=422)
        crop_path = f"uploads/{deferred['question_id']}/test-crop.jpg"
        (root / crop_path).write_bytes(raw)
        query(
            env,
            f"INSERT INTO question_assets (id,question_id,kind,path,sha256,bbox,created_at,updated_at) VALUES ('{uuid4()}','{deferred['question_id']}','crop','{crop_path}','{hashlib.sha256(raw).hexdigest()}',JSON_ARRAY(0,0,1,1),UTC_TIMESTAMP(),UTC_TIMESTAMP())",
        )
        state["mode"] = "block"
        started.clear()
        release.clear()
        calls_before = state["calls"]
        try:
            with ThreadPoolExecutor(max_workers=2) as executor:
                responses = list(
                    executor.map(
                        lambda _: request(
                            endpoint,
                            "POST",
                            recognition_base + "/reprocess",
                            token=token,
                        ),
                        range(2),
                    )
                )
            assert responses[0]["job_id"] == responses[1]["job_id"]
            assert sum(item.get("resumed", False) for item in responses) == 1
            assert started.wait(10)
            resumed = request(endpoint, "POST", recognition_base + "/ocr", token=token)
            assert resumed["resumed"] is True
            assert resumed["job"]["id"] == responses[0]["job_id"]
            assert resumed["question"]["id"] == deferred["question_id"]
        finally:
            release.set()
        wait_job(responses[0], "completed")
        assert state["calls"] == calls_before + 1
        state["mode"] = "good"
        recognized = request(endpoint, "POST", recognition_base + "/ocr", token=token)
        assert recognized["job"]["status"] == "completed"
        assert recognized["job"]["kind"] == "ocr"
        assert recognized["question"]["question_text"] == recognition["question_text"]
        assert (root / crop_path).read_bytes() == raw
        assert (root / original["path"]).read_bytes() == raw
        print(
            "Cangjie recognition passed: ownership, crop requirement, concurrent reuse, synchronous OCR and async reprocess"
        )
        analysis(
            endpoint,
            env,
            query,
            token,
            other["access_token"],
            state,
            started,
            release,
            raw,
        )
        diagnoses(
            endpoint, env, query, token, other["access_token"], state, started, release
        )
        tutor_start(
            endpoint, env, query, token, other["access_token"], state, started, release
        )
        tutor_completion(endpoint, env, query, token, other["access_token"], state)
        visualizations(endpoint, env, query, token, other["access_token"])
        variant_attempts(endpoint, env, query, token, other["access_token"], state)
        papers(endpoint, env, query, token, other["access_token"])
        system_admin(endpoint, env, query, token, other["access_token"])
        voice_pipeline(env, query, token, other["access_token"])
        tutor_dialogue(endpoint, env, query, token, other["access_token"], state)
        task_recovery = learning_tasks(
            endpoint, env, query, token, other["access_token"], state, started, release
        )
        practice(endpoint, env, query, token, other["access_token"], state)
        retrieval(endpoint, env, query, token, other["access_token"], state)
        reviews(endpoint, env, query, token, other["access_token"], state)
        assignments(endpoint, env, query, state)
        journey(endpoint, env, query, token, other["access_token"])
        for action in ("edit", "archive", "draft", "rollback"):
            started.clear()
            release.clear()
            state["mode"] = "block"
            item = upload()
            assert started.wait(10)
            path = "/api/v1/questions/" + item["question_id"]
            if action == "edit":
                request(
                    endpoint,
                    "PATCH",
                    path,
                    {"question_text": "用户修改后的新题"},
                    token=token,
                )
            elif action == "archive":
                request(endpoint, "DELETE", path, token=token)
            elif action == "draft":
                request(
                    endpoint,
                    "POST",
                    path + "/draft",
                    {"student_steps": ["人工核对步骤"]},
                    token=token,
                )
            else:
                query(
                    env,
                    f"ALTER TABLE questions ADD CONSTRAINT recognize_failure CHECK (id <> '{item['question_id']}' OR question_text = '')",
                )
            release.set()
            try:
                wait_job(item, "failed" if action == "rollback" else "cancelled")
                result = detail(item)
                assert result["ocr_runs"] == [] and len(result["assets"]) == 2
                cleanup_deadline = time.monotonic() + 10
                expected_files = {
                    root / "uploads" / item["question_id"] / "original.jpg",
                    root / "uploads" / item["question_id"] / "uploaded.png",
                }
                while {
                    file
                    for file in (root / "uploads" / item["question_id"]).rglob("*")
                    if file.is_file()
                } != expected_files:
                    assert time.monotonic() < cleanup_deadline
                    time.sleep(0.05)
                if action == "draft":
                    assert result["student_steps"][0]["text"] == "人工核对步骤"
                    assert result["status"] == "ocr_draft"
                if action == "edit":
                    assert result["question_text"] == "用户修改后的新题"
                if action == "archive":
                    assert result["status"] == "archived"
            finally:
                if action == "rollback":
                    query(env, "ALTER TABLE questions DROP CHECK recognize_failure")
        query(
            env,
            f"UPDATE questions SET status='processing' WHERE id='{deferred['question_id']}'",
        )
        recovery_job = str(uuid4())
        query(
            env,
            f"INSERT INTO processing_jobs (id,question_id,kind,status,progress,created_at,updated_at) VALUES ('{recovery_job}','{deferred['question_id']}','ingest','running',15,UTC_TIMESTAMP(),UTC_TIMESTAMP())",
        )
        assert not state["errors"], state["errors"]
        print(
            "Cangjie ingest passed: multipart, limits, original preservation, Qwen pipeline, assets, rollback, stale edit/archive protection"
        )
        state["restart_only_handwriting"] = True
        handed_off = True
        return {
            "close_upstream": close_upstream,
            "question_id": deferred["question_id"],
            "job_id": recovery_job,
            "learning_task_id": task_recovery,
            "visual_task_id": state.get("visual_recovery_id"),
            "token": token,
        }
    finally:
        if not handed_off:
            close_upstream()
