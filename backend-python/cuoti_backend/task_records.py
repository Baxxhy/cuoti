"""Student-owned task history and explicitly subjective self-check notes."""

from fastapi import APIRouter, Request
from starlette.concurrency import run_in_threadpool

from .learning_evidence import stamp_compact
from .learning_tasks import field, strict, task_owner, task_row
from .protocol import ApiError, envelope
from .question_data import insert, select_rows, update
from .question_routes import body
from .task_sources import load_snapshot, validate_version

router = APIRouter(prefix="/api/v1/learning-tasks")


def self_check_row(db, task):
    notes = select_rows(
        db,
        "learning_self_checks",
        "SELECT * FROM learning_self_checks WHERE user_id=? AND task_id=?",
        [task["user_id"], task["id"]],
    )
    return notes[0] if notes else {}


def self_check_public(note, current, can_save):
    output = {
        "version": note.get("version", 0),
        "source_current": current,
        "can_save": can_save,
        "note": None,
    }
    if note and note.get("deleted") is not True:
        output["note"] = {
            key: note[key]
            for key in ["id", "task_id", "question_id", "text", "version", "updated_at"]
        }
        output["note"]["kind"] = "student_self_report"
    return output


def audit_note(db, task, note, operation):
    evidence = {
        key: note[key]
        for key in ["task_id", "question_id", "version", "input_fingerprint"]
    }
    evidence.update(
        note_id=note["id"],
        operation=operation,
        scope="student_self_report",
        student_confirmed=True,
    )
    rid = insert(
        db,
        "agent_runs",
        session_id=task.get("session_id"),
        agent_name="student_self_check",
        status="completed",
        result=evidence,
    )
    insert(
        db,
        "agent_tool_calls",
        agent_run_id=rid,
        tool_name="save_self_check",
        input_json=evidence,
        output_json=evidence,
    )


@router.get("/{id}/self-check")
@router.patch("/{id}/self-check")
@router.delete("/{id}/self-check")
async def self_check_route(request: Request, id: str):
    value = {} if request.method == "GET" else await body(request)
    return envelope(request, await run_in_threadpool(self_check, request, id, value))


def self_check(request, id, value):
    method = request.method
    if method != "GET":
        strict(
            value,
            ["version"]
            if method == "DELETE"
            else ["text", "version", "confirmed", "input_fingerprint"],
        )
    service = request.app.state.questions
    with service.database.session() as db, db.begin():
        owner = task_owner(service, request, db)
        initial = task_row(db, id, owner)
        snapshot = load_snapshot(db, initial["question_id"], owner)
        task = task_row(db, id, owner, lock=True)
        current = validate_version(db, task, snapshot)
        can_save = current and task["status"] == "completed"
        note = self_check_row(db, task)
        version = note.get("version", 0)
        if method == "GET":
            return self_check_public(note, current, can_save)
        supplied = value.get("version")
        if type(supplied) is not int or supplied < 0:
            raise ApiError(422, "请提供要点版本")
        if method == "DELETE" and (not note or note.get("deleted") is True):
            return self_check_public(note, current, can_save)
        text = ""
        if method == "PATCH":
            if not can_save:
                raise ApiError(409, "请完成当前题目版本的学习，再保存自检要点")
            if value.get("confirmed") is not True:
                raise ApiError(422, "请先确认这是你要保存的自检要点")
            if field(value, "input_fingerprint", 64) != task["input_fingerprint"]:
                raise ApiError(409, "原题版本已变化，请重新核对")
            text = field(value, "text", 300)
            if note and note.get("deleted") is not True and note["text"] == text:
                return self_check_public(note, current, can_save)
        if supplied != version:
            raise ApiError(409, "自检要点已在别处更新，请重新读取后再保存")
        if not note:
            insert(
                db,
                "learning_self_checks",
                user_id=owner,
                question_id=task["question_id"],
                task_id=id,
                input_fingerprint=task["input_fingerprint"],
                text=text,
                version=1,
                deleted=False,
            )
        else:
            update(
                db,
                "learning_self_checks",
                note["id"],
                text=text,
                deleted=method == "DELETE",
                version=version + 1,
            )
        saved = self_check_row(db, task)
        audit_note(
            db,
            task,
            saved,
            "delete" if method == "DELETE" else "create" if version == 0 else "edit",
        )
        return self_check_public(saved, current, can_save)


def source_public(db, id):
    records = select_rows(
        db,
        "learning_task_sources",
        "SELECT * FROM learning_task_sources WHERE task_id=?",
        [id],
    )
    if not records:
        return None
    record = records[0]
    question = (record.get("source") or {}).get("question") or {}
    return {
        "snapshot_id": id,
        "origin": record["origin"],
        "captured_at": record["created_at"],
        **{
            key: question.get(key)
            for key in ["subject", "grade", "question_text", "options"]
        },
    }


@router.get("/{id}/history")
def history(request: Request, id: str):
    service = request.app.state.questions
    with service.database.session() as db:
        task = task_row(db, id, task_owner(service, request, db))
        actions = select_rows(
            db,
            "learning_task_actions",
            "SELECT * FROM learning_task_actions WHERE task_id=? ORDER BY created_at DESC,id DESC LIMIT 51",
            [id],
        )
        items = []
        for action in actions[:50]:
            result, event = action.get("result") or {}, action.get("body") or {}
            attempt = result.get("attempt") or {}
            item = {key: action[key] for key in ["id", "kind", "status", "created_at"]}
            item.update(
                text=event.get("text") or "",
                feedback=(result.get("student_view") or {}).get("feedback") or "",
                phase=attempt.get("phase") or "",
                verdict=attempt.get("verdict") or "",
                assisted=attempt.get("assisted") is True,
                source=attempt.get("source"),
                visualization=None,
                handwriting_image_url="",
            )
            visual = (result.get("checkpoint") or {}).get("visualization") or {}
            if (
                action["kind"]
                in ["visualize", "observe_visualization", "close_visualization"]
                and visual
            ):
                spec = visual.get("spec") or {}
                controls = "".join(
                    (variable.get("label") or "")
                    + "："
                    + stamp_compact(
                        (visual.get("values") or {}).get(variable.get("name"))
                    )
                    + "；"
                    for variable in spec.get("interactive_variables") or []
                )
                item.update(
                    visualization={
                        "title": spec.get("title"),
                        "relation_tex": visual.get("current_equation_tex"),
                        "controls": controls,
                    },
                    phase=visual.get("source_phase"),
                    assisted=True,
                )
            image_id = event.get("handwriting_id") or ""
            if image_id:
                images = select_rows(
                    db,
                    "learning_task_images",
                    "SELECT * FROM learning_task_images WHERE id=? AND task_id=? AND input_fingerprint=?",
                    [image_id, id, task["input_fingerprint"]],
                )
                if not images:
                    raise ApiError(422, "这张作答照片不属于当前任务版本")
                item["handwriting_image_url"] = service.media.url(
                    "/" + images[0]["original_path"]
                )
            items.append(item)
        return envelope(
            request,
            {
                "items": items,
                "has_more": len(actions) > 50,
                "source_question": source_public(db, id),
            },
        )
