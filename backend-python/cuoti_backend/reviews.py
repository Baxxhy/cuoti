"""Review answers and difficulty feedback, using the existing two-step contract."""

from fastapi import APIRouter, Request
from starlette.concurrency import run_in_threadpool

from .learning_evidence import question_version, stamp_compact
from .lessons import digest
from .protocol import ApiError, envelope
from .question_data import execute, insert, rows, select_rows, update
from .question_routes import body
from .question_validation import text_value
from .tutor_answers import handwriting

router = APIRouter(prefix="/api/v1/reviews")


def question(db, plan, owner):
    found = select_rows(
        db,
        "questions",
        "SELECT * FROM questions WHERE id=? AND user_id=?",
        [plan["question_id"], owner],
    )
    if not found:
        raise ApiError(404, "题目不存在")
    return found[0]


def refresh(media, record):
    details = record.get("grading_details") or {}
    path = (details.get("handwriting_image_url") or "").split("?", 1)[0]
    if path:
        details["handwriting_image_url"] = media.url(path)
    return record


def receipt(media, record):
    details = record.get("grading_details") or {}
    return {
        "attempt_id": record["id"],
        "request_id": details.get("review_request_id") or "",
        "correct": record["correct"]
        if details.get("can_update_learning") is True
        else None,
        **{
            key: details.get(key)
            for key in ["score", "feedback", "matched_points", "can_update_learning"]
        },
        "grading": {
            key: details.get(key)
            for key in [
                "verdict",
                "correct",
                "score",
                "feedback",
                "matched_points",
                "can_update_learning",
            ]
        },
        "expected_answer": record["expected_answer"],
        "student_answer": record["student_answer"],
        "handwriting_image_url": media.url(
            (details.get("handwriting_image_url") or "").split("?", 1)[0]
        ),
        "handwriting_recognition": details.get("handwriting_recognition"),
    }


@router.get("/today")
def today(request: Request):
    service = request.app.state.questions
    with service.database.session() as db:
        owner = service.user(request, db).id
        plans = select_rows(
            db,
            "review_plans",
            "SELECT * FROM review_plans WHERE user_id=? AND status='pending' AND due_at<TIMESTAMPADD(HOUR,16,DATE(TIMESTAMPADD(HOUR,8,UTC_TIMESTAMP()))) ORDER BY due_at,id",
            [owner],
        )
        seen, result = set(), []
        for plan in plans:
            q = question(db, plan, owner)
            if q["status"] == "archived":
                continue
            text = "".join(char for char in q["question_text"] if not char.isspace())
            key = (
                "".join(char for char in text if char not in "，。？?：:").lower()
                if text
                else "pending:" + q["id"]
            )
            if key in seen:
                continue
            seen.add(key)
            visible = {
                key: value for key, value in q.items() if key != "student_answer"
            }
            figures = select_rows(
                db,
                "question_assets",
                "SELECT * FROM question_assets WHERE question_id=? AND kind='question_figure' ORDER BY created_at,id",
                [q["id"]],
            )
            for figure in figures:
                figure["url"] = service.media.url("/" + figure["path"])
            visible["question_figures"] = figures
            version = question_version(db, q)
            plan.update(question=visible, source_version=version, pending_attempt=None)
            pending = select_rows(
                db,
                "review_records",
                "SELECT * FROM review_records WHERE plan_id=? AND grade='pending' AND COALESCE(JSON_UNQUOTE(JSON_EXTRACT(grading_details,'$.review_record_state')),'current')<>'superseded' ORDER BY created_at DESC,id DESC LIMIT 1",
                [plan["id"]],
            )
            if (
                pending
                and (pending[0].get("grading_details") or {}).get(
                    "memory_question_version"
                )
                == version
            ):
                plan["pending_attempt"] = receipt(service.media, pending[0])
            if "again" in (plan.get("reason") or "").lower():
                plan["reason"] = "本次作答需要重做，安排 1 天后再次复习"
            result.append(plan)
        return envelope(request, result)


