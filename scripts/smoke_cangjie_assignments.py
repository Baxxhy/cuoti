"""Real student assignment lifecycle, Python grading/cognition, teacher decisions."""

import ast
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlencode, urlsplit
from uuid import uuid4

from smoke_cangjie_accounts import request
from smoke_cangjie_detail import fixture_insert
from smoke_cangjie_handwriting import handwriting
from smoke_cangjie_insights import comparable
from smoke_cangjie_school import native


def assignments(endpoint, env, query, state):
    insert = fixture_insert(env, query)

    def account(role="student"):
        item = request(
            endpoint,
            "POST",
            "/api/v1/auth/register",
            {
                "email": f"assignment-{uuid4().hex}@example.test",
                "name": "作业验证",
                "password": "assignment-test-123",
            },
        )
        if role != "student":
            query(env, f"UPDATE users SET role='{role}' WHERE id='{item['id']}'")
        return item

    teacher, other_teacher, student, other = (
        account("teacher"),
        account("teacher"),
        account(),
        account(),
    )
    tt, ot, st, xt = (
        item["access_token"] for item in (teacher, other_teacher, student, other)
    )
    sid = student["id"]
    classroom = native(
        endpoint, "POST", "/api/v1/teachers/classes", tt, {"name": "作业流程班"}
    )
    cid = classroom["id"]
    native(
        endpoint,
        "POST",
        f"/api/v1/teachers/classes/{cid}/students",
        tt,
        {"email": student["email"]},
    )

    def question(**fields):
        return native(
            endpoint,
            "POST",
            "/api/v1/teachers/questions",
            tt,
            {
                "question_text": "解方程：3*x=15",
                "question_type": "填空题",
                "knowledge_points": ["一次方程"],
                "standard_answer": "x=5",
                "reference_steps": ["3x=15", "x=5"],
                **fields,
            },
        )

    q = question()
    qid = q["question"]["id"]

    def assign(question_id=qid, **settings):
        return native(
            endpoint,
            "POST",
            "/api/v1/teachers/assignments",
            tt,
            {
                "class_id": cid,
                "question_id": question_id,
                "student_ids": [sid],
                "due_at": "2030-01-02T18:30:00+08:00",
                "settings": settings,
            },
        )

    def tasks(token=st):
        return native(endpoint, "GET", "/api/v1/students/assignments", token)

    def link(assignment_id):
        return next(
            item for item in tasks() if item["assignment"]["id"] == assignment_id
        )

    def submit(link_id, answer="x=5", expected=200, **fields):
        return native(
            endpoint,
            "POST",
            f"/api/v1/students/assignments/{link_id}/attempts",
            st,
            {"answer": answer, "steps": ["3x=15", "x=5"], **fields},
            expected=expected,
        )

    def queue():
        return native(endpoint, "GET", "/api/v1/teachers/reviews", tt)

    def task_for(attempt):
        return next(item for item in queue() if item["source_id"] == attempt["id"])

    def decide(task, conclusion="confirmed_correct", expected=200, **fields):
        return native(
            endpoint,
            "POST",
            f"/api/v1/teachers/reviews/{task['id']}/decision",
            tt,
            {
                "version": task["version"],
                "conclusion": conclusion,
                "reason": "按作答证据复核",
                "student_hint": "先检查等式两边",
                "next_task": "独立再练一道题",
                **fields,
            },
            expected=expected,
        )

    assert native(endpoint, "GET", "/api/v1/teachers/questions", ot) == []
    native(endpoint, "GET", "/api/v1/teachers/questions", st, expected=403)
    native(endpoint, "GET", "/api/v1/students/assignments", tt, expected=403)
    native(
        endpoint,
        "POST",
        "/api/v1/teachers/questions",
        st,
        {"question_text": "越权"},
        expected=403,
    )
    native(
        endpoint,
        "POST",
        "/api/v1/teachers/assignments",
        ot,
        {"class_id": cid, "question_id": qid},
        expected=404,
    )
    native(
        endpoint,
        "POST",
        "/api/v1/teachers/assignments",
        tt,
        {"class_id": cid, "question_id": qid, "student_ids": [other["id"]]},
        expected=403,
    )
    native(
        endpoint,
        "POST",
        "/api/v1/teachers/assignments",
        tt,
        {"class_id": cid, "question_id": qid, "due_at": "bad-date"},
        expected=422,
    )
    automatic = assign(allow_repeat=True)
    item = link(automatic["id"])
    lid = item["student_assignment"]["id"]
    assert item["assignment"]["due_at"] == "2030-01-02T10:30:00+00:00"
    assert item["latest_attempt"] is None and "teacher_question" not in item
    assert item["question"]["student_answer"] is None
    assert tasks(xt) == []
    native(
        endpoint,
        "POST",
        f"/api/v1/students/assignments/{lid}/attempts",
        xt,
        {"answer": "x=5"},
        expected=404,
    )
    submit(lid, answer="", expected=422)
    first = submit(lid)
    assert (
        first["grading"]["verdict"] == "confirmed_correct"
        and not first["entered_review_queue"]
    )
    assert link(automatic["id"])["student_assignment"]["status"] == "completed"
    assert link(automatic["id"])["grading_feedback"]
    assert (
        query(
            env, f"SELECT mastery_score FROM mastery_states WHERE user_id='{sid}'"
        ).strip()
        == "0.12"
    )
    second = submit(lid, answer="x=100")
    assert (
        not second["entered_review_queue"]
        and second["grading"]["verdict"] == "confirmed_incorrect"
    )
    assert (
        query(
            env,
            f"SELECT COUNT(*) FROM assignment_attempts WHERE assignment_student_id='{lid}'",
        ).strip()
        == "2"
    )
    assert (
        query(
            env, f"SELECT evidence_count FROM mastery_states WHERE user_id='{sid}'"
        ).strip()
        == "2"
    )

    # Assignment policy can disable automatic grading independently of question metadata.
    teacher_only = assign(allow_auto_grade=False, count_mastery=False)
    teacher_only_link = link(teacher_only["id"])["student_assignment"]["id"]
    teacher_pending = submit(teacher_only_link)
    assert teacher_pending["grading"]["method"] == "teacher_pending"
    assert teacher_pending["entered_review_queue"]
    teacher_only_decision = decide(task_for(teacher_pending["attempt"]))
    assert not teacher_only_decision["result"]["allow_learning_update"]
    assert (
        query(
            env, f"SELECT evidence_count FROM mastery_states WHERE user_id='{sid}'"
        ).strip()
        == "2"
    )

    hand_question = question(allow_auto_grade=False, require_handwriting=True)
    handwritten = assign(
        question_id=hand_question["question"]["id"], require_teacher_review=True
    )
    hand_link = link(handwritten["id"])["student_assignment"]["id"]
    submit(hand_link, expected=422)
    written = handwriting(
        endpoint,
        env,
        st,
        xt,
        {"id": hand_link, "activity": {"id": ""}},
        state,
        kind="assignment",
    )
    aliased = {
        **written,
        "handwriting_image_url": "",
        "handwriting_asset_ref": written["handwriting_image_url"],
    }
    pending = submit(hand_link, **aliased)
    assert (
        pending["entered_review_queue"]
        and not pending["grading"]["can_update_learning"]
    )
    assert (
        query(
            env, f"SELECT evidence_count FROM mastery_states WHERE user_id='{sid}'"
        ).strip()
        == "2"
    )
    task = task_for(pending["attempt"])
    assert {"auto_grade_disabled", "teacher_required"} <= set(task["reason_codes"])
    assert (
        native(
            endpoint,
            "GET",
            "/api/v1/teachers/reviews?" + urlencode({"subject": "英语"}),
            tt,
        )
        == []
    )
    assert any(
        item["id"] == task["id"]
        for item in native(
            endpoint,
            "GET",
            "/api/v1/teachers/reviews?"
            + urlencode(
                {"class_id": cid, "conflict": "false", "verdict": "review_required"}
            ),
            tt,
        )
    )
    native(
        endpoint,
        "GET",
        "/api/v1/teachers/reviews?" + urlencode({"class_id": cid}),
        ot,
        expected=404,
    )
    native(endpoint, "GET", "/api/v1/teachers/reviews", st, expected=403)
    submit(hand_link, expected=409, **written)
    detail = native(endpoint, "GET", f"/api/v1/teachers/reviews/{task['id']}", tt)
    assert (
        detail["attempt"]["handwriting_image_url"]
        and "signature=" in detail["attempt"]["handwriting_image_url"]
    )
    native(endpoint, "GET", f"/api/v1/teachers/reviews/{task['id']}", ot, expected=404)
    native(
        endpoint,
        "POST",
        f"/api/v1/teachers/reviews/{task['id']}/decision",
        ot,
        {
            "version": task["version"],
            "conclusion": "confirmed_correct",
            "reason": "越权",
        },
        expected=404,
    )
    decide(task, version=0, expected=409)
    decide(task, conclusion="invented", expected=422)
    reviewed = decide(task)
    assert (
        reviewed["task"]["status"] == "resolved"
        and reviewed["task"]["learning_applied"]
    )
    assert (
        reviewed["result"]["learning_snapshot"]["mastery_after"]["evidence_count"] == 3
    )
    decide(task, expected=409)
    shown = link(handwritten["id"])
    assert shown["student_assignment"]["status"] == "completed"
    assert shown["teacher_feedback"]["student_hint"] == "先检查等式两边"
    assert shown["latest_attempt"]["answer"] == "x=5"
    assert (
        native(endpoint, "GET", "/api/v1/students/teacher-feedback", st)[0]["result"][
            "id"
        ]
        == reviewed["result"]["id"]
    )
    assert native(endpoint, "GET", "/api/v1/students/teacher-feedback", xt) == []

    # Resubmit and question-issue conclusions change both task and student state.
    manual_question = question(allow_auto_grade=False)
    retry = assign(question_id=manual_question["question"]["id"], count_mastery=False)
    retry_link = link(retry["id"])["student_assignment"]["id"]
    attempt = submit(retry_link)
    retry_task = task_for(attempt["attempt"])
    resubmit = decide(retry_task, conclusion="resubmit")
    assert (
        resubmit["task"]["status"] == "resubmit"
        and not resubmit["result"]["allow_learning_update"]
    )
    assert link(retry["id"])["student_assignment"]["status"] == "pending"
    attempt2 = submit(retry_link)
    new_task = task_for(attempt2["attempt"])
    issue = decide(new_task, conclusion="question_issue")
    assert issue["task"]["status"] == "question_issue"
    assert link(retry["id"])["student_assignment"]["status"] == "question_issue"
    submit(retry_link, expected=409)
    assert (
        query(
            env, f"SELECT evidence_count FROM mastery_states WHERE user_id='{sid}'"
        ).strip()
        == "3"
    )

    old_case = assign(
        question_id=manual_question["question"]["id"], count_mastery=False
    )
    old_link = link(old_case["id"])["student_assignment"]["id"]
    old_attempt = submit(old_link)
    old_task = task_for(old_attempt["attempt"])
    newer = insert(
        "assignment_attempts",
        assignment_student_id=old_link,
        student_id=sid,
        question_id=manual_question["question"]["id"],
        answer="新的作答",
        status="review_pending",
        version=2,
    )
    query(
        env,
        f"UPDATE assignment_students SET latest_attempt_id='{newer}' WHERE id='{old_link}'",
    )
    old_decision = decide(old_task)
    assert not old_decision["result"]["allow_learning_update"]
    assert link(old_case["id"])["student_assignment"]["status"] == "review_pending"
    assert link(old_case["id"])["latest_attempt"]["answer"] == "新的作答"

    # Inject audit failure to prove record, task and cognition updates roll back together.
    rollback_case = assign(question_id=manual_question["question"]["id"])
    rollback_link = link(rollback_case["id"])["student_assignment"]["id"]
    rollback_attempt = submit(rollback_link)
    rollback_task = task_for(rollback_attempt["attempt"])
    query(
        env,
        "ALTER TABLE teacher_audit_logs ADD CONSTRAINT assignment_audit_rollback CHECK (reason <> 'assignment-rollback-probe')",
    )
    try:
        before_count = query(env, "SELECT COUNT(*) FROM teacher_questions").strip()
        native(
            endpoint,
            "POST",
            "/api/v1/teachers/questions",
            tt,
            {"question_text": "回滚题目", "reason": "assignment-rollback-probe"},
            expected=503,
        )
        assert (
            query(env, "SELECT COUNT(*) FROM teacher_questions").strip() == before_count
        )
        before_assign = query(env, "SELECT COUNT(*) FROM question_assignments").strip()
        native(
            endpoint,
            "POST",
            "/api/v1/teachers/assignments",
            tt,
            {
                "class_id": cid,
                "question_id": qid,
                "reason": "assignment-rollback-probe",
            },
            expected=503,
        )
        assert (
            query(env, "SELECT COUNT(*) FROM question_assignments").strip()
            == before_assign
        )
        decide(rollback_task, reason="assignment-rollback-probe", expected=503)
        assert (
            task_for(rollback_attempt["attempt"])["version"] == rollback_task["version"]
        )
        assert (
            query(
                env, f"SELECT evidence_count FROM mastery_states WHERE user_id='{sid}'"
            ).strip()
            == "3"
        )
        assert (
            link(rollback_case["id"])["student_assignment"]["status"]
            == "review_pending"
        )
    finally:
        query(
            env, "ALTER TABLE teacher_audit_logs DROP CHECK assignment_audit_rollback"
        )
    decide(rollback_task, conclusion="partially_correct")
    assert link(rollback_case["id"])["student_assignment"]["status"] == "completed"
    assert (
        query(
            env, f"SELECT evidence_count FROM mastery_states WHERE user_id='{sid}'"
        ).strip()
        == "3"
    )

    async def parity():
        from app import models
        from app.media import sign_media_url
        from app.services.timestamps import iso_timestamp
        from fastapi import HTTPException
        from sqlalchemy import select
        from sqlalchemy.engine import URL
        from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

        names = {
            "teacher_questions",
            "assignments",
            "student_assignments",
            "student_feedback",
            "review_queue",
            "review_detail",
            "_row",
            "_managed_class",
            "_managed_student",
        }
        tree = ast.parse(
            (
                Path(__file__).resolve().parents[1] / "backend/app/teacher_api.py"
            ).read_text()
        )
        functions = []
        for node in ast.walk(tree):
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
        from sqlalchemy import func

        ns = {
            **vars(models),
            "select": select,
            "func": func,
            "datetime": datetime,
            "timezone": timezone,
            "HTTPException": HTTPException,
            "iso_timestamp": iso_timestamp,
            "settings": SimpleNamespace(auth_secret=env["CANGJIE_AUTH_SECRET"]),
            "sign_media_url": sign_media_url,
        }
        exec(  # noqa: S102 -- selected local reference routes and isolated MySQL only
            compile(
                ast.Module(body=functions, type_ignores=[]),
                "<reference-assignment-routes>",
                "exec",
            ),
            ns,
        )
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

        def stable(value):
            value = comparable(value)
            if isinstance(value, list):
                if not all(
                    isinstance(item, dict)
                    and any(
                        key in item
                        for key in ("id", "assignment", "question", "result")
                    )
                    for item in value
                ):
                    return [stable(item) for item in value]
                return sorted(
                    [stable(item) for item in value],
                    key=lambda item: str(
                        item.get(
                            "id",
                            item.get("assignment", {}).get(
                                "id",
                                item.get("question", {}).get(
                                    "id", item.get("result", {}).get("id", "")
                                ),
                            ),
                        )
                    ),
                )
            if isinstance(value, dict):
                return {
                    key: (
                        urlsplit(item).path
                        if isinstance(item, str) and "signature=" in item
                        else stable(item)
                    )
                    for key, item in value.items()
                    if key != "waiting_minutes"
                }
            return value

        try:
            async with async_sessionmaker(engine)() as db:
                teacher_user = SimpleNamespace(id=teacher["id"], role="teacher")
                student_user = SimpleNamespace(id=sid, role="student")
                for path, name, user in [
                    ("/teachers/questions", "teacher_questions", teacher_user),
                    ("/teachers/assignments", "assignments", teacher_user),
                    ("/students/assignments", "student_assignments", student_user),
                    ("/students/teacher-feedback", "student_feedback", student_user),
                ]:
                    actual = native(
                        endpoint,
                        "GET",
                        "/api/v1" + path,
                        tt if user == teacher_user else st,
                    )
                    expected = await ns[name](user=user, db=db)
                    assert stable(actual) == stable(expected), (
                        name,
                        actual,
                        comparable(expected),
                    )
                actual = queue()
                expected = await ns["review_queue"](
                    class_id=None,
                    student_id=None,
                    subject=None,
                    verdict=None,
                    conflict=None,
                    user=teacher_user,
                    db=db,
                )
                assert stable(actual) == stable(expected), (
                    actual,
                    comparable(expected),
                )
                actual = native(
                    endpoint, "GET", f"/api/v1/teachers/reviews/{task['id']}", tt
                )
                expected = await ns["review_detail"](
                    task_id=task["id"], user=teacher_user, db=db
                )
                assert stable(actual) == stable(expected), (
                    actual,
                    comparable(expected),
                )
        finally:
            await engine.dispose()

    asyncio.run(parity())
    print(
        "Cangjie assignments passed: 10 routes, teacher catalog/assignment, student answers/handwriting, Python grading/cognition, review/feedback, rollback and original parity"
    )
