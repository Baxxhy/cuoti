import asyncio
import base64
import hashlib
import json
import logging
from concurrent.futures import ThreadPoolExecutor

import httpx

from .protocol import ApiError
from .question_data import execute, insert, invalidate, owned, rows, select_rows, update
from .question_validation import short_title

logger = logging.getLogger("cuoti.backend")
KINDS = ["ingest", "crop", "ocr", "reprocess"]


class ComputeBridge:
    def __init__(self, app, secret, timeout=200):
        self.loop = asyncio.get_running_loop()
        self.timeout = timeout
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://algorithm",
            headers={"Authorization": "Bearer " + secret},
        )

    async def request(self, payload):
        response = await asyncio.wait_for(
            self.client.post("/v1/compute", json=payload), self.timeout
        )
        if response.status_code != 200:
            status = response.status_code if response.status_code in [422, 502] else 503
            raise ApiError(
                status,
                "图片或计算数据无效" if status == 422 else "内部算法计算暂时不可用",
            )
        body = response.json()
        if body.get("operation") != payload["operation"]:
            raise ApiError(503, "算法结果不匹配")
        return body["result"]

    def compute(self, operation, **values):
        future = asyncio.run_coroutine_threadsafe(
            self.request({"operation": operation, **values}), self.loop
        )
        try:
            return future.result(timeout=self.timeout + 5)
        except TimeoutError:
            future.cancel()
            raise ApiError(504, "算法计算超时") from None

    async def close(self):
        await self.client.aclose()


def image_bytes(value):
    try:
        raw = base64.b64decode(value["image_base64"], validate=True)
        if (
            0 < len(raw) <= 64 * 1024 * 1024
            and hashlib.sha256(raw).hexdigest() == value["sha256"]
        ):
            return raw
    except (ValueError, KeyError):
        pass
    raise ApiError(503, "算法图片校验失败")


def fingerprint(question):
    keys = [
        "question_text",
        "student_answer",
        "subject",
        "grade",
        "formulas",
        "options",
        "question_type",
        "knowledge_points",
        "confirmed",
    ]
    return json.dumps(
        [question.get(k) for k in keys], ensure_ascii=False, sort_keys=True
    )


