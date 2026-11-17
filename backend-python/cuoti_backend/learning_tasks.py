"""Versioned student learning tasks; contracts preserved from the legacy backend."""

from copy import deepcopy
from math import floor
from uuid import uuid4

from fastapi import APIRouter, Request
from starlette.concurrency import run_in_threadpool

from .learning_evidence import stamp_compact
from .lessons import compact, digest
from .protocol import ApiError, envelope
from .question_data import execute, insert, rows, select_rows
from .question_routes import body
from .question_validation import short_title, text_value
from .task_budget import at_limit, limit_view, stopped_view
from .task_sources import (
    capture_source,
    fingerprint_fields,
    load_snapshot,
    validate_version,
)

router = APIRouter(prefix="/api/v1/learning-tasks")


def strict(value, allowed):
    if set(value) - set(allowed):
        raise ApiError(422, "请求包含不支持的字段")


def field(value, key, maximum, optional=False):
    return text_value(
        value.get(key, "") if optional else value.get(key),
        maximum,
        minimum=0 if optional else 1,
        trim=not optional,
    )


def task_owner(service, request, db):
    user = service.user(request, db)
    if user.role != "student":
        raise ApiError(403, "请使用学生账号学习")
    return user.id


def task_row(db, id, owner, *, lock=False):
    found = select_rows(
        db,
        "learning_tasks",
        "SELECT * FROM learning_tasks WHERE id=? AND user_id=?"
        + (" FOR UPDATE" if lock else ""),
        [id, owner],
    )
    if not found:
        raise ApiError(404, "学习任务不存在或无权访问")
    return found[0]


def public(service, task):
    output = {
        key: task.get(key)
        for key in [
            "id",
            "question_id",
            "session_id",
            "status",
            "version",
            "step_id",
            "input_fingerprint",
            "created_at",
            "updated_at",
            "learning_applied",
        ]
    }
    view = deepcopy(task.get("student_view") or {})
    for block in view.get("prompt_blocks") or []:
        images = block.get("images") or []
        if images:
            block["images"] = [
                service.media.url("/" + str(path).lstrip("/")) for path in images
            ]
    draft = view.get("handwriting") or {}
    if draft.get("image_url"):
        draft["image_url"] = service.media.url(draft["image_url"])
    limited = at_limit(task) and task["status"] in [
        "waiting_student",
        "needs_review",
        "failed",
    ]
    output.update(
        restart_required=limited,
        student_view=limit_view() if limited else view,
        last_request_id=task.get("active_request"),
        current_action=(task.get("pending_action") or {}).get("kind", ""),
        exit_reason=task.get("exit_reason") or "",
    )
    return output


@router.get("")
def listing(request: Request):
    service = request.app.state.questions
    with service.database.session() as db:
        owner = task_owner(service, request, db)
        qid = request.query_params.get("question_id", "")
        result = []
        for task in select_rows(
            db,
            "learning_tasks",
            "SELECT * FROM learning_tasks WHERE user_id=? AND (?='' OR question_id=?) ORDER BY updated_at DESC,id DESC LIMIT 50",
            [owner, qid, qid],
        ):
            item = public(service, task)
            titles = rows(
                db,
                "SELECT question_text FROM questions WHERE id=?",
                [task["question_id"]],
            )
            item["question_title"] = (
                (
                    titles[0]["question_text"]
                    if "$" in titles[0]["question_text"]
                    or "\\" in titles[0]["question_text"]
                    else short_title(titles[0]["question_text"], 60)
                )
                if titles
                else "本题学习"
            )
            result.append(item)
        return envelope(request, result)


@router.post("", status_code=202)
async def create_route(request: Request):
    return envelope(
        request, await run_in_threadpool(create, request, await body(request))
    )


