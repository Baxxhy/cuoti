"""Original handwriting photos associated with a versioned learning task."""

import hashlib
import re
from uuid import uuid4

from fastapi import APIRouter, Request
from starlette.concurrency import run_in_threadpool

from .learning_tasks import field, public, strict, task_owner, task_row
from .lessons import compact, digest
from .protocol import ApiError, envelope
from .question_data import execute, insert, rows
from .question_routes import upload
from .task_budget import at_limit
from .task_sources import load_snapshot, validate_version

router = APIRouter(prefix="/api/v1/learning-tasks")


@router.post("/{id}/handwriting", status_code=202)
async def upload_route(request: Request, id: str):
    # Match legacy ordering: authenticate and check ownership before parsing uploads.
    await run_in_threadpool(authorize, request, id)
    data, _, fields = await upload(request, include_fields=True)
    return envelope(
        request, await run_in_threadpool(save_upload, request, id, fields, data)
    )


def authorize(request, id):
    service = request.app.state.questions
    with service.database.session() as db:
        task_row(db, id, task_owner(service, request, db))


def extension(data):
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "webp"
    raise ApiError(422, "请上传JPEG、PNG或WEBP作答照片")


def save_upload(request, id, value, data):
    strict(value, ["request_id", "version", "step_id", "input_fingerprint"])
    rid = field(value, "request_id", 80)
    step = field(value, "step_id", 36)
    fingerprint = field(value, "input_fingerprint", 64)
    if rid == "__initial__":
        raise ApiError(422, "请求编号不可用")
    raw_version = field(value, "version", 12)
    if not re.fullmatch(r"[+-]?[0-9]+", raw_version):
        raise ApiError(422, "步骤版本无效")
    version = int(raw_version)
    suffix = extension(data)
    checksum = hashlib.sha256(data).hexdigest()
    hashed = digest(compact([str(version), step, fingerprint, checksum]))
    service = request.app.state.questions
    written = ""
    try:
        with service.database.session() as db, db.begin():
            owner = task_owner(service, request, db)
            initial = task_row(db, id, owner)
            snapshot = load_snapshot(db, initial["question_id"], owner)
            task = task_row(db, id, owner, lock=True)
            previous = rows(
                db,
                "SELECT body_hash FROM learning_task_actions WHERE task_id=? AND request_id=?",
                [id, rid],
            )
            if previous:
                if previous[0]["body_hash"] != hashed:
                    raise ApiError(409, "同一上传编号不能更换照片或步骤")
                validate_version(db, task, snapshot)
                return public(service, task)
            if not validate_version(db, task, snapshot):
                return public(service, task)
            if (
                task["status"] not in ["waiting_student", "needs_review"]
                or (task.get("student_view") or {}).get("input_kind") != "text"
            ):
                raise ApiError(409, "请先回到当前可作答步骤再上传")
            if (
                version != task["version"]
                or step != task["step_id"]
                or fingerprint != task["input_fingerprint"]
            ):
                raise ApiError(409, "学习步骤已更新，请刷新后重新上传")
            if at_limit(task):
                raise ApiError(409, "这次学习已到上限，请结束后回原题重开")
            image_id = str(uuid4())
            path = f"uploads/answers/{owner}/learning_task/{id}/{image_id}.{suffix}"
            service.media.write(path, data)
            written = path
            insert(
                db,
                "learning_task_images",
                id=image_id,
                task_id=id,
                request_id=rid,
                input_fingerprint=fingerprint,
                upload_step_id=step,
                original_path=written,
                sha256=checksum,
            )
            event = {
                "kind": "recognize_handwriting",
                "text": "",
                "handwriting_id": image_id,
            }
            insert(
                db,
                "learning_task_actions",
                task_id=id,
                request_id=rid,
                body_hash=hashed,
                kind="recognize_handwriting",
                input_version=version,
                input_step_id=step,
                body=event,
                status="pending",
            )
            execute(
                db,
                "UPDATE learning_tasks SET status='queued',version=version+1,pending_action=?,active_request=?,lease_token=NULL,lease_until=NULL,exit_reason='',updated_at=UTC_TIMESTAMP(6) WHERE id=?",
                [compact(event), rid, id],
            )
            return public(service, task_row(db, id, owner))
    except BaseException:
        if written:
            service.media.remove(written)
        raise
