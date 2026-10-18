"""Manual question API verification against isolated MySQL records."""

import json
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID, uuid4

from smoke_cangjie_accounts import request
from smoke_cangjie_detail import detail


def query(env, sql):
    result = subprocess.run(
        [
            "mysql",
            "--protocol=TCP",
            "--default-character-set=utf8mb4",
            "-h",
            env["CANGJIE_DB_HOST"],
            "-P",
            env["CANGJIE_DB_PORT"],
            "-u",
            env["CANGJIE_DB_USER"],
            env["CANGJIE_DB_NAME"],
            "-NBe",
            sql,
        ],
        env={**os.environ, "MYSQL_PWD": env["CANGJIE_DB_PASSWORD"]},
        text=True,
        capture_output=True,
        check=True,
    )
    return result.stdout.strip()


def manual_questions(endpoint, env, token):
    assert env["CANGJIE_DB_NAME"].startswith("zhiwei_cangjie_test")
    user = request(endpoint, "GET", "/api/v1/auth/me", token=token)
    user_id = str(UUID(user["id"]))
    payload = {
        "question_text": "求解：x² = 4，说明解题步骤。",
        "subject": "数学",
        "grade": "初二",
        "student_answer": "x = 2",
        "student_steps": ["x² = 4", "x = 2"],
        "user_id": "cannot-override-owner",
    }
    created = request(
        endpoint, "POST", "/api/v1/questions/manual", payload, token=token
    )
    question_id = str(UUID(created["id"]))
    assert created["status"] == "confirmed"
    snapshot = query(
        env,
        "SELECT JSON_OBJECT('owner',user_id,'text',question_text,'answer',student_answer,"
        "'status',status,'confirmed',confirmed,'options',options) FROM questions WHERE id='"
        + question_id
        + "'",
    )
    row = json.loads(snapshot)
    assert row == {
        "owner": user_id,
        "text": payload["question_text"],
        "answer": "x = 2",
        "status": "confirmed",
        "confirmed": 1,
        "options": [],
    }
    assert (
        query(
            env,
            "SELECT COUNT(*) FROM student_steps s JOIN student_works w ON w.id=s.work_id "
            "WHERE w.question_id='"
            + question_id
            + "' AND s.source='user' AND s.user_confirmed=1",
        )
        == "2"
    )
    choice = {
        "question_text": "以下哪些成立？",
        "question_type": "多选题",
        "options": [{"label": "A", "text": "1+1=2"}, {"label": "B", "text": "2+2=4"}],
    }
    multi = request(endpoint, "POST", "/api/v1/questions/manual", choice, token=token)
    saved = query(
        env, "SELECT options FROM questions WHERE id='" + str(UUID(multi["id"])) + "'"
    )
    assert json.loads(saved) == choice["options"]
    long_question = request(
        endpoint,
        "POST",
        "/api/v1/questions/manual",
        {"question_text": "中" * 90 + "😀"},
        token=token,
    )
    assert (
        query(
            env,
            "SELECT CHAR_LENGTH(title) FROM questions WHERE id='"
            + str(UUID(long_question["id"]))
            + "'",
        )
        == "80"
    )
    request(
        endpoint,
        "POST",
        "/api/v1/questions/manual",
        {"question_text": "长步骤输入", "student_steps": ["推理" * 3000] * 10},
        token=token,
    )
    before = query(
        env, "SELECT COUNT(*) FROM questions WHERE user_id='" + user_id + "'"
    )
    for invalid in [
        {"question_text": ""},
        {"question_text": "x", "question_type": "未知"},
        {"question_text": "x", "question_type": "单选题"},
        {"question_text": "x", "options": choice["options"]},
        {**choice, "options": [choice["options"][0], choice["options"][0]]},
        {"question_text": "x", "student_steps": [""]},
        {"question_text": "x", "student_answer": None},
    ]:
        request(
            endpoint,
            "POST",
            "/api/v1/questions/manual",
            invalid,
            token=token,
            expected=422,
        )
    assert (
        query(env, "SELECT COUNT(*) FROM questions WHERE user_id='" + user_id + "'")
        == before
    )
    request(endpoint, "POST", "/api/v1/questions/manual", payload, expected=401)
    # This explicit role mutation occurs only in the disposable test database.
    query(env, "UPDATE users SET role='teacher' WHERE id='" + user_id + "'")
    try:
        request(
            endpoint,
            "POST",
            "/api/v1/questions/manual",
            payload,
            token=token,
            expected=403,
        )
    finally:
        query(env, "UPDATE users SET role='student' WHERE id='" + user_id + "'")
    print(
        "Cangjie manual questions passed: MySQL persistence, work/steps, choices, owner and role checks"
    )
    detail(endpoint, env, token, question_id, query)
    archive_question(endpoint, env, token, user_id, question_id)