class RecognitionJobs:
    def __init__(self, questions, bridge):
        self.questions = questions
        self.database = questions.database
        self.media = questions.media
        self.bridge = bridge
        self.executor = ThreadPoolExecutor(
            max_workers=2, thread_name_prefix="cuoti-ocr"
        )

    def manifest(self, job_id, question_id):
        return f"uploads/{question_id}/jobs/{job_id}.json"

    def track(self, job_id, question_id, path, crop):
        stored = self.manifest(job_id, question_id)
        payload = {
            "job_id": job_id,
            "question_id": question_id,
            "path": path,
            "crop": crop,
        }
        try:
            previous = json.loads(self.media.read(stored))
            if previous == payload:
                return stored
            self.media.remove(stored)
        except ApiError as error:
            if error.status != 404:
                raise
        except ValueError:
            self.media.remove(stored)
        self.media.write(stored, json.dumps(payload).encode())
        return stored

    def submit(self, job_id, question_id, path, crop=False):
        self.executor.submit(self.run, job_id, question_id, path, crop)

    def recover(self):
        # Only our durable manifests identify Python-owned jobs. Never touch native jobs.
        for file in self.media.root.glob("uploads/*/jobs/*.json"):
            try:
                item = json.loads(
                    self.media.read(file.relative_to(self.media.root).as_posix())
                )
                if (
                    file.stem != item["job_id"]
                    or file.parent.parent.name != item["question_id"]
                ):
                    continue
                with self.database.session() as db, db.begin():
                    jobs = rows(
                        db,
                        "SELECT status FROM processing_jobs WHERE id=? AND question_id=?",
                        [item["job_id"], item["question_id"]],
                    )
                if jobs and jobs[0]["status"] == "pending":
                    self.submit(
                        item["job_id"], item["question_id"], item["path"], item["crop"]
                    )
                elif jobs and jobs[0]["status"] == "running":
                    self.failure(
                        item["job_id"], item["question_id"], "", recovered=True
                    )
                else:
                    self.media.remove(file.relative_to(self.media.root).as_posix())
            except Exception:  # noqa: BLE001 -- Persist safe task failure without leaking provider details.
                logger.warning("recognition_recovery=deferred")

    def failure(self, job_id, question_id, expected, recovered=False, timed_out=False):
        try:
            with self.database.session() as db, db.begin():
                questions = select_rows(
                    db,
                    "questions",
                    "SELECT * FROM questions WHERE id=? FOR UPDATE",
                    [question_id],
                )
                jobs = rows(
                    db,
                    "SELECT status FROM processing_jobs WHERE id=? AND question_id=? FOR UPDATE",
                    [job_id, question_id],
                )
                if (
                    not questions
                    or not jobs
                    or jobs[0]["status"] not in ["pending", "running"]
                ):
                    return
                question = questions[0]
                cancelled = question["status"] == "archived" or (
                    expected and fingerprint(question) != expected
                )
                message = (
                    "题目已修改或归档，识别结果未应用"
                    if cancelled
                    else "识别计算超时，请重试"
                    if timed_out
                    else "识别任务因服务重启中断，请重试"
                    if recovered
                    else "识别暂时未完成，请检查图片后重试"
                )
                update(
                    db,
                    "processing_jobs",
                    job_id,
                    status="cancelled" if cancelled else "failed",
                    error=message,
                )
                if not cancelled and (
                    not recovered
                    or question["status"] in ["processing", "pending", "awaiting_crop"]
                ):
                    update(db, "questions", question_id, status="partial")
        except Exception:  # noqa: BLE001 -- Persist safe task failure without leaking provider details.
            logger.warning("recognition_failure_record=deferred")

    def run(self, job_id, question_id, path, crop=False):
        files = []
        committed = False
        expected = ""
        try:
            with self.database.session() as db, db.begin():
                questions = select_rows(
                    db,
                    "questions",
                    "SELECT * FROM questions WHERE id=? FOR UPDATE",
                    [question_id],
                )
                jobs = rows(
                    db,
                    "SELECT status FROM processing_jobs WHERE id=? AND question_id=? FOR UPDATE",
                    [job_id, question_id],
                )
                if not questions or not jobs or jobs[0]["status"] != "pending":
                    return
                if questions[0]["status"] == "archived":
                    update(
                        db,
                        "processing_jobs",
                        job_id,
                        status="cancelled",
                        error="题目已归档",
                    )
                    return
                if not rows(
                    db,
                    "SELECT id FROM question_assets WHERE question_id=? AND path=? AND kind=?",
                    [question_id, path, "crop" if crop else "original"],
                ):
                    raise ApiError(422, "识别图片不存在")
                expected = fingerprint(questions[0])
                update(
                    db,
                    "processing_jobs",
                    job_id,
                    status="running",
                    progress=15,
                    error=None,
                )
            if self.bridge is None:
                raise ApiError(503, "内部算法服务未配置")
            data = base64.b64encode(self.media.read(path)).decode()
            prepared = self.bridge.compute("preprocess", image_base64=data)
            with self.database.session() as db, db.begin():
                execute(
                    db,
                    "UPDATE processing_jobs SET progress=45,updated_at=UTC_TIMESTAMP() WHERE id=? AND status='running'",
                    [job_id],
                )
            computed = self.bridge.compute("recognize", image_base64=data)
            from learning_core.schemas import CroppedQuestionRecognition

            recognition = CroppedQuestionRecognition.model_validate(
                computed["recognition"]
            ).model_dump(mode="json")
            assets = []
            for asset in [*prepared["assets"], *computed["assets"]]:
                kind = asset["kind"]
                if kind not in [
                    "clean",
                    "red_mask",
                    "overlay",
                    "question_figure",
                    "student_working_figure",
                    "teacher_annotation_region",
                ]:
                    raise ApiError(503, "图片结果类型不正确")
                from uuid import uuid4

                stored = f"uploads/{question_id}/derived/{uuid4()}" + (
                    ".png" if kind == "red_mask" else ".jpg"
                )
                self.media.write(stored, image_bytes(asset))
                files.append(stored)
                assets.append({**asset, "path": stored})
            with self.database.session() as db, db.begin():
                question = select_rows(
                    db,
                    "questions",
                    "SELECT * FROM questions WHERE id=? FOR UPDATE",
                    [question_id],
                )[0]
                job = rows(
                    db,
                    "SELECT status FROM processing_jobs WHERE id=? AND question_id=? FOR UPDATE",
                    [job_id, question_id],
                )
                if not job or job[0]["status"] != "running":
                    return
                if (
                    question["status"] == "archived"
                    or fingerprint(question) != expected
                ):
                    update(
                        db,
                        "processing_jobs",
                        job_id,
                        status="cancelled",
                        error="题目已修改或归档，识别结果未应用",
                    )
                    return
                invalidate(db, question_id)
                execute(
                    db, "DELETE FROM teacher_marks WHERE question_id=?", [question_id]
                )
                execute(
                    db,
                    "DELETE FROM question_assets WHERE question_id=? AND kind IN ('question_figure','student_working_figure','teacher_annotation_region')",
                    [question_id],
                )
                for asset in assets:
                    insert(
                        db,
                        "question_assets",
                        question_id=question_id,
                        kind=asset["kind"],
                        path=asset["path"],
                        sha256=asset["sha256"],
                        role=asset.get("role"),
                        bbox=asset.get("bbox", []),
                        description=asset.get("description"),
                    )
                insert(
                    db,
                    "ocr_runs",
                    question_id=question_id,
                    provider="qwen-pool",
                    raw_result=recognition,
                    confidence=recognition["recognition_confidence"],
                    stream="qwen_crop",
                    status="completed",
                    model_name="Qwen",
                    duration_ms=computed["duration_ms"],
                    error=None,
                )
                content = recognition["question_text"]
                update(
                    db,
                    "questions",
                    question_id,
                    confirmed=False,
                    question_text=content,
                    student_answer=recognition["student_answer"],
                    subject=recognition["subject"],
                    grade=recognition["grade"],
                    question_type=recognition["question_type"],
                    formulas=[],
                    options=recognition["options"],
                    title=short_title(content, 60),
                    status="needs_confirmation",
                )
                self.questions.work(
                    db,
                    question_id,
                    question["user_id"],
                    recognition["student_answer"],
                    recognition["student_steps"],
                    confirmed=False,
                    source="qwen_crop",
                    confidence=recognition["recognition_confidence"],
                )
                for mark in recognition["teacher_annotations"]:
                    insert(
                        db,
                        "teacher_marks",
                        question_id=question_id,
                        mark_type=mark["type"],
                        comment=mark["text"],
                        bbox=[],
                        confidence=recognition["recognition_confidence"],
                        source="qwen_crop",
                    )
                update(
                    db,
                    "processing_jobs",
                    job_id,
                    status="completed",
                    progress=100,
                    error=None,
                )
            committed = True
        except Exception as error:  # noqa: BLE001 -- Persist safe task failure without leaking provider details.
            self.failure(
                job_id,
                question_id,
                expected,
                timed_out=isinstance(error, ApiError) and error.status == 504,
            )
        finally:
            if not committed:
                for file in files:
                    self.media.remove(file)
            try:
                with self.database.session() as db, db.begin():
                    saved = rows(
                        db, "SELECT status FROM processing_jobs WHERE id=?", [job_id]
                    )
                if not saved or saved[0]["status"] not in ["pending", "running"]:
                    self.media.remove(self.manifest(job_id, question_id))
            except Exception:  # noqa: BLE001 -- Keep the manifest for a later recovery attempt.
                logger.warning("recognition_manifest_cleanup=deferred")

    def close(self):
        self.executor.shutdown(wait=True)

    def active(self, db, id):
        jobs = select_rows(
            db,
            "processing_jobs",
            "SELECT * FROM processing_jobs WHERE question_id=? AND kind IN ('ingest','crop','ocr','reprocess') AND status IN ('pending','running') ORDER BY created_at DESC,id DESC LIMIT 1",
            [id],
        )
        return jobs[0] if jobs else None

    def start(self, request, id, synchronous):
        tracked = None
        try:
            with self.database.session() as db, db.begin():
                owner = self.questions.user(request, db).id
                question = owned(db, id, owner, lock=True)
                if question["status"] == "archived":
                    raise ApiError(404, "题目不存在或已归档")
                job = self.active(db, id)
                if job:
                    job_id = job["id"]
                    path = None
                else:
                    assets = rows(
                        db,
                        "SELECT path FROM question_assets WHERE question_id=? AND kind='crop' ORDER BY created_at DESC,id DESC LIMIT 1",
                        [id],
                    )
                    if not assets:
                        raise ApiError(422, "请先框选题目，生成裁剪图片后再识别")
                    path = assets[0]["path"]
                    job_id = insert(
                        db,
                        "processing_jobs",
                        question_id=id,
                        kind="ocr" if synchronous else "reprocess",
                        status="pending",
                        progress=0,
                    )
                    update(db, "questions", id, status="processing")
                    tracked = self.track(job_id, id, path, True)
        except BaseException:
            if tracked:
                self.media.remove(tracked)
            raise
        if path:
            if synchronous:
                self.run(job_id, id, path, True)
            else:
                self.submit(job_id, id, path, True)
        with self.database.session() as db, db.begin():
            result = (
                {
                    "job": select_rows(
                        db,
                        "processing_jobs",
                        "SELECT * FROM processing_jobs WHERE id=?",
                        [job_id],
                    )[0],
                    "question": self.questions.detail(db, id, owner),
                }
                if synchronous
                else {"job_id": job_id}
            )
        if not path:
            result["resumed"] = True
        return result

    def retry(self, request, job_id):
        tracked = None
        try:
            with self.database.session() as db, db.begin():
                owner = self.questions.user(request, db).id
                found = rows(
                    db,
                    "SELECT j.question_id FROM processing_jobs j JOIN questions q ON q.id=j.question_id WHERE j.id=? AND q.user_id=?",
                    [job_id, owner],
                )
                if not found:
                    raise ApiError(404, "任务不存在或无权访问")
                id = found[0]["question_id"]
                question = owned(db, id, owner, lock=True)
                if question["status"] == "archived":
                    raise ApiError(404, "题目不存在或已归档")
                job = select_rows(
                    db,
                    "processing_jobs",
                    "SELECT * FROM processing_jobs WHERE id=? FOR UPDATE",
                    [job_id],
                )[0]
                if job["status"] != "failed":
                    raise ApiError(409, "任务仍在处理或已完成，请刷新后查看结果")
                if job["kind"] not in KINDS:
                    raise ApiError(409, "该任务不支持识别重试")
                active = self.active(db, id)
                if active:
                    return {**active, "resumed": True}
                assets = rows(
                    db,
                    "SELECT path,kind FROM question_assets WHERE question_id=? AND (kind='crop' OR (kind='original' AND ?='ingest')) ORDER BY (kind='crop') DESC,created_at DESC,id DESC LIMIT 1",
                    [id, job["kind"]],
                )
                if not assets:
                    raise ApiError(422, "缺少识别图片，请重新框选题目")
                path = assets[0]["path"]
                crop = assets[0]["kind"] == "crop"
                update(
                    db,
                    "processing_jobs",
                    job_id,
                    status="pending",
                    progress=0,
                    error=None,
                )
                update(db, "questions", id, status="processing")
                tracked = self.track(job_id, id, path, crop)
                result = select_rows(
                    db,
                    "processing_jobs",
                    "SELECT * FROM processing_jobs WHERE id=?",
                    [job_id],
                )[0]
        except BaseException:
            if tracked:
                self.media.remove(tracked)
            raise
        self.submit(job_id, id, path, crop)
        return result