def create(request, value):
    strict(value, ["question_id", "session_id", "request_id"])
    qid, rid = field(value, "question_id", 36), field(value, "request_id", 80)
    sid = field(value, "session_id", 36, True)
    hashed = digest(qid + "|" + sid)
    service = request.app.state.questions
    with service.database.session() as db, db.begin():
        owner = task_owner(service, request, db)
        snapshot = load_snapshot(db, qid, owner)
        previous = rows(
            db,
            "SELECT task_id,body_hash FROM learning_task_requests WHERE user_id=? AND request_id=?",
            [owner, rid],
        )
        if previous:
            if previous[0]["body_hash"] != hashed:
                raise ApiError(409, "同一请求编号不能用于不同任务")
            task = task_row(db, previous[0]["task_id"], owner, lock=True)
            validate_version(db, task, snapshot)
            return public(service, task)
        question, analysis = snapshot["question"], snapshot.get("analysis")
        if (
            question["status"] == "archived"
            or question.get("confirmed") is not True
            or not isinstance(analysis, dict)
            or not (analysis.get("final_answer") or "").strip()
        ):
            raise ApiError(409, "请先核对题目并完成分析，再开始订正学习")
        if sid and not rows(
            db,
            "SELECT id FROM tutor_sessions WHERE id=? AND user_id=? AND question_id=?",
            [sid, owner, qid],
        ):
            raise ApiError(404, "关联学习会话不存在")
        active = select_rows(
            db,
            "learning_tasks",
            "SELECT * FROM learning_tasks WHERE user_id=? AND question_id=? AND status IN ('queued','running','waiting_student','needs_review','failed') ORDER BY created_at DESC,id DESC LIMIT 1 FOR UPDATE",
            [owner, qid],
        )
        id, origin = "", "legacy_revalidated"
        if active and validate_version(db, active[0], snapshot):
            id = active[0]["id"]
        if not id:
            origin = "created"
            id = insert(
                db,
                "learning_tasks",
                user_id=owner,
                question_id=qid,
                session_id=sid or None,
                input_fingerprint=digest(stamp_compact(fingerprint_fields(snapshot))),
                status="queued",
                step_id=str(uuid4()),
                checkpoint={},
                student_view=stopped_view("正在准备这一步"),
                pending_action={"kind": "start", "text": ""},
                active_request="__initial__",
            )
        task = task_row(db, id, owner)
        capture_source(db, task, snapshot, origin=origin)
        execute(
            db,
            "INSERT INTO learning_task_requests (user_id,request_id,task_id,body_hash,created_at) VALUES (?,?,?,?,UTC_TIMESTAMP(6))",
            [owner, rid, id, hashed],
        )
        return public(service, task)


@router.get("/{id}")
def read(request: Request, id: str):
    service = request.app.state.questions
    with service.database.session() as db, db.begin():
        owner = task_owner(service, request, db)
        initial = task_row(db, id, owner)
        snapshot = load_snapshot(db, initial["question_id"], owner)
        task = task_row(db, id, owner, lock=True)
        validate_version(db, task, snapshot)
        return envelope(request, public(service, task))


def visual_values(value):
    values = value.get("visual_values", {})
    if not isinstance(values, dict) or len(values) > 3:
        raise ApiError(422, "图示参数格式或数量不正确")
    if any(
        key not in ["delta", "k", "b", "a", "h"]
        or type(number) not in (int, float)
        or not -1e8 <= number <= 1e8
        for key, number in values.items()
    ):
        raise ApiError(422, "包含不支持的图示参数")
    return values


def validate_visual(task, value, kind, values):
    if kind != "observe_visualization" and "visual_values" in value:
        raise ApiError(422, "当前动作不接受图示参数")
    if (
        kind == "visualize"
        and (task.get("student_view") or {}).get("input_kind") != "text"
    ):
        raise ApiError(409, "请先核对原题再查看图示")
    if kind not in ["observe_visualization", "close_visualization"]:
        return
    state = task.get("checkpoint") or {}
    visual = state.get("visualization") or {}
    if (
        state.get("visual_open") is not True
        or not visual
        or visual.get("source_phase", "") != state.get("phase", "")
    ):
        raise ApiError(409, "当前没有可操作的图示，请先打开")
    if kind == "close_visualization":
        return
    variables = (visual.get("spec") or {}).get("interactive_variables") or []
    if len(values) != len(variables):
        raise ApiError(422, "图示参数与当前图示不匹配")
    for variable in variables:
        name, low, high, step = (variable[k] for k in ["name", "min", "max", "step"])
        if name not in values:
            raise ApiError(422, "图示参数与当前图示不匹配")
        number = values[name]
        if step <= 0 or number < low or number > high:
            raise ApiError(422, "图示参数超出范围")
        grid = (number - low) / step
        if abs(grid - floor(grid + 0.5)) > 1e-7:
            raise ApiError(422, "图示参数不符合当前步长")


def attach_image(db, task, value, event):
    id = field(value, "handwriting_id", 36, True)
    if not id:
        if "handwriting_confirmed" in value:
            raise ApiError(422, "核对标记缺少对应照片")
        return
    if event["kind"] != "answer" or value.get("handwriting_confirmed") is not True:
        raise ApiError(422, "请先核对照片识别文字，再确认提交")
    images = select_rows(
        db,
        "learning_task_images",
        "SELECT * FROM learning_task_images WHERE id=? AND task_id=? AND input_fingerprint=?",
        [id, task["id"], task["input_fingerprint"]],
    )
    if not images:
        raise ApiError(422, "这张作答照片不属于当前任务版本")
    image = images[0]
    if image.get("confirmation_step_id") != task["step_id"] or not isinstance(
        image.get("recognition"), dict
    ):
        raise ApiError(409, "照片对应的步骤已更新，请重新核对当前作答")
    event.update(
        handwriting_id=id,
        handwriting_confirmed=True,
        handwriting_recognition=image["recognition"],
    )


