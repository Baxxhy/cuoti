"""Snapshot-based practice/exam sessions and bounded grading outside transactions."""

import json
from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, Request
from starlette.concurrency import run_in_threadpool

from .dataset_images import layout, solution_images
from .learning_tasks import task_row
from .lessons import compact
from .protocol import ApiError, envelope
from .question_data import execute, rows, select_rows
from .question_routes import body
from .question_validation import text_value
from .retrieval import usable
from .study_bank import filters, public, scoped_where, student_grade
from .task_sources import load_snapshot, validate_version

router = APIRouter(prefix="/api/v1/study-sessions")


def integer(value, minimum, maximum):
    if type(value) is not int:
        raise ApiError(422, "请填写整数")
    if not minimum <= value <= maximum:
        raise ApiError(422, "整数超出允许范围")
    return value


def session_row(row):
    value = dict(row)
    for key, item in value.items():
        if (
            key
            in [
                "version",
                "duration_seconds",
                "remaining_seconds",
                "question_count",
                "expired",
            ]
            and item is not None
        ):
            value[key] = int(item)
        elif key == "results" and isinstance(item, str):
            value[key] = json.loads(item)
        elif isinstance(item, datetime):
            value[key] = item.strftime("%Y-%m-%d %H:%M:%S.%f")
    return value


def owned(db, id, owner, lock=False):
    found = rows(
        db,
        "SELECT *,CEIL(GREATEST(0,COALESCE(TIMESTAMPDIFF(MICROSECOND,UTC_TIMESTAMP(6),deadline_at),0))/1000000) AS remaining_seconds,IF(deadline_at IS NOT NULL AND deadline_at<=UTC_TIMESTAMP(6),1,0) AS expired FROM study_sessions WHERE id=? AND user_id=?"
        + (" FOR UPDATE" if lock else ""),
        [id, owner],
    )
    if not found:
        raise ApiError(404, "没有找到这次练习或考试")
    return session_row(found[0])


def items(db, id):
    return [
        {
            "id": row["id"],
            "position": int(row["position"]),
            **{
                key: json.loads(row[key]) if isinstance(row[key], str) else row[key]
                for key in ["snapshot", "student_answer", "grading"]
            },
        }
        for row in rows(
            db,
            "SELECT * FROM study_session_items WHERE session_id=? ORDER BY position",
            [id],
        )
    ]


def available(db, snapshot, lock=False):
    if layout(snapshot)["review"] or snapshot["quality_status"] == "format_review":
        return False
    found = rows(
        db,
        "SELECT quality_status,source_metadata FROM dataset_questions WHERE id=?"
        + (" FOR SHARE" if lock else ""),
        [snapshot["id"]],
    )
    if not found:
        return True
    current = found[0]
    if current["quality_status"] == "format_review":
        return False
    metadata = (
        json.loads(current["source_metadata"])
        if isinstance(current["source_metadata"], str)
        else current["source_metadata"]
    )
    return not any(
        entry.get("content_hash") == snapshot["content_hash"]
        for entry in metadata.get("format_review_history") or []
    )


def detail(service, db, session):
    shown = []
    submitted = session["status"] == "submitted"
    for item in items(db, session["id"]):
        snapshot = item["snapshot"]
        valid = available(db, snapshot)
        output = {
            "id": item["id"],
            "position": item["position"],
            "student_answer": item["student_answer"],
            "unavailable": not valid,
            "question": public(service.media, snapshot)
            if valid
            else {key: snapshot[key] for key in ["subject", "question_type"]},
        }
        if submitted:
            added = rows(
                db,
                "SELECT id FROM questions WHERE user_id=? AND status<>'archived' AND JSON_CONTAINS(tags,JSON_QUOTE(?)) LIMIT 1",
                [session["user_id"], "study-item:" + item["id"]],
            )
            output.update(
                mistake_id=added[0]["id"] if added else None, grading=item["grading"]
            )
            if valid:
                output.update(
                    answer=snapshot["answer"],
                    solution=snapshot["solution"],
                    **solution_images(service.media, snapshot),
                )
        shown.append(output)
    return {**session, "items": shown, "question_count": len(shown)}


