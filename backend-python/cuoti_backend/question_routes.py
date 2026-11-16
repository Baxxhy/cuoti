import base64
import hashlib
import io
from uuid import uuid4

from fastapi import APIRouter, Request
from PIL import Image
from python_multipart.exceptions import MultipartParseError
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException

from .accounts import json_body
from .protocol import ApiError, envelope
from .question_data import insert, owned, rows, select_rows, update
from .question_validation import boolean, crop_box
from .recognition import image_bytes

router = APIRouter(prefix="/api/v1")


async def body(request, empty=False, maximum=8 * 1024 * 1024):
    import json

    raw = await request.body()
    if len(raw) > maximum:
        raise ApiError(413, "请求内容过大")
    if not raw and empty:
        return {}
    try:
        value = json.loads(raw)
        if isinstance(value, dict):
            return value
    except (ValueError, UnicodeError):
        pass
    raise ApiError(422, "请输入有效的 JSON 对象")


@router.get("/questions")
def list_questions(request: Request):
    return envelope(request, request.app.state.questions.list(request))


@router.post("/questions/manual")
async def manual(request: Request):
    value = await body(request)
    result = await run_in_threadpool(request.app.state.questions.manual, request, value)
    return envelope(request, result)


async def upload(request):
    if (
        not request.headers.get("content-type", "")
        .lower()
        .startswith("multipart/form-data")
    ):
        raise ApiError(422, "请选择上传图片")
    try:
        form = await request.form(max_files=32, max_fields=32, max_part_size=4096)
    except (HTTPException, MultipartParseError, ValueError):
        raise ApiError(422, "上传内容格式不正确") from None
    try:
        entries = form.multi_items()
        if len(entries) > 32:
            raise ApiError(422, "上传字段过多")
        files = [value for key, value in entries if key == "file"]
        other_files = [
            v for key, v in entries if key != "file" and hasattr(v, "filename")
        ]
        if len(files) != 1 or not hasattr(files[0], "filename") or other_files:
            raise ApiError(422, "请上传一张图片")
        file = files[0]
        filename = file.filename or "上传错题"
        if len(filename) > 255:
            raise ApiError(422, "文件名称过长")
        data = await file.read(15 * 1024 * 1024 + 1)
        if len(data) > 15 * 1024 * 1024:
            raise ApiError(413, "图片不能超过 15 MB")
        if not data:
            raise ApiError(422, "图片为空，请重新选择图片")
        fields = {
            key: value for key, value in entries if not hasattr(value, "filename")
        }
        if any(len(v.encode()) > 4096 for v in fields.values()):
            raise ApiError(422, "上传字段过长")
        deferred = boolean(fields.get("defer_processing", ""))
        return data, filename, deferred
    finally:
        await form.close()


def ingest(request, data, filename, deferred):
    app = request.app
    service = app.state.questions
    files = []
    try:
        with service.database.session() as db, db.begin():
            owner = service.user(request, db).id
        if app.state.compute is None:
            raise ApiError(503, "内部算法服务未配置")
        normalized = app.state.compute.compute(
            "normalize", image_base64=base64.b64encode(data).decode()
        )
        if normalized["kind"] != "original":
            raise ApiError(503, "原图结果无效")
        id = str(uuid4())
        job_id = None
        with Image.open(io.BytesIO(data)) as image:
            suffix = {"PNG": "png", "JPEG": "jpg", "WEBP": "webp"}.get(
                image.format, "bin"
            )
        path = f"uploads/{id}/original.jpg"
        uploaded = f"uploads/{id}/uploaded.{suffix}"
        service.media.write(path, image_bytes(normalized))
        files.append(path)
        service.media.write(uploaded, data)
        files.append(uploaded)
        subject = request.query_params.get("subject", "") or "数学"
        if len(subject) > 30:
            raise ApiError(422, "学科名称过长")
        with service.database.session() as db, db.begin():
            insert(
                db,
                "questions",
                id=id,
                user_id=owner,
                subject=subject,
                title=filename,
                question_text="",
                status="awaiting_crop" if deferred else "processing",
                confirmed=False,
                favorite=False,
                tags=[],
                formulas=[],
                options=[],
                question_type="综合题",
                knowledge_points=[],
            )
            for stored, kind, sha in [
                (path, "original", normalized["sha256"]),
                (uploaded, "uploaded_original", hashlib.sha256(data).hexdigest()),
            ]:
                insert(
                    db,
                    "question_assets",
                    question_id=id,
                    kind=kind,
                    path=stored,
                    sha256=sha,
                    bbox=[],
                )
            if not deferred:
                job_id = insert(
                    db,
                    "processing_jobs",
                    question_id=id,
                    kind="ingest",
                    status="pending",
                    progress=0,
                )
                files.append(app.state.recognition.track(job_id, id, path, False))
        files.clear()
        if job_id:
            app.state.recognition.submit(job_id, id, path)
        return {
            "question_id": id,
            "job_id": job_id,
            "status": "awaiting_crop" if deferred else "pending",
        }
    finally:
        for stored in files:
            service.media.remove(stored)


