"""Transaction-bound exposure admission before awarding task learning credit."""

from .lessons import digest
from .protocol import ApiError
from .question_data import execute, rows


def learning_admission(db, task, result):
    state = result.get("checkpoint") or {}
    eligible = (
        result.get("learning_eligible") is True
        and task.get("learning_applied") is not True
        and result.get("status") == "completed"
    )
    contrast = (state.get("contrast") or {}).get("question") or ""
    if contrast and (
        state.get("contrast_passed") is True
        or (state.get("assistance") or {}).get("contrast") is True
    ):
        subjects = rows(
            db,
            "SELECT subject FROM questions WHERE id=? AND user_id=?",
            [task["question_id"], task["user_id"]],
        )
        if not subjects:
            raise ApiError(503, "任务来源不存在")
        hashed = digest(subjects[0]["subject"] + "|" + contrast)
        execute(
            db,
            "INSERT IGNORE INTO learning_task_exposures (user_id,contrast_hash,task_id,created_at) VALUES (?,?,?,UTC_TIMESTAMP(6))",
            [task["user_id"], hashed, task["id"]],
        )
        exposure = rows(
            db,
            "SELECT task_id FROM learning_task_exposures WHERE user_id=? AND contrast_hash=? FOR UPDATE",
            [task["user_id"], hashed],
        )
        if not exposure or exposure[0]["task_id"] != task["id"]:
            eligible = False
    if eligible and rows(
        db,
        "SELECT t.id FROM learning_tasks t JOIN questions q ON q.id=t.question_id WHERE t.user_id=? AND q.subject=(SELECT subject FROM questions WHERE id=?) AND JSON_UNQUOTE(JSON_EXTRACT(t.checkpoint,'$.contrast.question'))=? AND (JSON_UNQUOTE(JSON_EXTRACT(t.checkpoint,'$.contrast_passed'))='true' OR JSON_UNQUOTE(JSON_EXTRACT(t.checkpoint,'$.assistance.contrast'))='true') LIMIT 1",
        [task["user_id"], task["question_id"], contrast],
    ):
        eligible = False
    if eligible:
        if (task.get("pending_action") or {}).get("kind") != "answer":
            raise ApiError(503, "缺少学生确认的实际作答")
        attempt = result.get("attempt")
        if not isinstance(attempt, dict):
            raise ApiError(503, "缺少学习证据")
        if (
            attempt.get("phase") != "contrast"
            or attempt.get("verdict") != "confirmed_correct"
            or attempt.get("assisted") is True
            or (attempt.get("grading") or {}).get("can_update_learning") is not True
            or state.get("contrast_passed") is not True
        ):
            raise ApiError(503, "学习证据未达到更新条件")
    return eligible
