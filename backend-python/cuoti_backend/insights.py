"""Read models for the existing knowledge library and student dashboard."""

import re

from fastapi import APIRouter, Request

from .protocol import ApiError, envelope
from .question_data import rows, select_rows

router = APIRouter(prefix="/api/v1")


def mistake_label(value):
    return (
        "移项符号"
        if "移项" in value and ("符号" in value or "变号" in value)
        else value
    )


@router.get("/knowledge/cards")
def cards(request: Request):
    query = request.query_params
    sql, params = "SELECT * FROM knowledge_points WHERE 1=1", []
    if query.get("subject"):
        sql += " AND subject=?"
        params.append(query["subject"])
    words = [
        word for word in re.split(r"[\s，、]+", query.get("q", "")) if len(word) >= 2
    ][:5]
    if words:
        sql += (
            " AND ("
            + " OR ".join(
                "(name LIKE ? OR code LIKE ? OR CAST(content AS CHAR) LIKE ?)"
                for _ in words
            )
            + ")"
        )
        for word in words:
            params.extend(["%" + word + "%"] * 3)
    for key, path in [("grade", "grade"), ("misconception", "common_misconceptions")]:
        if query.get(key):
            sql += f" AND LOCATE(?,JSON_UNQUOTE(JSON_EXTRACT(content,'$.{path}'))) > 0"
            params.append(query[key])
    with request.app.state.database.session() as db:
        result = select_rows(
            db, "knowledge_points", sql + " ORDER BY subject,code LIMIT 50", params
        )
    filtered = []
    for item in result:
        content = item["content"] if isinstance(item["content"], dict) else {}
        if query.get("grade") and query["grade"] not in str(content.get("grade", "")):
            continue
        labels = content.get("common_misconceptions", [])
        if not isinstance(labels, list):
            labels = []
        if query.get("misconception") and query["misconception"] not in " ".join(
            str(v) for v in labels if isinstance(labels, list)
        ):
            continue
        filtered.append(item)
    return envelope(request, filtered)


@router.get("/knowledge/cards/{code}")
def card(request: Request, code: str):
    with request.app.state.database.session() as db, db.begin():
        matches = select_rows(
            db,
            "knowledge_points",
            "SELECT * FROM knowledge_points WHERE code=? OR id=? LIMIT 1",
            [code, code],
        )
        if not matches:
            raise ApiError(404, "知识卡不存在")
        result = matches[0]
        for key, sql in [
            (
                "prerequisites",
                "SELECT k.* FROM knowledge_relations r JOIN knowledge_points k ON k.id=r.target_id WHERE r.source_id=?",
            ),
            (
                "next_knowledge",
                "SELECT k.* FROM knowledge_relations r JOIN knowledge_points k ON k.id=r.source_id WHERE r.target_id=?",
            ),
        ]:
            result[key] = select_rows(db, "knowledge_points", sql, [result["id"]])
        return envelope(request, result)


@router.get("/knowledge/framework")
def framework(request: Request):
    service = request.app.state.questions
    with service.database.session() as db, db.begin():
        owner = service.user(request, db).id
        counts = {
            r["knowledge_point_id"]: int(r["total"])
            for r in rows(
                db,
                "SELECT l.knowledge_point_id,COUNT(DISTINCT l.question_id) AS total FROM user_question_knowledge_links l JOIN questions q ON q.id=l.question_id AND q.user_id=l.user_id WHERE l.user_id=? AND q.status<>'archived' GROUP BY l.knowledge_point_id",
                [owner],
            )
        }
        mastery = {
            (r["subject"], r["knowledge_point"]): r
            for r in select_rows(
                db,
                "mastery_states",
                "SELECT * FROM mastery_states WHERE user_id=?",
                [owner],
            )
        }
        nodes, ids = [], {}
        for value in select_rows(
            db,
            "knowledge_points",
            "SELECT * FROM knowledge_points ORDER BY subject,code",
        ):
            ids[value["id"]] = value["code"]
            content = value["content"] if isinstance(value["content"], dict) else {}
            nodes.append(
                {
                    **{key: value[key] for key in ["code", "subject", "name"]},
                    "grade": content.get("grade", "")
                    if isinstance(content.get("grade", ""), str)
                    else "",
                    "chapter": content.get("chapter", "")
                    if isinstance(content.get("chapter", ""), str)
                    else "",
                    "question_count": counts.get(value["id"], 0),
                    "mastery": mastery.get((value["subject"], value["name"])),
                }
            )
        relations = [
            {"code": ids[r["source_id"]], "prerequisite_code": ids[r["target_id"]]}
            for r in rows(
                db,
                "SELECT source_id,target_id FROM knowledge_relations WHERE relation_type='prerequisite' ORDER BY source_id,target_id",
            )
            if r["source_id"] in ids and r["target_id"] in ids
        ]
        profiles = select_rows(
            db,
            "student_profiles",
            "SELECT grade,preferences FROM student_profiles WHERE user_id=?",
            [owner],
        )
        profile = profiles[0] if profiles else {}
        preferences = profile.get("preferences") or {}
        if not isinstance(preferences, dict):
            preferences = {}
        return envelope(
            request,
            {
                "nodes": nodes,
                "relations": relations,
                "default_subject": preferences.get("focus_subject") or "数学",
                "default_grade": profile.get("grade") or "",
            },
        )


