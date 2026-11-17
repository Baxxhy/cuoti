"""Validate learning task outputs before transaction-bound audit persistence."""

from uuid import uuid4

from .learning_memory import audit_manifest
from .lessons import compact
from .protocol import ApiError
from .question_data import execute, insert
from .task_planning import validate_recommendation
from .task_sources import attempt_source

TOOLS = {
    "check_step",
    "grade_answer",
    "knowledge_search",
    "step_alignment",
    "compare_variant",
    "recognize_handwriting",
    "inspect_figure",
    "visualization",
}
VALIDATIONS = {"verified", "rejected", "needs_review", "not_applicable"}


def validate_result(result, domain, memory):
    traces = result.get("traces") or []
    if len(traces) > 3 or result.get("status") not in [
        "waiting_student",
        "needs_review",
        "completed",
    ]:
        raise ApiError(503, "学习任务结果格式不正确")
    validate_recommendation(result, domain)
    valid_refs = {entry["ref"] for entry in memory.get("entries", [])}
    for trace in traces:
        if (
            trace.get("tool_name") not in TOOLS
            or trace.get("validation") not in VALIDATIONS
        ):
            raise ApiError(503, "学习任务工具结果不正确")
        if any(ref not in valid_refs for ref in trace.get("memory_refs", [])):
            raise ApiError(503, "学习规划引用了无效记忆")


def save_traces(db, task, result, budget, memory, domain):
    """Caller must own the result transaction; checkpoint writes follow separately."""
    validate_result(result, domain, memory)
    attempt = result.get("attempt")
    if isinstance(attempt, dict):
        source = attempt_source(db, task, attempt.get("phase", ""))
        attempt["source"] = source
        for trace in result.get("traces") or []:
            if trace.get("tool_name") in ["check_step", "grade_answer"]:
                trace.setdefault("evidence", {})["source"] = source
    manifest = audit_manifest(memory)
    for index, trace in enumerate(result.get("traces") or []):
        run = {
            "task_id": task["id"],
            "request_id": task["active_request"],
            "trace": trace,
            "native_elapsed_ms": budget.elapsed_ms(),
            "elapsed_ms": result["elapsed_ms"],
            "usage": result["usage"],
            "memory_rule": "learning-memory-v1",
            "memory_manifest": manifest,
        }
        rid = insert(
            db,
            "agent_runs",
            session_id=task.get("session_id"),
            agent_name="learning_task",
            status="completed",
            result=run,
        )
        insert(
            db,
            "agent_tool_calls",
            agent_run_id=rid,
            tool_name=trace["tool_name"],
            input_json={
                "task_id": task["id"],
                "request_id": task["active_request"],
                "student_action": task["pending_action"],
            },
            output_json=trace,
        )
        execute(
            db,
            "INSERT INTO learning_task_steps (id,task_id,request_id,step_no,plan_version,tool_name,validation,agent_run_id,trace,created_at) VALUES (?,?,?,?,?,?,?,?,?,UTC_TIMESTAMP(6))",
            [
                str(uuid4()),
                task["id"],
                task["active_request"],
                index,
                task["version"] * 3 + index,
                trace["tool_name"],
                trace["validation"],
                rid,
                compact(trace),
            ],
        )


def save_images(db, task, result, view, next_step):
    from copy import deepcopy

    from .question_data import select_rows

    def image(id):
        found = select_rows(
            db,
            "learning_task_images",
            "SELECT * FROM learning_task_images WHERE id=? AND task_id=? AND input_fingerprint=?",
            [id, task["id"], task["input_fingerprint"]],
        )
        if not found:
            raise ApiError(422, "这张作答照片不属于当前任务版本")
        return found[0]

    kind = (task.get("pending_action") or {}).get("kind")
    if kind == "recognize_handwriting":
        draft = view.get("handwriting") or {}
        original = image(task["pending_action"].get("handwriting_id", ""))
        if draft.get("id") != original["id"] or not isinstance(
            draft.get("recognition"), dict
        ):
            raise ApiError(503, "手写转写结果格式不正确")
        execute(
            db,
            "UPDATE learning_task_images SET recognition=?,confirmation_step_id=?,updated_at=UTC_TIMESTAMP(6) WHERE id=?",
            [compact(draft["recognition"]), next_step, original["id"]],
        )
        draft["image_url"] = "/" + original["original_path"]
        view["handwriting"] = draft
    if (
        kind
        not in {
            "visualize",
            "observe_visualization",
            "close_visualization",
            "hint",
            "reveal",
            "resume",
        }
        or (task.get("checkpoint") or {}).get("phase", "")
        != (result.get("checkpoint") or {}).get("phase", "")
        or view.get("input_kind") != "text"
    ):
        return
    draft = (task.get("student_view") or {}).get("handwriting") or {}
    if not draft or view.get("handwriting"):
        return
    original = image(draft.get("id", ""))
    if original.get("confirmation_step_id") != task["step_id"]:
        return
    execute(
        db,
        "UPDATE learning_task_images SET confirmation_step_id=?,updated_at=UTC_TIMESTAMP(6) WHERE id=?",
        [next_step, original["id"]],
    )
    view["handwriting"] = deepcopy(draft)


