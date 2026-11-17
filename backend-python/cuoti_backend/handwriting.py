"""Shared photo input for tutor activities, reviews and practice."""

import base64
import io
from uuid import uuid4

from fastapi import APIRouter, Request
from PIL import Image
from starlette.concurrency import run_in_threadpool

from .practice_context import served, source_version
from .protocol import ApiError, envelope
from .question_data import select_rows
from .question_routes import upload
from .recognition import image_bytes
from .reviews import question as review_question
from .tutoring import current_activity

router = APIRouter(prefix="/api/v1/answers")


def practice_context(db, owner, mistake_id, id, mode):
    mistakes = select_rows(
        db,
        "questions",
        "SELECT * FROM questions WHERE id=? AND user_id=?",
        [mistake_id, owner],
    )
    generated = select_rows(
        db,
        "variant_questions",
        "SELECT v.* FROM variant_questions v JOIN tutor_sessions s ON s.id=v.session_id WHERE v.id=? AND v.question_id=? AND s.user_id=? AND s.stage='standalone_practice'",
        [id, mistake_id, owner],
    )
    if mistakes and generated:
        meta = generated[0].get("generation_metadata") or {}
        if meta.get("mode") != mode or meta.get("source_version") != source_version(
            db, mistakes[0]
        ):
            raise ApiError(409, "原题已更新，请重新获取练习")
        if meta.get("options"):
            raise ApiError(422, "选择题请直接选择选项")
        return {
            "subject": mistakes[0]["subject"],
            "text": generated[0]["question_text"],
        }
    questions = select_rows(
        db, "dataset_questions", "SELECT * FROM dataset_questions WHERE id=?", [id]
    )
    if not mistakes or not questions:
        raise ApiError(404, "没有找到这道练习题")
    q = questions[0]
    served(db, owner, mistakes[0], id, mode)
    if q.get("options"):
        raise ApiError(422, "选择题请直接选择选项")
    return {"subject": q["subject"], "text": q["question_text"]}


def visible(service, db, owner, fields):
    kind, id = fields.get("context_type", ""), fields.get("context_id", "")
    if kind == "practice":
        return practice_context(
            db, owner, fields.get("mistake_id", ""), id, fields.get("mode", "reinforce")
        )
    if kind == "review":
        plans = select_rows(
            db,
            "review_plans",
            "SELECT * FROM review_plans WHERE id=? AND user_id=? AND status='pending'",
            [id, owner],
        )
        if not plans:
            raise ApiError(404, "待复习题不存在")
        q = review_question(db, plans[0], owner)
        if q.get("options"):
            raise ApiError(422, "选择题请直接选择选项")
        return {"subject": q["subject"], "text": q["question_text"]}
    if kind != "tutor":
        raise ApiError(422, "不支持的答题场景")
    sessions = select_rows(
        db,
        "tutor_sessions",
        "SELECT * FROM tutor_sessions WHERE id=? AND user_id=?",
        [id, owner],
    )
    if not sessions:
        raise ApiError(404, "学习会话不存在")
    session = sessions[0]
    detail = service.detail(db, session["question_id"], owner)
    if (session.get("state") or {}).get("question_changed") is True or detail[
        "status"
    ] == "archived":
        raise ApiError(409, "题目已变化或归档，请重新开始学习")
    activity = current_activity(service, db, session, detail)
    if not isinstance(activity, dict) or activity.get("id", "") != fields.get(
        "activity_id", ""
    ):
        raise ApiError(409, "当前练习已经变化，请刷新后重新上传")
    if activity.get("type") in [
        "single_choice",
        "multiple_choice",
        "explanation",
        "teach_back",
    ]:
        raise ApiError(422, "当前练习不需要上传手写过程")
    return {"subject": detail["subject"], "text": activity["question"]}


def owner(request):
    service = request.app.state.questions
    with service.database.session() as db:
        return service.user(request, db).id


@router.post("/handwriting")
async def upload_route(request: Request):
    user = await run_in_threadpool(owner, request)
    data, _, fields = await upload(request, include_fields=True)
    return envelope(
        request,
        await run_in_threadpool(
            recognize, request.app.state.questions, user, data, fields
        ),
    )


def recognize(service, owner, data, fields):
    with service.database.session() as db, db.begin():
        context = visible(service, db, owner, fields)
    if service.compute is None:
        raise ApiError(503, "内部算法服务未配置")
    normalized = service.compute.compute(
        "normalize", image_base64=base64.b64encode(data).decode("ascii")
    )
    image = image_bytes(normalized)
    kind, id = fields["context_type"], fields["context_id"]
    image_id = uuid4().hex
    prefix = f"uploads/answers/{owner}/{kind}/{id}/handwriting-{image_id}"
    # Keep the exact uploaded file as well as the normalized image used by the old API.
    with Image.open(io.BytesIO(data)) as original:
        suffix = {"PNG": "png", "JPEG": "jpg", "WEBP": "webp"}.get(
            original.format, "bin"
        )
    raw_path, path = prefix + ".original." + suffix, prefix + ".jpg"
    service.media.write(raw_path, data)
    try:
        service.media.write(path, image)
    except BaseException:
        service.media.remove(raw_path)
        raise
    try:
        computed = service.compute.compute(
            "recognize_handwriting",
            image_base64=base64.b64encode(image).decode("ascii"),
            subject=context["subject"],
            text=context["text"],
        )
    except Exception:  # noqa: BLE001 -- Preserve photos and avoid exposing provider errors.
        raise ApiError(
            503, "照片已保留，但暂时无法识别，请稍后重试或使用文字输入"
        ) from None
    return {
        "image_url": service.media.url("/" + path),
        "recognition": computed["recognition"],
    }
