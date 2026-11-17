"""Validate learning task outputs before transaction-bound audit persistence."""

from uuid import uuid4

from .learning_memory import audit_manifest
from .lessons import compact
from .protocol import ApiError
from .question_data import execute, insert
from .task_planning import validate_recommendation

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
