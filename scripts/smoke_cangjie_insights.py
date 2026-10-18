"""Real HTTP/MySQL checks and differential checks against original Python routes.

Only selected functions are compiled from the original source. They use an
explicit disposable test DB session, never the original backend or its settings.
"""

import ast
import asyncio
import re
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import quote, urlencode
from uuid import uuid4

from smoke_cangjie_accounts import request
from smoke_cangjie_detail import fixture_insert


def original_routes():
    project = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(project / "backend"))
    from app import models
    from app.services.knowledge_base import search_knowledge_cards
    from app.services.question_mapping import student_facing_topic
    from sqlalchemy import func, select

    names = {
        "analytics",
        "dashboard",
        "cognition_graph",
        "knowledge_cards",
        "knowledge_card",
        "learning_method_label",
        "canonical_misconception_label",
        "learner_text",
        "question_display_key",
    }
    module = ast.parse((project / "backend/app/main.py").read_text())
    functions = []
    for node in module.body:
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
        "select": select,
        "func": func,
        "datetime": datetime,
        "timezone": timezone,
        "timedelta": timedelta,
        "re": re,
        "search_knowledge_cards": search_knowledge_cards,
        "student_facing_topic": student_facing_topic,
        "row_dict": lambda row: {
            column.name: getattr(row, column.name) for column in row.__table__.columns
        },
        "envelope": lambda data: data,
    }
    exec(  # noqa: S102 -- tracked local reference functions only
        compile(
            ast.Module(body=functions, type_ignores=[]),
            "<original-insight-routes>",
            "exec",
        ),
        namespace,
    )
    return namespace


