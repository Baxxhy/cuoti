"""Source-versioned knowledge lessons using the existing compute handler."""

import hashlib
import json
from uuid import uuid4

from fastapi import APIRouter, Request
from starlette.concurrency import run_in_threadpool

from .protocol import ApiError, envelope
from .question_data import execute, rows, select_rows
from .question_routes import body
from .question_validation import text_value

router = APIRouter(prefix="/api/v1/knowledge/cards")


def compact(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def source_version(cards):
    return digest(
        compact(
            [
                [
                    card.get(key)
                    for key in [
                        "code",
                        "name",
                        "subject",
                        "content",
                        "retrieval_role",
                        "anchor_code",
                    ]
                ]
                for card in cards
            ]
        )
    )


def version_matches(record, cards, prompt):
    suffix = ":" + digest(prompt)
    return record["input_fingerprint"] in [
        source_version(cards) + suffix,
        digest(compact(cards)) + suffix,
    ]


def lesson_cards(db, code):
    anchors = select_rows(
        db, "knowledge_points", "SELECT * FROM knowledge_points WHERE code=?", [code]
    )
    if not anchors:
        raise ApiError(404, "知识卡不存在")
    anchor = anchors[0]
    dependencies = select_rows(
        db,
        "knowledge_points",
        "SELECT k.* FROM knowledge_relations r JOIN knowledge_points k ON k.id=r.target_id WHERE r.source_id=? AND r.relation_type='prerequisite' AND k.subject=? ORDER BY k.code LIMIT 3",
        [anchor["id"], anchor["subject"]],
    )
    return [
        anchor,
        *[
            {**card, "retrieval_role": "prerequisite", "anchor_code": code}
            for card in dependencies
        ],
    ]


def record_rows(db, sql, params):
    # This table has no updated_at; use its original projection and timestamp text.
    records = rows(db, sql, params)
    for record in records:
        if isinstance(record.get("result"), str):
            record["result"] = json.loads(record["result"])
    return records


def lesson_row(value):
    return {
        key: value[key]
        for key in ["id", "knowledge_code", "prompt", "created_at", "result"]
    }


SELECT = "SELECT *,CAST(created_at AS CHAR) AS created_at FROM knowledge_lessons"


@router.get("/{code}/lessons")
def history(request: Request, code: str):
    service = request.app.state.questions
    with service.database.session() as db, db.begin():
        owner = service.user(request, db).id
        cards = lesson_cards(db, code)
        records = record_rows(
            db,
            SELECT
            + " WHERE user_id=? AND knowledge_code=? ORDER BY created_at DESC,id DESC LIMIT 10",
            [owner, code],
        )
        return envelope(
            request,
            [
                {
                    **lesson_row(record),
                    "source_current": version_matches(record, cards, record["prompt"]),
                }
                for record in records
            ],
        )


@router.post("/{code}/lessons")
async def explain_route(request: Request, code: str):
    value = await body(request, maximum=1024 * 1024)
    return envelope(request, await run_in_threadpool(explain, request, code, value))


def explain(request, code, value):
    prompt = text_value(value.get("prompt", ""), 800, trim=True)
    request_id = text_value(value.get("request_id", ""), 80, trim=True)
    if not request_id:
        raise ApiError(422, "缺少请求编号")
    service = request.app.state.questions
    with service.database.session() as db, db.begin():
        owner = service.user(request, db).id
        cards = lesson_cards(db, code)
        version = source_version(cards)
        fingerprint = version + ":" + digest(prompt)
        previous = record_rows(
            db, SELECT + " WHERE user_id=? AND request_id=?", [owner, request_id]
        )
        if previous:
            if previous[0]["knowledge_code"] != code or not version_matches(
                previous[0], cards, prompt
            ):
                raise ApiError(409, "这次提问或知识内容已变化，请重新提问")
            return lesson_row(previous[0])
        recent = record_rows(
            db,
            SELECT
            + " WHERE user_id=? AND knowledge_code=? AND (input_fingerprint LIKE ? OR input_fingerprint LIKE ?) ORDER BY created_at DESC,id DESC LIMIT 3",
            [owner, code, version + ":%", digest(compact(cards)) + ":%"],
        )
        turns = [
            {
                "question": record["prompt"],
                "explanation": record["result"].get("explanation", ""),
                "check_question": record["result"].get("check_question", ""),
            }
            for record in reversed(recent)
        ]
    if request.app.state.compute is None:
        raise ApiError(503, "内部算法服务未配置")
    content = cards[0]["content"] if isinstance(cards[0]["content"], dict) else {}
    try:
        result = request.app.state.compute.compute(
            "knowledge_lesson",
            timeout=30,
            subject=cards[0]["subject"],
            grade=content.get("grade", "")
            if isinstance(content.get("grade", ""), str)
            else "",
            text=prompt,
            dialogue_cards=cards,
            knowledge_history=turns,
        )
    except ApiError:
        raise ApiError(
            503, "讲解暂时没有完成，请稍后重试。可以先查看知识卡中的公式和示例。"
        ) from None
    if result.get("can_update_learning") is not False:
        raise ApiError(503, "讲解结果未通过检查")
    with service.database.session() as db, db.begin():
        latest = lesson_cards(db, code)
        if source_version(latest) != version:
            raise ApiError(409, "知识内容刚刚更新，请重新提问")
        execute(
            db,
            "INSERT INTO knowledge_lessons (id,user_id,knowledge_code,request_id,input_fingerprint,prompt,result,created_at) VALUES (?,?,?,?,?,?,?,UTC_TIMESTAMP(6)) ON DUPLICATE KEY UPDATE id=id",
            [
                str(uuid4()),
                owner,
                code,
                request_id,
                fingerprint,
                prompt,
                compact(result),
            ],
        )
        saved = record_rows(
            db,
            SELECT + " WHERE user_id=? AND request_id=? FOR UPDATE",
            [owner, request_id],
        )[0]
        if saved["knowledge_code"] != code or not version_matches(
            saved, latest, prompt
        ):
            raise ApiError(409, "请求编号已用于其他提问")
        return lesson_row(saved)
