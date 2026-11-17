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


def apply_mastery(service, db, task, result, budget, transfer_eligible):
    """Apply assistance-aware evidence inside the caller's locked transaction."""
    from uuid import uuid4

    from .learning_evidence import apply_evidence, knowledge_point
    from .question_data import select_rows

    state = result.get("checkpoint") or {}
    if state.get("workflow_version") != "langgraph-learning-v1":
        return False
    attempt = result.get("attempt") or {}
    grading = attempt.get("grading") or {}
    phase, verdict = attempt.get("phase"), attempt.get("verdict")
    if (
        phase not in ("independent", "contrast")
        or verdict not in ("confirmed_correct", "confirmed_incorrect")
        or grading.get("can_update_learning") is not True
    ):
        return False
    assisted = attempt.get("assisted") is True
    if (
        phase == "contrast"
        and verdict == "confirmed_correct"
        and not transfer_eligible
        and not assisted
    ):
        return False
    action = task.get("pending_action") or {}
    if action.get("kind") != "answer" or attempt.get("answer", "") != action.get(
        "text", ""
    ):
        raise ApiError(503, "作答证据与提交不一致")
    if (
        (task.get("checkpoint") or {}).get("phase") != phase
        or grading.get("verdict") != verdict
        or (grading.get("correct") is True) != (verdict == "confirmed_correct")
    ):
        raise ApiError(503, "作答核验与当前步骤不一致")
    owner, question_id = task["user_id"], task["question_id"]
    task_id, request_id = task["id"], task.get("active_request") or ""
    if rows(
        db,
        "SELECT id FROM cognitive_updates WHERE user_id=? AND question_id=? AND entity_type='mastery' AND JSON_UNQUOTE(JSON_EXTRACT(evidence,'$.learning_task_id'))=? AND JSON_UNQUOTE(JSON_EXTRACT(evidence,'$.action_request_id'))=? LIMIT 1",
        [owner, question_id, task_id, request_id],
    ):
        return False
    questions = select_rows(
        db,
        "questions",
        "SELECT * FROM questions WHERE id=? AND user_id=?",
        [question_id, owner],
    )
    if not questions:
        raise ApiError(409, "题目来源已变化")
    question = questions[0]
    revealed = phase in (state.get("revealed_phases") or [])
    hints = (state.get("hints") or {}).get(phase) or []
    if revealed or (assisted and not hints):
        return False
    elapsed = rows(
        db,
        "SELECT GREATEST(0,COALESCE(TIMESTAMPDIFF(SECOND,last_evidence_at,UTC_TIMESTAMP()),0)) AS seconds FROM mastery_states WHERE user_id=? AND subject=? AND knowledge_point=? ORDER BY updated_at DESC,id DESC LIMIT 1",
        [owner, question["subject"], knowledge_point(db, question)],
    )
    days = float(elapsed[0]["seconds"]) / 86400 if elapsed else 0.0
    clock = rows(
        db, "SELECT DATE_FORMAT(UTC_TIMESTAMP(),'%Y-%m-%dT%H:%i:%sZ') AS instant", []
    )
    event = {
        "event_id": task_id + ":" + request_id,
        "verdict": verdict,
        "scope": "contrast_question" if phase == "contrast" else "original_question",
        "hint_used": assisted and bool(hints),
        "solution_seen": False,
        "student_confirmed": True,
        "source_current": True,
        "grading_reliable": True,
        "option_count": len(question.get("options") or []),
        "days_since_last": days,
        "delayed_similar": phase == "contrast" and not assisted and days >= 1,
        "occurred_at": clock[0]["instant"],
    }
    evidence = {
        "aemt_event": event,
        "learning_task_id": task_id,
        "action_request_id": request_id,
        "strategy": "aemt_assistance_aware",
        "hint_level": 1 if assisted else 0,
    }
    if phase == "contrast" and not assisted:
        evidence["near_transfer"] = verdict == "confirmed_correct"
    budget.check("before_aemt")
    apply_evidence(
        service,
        db,
        owner,
        question,
        evidence,
        compute_timeout=budget.timeout_seconds(5, reserve_seconds=1),
    )
    if not rows(
        db,
        "SELECT id FROM review_plans WHERE user_id=? AND question_id=? AND status='pending' LIMIT 1",
        [owner, question_id],
    ):
        interval = 1 if assisted or verdict == "confirmed_incorrect" else 3
        execute(
            db,
            "INSERT INTO review_plans (id,user_id,question_id,due_at,interval_days,reason,status,created_at,updated_at) VALUES (?,?,?,TIMESTAMPADD(DAY,?,UTC_TIMESTAMP()),?,'根据本次作答安排复习','pending',UTC_TIMESTAMP(),UTC_TIMESTAMP())",
            [str(uuid4()), owner, question_id, interval, interval],
        )
    budget.check("after_aemt")
    return True