def adaptive(service, db, owner, grade, subject, band, source, search, count):
    candidates = select_rows(
        db,
        "dataset_questions",
        "SELECT q.*" + scoped_where(grade) + " ORDER BY RAND() LIMIT 200",
        filters(grade, subject, band, source, search),
    )
    if len(candidates) < count:
        raise ApiError(422, "当前范围可用题目不足，请减少题数或更换学科")
    keys = [
        "id",
        "subject",
        "grade_band",
        "question_type",
        "knowledge_points",
        "options",
    ]
    observations = []
    history = rows(
        db,
        "SELECT i.snapshot,i.grading FROM study_session_items i JOIN study_sessions s ON s.id=i.session_id JOIN dataset_questions q ON q.id=JSON_UNQUOTE(JSON_EXTRACT(i.snapshot,'$.id')) WHERE s.user_id=? AND s.status='submitted' AND q.usable_for_practice=1 AND q.usable_for_auto_grade=1 AND (?='' OR q.subject=?) ORDER BY s.created_at DESC,i.position DESC LIMIT 400",
        [owner, subject, subject],
    )
    for item in reversed(history):
        grading = (
            json.loads(item["grading"])
            if isinstance(item["grading"], str)
            else item["grading"]
        )
        if (
            not grading
            or grading.get("can_update_learning") is not True
            or type(grading.get("correct")) is not bool
        ):
            continue
        q = (
            json.loads(item["snapshot"])
            if isinstance(item["snapshot"], str)
            else item["snapshot"]
        )
        observations.append(
            {
                **{key: q[key] for key in keys},
                "correct": grading["correct"],
                "confirmed": True,
                "independent": True,
            }
        )
    if service.compute is None:
        raise ApiError(503, "内部算法服务未配置")
    result = service.compute.compute(
        "adaptive_practice",
        adaptive_practice={
            "candidates": [{key: q[key] for key in keys} for q in candidates],
            "observations": observations,
            "count": count,
        },
    )
    ids = result.get("question_ids") or []
    if len(ids) != count:
        raise ApiError(503, "选题未完成，请重试")
    allowed = {q["id"] for q in candidates}
    if any(not isinstance(id, str) or id not in allowed for id in ids) or len(
        set(ids)
    ) != len(ids):
        raise ApiError(503, "选题结果无效，请重试")
    return result


@router.get("")
def listing(request: Request):
    service = request.app.state.questions
    with service.database.session() as db:
        owner = service.user(request, db).id
        return envelope(
            request,
            [
                session_row(row)
                for row in rows(
                    db,
                    "SELECT s.*,(SELECT COUNT(*) FROM study_session_items i WHERE i.session_id=s.id) AS question_count FROM study_sessions s WHERE s.user_id=? ORDER BY s.created_at DESC,s.id DESC LIMIT 50",
                    [owner],
                )
            ],
        )


@router.post("")
async def create_route(request: Request):
    return envelope(
        request, await run_in_threadpool(create, request, await body(request))
    )