@router.get("/history")
def history(request: Request):
    service = request.app.state.questions
    with service.database.session() as db:
        owner = service.user(request, db).id
        records = select_rows(
            db,
            "review_records",
            "SELECT r.* FROM review_records r JOIN review_plans p ON p.id=r.plan_id WHERE p.user_id=? AND r.grade<>'pending' ORDER BY r.created_at DESC,r.id DESC",
            [owner],
        )
        for record in records:
            plan = select_rows(
                db,
                "review_plans",
                "SELECT * FROM review_plans WHERE id=?",
                [record["plan_id"]],
            )[0]
            found = select_rows(
                db,
                "questions",
                "SELECT * FROM questions WHERE id=? AND user_id=?",
                [plan["question_id"], owner],
            )
            record.update(plan=plan, question=found[0] if found else None)
            refresh(service.media, record)
        return envelope(request, records)


@router.post("/{id}/attempt")
async def attempt_route(request: Request, id: str):
    return envelope(
        request, await run_in_threadpool(attempt, request, id, await body(request))
    )


def attempt(request, id, value):
    answer = text_value(value.get("answer", ""), 12000, trim=True)
    service = request.app.state.questions
    with service.database.session() as db, db.begin():
        owner = service.user(request, db).id
        plans = select_rows(
            db,
            "review_plans",
            "SELECT * FROM review_plans WHERE id=? AND user_id=? AND status='pending' FOR UPDATE",
            [id, owner],
        )
        if not plans:
            raise ApiError(404, "待复习题不存在")
        plan = plans[0]
        q = question(db, plan, owner)
        if q["status"] == "archived":
            raise ApiError(409, "题目已归档")
        version = question_version(db, q)
        supplied = (
            value.get("source_version")
            if isinstance(value.get("source_version"), str)
            else ""
        )
        if supplied and supplied != version:
            raise ApiError(409, "原题或参考已更新，请刷新后核对答案")
        rid = (
            text_value(value["request_id"], 80, minimum=1, trim=True)
            if "request_id" in value
            else ""
        )
        hashed = digest(
            stamp_compact(
                [
                    value.get(key)
                    for key in [
                        "answer",
                        "handwriting_image_url",
                        "handwriting_recognition",
                    ]
                ]
            )
        )
        if rid:
            previous = select_rows(
                db,
                "review_records",
                "SELECT * FROM review_records WHERE plan_id=? AND JSON_UNQUOTE(JSON_EXTRACT(grading_details,'$.review_request_id'))=? LIMIT 1",
                [id, rid],
            )
            if previous:
                record = previous[0]
                details = record.get("grading_details") or {}
                if details.get("review_record_state") == "superseded":
                    raise ApiError(409, "已有更新的复习作答，请刷新查看当前判题")
                if (
                    details.get("review_request_digest") != hashed
                    or details.get("memory_question_version") != version
                ):
                    raise ApiError(
                        409, "提交编号对应的作答或原题已变化，请核对后重新提交"
                    )
                return receipt(service.media, record)
        analyses = select_rows(
            db,
            "problem_analyses",
            "SELECT * FROM problem_analyses WHERE question_id=? ORDER BY created_at,id LIMIT 1",
            [q["id"]],
        )
        if not analyses or not analyses[0]["final_answer"]:
            raise ApiError(422, "这道题还没有标准答案，请先在题目详情中完成分析")
        analysis = analyses[0]
        photo = handwriting(service, value, owner, id, kind="review")
        references = rows(
            db,
            "SELECT text FROM reference_steps WHERE analysis_id=? ORDER BY step_index",
            [analysis["id"]],
        )
        if service.compute is None:
            raise ApiError(503, "内部算法服务未配置")
        grading = service.compute.compute(
            "grade_answer",
            text=q["question_text"],
            answer=answer,
            expected=analysis["final_answer"],
            subject=q["subject"],
            question_type=q["question_type"],
            options=q["options"],
            reference_solution=[item["text"] for item in references],
        )
        details = {
            **grading,
            "memory_question_version": version,
            "review_request_id": rid,
            "review_request_digest": hashed,
            "handwriting_image_url": photo["image_url"],
            "handwriting_recognition": photo["recognition"],
        }
        execute(
            db,
            "UPDATE review_records SET grading_details=JSON_SET(grading_details,'$.review_record_state','superseded') WHERE plan_id=? AND grade='pending'",
            [id],
        )
        aid = insert(
            db,
            "review_records",
            timestamp_microseconds=False,
            plan_id=id,
            grade="pending",
            correct=grading["correct"],
            student_answer=answer,
            expected_answer=analysis["final_answer"],
            feedback=grading["feedback"],
            score=grading["score"],
            grading_details=details,
        )
        return receipt(
            service.media,
            select_rows(
                db, "review_records", "SELECT * FROM review_records WHERE id=?", [aid]
            )[0],
        )


