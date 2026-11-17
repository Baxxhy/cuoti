"""Student-owned mistake papers, preserving original filters and score contracts."""

import json

from fastapi import APIRouter, Request
from starlette.concurrency import run_in_threadpool

from .cognition_graph import display_key
from .protocol import ApiError, envelope
from .question_data import execute, insert, rows, select_rows, update
from .question_routes import body
from .question_validation import boolean, number, text_value
from .retrieval import answer_text

router = APIRouter(prefix="/api/v1/papers")


def integer(value, low, high):
    value = number(value)
    if not low <= value <= high or not value.is_integer():
        raise ApiError(422, "整数超出允许范围")
    return int(value)


def filters(value):
    if not isinstance(value, dict):
        raise ApiError(422, "筛选条件格式不正确")
    result = {
        key: text_value(value[key], maximum)
        for key, maximum in [
            ("subject", 30),
            ("knowledge_point", 100),
            ("error_type", 100),
        ]
        if key in value
    }
    low, high = number(value.get("mastery_min", 0)), number(value.get("mastery_max", 1))
    if low < 0 or high > 1 or low > high:
        raise ApiError(422, "掌握度范围无效")
    for key, amount in [("mastery_min", low), ("mastery_max", high)]:
        if key in value:
            result[key] = amount
    if "due_review" in value:
        result["due_review"] = boolean(value["due_review"])
    return result


def payload(value, creating):
    result = {}
    if "title" in value:
        result["title"] = text_value(value["title"], 255, minimum=1, trim=True)
    if "filters" in value:
        result["filters"] = filters(value["filters"])
    if "items" in value:
        entries = value["items"]
        if not isinstance(entries, list) or any(
            not isinstance(item, dict) for item in entries
        ):
            raise ApiError(422, "试卷题目格式不正确")
        if len(entries) > 200:
            raise ApiError(422, "试卷不能超过 200 题")
        result["items"] = [
            {
                "question_id": text_value(
                    item.get("question_id"), 36, minimum=1, trim=True
                ),
                "score": integer(item.get("score", 10), 1, 100),
            }
            for item in entries
        ]
    if creating:
        result.update(
            limit=integer(value.get("limit", 10), 1, 200),
            default_score=integer(value.get("default_score", 10), 1, 100),
        )
        ids = value.get("question_ids", [])
        if not isinstance(ids, list):
            raise ApiError(422, "题目编号格式不正确")
        if len(ids) > 200:
            raise ApiError(422, "试卷不能超过 200 题")
        result["question_ids"] = [
            text_value(id, 36, minimum=1, trim=True) for id in ids
        ]
    return result


def owned(db, id, owner):
    found = select_rows(
        db, "papers", "SELECT * FROM papers WHERE id=? AND user_id=?", [id, owner]
    )
    if not found:
        raise ApiError(404, "试卷不存在或无权访问")
    return found[0]


def question(db, id, owner):
    found = select_rows(
        db, "questions", "SELECT * FROM questions WHERE id=? AND user_id=?", [id, owner]
    )
    if not found:
        raise ApiError(404, "题目不存在或无权访问")
    return found[0]


def analysis_ready(db, id):
    found = rows(
        db,
        "SELECT id,final_answer FROM problem_analyses WHERE question_id=? ORDER BY created_at DESC,id DESC LIMIT 1",
        [id],
    )
    return bool(
        found
        and found[0]["final_answer"].strip()
        and any(
            row["text"].strip()
            for row in rows(
                db,
                "SELECT text FROM reference_steps WHERE analysis_id=? ORDER BY step_index,id",
                [found[0]["id"]],
            )
        )
    )


def detail(service, db, paper):
    items = select_rows(
        db,
        "paper_items",
        "SELECT * FROM paper_items WHERE paper_id=? ORDER BY position,id",
        [paper["id"]],
    )
    for item in items:
        item.update(
            question=question(db, item["question_id"], paper["user_id"]),
            analysis_ready=analysis_ready(db, item["question_id"]),
        )
    exports = select_rows(
        db,
        "export_jobs",
        "SELECT * FROM export_jobs WHERE paper_id=? ORDER BY created_at DESC,id DESC",
        [paper["id"]],
    )
    for job in exports:
        job["url"] = service.media.url("/" + job["path"])
    return {**paper, "items": items, "exports": exports}