def save_result(service, db, task, result, budget, memory, domain):
    """Caller locks the task/source and owns commit/rollback and lease validation."""
    from .learning_evidence import apply_evidence
    from .question_data import rows, select_rows
    from .task_evidence import apply_mastery, learning_admission

    save_traces(db, task, result, budget, memory, domain)
    eligible = learning_admission(db, task, result)
    state = result.get("checkpoint") or {}
    owner, question_id = task["user_id"], task["question_id"]
    if eligible:
        question = select_rows(
            db,
            "questions",
            "SELECT * FROM questions WHERE id=? AND user_id=?",
            [question_id, owner],
        )
        if not question:
            raise ApiError(409, "题目来源已变化")
        if state.get("workflow_version") != "langgraph-learning-v1":
            budget.check("before_learning")
            apply_evidence(
                service,
                db,
                owner,
                question[0],
                {
                    "near_transfer": True,
                    "hint_level": 0,
                    "strategy": "verified_condition_contrast",
                    "learning_task_id": task["id"],
                    "action_request_id": task["active_request"],
                },
                compute_timeout=budget.timeout_seconds(5, reserve_seconds=1),
            )
            budget.check("after_learning")
        if not rows(
            db,
            "SELECT id FROM review_plans WHERE user_id=? AND question_id=? AND status='pending' LIMIT 1",
            [owner, question_id],
        ):
            execute(
                db,
                "INSERT INTO review_plans (id,user_id,question_id,due_at,interval_days,reason,status,created_at,updated_at) VALUES (?,?,?,UTC_TIMESTAMP()+INTERVAL 3 DAY,3,'单条件对照已独立完成，稍后再确认稳定性','pending',UTC_TIMESTAMP(),UTC_TIMESTAMP())",
                [str(uuid4()), owner, question_id],
            )
    apply_mastery(service, db, task, result, budget, eligible)
    if task["active_request"] != "__initial__":
        execute(
            db,
            "UPDATE learning_task_actions SET result=?,status='applied',updated_at=UTC_TIMESTAMP(6) WHERE task_id=? AND request_id=? AND status='pending'",
            [compact(result), task["id"], task["active_request"]],
        )
    budget.check("before_checkpoint")
    next_step = str(uuid4())
    view = result.get("student_view") or {}
    save_images(db, task, result, view, next_step)
    execute(
        db,
        "UPDATE learning_tasks SET status=?,version=version+1,step_id=?,checkpoint=?,student_view=?,learning_applied=?,lease_token=NULL,lease_until=NULL,exit_reason=?,updated_at=UTC_TIMESTAMP(6) WHERE id=?",
        [
            result["status"],
            next_step,
            compact(state),
            compact(view),
            eligible or task.get("learning_applied") is True,
            result.get("exit_reason") or "",
            task["id"],
        ],
    )
    budget.check("after_checkpoint")
    execute(
        db,
        "UPDATE agent_runs r JOIN learning_task_steps s ON s.agent_run_id=r.id SET r.result=JSON_SET(r.result,'$.native_elapsed_ms',CAST(? AS UNSIGNED)) WHERE s.task_id=? AND s.request_id=?",
        [budget.elapsed_ms(), task["id"], task["active_request"]],
    )
    budget.check("after_audit")
