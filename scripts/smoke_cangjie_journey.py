"""Persisted journey projection, owner isolation and original Python parity."""

import asyncio
from datetime import datetime

from smoke_cangjie_accounts import request
from smoke_cangjie_detail import fixture_insert


def journey(endpoint, env, query, token, other):
    insert = fixture_insert(env, query)
    question = request(
        endpoint,
        "POST",
        "/api/v1/questions/manual",
        {"question_text": "学习历程：3x=15", "knowledge_points": ["一次方程"]},
        token=token,
    )
    qid = question["id"]
    owner = query(env, f"SELECT user_id FROM questions WHERE id='{qid}'").strip()
    other_owner = request(endpoint, "GET", "/api/v1/auth/me", token=other)["id"]
    path = f"/api/v1/questions/{qid}/journey"
    request(endpoint, "GET", path, expected=401)
    request(endpoint, "GET", path, token=other, expected=404)
    request(endpoint, "POST", path, token=token, expected=405)
    request(
        endpoint, "GET", "/api/v1/questions/missing/journey", token=token, expected=404
    )

    def read():
        return request(endpoint, "GET", path, token=token)

    baseline = read()
    assert baseline["next_action"]["label"] == "开始错因诊断"
    assert baseline["stages"][0]["completed"]
    assert not any(s["completed"] for s in baseline["stages"][1:])
    assert baseline["practice"] == {
        "attempts": 0,
        "verified_attempts": 0,
        "correct": 0,
        "pending": 0,
    }
    insert("problem_analyses", question_id=qid, subject="数学", verified=True)
    insert(
        "diagnoses", question_id=qid, root_misconception="移项符号", user_confirmed=True
    )
    assert read()["next_action"]["label"] == "查看诊断并学习"
    sid = insert(
        "tutor_sessions",
        user_id=owner,
        question_id=qid,
        status="completed",
        state={
            "assisted": True,
            "understanding_passed": True,
            "teach_back_passed": True,
            "near_transfer": True,
            "far_transfer": True,
        },
    )
    assisted = read()
    assert assisted["stages"][2]["completed"] and not assisted["stages"][3]["completed"]
    assert "不等于" in assisted["summary"]
    query(
        env,
        f"UPDATE tutor_sessions SET state=JSON_SET(state,'$.assisted',JSON_EXTRACT('false','$')) WHERE id='{sid}'",
    )
    assert read()["stages"][3]["completed"]
    query(
        env,
        f"UPDATE tutor_sessions SET state=JSON_SET(state,'$.question_changed',JSON_EXTRACT('true','$')) WHERE id='{sid}'",
    )
    invalidated = read()
    assert (
        not invalidated["stages"][2]["completed"]
        and not invalidated["stages"][3]["completed"]
    )
    assert invalidated["next_action"]["label"] == "查看诊断并学习"
    foreign_session = insert(
        "tutor_sessions",
        user_id=other_owner,
        question_id=qid,
        status="active",
        state={"understanding_passed": True, "teach_back_passed": True},
    )
    assert read()["next_action"]["label"] == "查看诊断并学习"
    # An active current session has priority over an overdue review plan.
    plan = insert(
        "review_plans",
        user_id=owner,
        question_id=qid,
        due_at="2026-01-01 00:00:00",
        status="pending",
    )
    assert read()["next_action"]["url"].endswith(plan)
    current = insert(
        "tutor_sessions",
        user_id=owner,
        question_id=qid,
        status="active",
        state={},
        created_at="2026-01-01 00:00:01",
        updated_at="2026-01-01 00:00:01",
    )
    assert read()["next_action"]["url"].endswith(current)
    query(env, f"UPDATE tutor_sessions SET status='completed' WHERE id='{current}'")
    source = insert("dataset_sources", key="journey-fixture", name="学习历程测试")
    dataset = insert(
        "dataset_questions",
        dataset_source_id=source,
        source_item_id="journey-1",
        subject="数学",
        grade_band="junior",
        content_hash="journey-fixture",
        question_text="2x=10",
        answer="5",
    )
    for index, details in enumerate(
        (
            {},
            {"can_update_learning": True},
            {"can_update_learning": True, "question_changed": True},
        )
    ):
        insert(
            "dataset_practice_attempts",
            user_id=owner,
            mistake_id=qid,
            dataset_question_id=dataset,
            source_dataset="journey-fixture",
            student_answer=["5"],
            mode="near",
            correct=True,
            grading_details=details,
            created_at=f"2026-01-02 01:02:0{index}",
        )
    for index, (grade, details) in enumerate(
        (
            ("pending", {"can_update_learning": True}),
            ("good", {"can_update_learning": True}),
            ("good", {"can_update_learning": True, "question_changed": True}),
        )
    ):
        insert(
            "review_records",
            plan_id=plan,
            grade=grade,
            correct=True,
            grading_details=details,
            created_at=f"2026-01-03 01:02:0{index}",
        )
    result = read()
    assert result["practice"] == {
        "attempts": 3,
        "verified_attempts": 1,
        "correct": 1,
        "pending": 1,
    }
    assert result["review"]["completed"] == 1 and result["review"]["due"] == 1
    assert result["stages"][4]["completed"]
    assert result["verification"] == {
        "label": "已完成规则校验",
        "verified": True,
        "diagnosis_confirmed": True,
    }
    assert len(result["events"]) == 10 and all(
        event["id"] != "session:" + foreign_session for event in result["events"]
    )

    async def parity():
        from app.models import Question
        from app.services.learning_journey import get_learning_journey
        from sqlalchemy import URL
        from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

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
                for count in (2, 55):
                    # Over 50 sessions: SQL history cap must match the original.
                    for index in range(count):
                        insert(
                            "tutor_sessions",
                            user_id=owner,
                            question_id=qid,
                            status="completed",
                            state={},
                            created_at=f"2026-02-01 00:00:{index:02d}",
                            updated_at=f"2026-02-01 00:00:{index:02d}",
                        )
                    # External fixture writes need a fresh MySQL repeatable-read snapshot.
                    await db.rollback()
                    actual = read()
                    expected = await get_learning_journey(
                        db, await db.get(Question, qid)
                    )
                    assert (
                        abs(
                            (
                                datetime.fromisoformat(actual.pop("generated_at"))
                                - datetime.fromisoformat(expected.pop("generated_at"))
                            ).total_seconds()
                        )
                        < 10
                    )
                    assert actual == expected, (actual, expected)
                    assert len(actual["events"]) <= 30 and actual["history_limit"] == 50
        finally:
            await engine.dispose()

    asyncio.run(parity())
    query(
        env, f"UPDATE questions SET status='awaiting_crop',confirmed=0 WHERE id='{qid}'"
    )
    assert read()["next_action"]["label"] == "继续框选题目"
    job = insert("processing_jobs", question_id=qid, status="running")
    query(env, f"UPDATE questions SET status='recognized' WHERE id='{qid}'")
    assert read()["next_action"]["url"].endswith(job)
    query(env, f"UPDATE processing_jobs SET status='failed' WHERE id='{job}'")
    assert read()["next_action"]["url"].endswith(job)
    query(env, f"UPDATE questions SET status='archived' WHERE id='{qid}'")
    request(endpoint, "GET", path, token=token, expected=404)
    print(
        "Cangjie journey passed: persisted stages, owner isolation, evidence filters, navigation, history limits and original Python parity"
    )
