import os
from uuid import uuid4

import pytest
from cuoti_backend.question_data import execute, insert, rows

# Reuse the existing temporary-account lifecycle, without starting another service.
from test_questions_mysql import (
    question_app as question_app,  # noqa: PLC0414 -- Export a shared pytest fixture.
)

pytestmark = [
    pytest.mark.mysql,
    pytest.mark.skipif(
        os.environ.get("CUOTI_TEST_MYSQL") != "1",
        reason="local MySQL check not enabled",
    ),
]


@pytest.fixture
def bank(question_app):
    app, client, student, _ = question_app
    user, headers = student()
    other_user, other = student()
    source, ids = str(uuid4()), []
    with app.state.database.session() as db, db.begin():
        execute(
            db, "UPDATE student_profiles SET grade='初一' WHERE user_id=?", [user["id"]]
        )
        execute(
            db,
            "UPDATE student_profiles SET grade='' WHERE user_id=?",
            [other_user["id"]],
        )
        insert(
            db,
            "dataset_sources",
            id=source,
            key="migration-" + source,
            name="学习卷测试",
            version="1",
            homepage="",
            license="test",
            local_path="",
            total_items=24,
            imported_items=24,
            source_metadata={},
        )
        for index in range(24):
            id = str(uuid4())
            ids.append(id)
            insert(
                db,
                "dataset_questions",
                id=id,
                dataset_source_id=source,
                source_item_id=str(index),
                split="test",
                subject="英语" if index % 2 else "数学",
                grade="七年级" if index == 1 else "初一",
                grade_band="初中",
                title="学习卷测试",
                question_text="求二次函数的顶点" if index == 23 else "2x=4",
                question_type="calculation",
                options=[],
                answer="2",
                solution="两边同除2",
                knowledge_points=["方程"],
                image_paths=[],
                difficulty="",
                content_hash=str(index).zfill(64),
                source_metadata={},
                has_answer=True,
                has_solution=True,
                answer_verified=True,
                quality_status="verified",
                usable_for_practice=True,
                usable_for_auto_grade=True,
            )
        # Put the explicitly later-stage example in mathematics.
        execute(db, "UPDATE dataset_questions SET subject='数学' WHERE id=?", [ids[-1]])
    try:
        yield app, client, user, headers, other, source, ids
    finally:
        with app.state.database.session() as db, db.begin():
            execute(
                db, "DELETE FROM dataset_questions WHERE dataset_source_id=?", [source]
            )
            execute(db, "DELETE FROM dataset_sources WHERE id=?", [source])


def test_bank_scope_seed_paging_and_legacy(bank):
    _, client, _, headers, other, source, ids = bank
    path = "/api/v1/study-bank?source_id=" + source + "&shuffle_seed=123"
    result = client.get(path, headers=headers)
    assert result.status_code == 200, result.text
    data = result.json()["data"]
    assert data["total"] == 23 and len(data["questions"]) == 20
    assert data["grade"] == "初一"
    assert all(
        "answer" not in question and "solution" not in question
        for question in data["questions"]
    )
    assert (
        data["questions"]
        == client.get(path, headers=headers).json()["data"]["questions"]
    )
    second = client.get(path + "&page=2", headers=headers).json()["data"]
    assert len(second["questions"]) == 3
    assert not {q["id"] for q in data["questions"]} & {
        q["id"] for q in second["questions"]
    }
    assert ids[-1] not in {q["id"] for q in data["questions"] + second["questions"]}
    assert client.get(path, headers=other).status_code == 422
    assert client.get(path + "&shuffle_seed=-1", headers=headers).status_code == 422
    if os.environ.get("CUOTI_LEGACY_URL"):
        import httpx

        old = httpx.get(
            os.environ["CUOTI_LEGACY_URL"] + path,
            headers=headers,
            trust_env=False,
            timeout=30,
        )
        assert old.status_code == 200, old.text
        before = old.json()["data"]
        for field in ["facets", "sources"]:
            before[field] = sorted(
                before[field],
                key=lambda item: (
                    item.get("id") or item["subject"] + "|" + item["grade_band"]
                ),
            )
            data[field] = sorted(
                data[field],
                key=lambda item: (
                    item.get("id") or item["subject"] + "|" + item["grade_band"]
                ),
            )
        assert before == data