@router.post("/questions/ingest")
async def ingest_route(request: Request):
    data, filename, deferred = await upload(request)
    return envelope(
        request, await run_in_threadpool(ingest, request, data, filename, deferred)
    )


def crop(request, id, box):
    app = request.app
    service = app.state.questions
    files = []
    try:
        with service.database.session() as db, db.begin():
            owner = service.user(request, db).id
            question = owned(db, id, owner, lock=True)
            if question["status"] == "archived":
                raise ApiError(404, "题目不存在或已归档")
            active = app.state.recognition.active(db, id)
            previous = select_rows(
                db,
                "question_assets",
                "SELECT * FROM question_assets WHERE question_id=? AND kind='crop' ORDER BY created_at DESC,id DESC LIMIT 1",
                [id],
            )
            if active:
                if previous:
                    asset = previous[0]
                    bounds = asset["bbox"]
                    stored = (
                        [
                            bounds[0],
                            bounds[1],
                            bounds[2] - bounds[0],
                            bounds[3] - bounds[1],
                        ]
                        if len(bounds) == 4
                        else []
                    )
                    if len(stored) == 4 and all(
                        abs(a - b) <= 0.000001 for a, b in zip(box, stored, strict=True)
                    ):
                        return {
                            **asset,
                            "url": service.media.url("/" + asset["path"]),
                            "job_id": active["id"],
                            "status": active["status"],
                            "resumed": True,
                            "crop_box": stored,
                        }
                raise ApiError(409, "已有识别任务正在处理，请先查看结果再调整范围")
            originals = rows(
                db,
                "SELECT path FROM question_assets WHERE question_id=? AND kind='original' ORDER BY created_at,id LIMIT 1",
                [id],
            )
            if not originals:
                raise ApiError(404, "原图不存在")
            if app.state.compute is None:
                raise ApiError(503, "内部算法服务未配置")
            computed = app.state.compute.compute(
                "crop",
                image_base64=base64.b64encode(
                    service.media.read(originals[0]["path"])
                ).decode(),
                box=box,
            )
            if computed["kind"] != "crop":
                raise ApiError(503, "裁剪结果无效")
            path = f"uploads/{id}/crops/{uuid4()}.jpg"
            service.media.write(path, image_bytes(computed))
            files.append(path)
            bounds = [box[0], box[1], min(1, box[0] + box[2]), min(1, box[1] + box[3])]
            if previous:
                asset_id = previous[0]["id"]
                update(
                    db,
                    "question_assets",
                    asset_id,
                    path=path,
                    sha256=computed["sha256"],
                    bbox=bounds,
                )
            else:
                asset_id = insert(
                    db,
                    "question_assets",
                    question_id=id,
                    kind="crop",
                    path=path,
                    sha256=computed["sha256"],
                    bbox=bounds,
                )
            job_id = insert(
                db,
                "processing_jobs",
                question_id=id,
                kind="crop",
                status="pending",
                progress=0,
            )
            update(db, "questions", id, status="processing")
            files.append(app.state.recognition.track(job_id, id, path, True))
            result = select_rows(
                db,
                "question_assets",
                "SELECT * FROM question_assets WHERE id=?",
                [asset_id],
            )[0]
            result.update(
                url=service.media.url("/" + path),
                geometry=computed["geometry"],
                original_preserved=True,
                job_id=job_id,
                status="pending",
            )
        files.clear()
        app.state.recognition.submit(job_id, id, path, True)
        return result
    finally:
        for stored in files:
            service.media.remove(stored)


@router.post("/questions/{id}/crop")
async def crop_route(request: Request, id: str):
    box = crop_box(await json_body(request))
    return envelope(request, await run_in_threadpool(crop, request, id, box))