NEXT = {
    "understanding": "理解错误原因",
    "teach_back": "用自己的话讲清思路",
    "teach_back_retry": "补充说明关键理由",
    "near_transfer": "完成一道相似题",
    "near_remediation": "再巩固一次",
    "far_transfer": "完成综合应用",
    "transfer_insufficient": "回顾方法后再练习",
}
TOPICS = {
    "fill_blank": "填空题",
    "choice": "单选题",
    "multiple_choice": "多选题",
    "calculation": "计算题",
    "proof": "证明题",
    "subjective": "主观题",
    "other": "其他题型",
}


@router.get("/dashboard")
def dashboard(request: Request):
    service = request.app.state.questions
    with service.database.session() as db, db.begin():
        owner = service.user(request, db).id
        questions = rows(
            db,
            "SELECT id,question_text FROM questions WHERE user_id=? AND status<>'archived'",
            [owner],
        )
        keys = {
            "".join(
                c
                for c in r["question_text"]
                if not c.isspace() and c not in "，。？?：:"
            ).lower()
            if (r["question_text"] or "").strip()
            else "pending:" + r["id"]
            for r in questions
        }
        reviews = int(
            rows(
                db,
                "SELECT COUNT(*) AS count FROM review_plans WHERE user_id=? AND status='pending' AND due_at<TIMESTAMP(DATE(UTC_TIMESTAMP()+INTERVAL 8 HOUR))+INTERVAL 16 HOUR",
                [owner],
            )[0]["count"]
        )
        mastery, mistakes, discoveries = [], [], []
        seen = set()
        for value in select_rows(
            db,
            "mastery_states",
            "SELECT * FROM mastery_states WHERE user_id=? ORDER BY updated_at DESC,id DESC LIMIT 8",
            [owner],
        ):
            key = (value["subject"], value["knowledge_point"])
            if key not in seen:
                seen.add(key)
                mastery.append(value)
        seen = set()
        for value in select_rows(
            db,
            "misconception_states",
            "SELECT * FROM misconception_states WHERE user_id=? ORDER BY probability DESC,id LIMIT 8",
            [owner],
        ):
            value["label"] = mistake_label(value["label"])
            key = (value["subject"], value["label"])
            if key in seen:
                continue
            seen.add(key)
            mistakes.append(value)
            if len(discoveries) < 2:
                discoveries.append(
                    {
                        "kind": "attention",
                        "title": value["label"],
                        "detail": "这是目前最需要优先巩固的错误原因",
                        "value": round(value["probability"] * 100),
                    }
                )
        for value in mastery[:2]:
            stable = value["mastery_score"] >= 0.75
            discoveries.append(
                {
                    "kind": "stable" if stable else "progress",
                    "title": value["knowledge_point"],
                    "detail": "掌握状态已经比较稳定"
                    if stable
                    else "继续完成相似题会更牢固",
                    "value": round(value["mastery_score"] * 100),
                }
            )
        sessions = select_rows(
            db,
            "tutor_sessions",
            "SELECT * FROM tutor_sessions WHERE user_id=? AND status='active' ORDER BY updated_at DESC,id DESC LIMIT 1",
            [owner],
        )
        continuation = None
        if sessions:
            session = sessions[0]
            active = select_rows(
                db,
                "questions",
                "SELECT * FROM questions WHERE id=? AND user_id=? AND status<>'archived'",
                [session["question_id"], owner],
            )
            state = session["state"] if isinstance(session["state"], dict) else {}
            if active and not state.get("question_changed", False):
                question = active[0]
                topic = (
                    str(question["knowledge_points"][0]).strip()
                    if question["knowledge_points"]
                    else question["question_type"] or "错题学习"
                )
                continuation = {
                    "session_id": session["id"],
                    "question_id": session["question_id"],
                    "stage": session["stage"],
                    "knowledge_point": TOPICS.get(topic, topic) or "错题学习",
                    "next_step": NEXT.get(session["stage"], "继续完成本次学习"),
                }
        streak, expected = 0, -1
        for value in rows(
            db,
            "SELECT DISTINCT DATEDIFF(DATE(UTC_TIMESTAMP()+INTERVAL 8 HOUR),DATE(created_at+INTERVAL 8 HOUR)) AS day_offset FROM questions WHERE user_id=? AND status<>'archived' AND created_at IS NOT NULL ORDER BY day_offset",
            [owner],
        ):
            day = int(value["day_offset"])
            if streak == 0:
                if day not in [0, 1]:
                    break
                expected = day
            if day != expected:
                break
            streak += 1
            expected += 1
        profiles = rows(
            db, "SELECT grade FROM student_profiles WHERE user_id=? LIMIT 1", [owner]
        )
        has_data = bool(questions or reviews or mastery or mistakes or continuation)
        return envelope(
            request,
            {
                "today_reviews": reviews,
                "weekly_questions": len(keys),
                "mastered_points": sum(m["mastery_score"] >= 0.7 for m in mastery),
                "streak_days": streak,
                "grade": profiles[0]["grade"] if profiles else "初二",
                "estimated_minutes": max(3, reviews + (5 if continuation else 2))
                if has_data
                else 0,
                "continue_learning": continuation,
                "discoveries": discoveries,
                "mastery": mastery,
                "misconceptions": mistakes,
                "ai_suggestion": "先弄懂最常出错的一步，再完成一道相似题。"
                if has_data
                else "拍下第一道错题，我会从你的解题步骤开始分析。",
            },
        )