def create(request, value):
    service = request.app.state.questions
    with service.database.session() as db:
        owner = service.user(request, db).id
        grade = student_grade(db, owner)
        mode = text_value(value.get("mode", "practice"), 20)
        if mode not in ["practice", "exam"]:
            raise ApiError(422, "请选择练习或模拟考试")
        subject, band, source, search = (
            text_value(value.get(key, ""), limit)
            for key, limit in [
                ("subject", 30),
                ("grade_band", 30),
                ("source_id", 36),
                ("search", 300),
            ]
        )
        count, minutes = (
            integer(value.get("count", 5), 1, 20),
            integer(value.get("minutes", 15), 1, 180),
        )
        ids = value.get("question_ids", [])
        if not isinstance(ids, list):
            raise ApiError(422, "题目编号格式无效")
        if len(ids) > 1:
            raise ApiError(422, "单题练习请选择一道题")
        strategy = text_value(value.get("selection_strategy", "random"), 20)
        if strategy not in ["random", "adaptive"]:
            raise ApiError(422, "选题方式无效")
        selection = (
            adaptive(service, db, owner, grade, subject, band, source, search, count)
            if strategy == "adaptive" and mode == "practice" and not ids
            else {}
        )
    task_id = text_value(value.get("learning_task_id", ""), 36)
    if task_id and (mode != "practice" or len(ids) != 1):
        raise ApiError(422, "请选择本次学习推荐的一道题")
    with service.database.session() as db, db.begin():
        selected_ids = selection.get("question_ids") or []
        criteria, params = (
            scoped_where(grade),
            filters(grade, subject, band, source, search),
        )
        if task_id:
            task = task_row(db, task_id, owner)
            requested = text_value(ids[0], 36, minimum=1, trim=True)
            plan = (task.get("student_view") or {}).get("recommendation") or {}
            if (
                task["status"] != "completed"
                or plan.get("question_source") != "dataset"
                or plan.get("question_id") != requested
            ):
                raise ApiError(409, "请从已完成的学习任务打开推荐题")
            snapshot = load_snapshot(db, task["question_id"], owner)
            if not validate_version(db, task, snapshot):
                raise ApiError(409, "原题已更新，请重新学习后获取推荐")
            candidates = select_rows(
                db,
                "dataset_questions",
                "SELECT * FROM dataset_questions WHERE id=?",
                [requested],
            )
            if not candidates or not usable(
                snapshot["question"], candidates[0], "practice"
            ):
                raise ApiError(409, "推荐题已更新，请重新获取练习")
        elif selected_ids:
            candidates = []
            for id in selected_ids:
                candidates.extend(
                    select_rows(
                        db,
                        "dataset_questions",
                        "SELECT q.*" + criteria + " AND q.id=?",
                        [*params, id],
                    )
                )
        elif ids:
            candidates = select_rows(
                db,
                "dataset_questions",
                "SELECT q.*" + criteria + " AND q.id=?",
                [*params, text_value(ids[0], 36, minimum=1, trim=True)],
            )
        else:
            candidates = select_rows(
                db,
                "dataset_questions",
                "SELECT q.*" + criteria + " ORDER BY RAND() LIMIT " + str(count),
                params,
            )
        if not candidates or not ids and len(candidates) < count:
            raise ApiError(422, "当前范围可用题目不足，请减少题数或更换学科")
        if any(layout(candidate)["review"] for candidate in candidates):
            raise ApiError(422, "题图需要核对，请选择其他题目")
        id = str(uuid4())
        title = (
            ((subject or "综合") + "模拟试卷")
            if mode == "exam"
            else (subject or "题库") + "练习"
        )
        execute(
            db,
            "INSERT INTO study_sessions (id,user_id,mode,title,subject,grade_band,status,duration_seconds,deadline_at,version,created_at,updated_at) VALUES (?,?,?,?,?,?,'active',?,IF(?='exam',TIMESTAMPADD(SECOND,?,UTC_TIMESTAMP(6)),NULL),1,UTC_TIMESTAMP(6),UTC_TIMESTAMP(6))",
            [id, owner, mode, title, subject, band, minutes * 60, mode, minutes * 60],
        )
        for position, candidate in enumerate(candidates):
            names = rows(
                db,
                "SELECT name FROM dataset_sources WHERE id=?",
                [candidate["dataset_source_id"]],
            )
            candidate["source_name"] = names[0]["name"] if names else "题库"
            if selected_ids:
                candidate["adaptive_selection"] = selection
            execute(
                db,
                "INSERT INTO study_session_items (id,session_id,position,snapshot,student_answer,grading) VALUES (?,?,?,?,NULL,NULL)",
                [str(uuid4()), id, position, compact(candidate)],
            )
        return detail(service, db, owned(db, id, owner))


def clean_answer(value):
    if value is None:
        return None
    if isinstance(value, str):
        return text_value(value, 3000)
    if not isinstance(value, list):
        raise ApiError(422, "作答格式无效")
    if len(value) > 12:
        raise ApiError(422, "选项过多")
    clean = [text_value(item, 30, minimum=1, trim=True) for item in value]
    if len(set(clean)) != len(clean):
        raise ApiError(422, "选项不能重复")
    return clean


def answered(value):
    return (
        bool(value.strip())
        if isinstance(value, str)
        else bool(value)
        if isinstance(value, list)
        else False
    )


@router.get("/{id}")
def read(request: Request, id: str):
    service = request.app.state.questions
    with service.database.session() as db:
        return envelope(
            request, detail(service, db, owned(db, id, service.user(request, db).id))
        )


@router.patch("/{id}")
async def save_route(request: Request, id: str):
    return envelope(
        request, await run_in_threadpool(save, request, id, await body(request))
    )