@router.post("/questions/{id}/ocr")
def recognize(request: Request, id: str):
    return envelope(request, request.app.state.recognition.start(request, id, True))


@router.post("/questions/{id}/reprocess")
def reprocess(request: Request, id: str):
    return envelope(request, request.app.state.recognition.start(request, id, False))


@router.post("/questions/{id}/draft")
async def draft(request: Request, id: str):
    data = await body(request, empty=True)
    return envelope(
        request,
        await run_in_threadpool(
            request.app.state.questions.edit, request, id, data, False
        ),
    )


@router.post("/questions/{id}/confirm")
async def confirm(request: Request, id: str):
    data = await body(request, empty=True)
    return envelope(
        request,
        await run_in_threadpool(
            request.app.state.questions.edit, request, id, data, True
        ),
    )


@router.get("/jobs/{id}")
def job(request: Request, id: str):
    service = request.app.state.questions
    with service.database.session() as db, db.begin():
        owner = service.user(request, db).id
        items = select_rows(
            db,
            "processing_jobs",
            "SELECT j.* FROM processing_jobs j JOIN questions q ON q.id=j.question_id WHERE j.id=? AND q.user_id=?",
            [id, owner],
        )
        if not items:
            raise ApiError(404, "任务不存在或无权访问")
        return envelope(request, items[0])


@router.post("/jobs/{id}/retry")
def retry(request: Request, id: str):
    return envelope(request, request.app.state.recognition.retry(request, id))


@router.get("/questions/{id}")
def detail(request: Request, id: str):
    service = request.app.state.questions
    with service.database.session() as db, db.begin():
        owner = service.user(request, db).id
        return envelope(request, service.detail(db, id, owner))


@router.patch("/questions/{id}")
async def edit(request: Request, id: str):
    data = await body(request)
    return envelope(
        request,
        await run_in_threadpool(request.app.state.questions.edit, request, id, data),
    )


@router.delete("/questions/{id}")
def delete_question(request: Request, id: str):
    return envelope(request, request.app.state.questions.archive(request, id))


def attach_image(request, id, data, filename, deferred, replace):
    app = request.app
    service = app.state.questions
    stored = []
    job_id = None
    try:
        with service.database.session() as db, db.begin():
            owner = service.user(request, db).id
            question = owned(db, id, owner, lock=True)
            if question["status"] == "archived":
                raise ApiError(409, "题目已归档，不能修改")
            if app.state.compute is None:
                raise ApiError(503, "内部算法服务未配置")
            normalized = app.state.compute.compute(
                "normalize", image_base64=base64.b64encode(data).decode()
            )
            with Image.open(io.BytesIO(data)) as image:
                suffix = {"PNG": "png", "JPEG": "jpg", "WEBP": "webp"}[image.format]
            expected_kind = "original" if replace else "question_figure"
            existing = select_rows(
                db,
                "question_assets",
                "SELECT * FROM question_assets WHERE question_id=? AND kind=? AND sha256=? ORDER BY created_at DESC LIMIT 1",
                [id, expected_kind, normalized["sha256"]],
            )
            originals = select_rows(
                db,
                "question_assets",
                "SELECT * FROM question_assets WHERE question_id=? AND kind='uploaded_original' AND sha256=? ORDER BY created_at DESC LIMIT 1",
                [id, hashlib.sha256(data).hexdigest()],
            )
            if existing and originals:
                asset, raw_asset = existing[0], originals[0]
                asset["url"] = service.media.url("/" + asset["path"])
                raw_asset["url"] = service.media.url("/" + raw_asset["path"])
                active = app.state.recognition.active(db, id)
                return {
                    "asset": asset,
                    "uploaded_asset": raw_asset,
                    "job_id": active["id"] if active else None,
                    "original_preserved": True,
                    "resumed": True,
                }
            unique = str(uuid4())
            path = f"uploads/{id}/supplements/{unique}.jpg"
            raw_path = f"uploads/{id}/supplements/{unique}-uploaded.{suffix}"
            service.media.write(path, image_bytes(normalized))
            stored.append(path)
            service.media.write(raw_path, data)
            stored.append(raw_path)
            from .question_data import execute, invalidate

            invalidate(db, id)
            execute(
                db,
                "UPDATE processing_jobs SET status='cancelled',error='题目图片已更新',updated_at=UTC_TIMESTAMP() WHERE question_id=? AND status IN ('pending','running')",
                [id],
            )
            if replace:
                execute(
                    db,
                    "UPDATE question_assets SET kind=CASE kind WHEN 'original' THEN 'previous_original' WHEN 'crop' THEN 'previous_crop' WHEN 'uploaded_original' THEN 'previous_uploaded_original' ELSE 'historical_figure' END,updated_at=UTC_TIMESTAMP() WHERE question_id=? AND kind IN ('original','crop','uploaded_original','question_figure','student_working_figure','teacher_annotation_region')",
                    [id],
                )
                execute(
                    db,
                    "UPDATE ocr_runs SET stream='previous_qwen_crop' WHERE question_id=? AND stream='qwen_crop'",
                    [id],
                )
            asset_id = insert(
                db,
                "question_assets",
                question_id=id,
                kind="original" if replace else "question_figure",
                path=path,
                sha256=normalized["sha256"],
                bbox=[],
                description=filename,
            )
            raw_id = insert(
                db,
                "question_assets",
                question_id=id,
                kind="uploaded_original",
                path=raw_path,
                sha256=hashlib.sha256(data).hexdigest(),
                bbox=[],
            )
            update(
                db,
                "questions",
                id,
                confirmed=False,
                status="awaiting_crop" if replace else "needs_confirmation",
            )
            if replace and not deferred:
                job_id = insert(
                    db,
                    "processing_jobs",
                    question_id=id,
                    kind="ingest",
                    status="pending",
                    progress=0,
                )
                update(db, "questions", id, status="processing")
                stored.append(app.state.recognition.track(job_id, id, path, False))
            asset = select_rows(
                db,
                "question_assets",
                "SELECT * FROM question_assets WHERE id=?",
                [asset_id],
            )[0]
            uploaded = select_rows(
                db,
                "question_assets",
                "SELECT * FROM question_assets WHERE id=?",
                [raw_id],
            )[0]
            asset["url"] = service.media.url("/" + path)
            uploaded["url"] = service.media.url("/" + raw_path)
        stored.clear()
        if job_id:
            app.state.recognition.submit(job_id, id, path, False)
        return {
            "asset": asset,
            "uploaded_asset": uploaded,
            "job_id": job_id,
            "original_preserved": True,
        }
    finally:
        for path in stored:
            service.media.remove(path)


