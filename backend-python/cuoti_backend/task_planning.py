"""Admission rules for task recommendations, grounded in the prepared candidate set."""

from .protocol import ApiError
from .question_data import rows, select_rows, serialize
from .retrieval import usable


def plan_candidates(db, owner, question, points):
    result = []
    for item in select_rows(
        db,
        "questions",
        "SELECT q.* FROM questions q WHERE q.user_id=? AND q.subject=? AND q.id<>? AND EXISTS(SELECT 1 FROM review_plans r WHERE r.question_id=q.id AND r.user_id=? AND r.status='pending' AND r.due_at<=UTC_TIMESTAMP()) ORDER BY q.id LIMIT 30",
        [owner, question["subject"], question["id"], owner],
    ):
        result.append(
            {
                "id": item["id"],
                "subject": item["subject"],
                "source": "notebook",
                "due": True,
                "estimated_minutes": 3,
                "question_type": item["question_type"],
            }
        )
    sql = "SELECT q.*,(SELECT COUNT(*) FROM study_session_items i JOIN study_sessions s ON s.id=i.session_id WHERE s.user_id=? AND s.created_at>=UTC_TIMESTAMP()-INTERVAL 7 DAY AND JSON_UNQUOTE(JSON_EXTRACT(i.snapshot,'$.id'))=q.id) AS recent_n,EXISTS(SELECT 1 FROM study_session_items i JOIN study_sessions s ON s.id=i.session_id WHERE s.user_id=? AND s.status='submitted' AND s.created_at>=UTC_TIMESTAMP()-INTERVAL 1 DAY AND JSON_UNQUOTE(JSON_EXTRACT(i.snapshot,'$.id'))=q.id AND JSON_EXTRACT(i.grading,'$.correct')=true AND JSON_EXTRACT(i.grading,'$.can_update_learning')=true) AS recent_pass FROM dataset_questions q WHERE q.subject=? AND q.usable_for_practice=1 AND q.usable_for_auto_grade=1 AND q.has_answer=1 ORDER BY q.id LIMIT 200"
    for record in rows(db, sql, [owner, owner, question["subject"]]):
        if len(result) >= 200:
            break
        item = serialize(
            "dataset_questions",
            {k: v for k, v in record.items() if k not in ["recent_n", "recent_pass"]},
        )
        if not usable(question, item, "practice"):
            continue
        labels = [
            p if isinstance(p, str) else p.get("name", "")
            for p in item["knowledge_points"]
        ]
        related = any(label and label in points for label in labels)
        if not related and item["question_type"] != question["question_type"]:
            continue
        difficulty = item.get("difficulty") or ""
        result.append(
            {
                **{
                    k: item[k]
                    for k in [
                        "id",
                        "subject",
                        "question_type",
                        "grade_band",
                        "knowledge_points",
                        "options",
                    ]
                },
                "source": "dataset",
                "error_relevance": 1.0 if related else 0.2,
                "estimated_minutes": 3,
                "difficulty": 0.25
                if difficulty in ["easy", "简单", "容易"]
                else 0.8
                if difficulty in ["hard", "困难", "较难"]
                else 0.5,
                "recent_exposures": int(record["recent_n"]),
                "just_mastered": bool(record["recent_pass"]),
            }
        )
    return result


def validate_recommendation(result, domain):
    plan = (result.get("student_view") or {}).get("recommendation") or {}
    id = plan.get("question_id") or ""
    if not id:
        return
    candidates = domain.get("practice_candidates") or []
    if not any(
        c["id"] == id
        and c.get("source") == plan.get("question_source")
        and not c.get("just_mastered", False)
        for c in candidates
    ):
        raise ApiError(503, "推荐题目不在本次可用范围内")
    for alternate in plan.get("alternatives", []):
        if alternate == id or not any(
            c["id"] == alternate and not c.get("just_mastered", False)
            for c in candidates
        ):
            raise ApiError(503, "备选题目不在本次可用范围内")