def save(request, id, value):
    version = integer(value.get("version"), 1, 100000000)
    answers = value.get("answers")
    if not isinstance(answers, list):
        raise ApiError(422, "请提交作答列表")
    service = request.app.state.questions
    with service.database.session() as db, db.begin():
        owner = service.user(request, db).id
        session = owned(db, id, owner, True)
        if session["status"] != "active":
            raise ApiError(409, "已经交卷，不能修改作答")
        if session["version"] != version:
            raise ApiError(409, "作答已在其他页面更新，请重新读取")
        if session["mode"] == "exam" and session["expired"] == 1:
            raise ApiError(409, "考试时间已到，请交卷")
        current = items(db, id)
        if len(answers) != len(current):
            raise ApiError(422, "作答题目与试卷不一致")
        allowed, seen = {item["id"] for item in current}, set()
        for answer in answers:
            if not isinstance(answer, dict):
                raise ApiError(422, "作答格式无效")
            aid = text_value(answer.get("id", ""), 36)
            if aid not in allowed or aid in seen:
                raise ApiError(422, "作答题目与试卷不一致")
            seen.add(aid)
            execute(
                db,
                "UPDATE study_session_items SET student_answer=? WHERE id=? AND session_id=?",
                [compact(clean_answer(answer.get("answer"))), aid, id],
            )
        execute(
            db,
            "UPDATE study_sessions SET version=version+1,updated_at=UTC_TIMESTAMP(6) WHERE id=?",
            [id],
        )
        return detail(service, db, owned(db, id, owner))


def unavailable_grade():
    return {
        "correct": None,
        "can_update_learning": False,
        "method": "question_unavailable",
        "feedback": "此题已暂停使用，未计分",
    }


def grade_item(service, item):
    if not answered(item["student_answer"]):
        return {
            "correct": False,
            "can_update_learning": True,
            "feedback": "未作答",
            "method": "unanswered",
        }
    if service.compute is None:
        raise ApiError(503, "内部算法服务未配置")
    question = item["snapshot"]
    return service.compute.compute(
        "grade_answer",
        timeout=20,
        text=question["question_text"],
        answer=item["student_answer"],
        expected=question["answer"],
        subject=question["subject"],
        question_type=question["question_type"],
        options=question["options"],
        reference_solution=[
            line for line in question["solution"].split("\n") if line.strip()
        ],
    )


@router.post("/{id}/submit")
async def submit_route(request: Request, id: str):
    return envelope(
        request, await run_in_threadpool(submit, request, id, await body(request))
    )


def submit(request, id, value):
    from concurrent.futures import ThreadPoolExecutor

    version = integer(value.get("version"), 1, 100000000)
    service = request.app.state.questions
    with service.database.session() as db:
        owner = service.user(request, db).id
        before = owned(db, id, owner)
        if before["status"] == "submitted":
            return detail(service, db, before)
        if before["version"] != version:
            raise ApiError(409, "作答已更新，请重新读取后交卷")
        current = items(db, id)
        blocked = {
            item["id"] for item in current if not available(db, item["snapshot"])
        }
    # Keep batches of four, preserving order and avoiding locks during model calls.
    results = []
    with ThreadPoolExecutor(
        max_workers=4, thread_name_prefix="cuoti-study-grading"
    ) as executor:
        for start in range(0, len(current), 4):
            jobs = [
                executor.submit(unavailable_grade)
                if item["id"] in blocked
                else executor.submit(grade_item, service, item)
                for item in current[start : start + 4]
            ]
            results.extend(job.result() for job in jobs)
    with service.database.session() as db, db.begin():
        session = owned(db, id, owner, True)
        if session["status"] == "submitted":
            return detail(service, db, session)
        if session["version"] != version:
            raise ApiError(409, "作答已更新，本次判分未保存，请重新交卷")
        correct = pending = answered_count = excluded = 0
        for item, result in zip(current, results, strict=True):
            valid = available(db, item["snapshot"], True)
            grading = result if valid else unavailable_grade()
            answered_count += answered(item["student_answer"])
            if not valid:
                excluded += 1
            elif grading.get("can_update_learning") is not True:
                pending += 1
            elif grading.get("correct") is True:
                correct += 1
            execute(
                db,
                "UPDATE study_session_items SET grading=? WHERE id=? AND session_id=?",
                [compact(grading), item["id"], id],
            )
        summary = {
            "correct": correct,
            "pending": pending,
            "answered": answered_count,
            "total": len(current),
            "score": correct * 5,
            "max_score": (len(current) - excluded) * 5,
        }
        if excluded:
            summary["excluded"] = excluded
        execute(
            db,
            "UPDATE study_sessions SET status='submitted',results=?,version=version+1,submitted_at=UTC_TIMESTAMP(6),updated_at=UTC_TIMESTAMP(6) WHERE id=?",
            [compact(summary), id],
        )
        return detail(service, db, owned(db, id, owner))