def candidates(db, owner, selected):
    sql, params = (
        "SELECT * FROM questions WHERE user_id=? AND status<>'archived'",
        [owner],
    )
    if selected.get("subject"):
        sql += " AND subject=?"
        params.append(selected["subject"])
    result, seen = [], set()
    for q in select_rows(
        db, "questions", sql + " ORDER BY created_at DESC,id DESC", params
    ):
        id = q["id"]
        key = display_key(q["question_text"], id)
        if key in seen:
            continue
        seen.add(key)
        analyses = select_rows(
            db,
            "problem_analyses",
            "SELECT * FROM problem_analyses WHERE question_id=? ORDER BY created_at,id LIMIT 1",
            [id],
        )
        points = q.get("knowledge_points") or (
            analyses[0]["knowledge_points"] if analyses else []
        )
        diagnoses = select_rows(
            db,
            "diagnoses",
            "SELECT * FROM diagnoses WHERE question_id=? ORDER BY created_at DESC,id DESC LIMIT 1",
            [id],
        )
        diagnosis = diagnoses[0] if diagnoses else {}
        wanted = selected.get("knowledge_point") or ""
        if wanted and not any(wanted in answer_text(point) for point in points):
            continue
        if selected.get("error_type") and selected["error_type"] not in (
            diagnosis.get("error_type") or ""
        ):
            continue
        states = select_rows(
            db,
            "mastery_states",
            "SELECT * FROM mastery_states WHERE user_id=? AND subject=? ORDER BY updated_at DESC,id DESC",
            [owner, q["subject"]],
        )
        score = next(
            (
                state["mastery_score"]
                for state in states
                if state["knowledge_point"] in [answer_text(point) for point in points]
            ),
            0.0,
        )
        if (
            not selected.get("mastery_min", 0)
            <= score
            <= selected.get("mastery_max", 1)
        ):
            continue
        reviews = select_rows(
            db,
            "review_plans",
            "SELECT * FROM review_plans WHERE user_id=? AND question_id=? ORDER BY due_at DESC,id DESC LIMIT 1",
            [owner, id],
        )
        if selected.get("due_review") is True and (
            not reviews or reviews[0]["status"] != "pending"
        ):
            continue
        result.append(
            {
                **q,
                "knowledge_points": points,
                "mastery_score": float(score),
                "error_type": diagnosis.get("error_type") or "未诊断",
                "root_misconception": diagnosis.get("root_misconception") or "",
                "review_due_at": reviews[0]["due_at"] if reviews else None,
            }
        )
    return result


@router.get("/candidates")
def candidate_route(request: Request):
    raw = {
        key: request.query_params[key]
        for key in ["subject", "knowledge_point", "error_type", "due_review"]
        if request.query_params.get(key)
    }
    for key in ["mastery_min", "mastery_max"]:
        if request.query_params.get(key):
            try:
                raw[key] = json.loads(request.query_params[key])
            except ValueError:
                raise ApiError(422, "掌握度范围无效") from None
    selected = filters(raw)
    service = request.app.state.questions
    with service.database.session() as db:
        return envelope(request, candidates(db, service.user(request, db).id, selected))


@router.get("")
def listing(request: Request):
    service = request.app.state.questions
    with service.database.session() as db:
        return envelope(
            request,
            select_rows(
                db,
                "papers",
                "SELECT * FROM papers WHERE user_id=? ORDER BY created_at,id",
                [service.user(request, db).id],
            ),
        )


def insert_items(db, id, owner, items):
    for position, item in enumerate(items):
        question(db, item["question_id"], owner)
        insert(
            db,
            "paper_items",
            timestamp_microseconds=False,
            paper_id=id,
            question_id=item["question_id"],
            position=position,
            score=item["score"],
        )


@router.post("")
async def create_route(request: Request):
    return envelope(
        request, await run_in_threadpool(create, request, await body(request))
    )


def create(request, raw):
    value = payload(raw, True)
    service = request.app.state.questions
    with service.database.session() as db, db.begin():
        owner = service.user(request, db).id
        selected = value.get("filters") or {}
        ids = value["question_ids"] or [
            item["id"] for item in candidates(db, owner, selected)[: value["limit"]]
        ]
        items = [
            {
                "question_id": id,
                "score": next(
                    (
                        item["score"]
                        for item in reversed(value.get("items") or [])
                        if item["question_id"] == id
                    ),
                    value["default_score"],
                ),
            }
            for id in ids
        ]
        id = insert(
            db,
            "papers",
            timestamp_microseconds=False,
            user_id=owner,
            title=value.get("title", "我的错题练习"),
            filters=selected,
        )
        insert_items(db, id, owner, items)
        return owned(db, id, owner)


@router.get("/{id}")
def read(request: Request, id: str):
    service = request.app.state.questions
    with service.database.session() as db:
        return envelope(
            request, detail(service, db, owned(db, id, service.user(request, db).id))
        )


@router.patch("/{id}")
async def patch_route(request: Request, id: str):
    return envelope(
        request, await run_in_threadpool(patch, request, id, await body(request))
    )


def patch(request, id, raw):
    value = payload(raw, False)
    service = request.app.state.questions
    with service.database.session() as db, db.begin():
        owner = service.user(request, db).id
        owned(db, id, owner)
        for key in ["title", "filters"]:
            if key in value:
                update(
                    db, "papers", id, timestamp_microseconds=False, **{key: value[key]}
                )
        if "items" in value:
            execute(db, "DELETE FROM paper_items WHERE paper_id=?", [id])
            insert_items(db, id, owner, value["items"])
        return detail(service, db, owned(db, id, owner))


@router.delete("/{id}")
def delete(request: Request, id: str):
    service = request.app.state.questions
    with service.database.session() as db, db.begin():
        owner = service.user(request, db).id
        if not rows(db, "SELECT id FROM papers WHERE id=? AND user_id=?", [id, owner]):
            return envelope(request, {"deleted": False})
        for table in ["export_jobs", "paper_items"]:
            execute(db, f"DELETE FROM {table} WHERE paper_id=?", [id])
        execute(db, "DELETE FROM papers WHERE id=?", [id])
        return envelope(request, {"deleted": True})