def archive_question(endpoint, env, token, user_id, question_id):
    path = "/api/v1/questions/" + question_id
    other = request(
        endpoint,
        "POST",
        "/api/v1/auth/register",
        {
            "email": f"archive-{uuid4().hex}@example.test",
            "password": "test-password-123",
            "name": "另一位学生",
        },
    )
    request(endpoint, "DELETE", path, expected=401)
    request(endpoint, "DELETE", path, token=other["access_token"], expected=404)
    request(
        endpoint,
        "DELETE",
        "/api/v1/questions/" + str(uuid4()),
        token=token,
        expected=404,
    )
    request(
        endpoint,
        "DELETE",
        "/api/v1/questions/x%27%20OR%201%3D1",
        token=token,
        expected=404,
    )
    request(endpoint, "POST", path, token=token, expected=405)
    # Exact routes take priority over the parameter route.
    request(endpoint, "DELETE", "/api/v1/questions/manual", token=token, expected=405)
    for status in ("pending", "completed", "cancelled"):
        query(
            env,
            "INSERT INTO review_plans (id,user_id,question_id,due_at,interval_days,reason,status,created_at,updated_at) VALUES "
            f"('{uuid4()}','{user_id}','{question_id}',UTC_TIMESTAMP(),1,'测试','{status}',UTC_TIMESTAMP(),UTC_TIMESTAMP())",
        )
    # Force the second write to fail, proving the first write rolls back too.
    pending_id = str(
        UUID(
            query(
                env,
                f"SELECT id FROM review_plans WHERE question_id='{question_id}' AND status='pending'",
            )
        )
    )
    query(
        env,
        f"ALTER TABLE review_plans ADD CONSTRAINT archive_failure CHECK (id <> '{pending_id}' OR status = 'pending')",
    )
    try:
        request(endpoint, "DELETE", path, token=token, expected=503)
        assert (
            query(env, f"SELECT status FROM questions WHERE id='{question_id}'")
            == "confirmed"
        )
        assert (
            query(
                env,
                f"SELECT COUNT(*) FROM review_plans WHERE question_id='{question_id}' AND status='pending'",
            )
            == "1"
        )
    finally:
        query(env, "ALTER TABLE review_plans DROP CHECK archive_failure")
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(
            executor.map(
                lambda _: request(endpoint, "DELETE", path, token=token), range(4)
            )
        )
    assert all(result == {"deleted": True} for result in results)
    assert (
        query(env, f"SELECT status FROM questions WHERE id='{question_id}'")
        == "archived"
    )
    assert (
        query(
            env,
            f"SELECT GROUP_CONCAT(status ORDER BY status) FROM review_plans WHERE question_id='{question_id}'",
        )
        == "cancelled,cancelled,completed"
    )
    assert (
        query(
            env,
            f"SELECT COUNT(*) FROM student_steps s JOIN student_works w ON s.work_id=w.id WHERE w.question_id='{question_id}'",
        )
        == "2"
    )
    assert (
        query(
            env,
            f"SELECT COUNT(*) FROM questions WHERE user_id='{user_id}' AND status='confirmed'",
        )
        == "3"
    )
    print(
        "Cangjie archive passed: ownership, SQL binding, rollback, concurrent repeat, review cancellation and retained work"
    )
