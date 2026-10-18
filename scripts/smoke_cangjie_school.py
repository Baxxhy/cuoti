"""Teacher/guardian API contracts on real Cangjie HTTP and isolated MySQL."""

import ast
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from uuid import uuid4

from smoke_cangjie_accounts import request
from smoke_cangjie_detail import fixture_insert
from smoke_cangjie_insights import comparable


def native(endpoint, method, path, token=None, payload=None, expected=200):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    try:
        response = urlopen(
            Request(
                endpoint + path,
                method=method,
                headers=headers,
                data=json.dumps(payload).encode() if payload is not None else None,
            ),
            timeout=15,
        )
    except HTTPError as error:
        response = error
    with response:
        value = json.load(response)
        assert response.status == expected, (path, response.status, value)
    assert "password_hash" not in json.dumps(value)
    if expected == 200:
        assert not isinstance(value, dict) or "success" not in value, (path, value)
        return value
    return expected


def reference_routes():
    project = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(project / "backend"))
    from app import models
    from app.services.timestamps import iso_timestamp
    from fastapi import HTTPException
    from sqlalchemy import func, select

    namespace = {
        **vars(models),
        "select": select,
        "func": func,
        "datetime": datetime,
        "timezone": timezone,
        "HTTPException": HTTPException,
        "iso_timestamp": iso_timestamp,
        "envelope": lambda data: data,
    }
    sources = {
        "main.py": {
            "row_dict",
            "user_dict",
            "guardian_students",
            "student_report",
            "teacher_classes",
            "teacher_class",
        },
        "teacher_api.py": {
            "dashboard",
            "student_plans",
            "audit_logs",
            "_row",
            "_managed_class",
            "_managed_student",
        },
    }
    functions = []
    for filename, names in sources.items():
        tree = ast.parse((project / "backend/app" / filename).read_text())
        selected = [
            node
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name in names
        ]
        assert len(selected) == len(names)
        for node in selected:
            node.decorator_list = []
            node.args.defaults = []
            node.args.kw_defaults = [None] * len(node.args.kwonlyargs)
            node.returns = None
            for arg in (*node.args.args, *node.args.kwonlyargs):
                arg.annotation = None
            functions.append(node)
    exec(  # noqa: S102 -- selected tracked reference functions, isolated test DB only
        compile(
            ast.Module(body=functions, type_ignores=[]),
            "<reference-school-routes>",
            "exec",
        ),
        namespace,
    )
    return namespace