def comparable(value):
    if isinstance(value, datetime):
        return value.replace(tzinfo=timezone.utc).isoformat()
    if isinstance(value, dict):
        return {k: comparable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [comparable(v) for v in value]
    return value


def graph_comparable(value):
    value = comparable(value)
    # Strategy sets and DB row order do not carry an API ordering guarantee.
    value["nodes"] = sorted(value["nodes"], key=lambda node: node["id"])
    value["links"] = sorted(
        value["links"],
        key=lambda edge: (edge["source"], edge["target"], edge["relation"]),
    )
    return value


def insights(endpoint, env, query):
    insert = fixture_insert(env, query)

    def register():
        return request(
            endpoint,
            "POST",
            "/api/v1/auth/register",
            {
                "email": f"insights-{uuid4().hex}@example.test",
                "password": "insights-test-123",
                "name": "档案检查",
            },
        )

    account, other = register(), register()
    token, other_token = account["access_token"], other["access_token"]
    owner = request(endpoint, "GET", "/api/v1/auth/me", token=token)["id"]
    other_id = request(endpoint, "GET", "/api/v1/auth/me", token=other_token)["id"]
    empty_dashboard = request(endpoint, "GET", "/api/v1/dashboard", token=token)
    assert empty_dashboard["weekly_questions"] == 0
    assert empty_dashboard["estimated_minutes"] == 0
    assert empty_dashboard["continue_learning"] is None
    request(endpoint, "GET", "/api/v1/dashboard", expected=401)
    request(endpoint, "POST", "/api/v1/dashboard", token=token, expected=405)
    aliases = ["overview"]
    for suffix in aliases:
        path = "/api/v1/analytics/" + suffix
        assert request(endpoint, "GET", path, token=token) == {
            "mastery": [],
            "misconceptions": [],
            "trend": [],
            "summary": {
                "knowledge_count": 0,
                "misconception_count": 0,
                "evidence_count": 0,
            },
        }
        request(endpoint, "GET", path, expected=401)
        request(endpoint, "POST", path, token=token, expected=405)
        for days in ("0", "366", "x", "1.5", ""):
            request(endpoint, "GET", path + "?days=" + days, token=token, expected=422)
    assert (
        request(endpoint, "GET", "/api/v1/analytics/cognition-graph", token=token)[
            "nodes"
        ]
        == []
    )
    request(endpoint, "GET", "/api/v1/analytics/cognition-graph", expected=401)
    for days in ("0", "3651", "NaN"):
        request(
            endpoint,
            "GET",
            "/api/v1/analytics/cognition-graph?days=" + days,
            token=token,
            expected=422,
        )

    now = query(env, "SELECT UTC_TIMESTAMP()").strip()
    q = request(
        endpoint,
        "POST",
        "/api/v1/questions/manual",
        {
            "question_text": "认知档案测试：求一次函数斜率",
            "knowledge_points": ["一次函数"],
            "question_type": "综合题",
        },
        token=token,
    )
    qid = q["id"]
    foreign = request(
        endpoint,
        "POST",
        "/api/v1/questions/manual",
        {"question_text": "其他账号专属题目"},
        token=other_token,
    )["id"]
    card = insert(
        "knowledge_points",
        code="insights_linear",
        name="一次函数",
        subject="数学",
        content={
            "grade": "初二",
            "common_misconceptions": ["移项符号", "斜率错误"],
            "chapter": "函数",
        },
    )
    prerequisite = insert(
        "knowledge_points",
        code="insights_equation",
        name="一元一次方程",
        subject="数学",
        content={"grade": "初一"},
    )
    english_card = insert(
        "knowledge_points",
        code="insights_english",
        name="定语从句",
        subject="英语",
        content={"grade": "初三"},
    )
    unicode_card = insert(
        "knowledge_points", code="中文编码", name="中文知识卡", subject="数学"
    )
    insert("knowledge_relations", source_id=card, target_id=prerequisite)
    for name, score, updated in [
        ("一次函数", 0.2, "2026-01-01 00:00:00"),
        ("一次函数", 0.8, now),
        ("一元一次方程", 0.7, now),
    ]:
        insert(
            "mastery_states",
            user_id=owner,
            subject="数学",
            knowledge_point=name,
            mastery_score=score,
            confidence=0.8,
            update_reason="教回、近迁移、远迁移通过，提示等级1",
            updated_at=(
                datetime.strptime(now, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
                - timedelta(seconds=1)
            ).strftime("%Y-%m-%d %H:%M:%S")
            if name == "一元一次方程"
            else updated,
        )
    insert(
        "mastery_states",
        user_id=owner,
        subject="英语",
        knowledge_point="定语从句",
        mastery_score=0.6,
    )
    insert(
        "mastery_states",
        user_id=other_id,
        subject="数学",
        knowledge_point="私密知识点",
        mastery_score=0.99,
    )
    for code, label, probability in [
        ("move_sign", "移项忘记变号", 0.8),
        ("move_sign2", "移项符号不变", 0.3),
    ]:
        insert(
            "misconception_states",
            user_id=owner,
            subject="数学",
            code=code,
            label=label,
            probability=probability,
            successful_strategy="micro_activity",
            failed_strategy="incremental_hint",
        )
    insert(
        "misconception_states",
        user_id=other_id,
        subject="数学",
        code="private",
        label="私密错因",
        probability=0.9,
    )
    for entity, key, score, question_id in [
        ("mastery", "一次函数", 0.6, qid),
        ("mastery", "一次函数", 0.8, qid),
        ("misconception", "move_sign", 0.2, qid),
        ("note_evidence", "note", 0.5, qid),
    ]:
        insert(
            "cognitive_updates",
            user_id=owner,
            question_id=question_id,
            entity_type=entity,
            entity_key=key,
            new_value=score,
            created_at=now,
        )
    insert(
        "cognitive_updates",
        user_id=owner,
        question_id=qid,
        entity_type="mastery",
        entity_key="一次函数",
        new_value=0.1,
    )
    insert(
        "cognitive_updates",
        user_id=other_id,
        question_id=foreign,
        entity_type="mastery",
        entity_key="私密知识点",
        new_value=0.99,
        created_at=now,
    )
    for point, role in [(card, "primary"), (prerequisite, "prerequisite")]:
        insert(
            "user_question_knowledge_links",
            user_id=owner,
            question_id=qid,
            knowledge_point_id=point,
            confidence=0.9,
            role=role,
            evidence_text="题目分析",
            created_at=now,
        )

    insert("review_plans", user_id=owner, question_id=qid, due_at=now)
    insert("review_plans", user_id=owner, question_id=qid, due_at="2099-01-01 00:00:00")
    active_session = insert(
        "tutor_sessions",
        user_id=owner,
        question_id=qid,
        stage="near_transfer",
        status="active",
        state={},
        updated_at=now,
    )
    class_id = insert("teacher_classes", teacher_id=other_id, name="测试班级")
    assignment = insert(
        "question_assignments", teacher_id=other_id, question_id=qid, class_id=class_id
    )
    insert("assignment_students", assignment_id=assignment, student_id=owner)
    task = insert(
        "teacher_review_tasks",
        class_id=class_id,
        student_id=owner,
        question_id=qid,
        source_id=str(uuid4()),
    )
    insert(
        "teacher_review_results",
        task_id=task,
        teacher_id=other_id,
        conclusion="correct",
        reason="教师核对",
        student_hint="请独立复习",
        created_at=now,
    )
    insert(
        "teacher_review_results",
        task_id=task,
        teacher_id=other_id,
        conclusion="incorrect",
        reason="已撤销的反馈",
        revoked_at=now,
        created_at="2099-01-01 00:00:00",
    )

    async def parity():
        from sqlalchemy.engine import URL
        from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

        original = original_routes()
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
                for days in (2, 14, 365):
                    expected = comparable(
                        await original["analytics"](
                            days=days, user=SimpleNamespace(id=owner), db=db
                        )
                    )
                    for suffix in aliases:
                        actual = request(
                            endpoint,
                            "GET",
                            "/api/v1/analytics/" + suffix + "?days=" + str(days),
                            token=token,
                        )
                        assert actual == expected, (suffix, actual, expected)
                # The original graph does not order duplicate mastery rows. The
                # analytics comparison above covers latest-row selection; remove
                # the obsolete fixture before comparing graph and dashboard order.
                await db.rollback()
                query(
                    env,
                    f"DELETE FROM mastery_states WHERE user_id='{owner}' AND knowledge_point='一次函数' AND mastery_score<0.3",
                )
                expected_dashboard = comparable(
                    await original["dashboard"](user=SimpleNamespace(id=owner), db=db)
                )
                actual_dashboard = request(
                    endpoint, "GET", "/api/v1/dashboard", token=token
                )
                assert actual_dashboard == expected_dashboard, (
                    actual_dashboard,
                    expected_dashboard,
                )
                for subject in (None, "数学", "英语", "不存在的学科"):
                    args = {"days": 90}
                    if subject is not None:
                        args["subject"] = subject
                    expected = await original["cognition_graph"](
                        subject=subject, days=90, user=SimpleNamespace(id=owner), db=db
                    )
                    actual = request(
                        endpoint,
                        "GET",
                        "/api/v1/analytics/cognition-graph?" + urlencode(args),
                        token=token,
                    )
                    assert graph_comparable(actual) == graph_comparable(expected), (
                        actual,
                        expected,
                    )
                for args in (
                    {},
                    {"q": "一次、移项"},
                    {"subject": "数学", "grade": "初二"},
                    {"misconception": "斜率错误"},
                    {"q": "insights\u3000方程"},
                    {"q": "' OR 1=1 --"},
                ):
                    expected = await original["knowledge_cards"](
                        q=args.get("q", ""),
                        subject=args.get("subject"),
                        grade=args.get("grade"),
                        misconception=args.get("misconception"),
                        db=db,
                    )
                    actual = request(
                        endpoint, "GET", "/api/v1/knowledge/cards?" + urlencode(args)
                    )
                    assert actual == comparable(expected), (actual, expected)
                for code in ("insights_linear", "insights_equation", "中文编码"):
                    actual = request(
                        endpoint,
                        "GET",
                        "/api/v1/knowledge/cards/" + quote(code, safe=""),
                    )
                    expected = await original["knowledge_card"](code=code, db=db)
                    assert actual == comparable(expected), (actual, expected)
        finally:
            await engine.dispose()

    asyncio.run(parity())
    dashboard = request(endpoint, "GET", "/api/v1/dashboard", token=token)
    assert dashboard["weekly_questions"] == 1 and dashboard["streak_days"] == 1
    assert (
        dashboard["today_reviews"] == 1 and dashboard["teacher_assignment_count"] == 1
    )
    assert dashboard["continue_learning"]["session_id"] == active_session
    assert dashboard["teacher_feedback"]["reason"] == "教师核对"
    query(
        env,
        f"UPDATE tutor_sessions SET state=JSON_OBJECT('question_changed',TRUE) WHERE id='{active_session}'",
    )
    assert (
        request(endpoint, "GET", "/api/v1/dashboard", token=token)["continue_learning"]
        is None
    )
    summary = request(endpoint, "GET", "/api/v1/analytics/overview", token=token)
    assert summary["summary"] == {
        "knowledge_count": 3,
        "misconception_count": 1,
        "evidence_count": 2,
    }
    assert summary["trend"][0]["score"] == 70.0
    assert summary["misconceptions"][0]["successful_strategy"] == "小步练习"
    graph = request(endpoint, "GET", "/api/v1/analytics/cognition-graph", token=token)
    assert graph["personal_mapping_count"] == 2 and graph["mapped_question_count"] == 1
    assert {edge["relation"] for edge in graph["links"]} >= {
        "涉及知识点",
        "需要先修",
        "提供掌握证据",
        "暴露错因",
        "prerequisite",
        "有效策略",
        "待改进策略",
    }
    assert all(node.get("question_id") != foreign for node in graph["nodes"])
    assert Counter(node["category"] for node in graph["nodes"])["question"] == 1
    request(endpoint, "GET", "/api/v1/knowledge/cards/missing-card", expected=404)
    request(endpoint, "POST", "/api/v1/knowledge/cards", expected=405)
    assert (
        request(
            endpoint, "GET", "/api/v1/knowledge/cards/" + quote("中文编码", safe="")
        )["id"]
        == unicode_card
    )
    # Archive hides the question and its evidence links while retaining personal states.
    request(endpoint, "DELETE", "/api/v1/questions/" + qid, token=token)
    archived = request(
        endpoint, "GET", "/api/v1/analytics/cognition-graph", token=token
    )
    assert not any(node["category"] == "question" for node in archived["nodes"])
    assert not any(edge["source"] == "question:" + qid for edge in archived["links"])
    # Shared cards must not change later analysis/tutor reference selection.
    # Delete only this module's own fixture IDs, keeping personal history intact.
    fixture_ids = ",".join(
        f"'{identifier}'"
        for identifier in (card, prerequisite, english_card, unicode_card)
    )
    query(
        env,
        f"DELETE FROM user_question_knowledge_links WHERE knowledge_point_id IN ({fixture_ids})",
    )
    query(
        env,
        f"DELETE FROM knowledge_relations WHERE source_id IN ({fixture_ids}) OR target_id IN ({fixture_ids})",
    )
    query(env, f"DELETE FROM knowledge_points WHERE id IN ({fixture_ids})")
    print(
        "Cangjie insights passed: 5 routes, original Python parity, UTC trend, cards/relations, graph evidence, filters and owner isolation"
    )