METHODS = {
    "socratic": "逐步提问",
    "micro_activity": "小步练习",
    "assisted_progression": "分步辅助练习",
    "independent_dataset_practice": "独立完成题库练习",
    "incremental_hint": "分层提示",
    "understanding_check_prompt": "理解检查",
    "preserve_correct_part": "保留正确部分再提示",
    "visual_counterexample": "图形演示和反例",
    "prerequisite_example": "补充基础例子",
    "temporary_rediagnosis": "重新分析题目",
    "answer_with_explanation": "结合答案讲解",
    "targeted_remediation": "针对错误讲解",
    "guided": "逐步引导",
}


@router.get("/analytics/overview")
def overview(request: Request):
    try:
        days = int(request.query_params.get("days", "14").strip())
    except ValueError:
        raise ApiError(422, "days 必须是整数") from None
    if not 1 <= days <= 365:
        raise ApiError(422, "days 超出允许范围")
    service = request.app.state.questions
    with service.database.session() as db, db.begin():
        owner = service.user(request, db).id
        mastery, mistakes, trend = [], [], []
        seen = set()
        for value in select_rows(
            db,
            "mastery_states",
            "SELECT * FROM mastery_states WHERE user_id=? ORDER BY updated_at DESC,id DESC",
            [owner],
        ):
            key = (value["subject"], value["knowledge_point"])
            if key not in seen:
                seen.add(key)
                mastery.append(value)
        seen = set()
        for value in select_rows(
            db,
            "misconception_states",
            "SELECT * FROM misconception_states WHERE user_id=? ORDER BY probability DESC,id",
            [owner],
        ):
            value["label"] = mistake_label(value["label"])
            key = (value["subject"], value["label"])
            if key in seen:
                continue
            seen.add(key)
            for field in ["successful_strategy", "failed_strategy"]:
                raw = value.get(field) or ""
                value[field] = METHODS.get(raw, raw)
            mistakes.append(value)
        count = 0
        for value in rows(
            db,
            "SELECT DATE(created_at) AS day,AVG(new_value) AS average,COUNT(*) AS count FROM cognitive_updates WHERE user_id=? AND entity_type='mastery' AND created_at>=TIMESTAMPADD(DAY,?,UTC_TIMESTAMP(6)) GROUP BY DATE(created_at) ORDER BY day",
            [owner, 1 - days],
        ):
            total = int(value["count"])
            count += total
            trend.append(
                {
                    "date": str(value["day"]),
                    "score": int(float(value["average"]) * 1000 + 0.5) / 10,
                    "evidence_count": total,
                }
            )
        return envelope(
            request,
            {
                "mastery": mastery,
                "misconceptions": mistakes,
                "trend": trend,
                "summary": {
                    "knowledge_count": len(mastery),
                    "misconception_count": len(mistakes),
                    "evidence_count": count,
                },
            },
        )
