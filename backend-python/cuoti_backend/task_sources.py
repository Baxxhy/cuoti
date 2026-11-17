"""Immutable source capture for learning tasks, preserving legacy fingerprints."""

import json

from .learning_evidence import stamp_compact
from .lessons import compact, digest
from .question_data import execute, rows, select_rows


class TaskSourceError(Exception):
    def __init__(self, reason):
        super().__init__("任务来源校验未通过")
        self.reason = reason


def source_equal(left, right):
    numeric = (int, float)
    if type(left) in numeric and type(right) in numeric:
        return left == right
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(
            source_equal(value, right[key]) for key, value in left.items()
        )
    if isinstance(left, list):
        return len(left) == len(right) and all(
            source_equal(a, b) for a, b in zip(left, right, strict=True)
        )
    return left == right


def fingerprint_fields(snapshot):
    q = snapshot["question"]
    values = [
        q[key]
        for key in [
            "question_text",
            "subject",
            "grade",
            "question_type",
            "student_answer",
            "options",
            "knowledge_points",
            "confirmed",
            "status",
        ]
    ]
    values.extend(
        snapshot[key]
        for key in ["work", "steps", "assets", "analysis", "references", "diagnosis"]
    )
    if "diagnostic_cards" in snapshot:
        values.append(snapshot["diagnostic_cards"])
    return values


def capture_source(db, task, current, origin="legacy_revalidated"):
    saved = rows(
        db, "SELECT * FROM learning_task_sources WHERE task_id=?", [task["id"]]
    )
    if saved:
        record = saved[0]
        try:
            source = (
                json.loads(record["source"])
                if isinstance(record["source"], str)
                else record["source"]
            )
            old, fresh = fingerprint_fields(source), fingerprint_fields(current)
        except (ValueError, KeyError, TypeError):
            raise TaskSourceError("source_parse") from None
        if record["input_fingerprint"] != task["input_fingerprint"]:
            raise TaskSourceError("source_fingerprint")
        if len(old) != len(fresh):
            raise TaskSourceError("source_shape")
        for index, (left, right) in enumerate(zip(old, fresh, strict=True)):
            if not source_equal(left, right):
                raise TaskSourceError("source_field_" + str(index))
        return source
    if task["input_fingerprint"] != digest(stamp_compact(fingerprint_fields(current))):
        raise TaskSourceError("source_legacy_stale")
    execute(
        db,
        "INSERT INTO learning_task_sources (task_id,schema_version,input_fingerprint,origin,source,created_at) VALUES (?,'1.0',?,?,?,UTC_TIMESTAMP(6))",
        [task["id"], task["input_fingerprint"], origin, compact(current)],
    )
    return current


def _first(db, table, sql, params):
    values = select_rows(db, table, sql, params)
    return values[0] if values else None


def load_snapshot(db, id, owner, *, lock=True):
    q = _first(
        db,
        "questions",
        "SELECT * FROM questions WHERE id=? AND user_id=?"
        + (" FOR UPDATE" if lock else ""),
        [id, owner],
    )
    if not q:
        from .protocol import ApiError

        raise ApiError(404, "题目不存在或无权访问")
    work = _first(
        db,
        "student_works",
        "SELECT * FROM student_works WHERE question_id=? ORDER BY created_at DESC,id DESC LIMIT 1",
        [id],
    )
    steps = select_rows(
        db,
        "student_steps",
        "SELECT * FROM student_steps WHERE work_id=(SELECT id FROM student_works WHERE question_id=? ORDER BY created_at DESC,id DESC LIMIT 1) ORDER BY step_index,id",
        [id],
    )
    assets = select_rows(
        db,
        "question_assets",
        "SELECT * FROM question_assets WHERE question_id=? AND kind IN ('crop','question_figure') ORDER BY created_at,id",
        [id],
    )
    analysis = _first(
        db,
        "problem_analyses",
        "SELECT * FROM problem_analyses WHERE question_id=?",
        [id],
    )
    refs = select_rows(
        db,
        "reference_steps",
        "SELECT r.* FROM reference_steps r JOIN problem_analyses a ON a.id=r.analysis_id WHERE a.question_id=? ORDER BY r.step_index,r.id",
        [id],
    )
    diagnosis = _first(
        db,
        "diagnoses",
        "SELECT * FROM diagnoses WHERE question_id=? ORDER BY created_at DESC,id DESC LIMIT 1",
        [id],
    )
    return {
        "question": q,
        "work": work,
        "steps": steps,
        "assets": assets,
        "analysis": analysis,
        "references": refs,
        "diagnosis": diagnosis,
    }


def validate_version(db, task, snapshot):
    from .task_budget import stopped_view

    q = snapshot["question"]
    if (
        task["input_fingerprint"] == digest(stamp_compact(fingerprint_fields(snapshot)))
        and q["status"] != "archived"
        and q["confirmed"] is True
    ):
        view = task.get("student_view") or {}
        for block in view.get("prompt_blocks", []):
            if (
                block.get("kind") == "question"
                and block.get("text") == q["question_text"]
                and (task.get("checkpoint") or {}).get("phase") != "contrast"
            ):
                block.update(
                    options=q["options"],
                    question_type=q["question_type"],
                    images=[
                        asset["path"]
                        for asset in snapshot["assets"]
                        if asset["kind"] == "question_figure"
                    ],
                )
        task["student_view"] = view
        return True
    if task.get("status") not in ["cancelled", "stale"]:
        view = stopped_view("题目或学习依据已更新，请回原题重新开始")
        execute(
            db,
            "UPDATE learning_tasks SET status='stale',version=version+1,lease_token=NULL,lease_until=NULL,student_view=?,exit_reason='input_changed',updated_at=UTC_TIMESTAMP(6) WHERE id=?",
            [compact(view), task["id"]],
        )
        execute(
            db,
            "UPDATE learning_task_actions SET status='stale',updated_at=UTC_TIMESTAMP(6) WHERE task_id=? AND status='pending'",
            [task["id"]],
        )
        task.update(
            status="stale", student_view=view, version=task.get("version", 0) + 1
        )
    return False
