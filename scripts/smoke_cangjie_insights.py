"""Real HTTP/MySQL checks for analytics, knowledge, graph and owner isolation."""

from collections import Counter
from datetime import datetime, timedelta, timezone
from urllib.parse import quote, urlencode
from uuid import uuid4

from smoke_cangjie_accounts import request
from smoke_cangjie_detail import fixture_insert


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

    for days in (2, 14, 365):
        replies = [request(endpoint, "GET", "/api/v1/analytics/" + suffix + "?days=" + str(days), token=token) for suffix in aliases]
        assert all(reply == replies[0] for reply in replies)
    for args in ({}, {"q": "一次、移项"}, {"subject": "数学", "grade": "初二"}, {"misconception": "斜率错误"}, {"q": "' OR 1=1 --"}):
        cards = request(endpoint, "GET", "/api/v1/knowledge/cards?" + urlencode(args))
        assert isinstance(cards, list)
        if args.get("subject"):
            assert all(card["subject"] == args["subject"] for card in cards)
    for code in ("insights_linear", "insights_equation", "中文编码"):
        found_card = request(endpoint, "GET", "/api/v1/knowledge/cards/" + quote(code, safe=""))
        assert found_card["code"] == code
        assert request(endpoint, "GET", "/api/v1/knowledge/cards/" + found_card["id"]) == found_card
    dashboard = request(endpoint, "GET", "/api/v1/dashboard", token=token)
    assert dashboard["weekly_questions"] == 1 and dashboard["streak_days"] == 1
    assert dashboard["today_reviews"] == 1
    assert dashboard["continue_learning"]["session_id"] == active_session
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
        "Cangjie insights passed: 5 routes, native response contracts, UTC trend, cards/relations, graph evidence, filters and owner isolation"
    )
