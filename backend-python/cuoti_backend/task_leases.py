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


def fail_preparation(db, task, reason, *, limit=False):
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
