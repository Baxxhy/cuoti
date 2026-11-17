"""Lease ownership and failure persistence for the learning worker."""

from .lessons import compact
from .question_data import execute
from .task_budget import limit_view, stopped_view


def lease_valid(task, lease):
    return (
        task.get("status") == "running"
        and task.get("lease_token") == lease
        and task.get("cancel_requested") is not True
    )


def fail_preparation(db, task, reason, *, limit=False, source_error=False):
    recoverable = not limit or reason == "prepare_budget"
    view = (
        stopped_view(
            "准备耗时较长，内容已保留，可以稍后继续"
            if limit
            else "暂时未能准备题目，内容已保留，可以重试"
        )
        if recoverable
        else limit_view()
    )
    if source_error:
        view = stopped_view(
            "任务来源无法核对，请结束本次学习后回原题重开；旧记录仍保留"
        )
        recoverable = False
    if recoverable:
        view["secondary_actions"] = ["resume"]
        photo = (task.get("student_view") or {}).get("handwriting")
        if photo:
            view["handwriting"] = photo
    execute(
        db,
        "UPDATE learning_tasks SET status='failed',version=version+1,student_view=?,exit_reason=?,lease_token=NULL,lease_until=NULL,updated_at=UTC_TIMESTAMP(6) WHERE id=?",
        [compact(view), reason, task["id"]],
    )
    execute(
        db,
        "UPDATE learning_task_actions SET status='failed',updated_at=UTC_TIMESTAMP(6) WHERE task_id=? AND status='pending'",
        [task["id"]],
    )


def recoverable_ids(db):
    from .question_data import rows

    return [
        row["id"]
        for row in rows(
            db,
            "SELECT id FROM learning_tasks WHERE cancel_requested=0 AND (status='queued' OR (status='running' AND lease_until<UTC_TIMESTAMP(6))) ORDER BY created_at,id LIMIT 1",
        )
    ]


def claim_lease(db, id, budget):
    """Reserve one task inside the caller's transaction; never start computation."""
    from uuid import uuid4

    from sqlalchemy.exc import SQLAlchemyError

    from .question_data import rows, select_rows
    from .task_budget import TaskBudgetExceeded, at_limit
    from .task_context import prepare_context
    from .task_sources import (
        TaskSourceError,
        capture_source,
        load_snapshot,
        validate_version,
    )

    identity = rows(
        db, "SELECT user_id,question_id FROM learning_tasks WHERE id=?", [id]
    )
    if not identity:
        return None
    owner, qid = identity[0]["user_id"], identity[0]["question_id"]
    snapshot = load_snapshot(db, qid, owner)
    tasks = select_rows(
        db,
        "learning_tasks",
        "SELECT * FROM learning_tasks WHERE id=? AND user_id=? FOR UPDATE",
        [id, owner],
    )
    if not tasks:
        return None
    task = tasks[0]
    eligible = rows(
        db,
        "SELECT id FROM learning_tasks WHERE id=? AND cancel_requested=0 AND (status='queued' OR (status='running' AND lease_until<UTC_TIMESTAMP(6)))",
        [id],
    )
    if not eligible or not validate_version(db, task, snapshot):
        return None
    if at_limit(task):
        fail_preparation(
            db,
            task,
            "retry_budget" if task["run_count"] >= 72 else "round_budget",
            limit=True,
        )
        return None
    execute(db, "UPDATE learning_tasks SET run_count=run_count+1 WHERE id=?", [id])
    try:
        source = capture_source(db, task, snapshot)
        domain = prepare_context(db, source, owner)
        domain["source_snapshot_id"] = task["id"]
        domain["action_id"] = id + ":" + (task.get("active_request") or "")
        budget.check("prepare")
    except TaskSourceError as error:
        fail_preparation(db, task, error.reason, source_error=True)
        return None
    except TaskBudgetExceeded:
        fail_preparation(db, task, "prepare_budget", limit=True)
        return None
    except SQLAlchemyError as error:
        arguments = getattr(getattr(error, "orig", None), "args", ())
        code = (
            str(arguments[0]) if arguments and type(arguments[0]) is int else "unknown"
        )
        fail_preparation(db, task, "prepare_database_" + code)
        return None
    except (ValueError, KeyError, TypeError):
        fail_preparation(db, task, "prepare_context_invalid")
        return None
    lease = str(uuid4())
    execute(
        db,
        "UPDATE learning_tasks SET status='running',lease_token=?,lease_until=UTC_TIMESTAMP(6)+INTERVAL 90 SECOND,updated_at=UTC_TIMESTAMP(6) WHERE id=?",
        [lease, id],
    )
    return {"task": task, "source": source, "context": domain, "lease": lease}
