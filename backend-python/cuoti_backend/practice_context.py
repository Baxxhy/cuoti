"""Legacy-compatible practice provenance and alignment admission checks."""

import json

from .learning_evidence import stamp_compact
from .lessons import digest
from .protocol import ApiError
from .question_data import rows, select_rows
from .retrieval import prepare
from .task_sources import source_equal


def fingerprint_json(value):
    return json.dumps(
        json.loads(stamp_compact(value)),
        ensure_ascii=False,
        sort_keys=True,
        allow_nan=False,
    )


def source_fingerprint(db, question):
    value = {
        key: question[key]
        for key in [
            "question_text",
            "student_answer",
            "subject",
            "grade",
            "title",
            "formulas",
            "options",
            "question_type",
            "knowledge_points",
        ]
    }
    value["student_work_revisions"] = [
        item["id"]
        for item in rows(
            db,
            "SELECT id FROM student_works WHERE question_id=? ORDER BY id",
            [question["id"]],
        )
    ]
    return digest(fingerprint_json(value))


def source_version(db, question):
    value = {"question": source_fingerprint(db, question)}
    for key, table in [("analysis", "problem_analyses"), ("diagnosis", "diagnoses")]:
        found = select_rows(
            db,
            table,
            f"SELECT * FROM {table} WHERE question_id=? ORDER BY created_at DESC,id DESC LIMIT 1",
            [question["id"]],
        )
        value[key] = found[0] if found else None
    return digest(fingerprint_json(value))


def served(db, owner, mistake, id, mode):
    records = select_rows(
        db,
        "practice_recommendations",
        "SELECT * FROM practice_recommendations WHERE user_id=? AND mistake_id=? AND dataset_question_id=? AND mode=? ORDER BY created_at DESC LIMIT 1",
        [owner, mistake["id"], id, mode],
    )
    if not records:
        raise ApiError(409, "请先获取推荐题再作答")
    record = records[0]
    if (record.get("retrieval_trace") or {}).get(
        "source_question_fingerprint"
    ) != source_fingerprint(db, mistake):
        raise ApiError(409, "题目或推荐已更新，请重新获取推荐题再提交")
    return record


def preparation(service, db, question, mode):
    found = select_rows(
        db,
        "problem_analyses",
        "SELECT * FROM problem_analyses WHERE question_id=? ORDER BY created_at DESC,id DESC LIMIT 1",
        [question["id"]],
    )
    return prepare(service, db, question, found[0] if found else None, "practice", mode)


def aligned(service, db, source, prepared, candidates):
    targets = select_rows(
        db,
        "knowledge_points",
        "SELECT * FROM knowledge_points WHERE id=? AND subject=?",
        [prepared.get("target_knowledge_id", ""), source["subject"]],
    )
    if not targets:
        return []
    return service.compute.compute(
        "practice_alignment",
        retrieval_source=source,
        retrieval_target=targets[0],
        retrieval_candidates=candidates,
    )["checks"]


def alignment_method(checks, id):
    return next(
        (
            item.get("method") or ""
            for item in checks
            if item.get("id") == id and item.get("aligned") is True
        ),
        "",
    )


def proof_context(db, source, prepared, candidate):
    targets = select_rows(
        db,
        "knowledge_points",
        "SELECT * FROM knowledge_points WHERE id=? AND subject=?",
        [prepared.get("target_knowledge_id", ""), source["subject"]],
    )
    return {
        "policy": 1,
        "source": source_version(db, source),
        "candidate": digest(fingerprint_json(candidate)),
        "target": digest(fingerprint_json(targets[0])) if targets else "",
    }


def proof_valid(db, source, prepared, candidate, trace):
    proof = trace.get("alignment_proof") or {}
    return proof.get("method") in [
        "symbolic_linear",
        "qwen_grounded_concept",
    ] and source_equal(
        proof.get("context"), proof_context(db, source, prepared, candidate)
    )


def save_proof(db, source, prepared, candidate, trace, method):
    trace.update(
        alignment_proof={
            "method": method,
            "context": proof_context(db, source, prepared, candidate),
        },
        alignment_method=method,
    )