@router.post("/{id}/actions", status_code=202)
async def action_route(request: Request, id: str):
    return envelope(
        request, await run_in_threadpool(action, request, id, await body(request))
    )


@router.post("/{id}/cancel")
async def cancel_route(request: Request, id: str):
    return envelope(
        request,
        await run_in_threadpool(
            action, request, id, await body(request, empty=True), True
        ),
    )


def action(request, id, value, cancel=False):
    if not cancel:
        strict(
            value,
            [
                "kind",
                "text",
                "version",
                "step_id",
                "input_fingerprint",
                "request_id",
                "handwriting_id",
                "handwriting_confirmed",
                "visual_values",
            ],
        )
    service = request.app.state.questions
    with service.database.session() as db, db.begin():
        owner = task_owner(service, request, db)
        initial = task_row(db, id, owner)
        snapshot = load_snapshot(db, initial["question_id"], owner)
        task = task_row(db, id, owner, lock=True)
        if cancel:
            if task["status"] not in ["completed", "cancelled", "stale"]:
                execute(
                    db,
                    "UPDATE learning_tasks SET status='cancelled',cancel_requested=1,version=version+1,lease_token=NULL,lease_until=NULL,student_view=?,exit_reason='student_cancelled',updated_at=UTC_TIMESTAMP(6) WHERE id=?",
                    [compact(stopped_view("已结束这次学习，之前的记录仍在")), id],
                )
                execute(
                    db,
                    "UPDATE learning_task_actions SET status='cancelled',updated_at=UTC_TIMESTAMP(6) WHERE task_id=? AND status='pending'",
                    [id],
                )
            return public(service, task_row(db, id, owner))
        rid, values = field(value, "request_id", 80), visual_values(value)
        parts = [
            value.get(key, "" if key == "text" else None)
            for key in [
                "kind",
                "text",
                "version",
                "step_id",
                "input_fingerprint",
                "handwriting_id",
                "handwriting_confirmed",
            ]
        ]
        if "visual_values" in value:
            parts.append([values.get(key) for key in ["delta", "k", "b", "a", "h"]])
        hashed = digest(stamp_compact(parts))
        if rid == "__initial__":
            raise ApiError(422, "请求编号不可用")
        prior = rows(
            db,
            "SELECT body_hash FROM learning_task_actions WHERE task_id=? AND request_id=?",
            [id, rid],
        )
        if prior:
            if prior[0]["body_hash"] != hashed:
                raise ApiError(409, "同一请求编号不能修改提交内容")
            validate_version(db, task, snapshot)
            return public(service, task)
        if not validate_version(db, task, snapshot):
            return public(service, task)
        status = task["status"]
        if status not in ["waiting_student", "needs_review", "failed"]:
            raise ApiError(409, "任务仍在处理或已结束，请先刷新状态")
        if (
            type(value.get("version")) is not int
            or value["version"] != task["version"]
            or field(value, "step_id", 36) != task["step_id"]
            or field(value, "input_fingerprint", 64) != task["input_fingerprint"]
        ):
            raise ApiError(409, "这一步已更新，请保留内容并刷新后再提交")
        kind = field(value, "kind", 30)
        if kind not in [
            "answer",
            "hint",
            "reveal",
            "resume",
            "use_text",
            "visualize",
            "observe_visualization",
            "close_visualization",
        ]:
            raise ApiError(422, "不支持的学习动作")
        validate_visual(task, value, kind, values)
        text = field(
            value,
            "text",
            1200 if kind == "observe_visualization" else 12000,
            kind != "observe_visualization",
        )
        if kind in ["answer", "observe_visualization"] and not text.strip():
            raise ApiError(422, "请先写下你的回答")
        if at_limit(task):
            raise ApiError(409, "这次学习已到上限，请结束后回原题重开")
        event = {"kind": kind, "text": text}
        if kind == "observe_visualization":
            event["visual_values"] = values
        attach_image(db, task, value, event)
        if (
            kind == "resume"
            and status == "failed"
            and (task.get("pending_action") or {}).get("kind")
            == "recognize_handwriting"
        ):
            event.update(
                kind="recognize_handwriting",
                handwriting_id=task["pending_action"]["handwriting_id"],
            )
        insert(
            db,
            "learning_task_actions",
            task_id=id,
            request_id=rid,
            body_hash=hashed,
            kind=kind,
            input_version=value["version"],
            input_step_id=task["step_id"],
            body=event,
            status="pending",
        )
        execute(
            db,
            "UPDATE learning_tasks SET status='queued',version=version+1,pending_action=?,active_request=?,lease_token=NULL,lease_until=NULL,exit_reason='',updated_at=UTC_TIMESTAMP(6) WHERE id=?",
            [compact(event), rid, id],
        )
        return public(service, task_row(db, id, owner))