@router.post("/{id}/grade")
async def grade_route(request: Request, id: str):
    return envelope(
        request, await run_in_threadpool(grade, request, id, await body(request))
    )


def grade(request, id, value):
    service = request.app.state.questions
    with service.database.session() as db, db.begin():
        owner = service.user(request, db).id
        plans = select_rows(
            db,
            "review_plans",
            "SELECT * FROM review_plans WHERE id=? AND user_id=? FOR UPDATE",
            [id, owner],
        )
        if not plans:
            raise ApiError(404, "复习计划不存在")
        plan = plans[0]
        if plan["status"] != "pending":
            raise ApiError(409, "这次复习已完成，请刷新复习列表")
        aid = (
            value.get("attempt_id") if isinstance(value.get("attempt_id"), str) else ""
        )
        records = select_rows(
            db,
            "review_records",
            "SELECT * FROM review_records WHERE id=? AND plan_id=? AND grade='pending'",
            [aid, id],
        )
        if not records:
            raise ApiError(422, "请先提交答案并完成系统判定")
        record = records[0]
        details = record.get("grading_details") or {}
        if details.get("review_record_state") == "superseded":
            raise ApiError(409, "已有更新的复习作答，请刷新查看当前判题")
        if details.get("can_update_learning", True) is not True:
            raise ApiError(409, "这次判题仍需核对，不能据此更新复习计划")
        q = question(db, plan, owner)
        version = details.get("memory_question_version") or ""
        if q["status"] == "archived" or version and version != question_version(db, q):
            raise ApiError(409, "原题或参考已更新，请重新提交作答再评价复习")
        chosen = value.get("grade", "good")
        correct = record["correct"] is True
        if chosen not in ["again", "hard", "good", "easy"]:
            raise ApiError(422, "请选择有效的复习反馈")
        days, label = {
            "again": (1, "还没想起来"),
            "hard": (2 if correct else 1, "有点困难"),
            "good": (7 if correct else 2, "已经掌握"),
            "easy": (15 if correct else 4, "很轻松"),
        }[chosen]
        update(db, "review_plans", id, timestamp_microseconds=False, status="completed")
        update(db, "review_records", aid, timestamp_microseconds=False, grade=chosen)
        from uuid import uuid4

        next_id = str(uuid4())
        execute(
            db,
            "INSERT INTO review_plans (id,user_id,question_id,due_at,interval_days,reason,status,created_at,updated_at) VALUES (?,?,?,TIMESTAMPADD(DAY,?,UTC_TIMESTAMP()),?,?,'pending',UTC_TIMESTAMP(),UTC_TIMESTAMP())",
            [
                next_id,
                owner,
                q["id"],
                days,
                days,
                "上次作答"
                + ("正确" if correct else "有误")
                + "，随后选择了“"
                + label
                + "”",
            ],
        )
        saved = select_rows(
            db, "review_records", "SELECT * FROM review_records WHERE id=?", [aid]
        )[0]
        return {
            "record": refresh(service.media, saved),
            "next_plan": select_rows(
                db, "review_plans", "SELECT * FROM review_plans WHERE id=?", [next_id]
            )[0],
        }
