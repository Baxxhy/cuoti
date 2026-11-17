"""Search-only review projections and the student's saved review ranges."""

import re
from uuid import uuid4

from fastapi import APIRouter, Request
from starlette.concurrency import run_in_threadpool

from .protocol import ApiError, envelope
from .question_data import execute, rows, serialize
from .question_routes import body
from .question_validation import text_value

router = APIRouter(prefix="/api/v1/reviews")
DAY = "TIMESTAMPADD(HOUR,16,DATE(TIMESTAMPADD(HOUR,8,UTC_TIMESTAMP())))"


@router.get("/search")
def search(request: Request):
    values = request.query_params
    query, subject = values.get("q", "").strip(), values.get("subject", "")
    scope = values.get("scope", "") or "pending"
    raw_page = values.get("page", "") or "1"
    if (
        len(query.encode()) > 300
        or len(subject.encode()) > 100
        or scope not in ["pending", "today", "completed"]
    ):
        raise ApiError(422, "复习筛选条件无效")
    if not re.fullmatch(r"[+-]?[0-9]+", raw_page) or not 1 <= int(raw_page) <= 10000:
        raise ApiError(422, "页码无效")
    page = int(raw_page)
    service = request.app.state.questions
    with service.database.session() as db:
        owner = service.user(request, db).id
        criteria = " FROM review_plans p JOIN questions q ON q.id=p.question_id AND q.user_id=p.user_id WHERE p.user_id=? AND q.status<>'archived'"
        params = [owner]
        criteria += (
            " AND p.status='completed'"
            if scope == "completed"
            else " AND p.status='pending'"
        )
        if scope == "today":
            criteria += " AND p.due_at<" + DAY
        if subject:
            criteria += " AND q.subject=?"
            params.append(subject)
        if query:
            criteria += " AND (LOCATE(?,q.question_text)>0 OR LOCATE(?,CAST(q.knowledge_points AS CHAR))>0 OR LOCATE(?,p.reason)>0 OR LOCATE(?,q.title)>0)"
            params.extend([query] * 4)
        total = rows(db, "SELECT COUNT(*) AS total" + criteria, params)[0]["total"]
        sql = (
            "SELECT p.id,p.question_id,p.due_at,p.reason,p.status,q.subject,q.grade,q.title,q.question_text,q.knowledge_points,(p.due_at<"
            + DAY
            + ") AS is_due"
            + criteria
            + " ORDER BY p.due_at "
            + ("DESC" if scope == "completed" else "ASC")
            + ",p.id LIMIT 20 OFFSET "
            + str((page - 1) * 20)
        )
        items = []
        for raw in rows(db, sql, params):
            item = serialize("questions", raw)
            item.update(title=raw["title"], is_due=raw["is_due"] == 1)
            items.append(item)
        return envelope(
            request,
            {"items": items, "total": int(total), "page": page, "page_size": 20},
        )


def saved_rows(db, owner):
    return [
        {
            "id": row["id"],
            "name": row["name"],
            "subject": row["subject"],
            "scope": row["scope"],
            "q": row["query_text"],
        }
        for row in rows(
            db,
            "SELECT * FROM saved_review_filters WHERE user_id=? ORDER BY created_at DESC,id DESC",
            [owner],
        )
    ]


@router.get("/filters")
def listing(request: Request):
    service = request.app.state.questions
    with service.database.session() as db:
        return envelope(request, saved_rows(db, service.user(request, db).id))


@router.post("/filters")
async def create_route(request: Request):
    return envelope(
        request, await run_in_threadpool(create, request, await body(request))
    )


def create(request, value):
    name = text_value(value.get("name", ""), 80).strip()
    query = text_value(value.get("q", ""), 300).strip()
    subject = text_value(value.get("subject", ""), 30)
    scope = text_value(value.get("scope", "pending"), 20)
    if not name or scope not in ["pending", "today", "completed"]:
        raise ApiError(422, "请填写名称并选择有效的复习范围")
    service = request.app.state.questions
    with service.database.session() as db, db.begin():
        owner = service.user(request, db).id
        execute(db, "SELECT id FROM users WHERE id=? FOR UPDATE", [owner])
        existing = rows(
            db,
            "SELECT id FROM saved_review_filters WHERE user_id=? AND name=? AND query_text=? AND subject=? AND scope=?",
            [owner, name, query, subject, scope],
        )
        if not existing:
            if (
                rows(
                    db,
                    "SELECT COUNT(*) AS total FROM saved_review_filters WHERE user_id=?",
                    [owner],
                )[0]["total"]
                >= 20
            ):
                raise ApiError(409, "最多保存20个复习范围，请先移除不再使用的范围")
            execute(
                db,
                "INSERT INTO saved_review_filters (id,user_id,name,query_text,subject,scope,created_at) VALUES (?,?,?,?,?,?,UTC_TIMESTAMP(6))",
                [str(uuid4()), owner, name, query, subject, scope],
            )
        return saved_rows(db, owner)


@router.delete("/filters/{id}")
def delete(request: Request, id: str):
    service = request.app.state.questions
    with service.database.session() as db, db.begin():
        owner = service.user(request, db).id
        if not rows(
            db,
            "SELECT id FROM saved_review_filters WHERE id=? AND user_id=?",
            [id, owner],
        ):
            raise ApiError(404, "复习范围不存在")
        execute(
            db, "DELETE FROM saved_review_filters WHERE id=? AND user_id=?", [id, owner]
        )
        return envelope(request, {"deleted": True})