def test_study_save_submit_unavailable_and_adaptive(bank):
    app, client, user, headers, other, source, ids = bank
    base = "/api/v1/study-sessions"
    single = {"question_ids": [ids[0]], "mode": "practice", "source_id": source}
    assert (
        client.post(base, headers=headers, json={**single, "question_ids": {}}).json()[
            "detail"
        ]
        == "题目编号格式无效"
    )
    created = client.post(base, headers=headers, json=single)
    assert created.status_code == 200, created.text
    session = created.json()["data"]
    path = base + "/" + session["id"]
    assert session["question_count"] == 1 and "answer" not in session["items"][0]
    assert client.get(path, headers=other).status_code == 404
    assert client.get(base, headers=other).json()["data"] == []
    answer = {
        "version": session["version"],
        "answers": [{"id": session["items"][0]["id"], "answer": "2"}],
    }
    saved = client.patch(path, headers=headers, json=answer)
    assert saved.status_code == 200, saved.text
    assert client.patch(path, headers=headers, json=answer).status_code == 409
    result = client.post(
        path + "/submit",
        headers=headers,
        json={"version": saved.json()["data"]["version"]},
    )
    assert result.status_code == 200, result.text
    submitted = result.json()["data"]
    assert submitted["results"] == {
        "correct": 1,
        "pending": 0,
        "answered": 1,
        "total": 1,
        "score": 5,
        "max_score": 5,
    }
    assert submitted["items"][0]["answer"] == "2"
    assert (
        client.post(path + "/submit", headers=headers, json={"version": 1}).json()[
            "data"
        ]["results"]
        == submitted["results"]
    )
    assert client.patch(path, headers=headers, json=answer).status_code == 409
    if os.environ.get("CUOTI_LEGACY_URL"):
        import httpx

        old = httpx.get(
            os.environ["CUOTI_LEGACY_URL"] + path,
            headers=headers,
            trust_env=False,
            timeout=15,
        )
        assert old.status_code == 200
        assert old.json()["data"] == client.get(path, headers=headers).json()["data"]
    adaptive = client.post(
        base,
        headers=headers,
        json={"source_id": source, "selection_strategy": "adaptive", "count": 2},
    )
    assert adaptive.status_code == 200, adaptive.text
    assert adaptive.json()["data"]["question_count"] == 2
    expired = client.post(
        base, headers=headers, json={**single, "mode": "exam", "minutes": 1}
    ).json()["data"]
    exam_path = base + "/" + expired["id"]
    with app.state.database.session() as db, db.begin():
        execute(
            db,
            "UPDATE study_sessions SET deadline_at=UTC_TIMESTAMP(6)-INTERVAL 1 SECOND WHERE id=?",
            [expired["id"]],
        )
        execute(
            db,
            "UPDATE dataset_questions SET quality_status='format_review' WHERE id=?",
            [ids[0]],
        )
    assert (
        client.patch(
            exam_path,
            headers=headers,
            json={
                "version": 1,
                "answers": [{"id": expired["items"][0]["id"], "answer": "2"}],
            },
        ).status_code
        == 409
    )
    excluded = client.post(exam_path + "/submit", headers=headers, json={"version": 1})
    assert excluded.status_code == 200, excluded.text
    assert excluded.json()["data"]["results"]["excluded"] == 1
    assert excluded.json()["data"]["results"]["max_score"] == 0
    assert "answer" not in excluded.json()["data"]["items"][0]
    with app.state.database.session() as db:
        assert not rows(
            db, "SELECT id FROM cognitive_updates WHERE user_id=?", [user["id"]]
        )


def test_submit_rejects_answers_changed_during_grading(bank, monkeypatch):
    app, client, _, headers, _, source, ids = bank
    session = client.post(
        "/api/v1/study-sessions",
        headers=headers,
        json={"question_ids": [ids[0]], "source_id": source},
    ).json()["data"]
    path = "/api/v1/study-sessions/" + session["id"]
    aid = session["items"][0]["id"]
    saved = client.patch(
        path,
        headers=headers,
        json={"version": 1, "answers": [{"id": aid, "answer": "2"}]},
    ).json()["data"]
    original = app.state.questions.compute.compute
    changed = []

    def compute(operation, **values):
        if operation == "grade_answer":
            result = client.patch(
                path,
                headers=headers,
                json={
                    "version": saved["version"],
                    "answers": [{"id": aid, "answer": "3"}],
                },
            )
            changed.append(result.status_code)
        return original(operation, **values)

    monkeypatch.setattr(app.state.questions.compute, "compute", compute)
    response = client.post(
        path + "/submit", headers=headers, json={"version": saved["version"]}
    )
    assert response.status_code == 409 and changed == [200]
    current = client.get(path, headers=headers).json()["data"]
    assert (
        current["status"] == "active" and current["items"][0]["student_answer"] == "3"
    )
    assert "grading" not in current["items"][0]
    with app.state.database.session() as db:
        assert (
            rows(db, "SELECT grading FROM study_session_items WHERE id=?", [aid])[0][
                "grading"
            ]
            is None
        )


def test_completed_task_recommendation_keeps_original_grade_scope(bank):
    from cuoti_backend.learning_memory import task_fingerprint
    from cuoti_backend.question_data import select_rows
    from cuoti_backend.task_sources import capture_source, load_snapshot

    app, client, user, headers, _, source, ids = bank
    qid = client.post(
        "/api/v1/questions/manual",
        headers=headers,
        json={"question_text": "3x=15", "correct_answer": "5", "grade": "初一"},
    ).json()["data"]["id"]
    tid = str(uuid4())
    try:
        with app.state.database.session() as db, db.begin():
            insert(
                db,
                "learning_tasks",
                id=tid,
                user_id=user["id"],
                question_id=qid,
                status="completed",
                input_fingerprint=task_fingerprint(db, qid, user["id"]),
                step_id=str(uuid4()),
                checkpoint={},
                student_view={
                    "recommendation": {
                        "question_source": "dataset",
                        "question_id": ids[0],
                    }
                },
                pending_action={},
            )
            task = select_rows(
                db, "learning_tasks", "SELECT * FROM learning_tasks WHERE id=?", [tid]
            )[0]
            capture_source(db, task, load_snapshot(db, qid, user["id"]))
            execute(
                db,
                "UPDATE student_profiles SET grade='高一' WHERE user_id=?",
                [user["id"]],
            )
        request = {"question_ids": [ids[0]], "source_id": source}
        assert (
            client.post(
                "/api/v1/study-sessions", headers=headers, json=request
            ).status_code
            == 422
        )
        linked = client.post(
            "/api/v1/study-sessions",
            headers=headers,
            json={**request, "learning_task_id": tid},
        )
        assert linked.status_code == 200, linked.text
        assert linked.json()["data"]["items"][0]["question"]["grade"] == "初一"
    finally:
        with app.state.database.session() as db, db.begin():
            execute(db, "DELETE FROM learning_task_sources WHERE task_id=?", [tid])
            execute(db, "DELETE FROM learning_tasks WHERE id=?", [tid])
