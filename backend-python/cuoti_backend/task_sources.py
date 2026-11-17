"""Immutable source capture for learning tasks, preserving legacy fingerprints."""

import json

from .learning_evidence import stamp_compact
from .lessons import compact, digest
from .question_data import execute, rows


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