@router.post("/questions/{id}/images")
async def attach_image_route(request: Request, id: str):
    data, filename, deferred = await upload(request)
    replace = boolean(request.query_params.get("replace", "false"))
    result = await run_in_threadpool(
        attach_image, request, id, data, filename, deferred, replace
    )
    return envelope(request, result)


@router.post("/questions/{id}/student-work")
async def student_work(request: Request, id: str):
    value = await body(request)
    return envelope(
        request, await run_in_threadpool(save_student_work, request, id, value)
    )


def save_student_work(request, id, value):
    from .question_data import execute, invalidate
    from .question_validation import array, text_value

    answer = text_value(value.get("answer", ""), 12000)
    explanation = text_value(value.get("explanation", ""), 12000)
    steps = [text_value(s, 12000) for s in array(value, "steps", 100)]
    service = request.app.state.questions
    with service.database.session() as db, db.begin():
        owner = service.user(request, db).id
        question = owned(db, id, owner, lock=True)
        if question["status"] == "archived":
            raise ApiError(409, "题目已归档，不能提交作答")
        invalidate(db, id)
        execute(
            db,
            "UPDATE processing_jobs SET status='cancelled',error='已提交新作答，旧识别结果未应用',updated_at=UTC_TIMESTAMP() WHERE question_id=? AND kind IN ('ingest','crop','ocr','reprocess') AND status IN ('pending','running')",
            [id],
        )
        update(
            db,
            "questions",
            id,
            student_answer=answer or None,
            status="confirmed" if question["confirmed"] else "needs_confirmation",
        )
        work_id = insert(
            db,
            "student_works",
            question_id=id,
            user_id=owner,
            answer=answer,
            explanation=explanation,
        )
        for index, content in enumerate(steps):
            insert(
                db,
                "student_steps",
                work_id=work_id,
                step_index=index,
                text=content,
                bbox=[],
                raw_text=content,
                normalized_text=" ".join(content.split()),
                formula=content if "=" in content else "",
                confidence=1,
                source="user",
                user_confirmed=True,
            )
        return select_rows(
            db, "student_works", "SELECT * FROM student_works WHERE id=?", [work_id]
        )[0]