def school(endpoint, env, query):
    insert = fixture_insert(env, query)

    def account(role="student"):
        result = request(
            endpoint,
            "POST",
            "/api/v1/auth/register",
            {
                "email": f"school-{uuid4().hex}@example.test",
                "name": "学校功能检查",
                "password": "school-test-123",
            },
        )
        if role != "student":
            query(env, f"UPDATE users SET role='{role}' WHERE id='{result['id']}'")
        return result

    teacher, other_teacher, guardian, unlinked_guardian, student, other_student = (
        account("teacher"),
        account("teacher"),
        account("guardian"),
        account("guardian"),
        account(),
        account(),
    )
    tt, ot, gt, ut, st = (
        item["access_token"]
        for item in (teacher, other_teacher, guardian, unlinked_guardian, student)
    )
    tid, sid = teacher["id"], student["id"]
    assert request(endpoint, "GET", "/api/v1/teachers/classes", token=tt) == []
    assert (
        native(endpoint, "GET", "/api/v1/teachers/dashboard", tt)["pending_reviews"]
        == 0
    )
    assert request(endpoint, "GET", "/api/v1/guardians/students", token=gt) == []
    assert native(endpoint, "GET", "/api/v1/teachers/audit-logs", tt) == []
    for path in ("/api/v1/teachers/dashboard", "/api/v1/teachers/audit-logs"):
        native(endpoint, "GET", path, expected=401)
        native(endpoint, "GET", path, st, expected=403)
    request(endpoint, "GET", "/api/v1/teachers/classes", token=st, expected=403)
    request(endpoint, "GET", "/api/v1/guardians/students", token=tt, expected=403)
    native(
        endpoint, "POST", "/api/v1/teachers/classes", tt, {"name": "   "}, expected=422
    )
    classroom = native(
        endpoint,
        "POST",
        "/api/v1/teachers/classes",
        tt,
        {
            "name": "  仓颉验证班  ",
            "grade": "初二",
            "teacher_id": other_teacher["id"],
            "reason": "建立教学班",
        },
    )
    cid = classroom["id"]
    assert classroom["name"] == "仓颉验证班" and classroom["teacher_id"] == tid
    collection = request(endpoint, "GET", "/api/v1/teachers/classes", token=tt)
    assert collection == [{**classroom, "student_count": 0}]
    class_path = "/api/v1/teachers/classes/" + cid
    assert request(endpoint, "GET", class_path, token=tt)["students"] == []
    request(endpoint, "GET", class_path, token=ot, expected=404)
    native(
        endpoint,
        "POST",
        class_path + "/students",
        ot,
        {"email": student["email"]},
        expected=404,
    )
    native(
        endpoint,
        "POST",
        class_path + "/students",
        tt,
        {"email": teacher["email"]},
        expected=404,
    )
    native(
        endpoint,
        "POST",
        class_path + "/students",
        tt,
        {"email": "' OR 1=1 --"},
        expected=404,
    )
    enrolled = native(
        endpoint,
        "POST",
        class_path + "/students",
        tt,
        {"email": "  " + student["email"].upper() + "  "},
    )
    assert enrolled == {k: student[k] for k in ("id", "email", "name")}
    assert (
        native(
            endpoint, "POST", class_path + "/students", tt, {"email": student["email"]}
        )
        == enrolled
    )
    logs = native(endpoint, "GET", "/api/v1/teachers/audit-logs", tt)
    assert len(logs) == 2 and {item["action"] for item in logs} == {
        "class.create",
        "class.student.add",
    }
    assert all(item["teacher_id"] == tid for item in logs)
    assert native(endpoint, "GET", "/api/v1/teachers/audit-logs", ot) == []

    insert("guardian_student_links", guardian_id=guardian["id"], student_id=sid)
    assert [
        item["id"]
        for item in request(endpoint, "GET", "/api/v1/guardians/students", token=gt)
    ] == [sid]
    question = request(
        endpoint,
        "POST",
        "/api/v1/questions/manual",
        {"question_text": "学校报告验证题"},
        token=st,
    )
    qid = question["id"]
    insert(
        "mastery_states",
        user_id=sid,
        subject="数学",
        knowledge_point="方程",
        mastery_score=0.8,
        confidence=0.9,
    )
    insert(
        "mastery_states",
        user_id=sid,
        subject="数学",
        knowledge_point="函数",
        mastery_score=0.4,
        confidence=0.7,
    )
    insert(
        "misconception_states",
        user_id=sid,
        subject="数学",
        code="sign",
        label="符号错误",
        probability=0.75,
    )
    insert(
        "misconception_states",
        user_id=sid,
        subject="数学",
        code="resolved",
        label="已解决错因",
        status="resolved",
        probability=0.1,
    )
    insert(
        "mastery_states",
        user_id=other_student["id"],
        subject="数学",
        knowledge_point="外班私密点",
        mastery_score=0.99,
    )
    insert(
        "cognitive_updates",
        user_id=sid,
        question_id=qid,
        entity_type="mastery",
        entity_key="函数",
        new_value=0.4,
    )
    insert("tutor_sessions", user_id=sid, question_id=qid, status="completed")
    plan = insert(
        "review_plans", user_id=sid, question_id=qid, due_at="2026-01-01 00:00:00"
    )
    insert("review_records", plan_id=plan, grade="good", correct=True)
    assignment = insert(
        "question_assignments", teacher_id=tid, class_id=cid, question_id=qid
    )
    insert("assignment_students", assignment_id=assignment, student_id=sid)
    insert(
        "teacher_review_tasks",
        class_id=cid,
        student_id=sid,
        question_id=qid,
        source_id=str(uuid4()),
    )
    # An unrelated teacher's task must not leak into this dashboard.
    foreign_class = native(
        endpoint, "POST", "/api/v1/teachers/classes", ot, {"name": "外班"}
    )["id"]
    foreign_q = request(
        endpoint,
        "POST",
        "/api/v1/questions/manual",
        {"question_text": "外班专属题"},
        token=other_student["access_token"],
    )["id"]
    insert(
        "teacher_review_tasks",
        class_id=foreign_class,
        student_id=other_student["id"],
        question_id=foreign_q,
        source_id=str(uuid4()),
    )
    report_path = "/api/v1/teachers/students/" + sid + "/report"
    overview_path = "/api/v1/guardians/students/" + sid + "/overview"
    report = request(endpoint, "GET", report_path, token=tt)
    assert report == request(endpoint, "GET", overview_path, token=gt)
    assert report["summary"] == {
        "questions": 1,
        "completed_sessions": 1,
        "review_records": 1,
    }
    assert "函数" in report["suggestion"]
    for token in (ot, ut, st):
        request(endpoint, "GET", report_path, token=token, expected=403)
    assert (
        request(endpoint, "GET", class_path, token=tt)["students"][0][
            "active_misconceptions"
        ]
        == 1
    )
    dashboard = native(endpoint, "GET", "/api/v1/teachers/dashboard", tt)
    assert (
        dashboard["pending_reviews"] == 1 and dashboard["unfinished_assignments"] == 1
    )
    assert dashboard["overdue_students"] == 1 and dashboard["average_mastery"] == 0.6
    assert dashboard["frequent_errors"] == [{"name": "符号错误", "probability": 0.75}]
    assert dashboard["attention_students"] == [
        {"id": sid, "name": student["name"], "pending_reviews": 1}
    ]

    plan_path = "/api/v1/teachers/plans/" + plan
    student_plans = "/api/v1/teachers/students/" + sid + "/plans"
    native(endpoint, "GET", student_plans, tt, expected=422)
    native(
        endpoint,
        "GET",
        student_plans + "?" + urlencode({"class_id": cid}),
        ot,
        expected=404,
    )
    plans = native(
        endpoint, "GET", student_plans + "?" + urlencode({"class_id": cid}), tt
    )
    assert len(plans) == 1 and plans[0]["id"] == plan
    native(endpoint, "PATCH", plan_path, tt, {"class_id": cid}, expected=422)
    native(
        endpoint,
        "PATCH",
        plan_path,
        ot,
        {"class_id": cid, "reason": "越权"},
        expected=404,
    )
    before = dict(plans[0])
    native(
        endpoint,
        "PATCH",
        plan_path,
        tt,
        {"class_id": cid, "reason": "错误时间", "due_at": "2030-02-30T12:00:00+08:00"},
        expected=422,
    )
    assert native(
        endpoint, "GET", student_plans + "?" + urlencode({"class_id": cid}), tt
    ) == [before]
    for date, utc in [
        ("2030-01-02T18:30:00+08:00", "2030-01-02T10:30:00+00:00"),
        ("2030-01-03T10:15", "2030-01-03T10:15:00+00:00"),
        ("2030-01-04", "2030-01-04T00:00:00+00:00"),
        ("2030-01-05T10:15:00Z", "2030-01-05T10:15:00+00:00"),
    ]:
        changed = native(
            endpoint,
            "PATCH",
            plan_path,
            tt,
            {
                "class_id": cid,
                "reason": "调整复习",
                "task_reason": "先巩固函数",
                "status": "paused",
                "due_at": date,
            },
        )
        assert changed["due_at"] == utc and changed["status"] == "paused"
        assert changed["reason"] == "先巩固函数"
    ignored = native(
        endpoint,
        "PATCH",
        plan_path,
        tt,
        {
            "class_id": cid,
            "reason": "状态白名单",
            "status": "completed",
            "user_id": other_student["id"],
        },
    )
    assert ignored["status"] == "paused" and ignored["user_id"] == sid

    # Audit failure must roll back each kind of business change.
    query(
        env,
        "ALTER TABLE teacher_audit_logs ADD CONSTRAINT school_audit_rollback CHECK (reason <> 'rollback-probe')",
    )
    try:
        count = len(request(endpoint, "GET", "/api/v1/teachers/classes", token=tt))
        native(
            endpoint,
            "POST",
            "/api/v1/teachers/classes",
            tt,
            {"name": "回滚班级", "reason": "rollback-probe"},
            expected=503,
        )
        assert (
            len(request(endpoint, "GET", "/api/v1/teachers/classes", token=tt)) == count
        )
        native(
            endpoint,
            "POST",
            class_path + "/students",
            tt,
            {"email": other_student["email"], "reason": "rollback-probe"},
            expected=503,
        )
        assert [
            u["id"] for u in request(endpoint, "GET", class_path, token=tt)["students"]
        ] == [sid]
        native(
            endpoint,
            "DELETE",
            class_path + "/students/" + sid + "?reason=rollback-probe",
            tt,
            expected=503,
        )
        assert request(endpoint, "GET", report_path, token=tt)["student"]["id"] == sid
        native(
            endpoint,
            "PATCH",
            plan_path,
            tt,
            {"class_id": cid, "reason": "rollback-probe", "status": "cancelled"},
            expected=503,
        )
        assert native(
            endpoint, "GET", student_plans + "?" + urlencode({"class_id": cid}), tt
        ) == [ignored]
    finally:
        query(env, "ALTER TABLE teacher_audit_logs DROP CHECK school_audit_rollback")

    async def parity():
        from sqlalchemy.engine import URL
        from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

        reference = reference_routes()
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
            async with async_sessionmaker(engine)() as db:
                t = SimpleNamespace(id=tid, role="teacher")
                g = SimpleNamespace(id=guardian["id"], role="guardian")
                pairs = [
                    (
                        request(endpoint, "GET", "/api/v1/teachers/classes", token=tt),
                        await reference["teacher_classes"](user=t, db=db),
                    ),
                    (
                        request(endpoint, "GET", class_path, token=tt),
                        await reference["teacher_class"](class_id=cid, user=t, db=db),
                    ),
                    (
                        request(
                            endpoint, "GET", "/api/v1/guardians/students", token=gt
                        ),
                        await reference["guardian_students"](user=g, db=db),
                    ),
                    (
                        request(endpoint, "GET", report_path, token=tt),
                        await reference["student_report"](
                            student_id=sid, account=t, db=db
                        ),
                    ),
                    (
                        native(endpoint, "GET", "/api/v1/teachers/dashboard", tt),
                        await reference["dashboard"](user=t, db=db),
                    ),
                    (
                        native(
                            endpoint,
                            "GET",
                            student_plans + "?" + urlencode({"class_id": cid}),
                            tt,
                        ),
                        await reference["student_plans"](
                            student_id=sid, class_id=cid, user=t, db=db
                        ),
                    ),
                ]
                for actual, expected in pairs:
                    assert actual == comparable(expected), (
                        actual,
                        comparable(expected),
                    )
                actual = native(endpoint, "GET", "/api/v1/teachers/audit-logs", tt)
                expected = comparable(await reference["audit_logs"](user=t, db=db))
                assert sorted(actual, key=lambda row: row["id"]) == sorted(
                    expected, key=lambda row: row["id"]
                )
        finally:
            await engine.dispose()

    asyncio.run(parity())
    native(endpoint, "DELETE", class_path + "/students/" + sid, tt, expected=422)
    native(
        endpoint,
        "DELETE",
        class_path + "/students/" + sid + "?reason=remove",
        ot,
        expected=404,
    )
    removed = native(
        endpoint,
        "DELETE",
        class_path + "/students/" + sid + "?" + urlencode({"reason": "调班"}),
        tt,
    )
    assert removed == {"removed": True}
    assert request(endpoint, "GET", class_path, token=tt)["students"] == []
    request(endpoint, "GET", report_path, token=tt, expected=403)
    native(
        endpoint,
        "GET",
        student_plans + "?" + urlencode({"class_id": cid}),
        tt,
        expected=404,
    )
    assert request(endpoint, "GET", overview_path, token=gt)["student"]["id"] == sid
    assert (
        native(endpoint, "GET", "/api/v1/teachers/dashboard", tt)["pending_reviews"]
        == 1
    )
    # Review tasks remain a persisted teacher responsibility after class removal.
    assert (
        native(endpoint, "GET", "/api/v1/teachers/dashboard", tt)["overdue_students"]
        == 0
    )
    from smoke_cangjie_guardian_links import guardian_links

    guardian_links(endpoint, env, query)
    print(
        "Cangjie school passed: 12 route contracts, classes, enrollment, guardian/reports, dashboard, plans/timezones, audit rollback and original parity"
    )
