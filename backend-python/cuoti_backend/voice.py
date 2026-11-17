"""Speech adapters retain original audio and reuse the existing compute provider."""

import base64
import hashlib
from uuid import uuid4

from fastapi import APIRouter, Request
from starlette.concurrency import run_in_threadpool

from .protocol import ApiError, envelope
from .question_data import execute, insert, rows, select_rows
from .question_routes import body, upload
from .question_validation import number, text_value

router = APIRouter(prefix="/api/v1/voice")


def context(db, owner, question_id, work_id):
    if question_id and not rows(
        db, "SELECT id FROM questions WHERE id=? AND user_id=?", [question_id, owner]
    ):
        raise ApiError(404, "题目不存在或无权访问")
    if work_id:
        works = rows(
            db, "SELECT * FROM student_works WHERE id=? AND user_id=?", [work_id, owner]
        )
        if not works:
            raise ApiError(404, "作答记录不存在或无权访问")
        if question_id and works[0]["question_id"] != question_id:
            raise ApiError(422, "作答记录与题目不匹配")


def saved(db, owner, question_id, work_id, kind, path, text, metadata, failed=False):
    duration = number(metadata.get("duration_ms", 0))
    if not 0 <= duration <= 2147483647 or not duration.is_integer():
        raise ApiError(422, "整数超出允许范围")
    id = insert(
        db,
        "voice_records",
        timestamp_microseconds=False,
        user_id=owner,
        question_id=question_id or None,
        work_id=work_id or None,
        kind=kind,
        audio_path=path,
        transcript=text,
        model_name=metadata.get("model") or "",
        status="failed" if failed else "completed",
        duration_ms=int(duration),
    )
    return select_rows(
        db, "voice_records", "SELECT * FROM voice_records WHERE id=?", [id]
    )[0]


def authorize(request):
    service = request.app.state.questions
    question_id, work_id = (
        request.query_params.get("question_id", ""),
        request.query_params.get("work_id", ""),
    )
    with service.database.session() as db:
        owner = service.user(request, db).id
        context(db, owner, question_id, work_id)
    return owner, question_id, work_id


@router.post("/transcribe")
async def transcribe_route(request: Request):
    owner, question_id, work_id = await run_in_threadpool(authorize, request)
    data, filename, _ = await upload(request, include_fields=True, audio=True)
    return envelope(
        request,
        await run_in_threadpool(
            transcribe,
            request.app.state.questions,
            owner,
            question_id,
            work_id,
            data,
            filename,
        ),
    )


def transcribe(service, owner, question_id, work_id, data, filename):
    suffix = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ".webm"
    if suffix not in [".webm", ".wav", ".mp3", ".m4a", ".ogg", ".mp4"]:
        suffix = ".webm"
    path = f"uploads/voice/{owner}/{uuid4()}{suffix}"
    service.media.write(path, data)
    try:
        if service.compute is None:
            raise ApiError(503, "内部算法服务未配置")
        computed = service.compute.compute(
            "voice_transcribe",
            audio_base64=base64.b64encode(data).decode("ascii"),
            audio_suffix=suffix,
        )
    except Exception:  # noqa: BLE001 -- Persist the failed audio without leaking provider errors.
        with service.database.session() as db, db.begin():
            saved(
                db,
                owner,
                question_id,
                work_id,
                "stt",
                path,
                "",
                {"model": "faster-whisper-small"},
                True,
            )
        raise ApiError(502, "语音转写失败，请稍后重试或使用文字输入") from None
    metadata, text = computed.get("metadata") or {}, computed["text"]
    with service.database.session() as db, db.begin():
        record = saved(db, owner, question_id, work_id, "stt", path, text, metadata)
        if work_id:
            execute(
                db,
                "UPDATE student_works SET explanation=?,updated_at=UTC_TIMESTAMP(6) WHERE id=? AND user_id=?",
                [text, work_id, owner],
            )
    return {
        **record,
        "text": text,
        "bytes": len(data),
        "editable": True,
        "metadata": metadata,
        "audio_url": service.media.url("/" + path),
    }


@router.post("/synthesize")
async def synthesize_route(request: Request):
    return envelope(
        request, await run_in_threadpool(synthesize, request, await body(request))
    )


def synthesize(request, value):
    service = request.app.state.questions
    with service.database.session() as db:
        owner = service.user(request, db).id
        text = text_value(value.get("text", ""), 12000).strip()
        if not text:
            raise ApiError(400, "朗读文本不能为空")
        question_id = (
            ""
            if value.get("question_id") is None
            else text_value(value["question_id"], 36)
        )
        voice = text_value(value.get("voice", "zh-CN-XiaoxiaoNeural"), 100)
        context(db, owner, question_id, "")
    if service.compute is None:
        raise ApiError(503, "内部算法服务未配置")
    computed = service.compute.compute("voice_synthesize", text=text, voice=voice)
    try:
        data = base64.b64decode(computed["audio_base64"], validate=True)
        if (
            not data
            or len(data) > 64 * 1024 * 1024
            or hashlib.sha256(data).hexdigest() != computed["sha256"]
        ):
            raise ValueError("invalid audio")
    except (ValueError, KeyError, TypeError):
        raise ApiError(502, "语音合成结果无效") from None
    path = f"uploads/voice/{owner}/tts-{uuid4()}.mp3"
    service.media.write(path, data)
    try:
        with service.database.session() as db, db.begin():
            record = saved(
                db,
                owner,
                question_id,
                "",
                "tts",
                path,
                text,
                computed.get("metadata") or {},
            )
    except BaseException:
        service.media.remove(path)
        raise
    return {
        **record,
        "text": text,
        "browser_fallback": False,
        "metadata": computed.get("metadata") or {},
        "audio_url": service.media.url("/" + path),
    }
