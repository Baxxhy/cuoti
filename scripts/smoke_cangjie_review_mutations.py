"""Teacher corrections on real HTTP/MySQL; original routes run only in rollback snapshots."""

import ast
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from smoke_cangjie_accounts import request
from smoke_cangjie_school import native


def review_mutations(endpoint, env, query):
    def account(role):
        user = request(
            endpoint,
            "POST",
            "/api/v1/auth/register",
            {
                "email": f"correction-{uuid4().hex}@example.test",
                "name": "复核纠正",
                "password": "correction-test-123",
            },
        )
        query(env, f"UPDATE users SET role='{role}' WHERE id='{user['id']}'")
        return user

    teacher, other_teacher, student = (
        account("teacher"),
        account("teacher"),
        account("student"),
    )
    tt, ot, st = (u["access_token"] for u in (teacher, other_teacher, student))
    sid = student["id"]
    classroom = native(
        endpoint, "POST", "/api/v1/teachers/classes", tt, {"name": "复核纠正班"}
    )
    cid = classroom["id"]
    native(
        endpoint,
        "POST",
        f"/api/v1/teachers/classes/{cid}/students",
        tt,
        {"email": student["email"]},
    )
    question = native(
        endpoint,
        "POST",
        "/api/v1/teachers/questions",
        tt,
        {
            "question_text": "3*x=15",
            "question_type": "填空题",
            "knowledge_points": ["一次方程"],
            "standard_answer": "x=5",
            "reference_steps": ["3x=15", "x=5"],
            "allow_auto_grade": False,
        },
    )
    qid = question["question"]["id"]

    def task(task_id):
        return native(endpoint, "GET", f"/api/v1/teachers/reviews/{task_id}", tt)[
            "task"
        ]

    def operation(item, name, payload, expected=200, token=tt):
        return native(
            endpoint,
            "POST",
            f"/api/v1/teachers/reviews/{item['id']}/{name}",
            token,
            payload,
            expected=expected,
        )

    def submit(link):
        attempt = native(
            endpoint,
            "POST",
            f"/api/v1/students/assignments/{link}/attempts",
            st,
            {"answer": "x=100", "steps": []},
        )["attempt"]
        rows = native(endpoint, "GET", "/api/v1/teachers/reviews", tt)
        return next(t for t in rows if t["source_id"] == attempt["id"])

    def new_case(count=True):
        assignment = native(
            endpoint,
            "POST",
            "/api/v1/teachers/assignments",
            tt,
            {
                "class_id": cid,
                "question_id": qid,
                "settings": {"allow_repeat": True, "count_mastery": count},
            },
        )
        rows = native(endpoint, "GET", "/api/v1/students/assignments", st)
        link = next(
            r["student_assignment"]["id"]
            for r in rows
            if r["assignment"]["id"] == assignment["id"]
        )
        return submit(link), link

    def decide(item, **extra):
        return operation(
            item,
            "decision",
            {
                "version": item["version"],
                "conclusion": "confirmed_correct",
                "reason": "教师确认",
                **extra,
            },
        )

    def scalar(sql):
        return query(env, sql).strip()

    def score():
        return scalar(
            f"SELECT mastery_score,evidence_count FROM mastery_states WHERE user_id='{sid}'"
        )

    # Execute selected original code against this test DB in an outer transaction.
    # Its commit only releases a savepoint; roll back before the actual HTTP call.
    project = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(project / "backend"))
    from app import models
    from app.services.grading import grade_answer
    from app.services.timestamps import iso_timestamp
    from fastapi import HTTPException
    from sqlalchemy import URL, select
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

    names = {
        "_row",
        "_audit",
        "_managed_class",
        "_managed_student",
        "_assignment_review_context",
        "_sync_assignment_review",
        "_review_reasons",
        "revoke_review",
        "regrade_review",
        "transfer_review",
    }
    functions = []
    for node in ast.walk(
        ast.parse((project / "backend/app/teacher_api.py").read_text())
    ):
        if (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name in names
        ):
            node.decorator_list = []
            node.args.defaults = []
            node.args.kw_defaults = [None] * len(node.args.kwonlyargs)
            node.returns = None
            for arg in (*node.args.args, *node.args.kwonlyargs):
                arg.annotation = None
            functions.append(node)
    assert len(functions) == len(names)
    namespace = {
        **vars(models),
        "datetime": datetime,
        "timezone": timezone,
        "select": select,
        "HTTPException": HTTPException,
        "iso_timestamp": iso_timestamp,
        "grade_answer": grade_answer,
        "provider": None,
    }
    exec(  # noqa: S102 -- selected local reference routes, isolated DB and outer rollback
        compile(
            ast.Module(body=functions, type_ignores=[]),
            "<reference-review-corrections>",
            "exec",
        ),
        namespace,
    )

    def stable(value):
        if isinstance(value, datetime):
            return iso_timestamp(value)
        if isinstance(value, dict):
            return {k: stable(v) for k, v in value.items() if k != "updated_at"}
        if isinstance(value, list):
            return [stable(v) for v in value]
        return value

    async def reference(name, item, payload):
        engine = create_async_engine(
            URL.create(
                "mysql+asyncmy",
                username=env["CANGJIE_DB_USER"],
                password=env["CANGJIE_DB_PASSWORD"],
                host=env["CANGJIE_DB_HOST"],
                port=int(env["CANGJIE_DB_PORT"]),
                database=env["CANGJIE_DB_NAME"],
            )
        )
        try:
            async with engine.connect() as connection:
                outer = await connection.begin()
                try:
                    async with AsyncSession(
                        bind=connection,
                        join_transaction_mode="create_savepoint",
                        expire_on_commit=False,
                    ) as db:
                        return stable(
                            await namespace[name + "_review"](
                                task_id=item["id"],
                                payload=payload,
                                user=SimpleNamespace(id=teacher["id"], role="teacher"),
                                db=db,
                            )
                        )
                finally:
                    await outer.rollback()
        finally:
            await engine.dispose()

    def compared(item, name, payload):
        expected = asyncio.run(reference(name, item, payload))
        actual = operation(item, name, payload)
        assert stable(actual) == expected, (name, actual, expected)
        return actual

    current, link = new_case()
    for name in ("revoke", "regrade", "transfer"):
        operation(current, name, {}, expected=401, token=None)
        operation(current, name, {}, expected=403, token=st)
        operation(current, name, {}, expected=404, token=ot)
        native(
            endpoint,
            "GET",
            f"/api/v1/teachers/reviews/{current['id']}/{name}",
            tt,
            expected=405,
        )
        operation({"id": str(uuid4())}, name, {}, expected=404)
    operation(current, "revoke", {"reason": "尚未判定"}, expected=409)
    operation(current, "revoke", {}, expected=422)
    operation(
        current, "transfer", {"teacher_id": sid, "reason": "学生不能收取"}, expected=422
    )
    operation(
        current,
        "transfer",
        {"teacher_id": other_teacher["id"], "reason": "不属于班级"},
        expected=403,
    )
    operation(current, "transfer", {"teacher_id": teacher["id"]}, expected=422)
    current = compared(
        current, "transfer", {"teacher_id": teacher["id"], "reason": "确认班级负责人"}
    )
    assert current["assigned_teacher_id"] == teacher["id"]
    operation(current, "regrade", {"version": 0, "reason": "旧版本"}, expected=409)
    operation(current, "regrade", {"version": current["version"]}, expected=422)
    operation(
        current,
        "regrade",
        {
            "version": current["version"],
            "reason": "检查",
            "reference_steps": "不是数组",
        },
        expected=422,
    )
    before = json.loads(
        scalar(
            f"SELECT grading_details FROM assignment_attempts WHERE id='{current['source_id']}'"
        )
    )
    regraded = compared(
        current,
        "regrade",
        {
            "version": current["version"],
            "reason": "纠正识别与本次参考答案",
            "ocr_text": "x=6",
            "standard_answer": "x=6",
            "reference_steps": ["本次参考 x=6"],
        },
    )
    current = regraded["task"]
    assert regraded["grading"]["verdict"] == "confirmed_correct"
    assert (
        current["reason_codes"] == ["teacher_regrade_confirmation"]
        and current["status"] == "pending"
    )
    details = json.loads(
        scalar(
            f"SELECT grading_details FROM assignment_attempts WHERE id='{current['source_id']}'"
        )
    )
    assert details["original_grading"] == before and details["student_answer"] == "x=6"
    assert details["teacher_revision"]["standard_answer"] == "x=6"
    assert (
        scalar(
            f"SELECT answer FROM assignment_attempts WHERE id='{current['source_id']}'"
        )
        == "x=100"
    )
    assert (
        scalar(
            f"SELECT standard_answer FROM teacher_questions WHERE question_id='{qid}'"
        )
        == "x=5"
    )
    assert scalar(f"SELECT COUNT(*) FROM mastery_states WHERE user_id='{sid}'") == "0"
    # A revised answer still needs a teacher decision before it changes learning.
    reviewed = decide(current)
    assert reviewed["task"]["learning_applied"] and score() == "0.12\t1"
    current = compared(reviewed["task"], "revoke", {"reason": "撤回本次结论"})
    assert current["status"] == "pending" and not current["learning_applied"]
    assert score() == "0\t0"
    assert (
        scalar(
            f"SELECT probability,evidence_count FROM misconception_states WHERE user_id='{sid}'"
        )
        == "0.5\t1"
    )
    assert (
        scalar(f"SELECT status FROM assignment_students WHERE id='{link}'")
        == "review_pending"
    )
    assert (
        scalar(
            f"SELECT status FROM assignment_attempts WHERE id='{current['source_id']}'"
        )
        == "review_pending"
    )
    assert (
        scalar(
            f"SELECT COUNT(*) FROM teacher_review_results WHERE id='{reviewed['result']['id']}' AND revoked_at IS NOT NULL"
        )
        == "1"
    )
    assert native(endpoint, "GET", "/api/v1/students/teacher-feedback", st) == []
    operation(current, "revoke", {"reason": "重复撤回"}, expected=409)
    # Reversal must preserve newer learning rather than reset an old snapshot.
    reviewed = decide(current)
    query(
        env,
        f"UPDATE mastery_states SET mastery_score=0.7,evidence_count=9 WHERE user_id='{sid}'",
    )
    query(
        env,
        f"UPDATE misconception_states SET probability=0.2,evidence_count=9 WHERE user_id='{sid}'",
    )
    current = compared(reviewed["task"], "revoke", {"reason": "已有后续学习"})
    assert score() == "0.7\t9"
    assert (
        scalar(
            f"SELECT probability,evidence_count FROM misconception_states WHERE user_id='{sid}'"
        )
        == "0.2\t9"
    )
    assert (
        scalar(
            f"SELECT COUNT(*) FROM cognitive_updates WHERE user_id='{sid}' AND entity_type='teacher_review_reversal'"
        )
        == "2"
    )
    # No-learning decisions and old submissions have their own status paths.
    old, second_link = new_case(count=False)
    old_review = decide(old)
    newer = submit(second_link)
    decide(newer, conclusion="partially_correct")
    old = compared(old_review["task"], "revoke", {"reason": "撤销旧提交"})
    assert (
        scalar(f"SELECT status FROM assignment_students WHERE id='{second_link}'")
        == "completed"
    )
    assert (
        scalar(
            f"SELECT status FROM assignment_attempts WHERE id='{newer['source_id']}'"
        )
        == "graded"
    )
    assert score() == "0.7\t9"
    # Incomplete references remain in the queue even after a fresh calculation.
    uncertain = compared(
        current,
        "regrade",
        {
            "version": current["version"],
            "reason": "参考待补充",
            "standard_answer": "",
            "reference_steps": [],
        },
    )
    current = uncertain["task"]
    assert (
        "incomplete_reference" in current["reason_codes"]
        and not current["learning_applied"]
    )
    # One failed audit must undo every business write in that operation.
    query(
        env,
        "ALTER TABLE teacher_audit_logs ADD CONSTRAINT correction_audit_rollback CHECK (reason <> 'correction-rollback-probe')",
    )
    try:
        version = current["version"]
        operation(
            current,
            "transfer",
            {"teacher_id": teacher["id"], "reason": "correction-rollback-probe"},
            expected=503,
        )
        assert task(current["id"])["version"] == version
        previous = scalar(
            f"SELECT grading_details,version FROM assignment_attempts WHERE id='{current['source_id']}'"
        )
        operation(
            current,
            "regrade",
            {
                "version": version,
                "reason": "correction-rollback-probe",
                "ocr_text": "x=5",
            },
            expected=503,
        )
        assert (
            scalar(
                f"SELECT grading_details,version FROM assignment_attempts WHERE id='{current['source_id']}'"
            )
            == previous
        )
        assert task(current["id"])["version"] == version
        reviewed = decide(current)
        score_before = score()
        updates = scalar(
            f"SELECT COUNT(*) FROM cognitive_updates WHERE user_id='{sid}'"
        )
        operation(
            reviewed["task"],
            "revoke",
            {"reason": "correction-rollback-probe"},
            expected=503,
        )
        assert (
            score() == score_before
            and task(current["id"])["version"] == reviewed["task"]["version"]
        )
        assert (
            scalar(f"SELECT COUNT(*) FROM cognitive_updates WHERE user_id='{sid}'")
            == updates
        )
        assert (
            scalar(
                f"SELECT COUNT(*) FROM teacher_review_results WHERE id='{reviewed['result']['id']}' AND revoked_at IS NULL"
            )
            == "1"
        )
    finally:
        query(
            env, "ALTER TABLE teacher_audit_logs DROP CHECK correction_audit_rollback"
        )
    compared(reviewed["task"], "revoke", {"reason": "恢复既有学习基线"})
    assert score() == "0.7\t9"
    assert (
        scalar(
            f"SELECT probability,evidence_count FROM misconception_states WHERE user_id='{sid}'"
        )
        == "0.2\t9"
    )
    assert (
        scalar(
            f"SELECT COUNT(*) FROM teacher_audit_logs WHERE teacher_id='{teacher['id']}' AND action IN ('review.revoke','review.regrade','review.transfer')"
        )
        == "7"
    )
    print(
        "Cangjie review corrections passed: 3 routes, Python grading, guarded reversal, newer submission/learning preservation, permissions, audit rollback and original route parity"
    )
