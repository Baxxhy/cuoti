"""OCR corrections, revision retention and atomic confirmation over real HTTP/MySQL."""

import subprocess
from pathlib import Path
from uuid import uuid4

from smoke_cangjie_accounts import request
from smoke_cangjie_detail import fixture_insert


def ocr_edits(endpoint, env, query):
    account = request(
        endpoint,
        "POST",
        "/api/v1/auth/register",
        {
            "email": f"draft-{uuid4()}@example.test",
            "name": "草稿",
            "password": "test-password-123",
        },
    )
    token = account["access_token"]
    created = request(
        endpoint,
        "POST",
        "/api/v1/questions/manual",
        {"question_text": "原题", "student_steps": ["旧步骤"]},
        token=token,
    )
    qid = created["id"]
    path = f"/api/v1/questions/{qid}"
    # Upgrade a populated previous-version test schema, then repeat safely.
    assert env["CANGJIE_DB_NAME"].startswith("zhiwei_cangjie_test_")
    query(
        env,
        "ALTER TABLE student_works MODIFY created_at DATETIME NOT NULL, MODIFY updated_at DATETIME NOT NULL",
    )
    query(env, "DELETE FROM cangjie_schema_versions WHERE version='002_work_precision'")
    diagnosis_count = query(env, "SELECT COUNT(*) FROM diagnoses")
    query(
        env,
        "ALTER TABLE diagnoses MODIFY created_at DATETIME NOT NULL, MODIFY updated_at DATETIME NOT NULL",
    )
    query(
        env,
        "DELETE FROM cangjie_schema_versions WHERE version='003_diagnosis_precision'",
    )
    project = Path(__file__).resolve().parents[1]
    for _ in range(2):
        subprocess.run(
            ["bash", "scripts/cangjie.sh", "upgrade-db"],
            cwd=project,
            env=env,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=90,
        )
    assert (
        query(
            env,
            "SELECT DATETIME_PRECISION FROM information_schema.columns WHERE table_schema=DATABASE() AND table_name='student_works' AND column_name='created_at'",
        )
        == "6"
    )
    assert (
        request(endpoint, "GET", path, token=token)["student_steps"][0]["text"]
        == "旧步骤"
    )
    assert query(env, "SELECT COUNT(*) FROM diagnoses") == diagnosis_count
    assert (
        query(
            env,
            "SELECT DATETIME_PRECISION FROM information_schema.columns WHERE table_schema=DATABASE() AND table_name='diagnoses' AND column_name='created_at'",
        )
        == "6"
    )
    insert = fixture_insert(env, query)
    analysis = insert("problem_analyses", question_id=qid, subject="数学")
    request(endpoint, "POST", path + "/draft", {}, expected=401)
    other = request(
        endpoint,
        "POST",
        "/api/v1/auth/register",
        {
            "email": f"other-{uuid4()}@example.test",
            "name": "另一人",
            "password": "test-password-123",
        },
    )
    request(
        endpoint,
        "POST",
        path + "/confirm",
        {},
        token=other["access_token"],
        expected=404,
    )
    for i in range(4):
        saved = request(
            endpoint,
            "POST",
            path + "/draft",
            {
                "question_text": "修改题目",
                "student_answer": " 4 ",
                "student_steps": [
                    {
                        "text": f"x = {i}",
                        "raw_text": "手写",
                        "bbox": [0, "0.1", 0.8, 0.9],
                        "confidence": 0.8,
                    }
                ],
                "teacher_marks": [{"comment": "核对", "confidence": 0.9}],
                "title": "忽略标题",
            },
            token=token,
        )
        assert saved["status"] == "ocr_draft" and saved["student_answer"] == "4"
        assert saved["title"] == "原题"
        assert saved["student_steps"][0]["text"] == f"x = {i}", saved["student_steps"]
        assert saved["student_steps"][0]["user_confirmed"] is True
        assert saved["student_steps"][0]["raw_text"] == "手写"
        assert saved["student_steps"][0]["bbox"] == [0, 0.1, 0.8, 0.9]
        assert saved["teacher_marks"][0]["comment"] == "核对"
    assert (
        query(env, f"SELECT COUNT(*) FROM student_works WHERE question_id='{qid}'")
        == "5"
    )
    assert (
        query(env, f"SELECT COUNT(*) FROM problem_analyses WHERE id='{analysis}'")
        == "0"
    )
    empty_grade = request(endpoint, "POST", path + "/draft", {"grade": ""}, token=token)
    assert empty_grade["grade"] is None
    confirmed = request(endpoint, "POST", path + "/confirm", token=token)
    assert confirmed["confirmed"] is True and confirmed["status"] == "confirmed"
    request(
        endpoint,
        "POST",
        path + "/confirm",
        {"question_text": "  ", "student_steps": ["不能保存"]},
        token=token,
        expected=422,
    )
    after = request(endpoint, "GET", path, token=token)
    assert (
        after["question_text"] == "修改题目"
        and after["student_steps"][0]["text"] == "x = 3"
    )
    assert (
        query(env, f"SELECT COUNT(*) FROM student_works WHERE question_id='{qid}'")
        == "5"
    )
    request(
        endpoint,
        "POST",
        path + "/draft",
        {"student_steps": [{"confidence": 2}]},
        token=token,
        expected=422,
    )
    selected = request(
        endpoint,
        "POST",
        path + "/draft",
        {
            "question_type": "选择题",
            "options": [{"label": "A", "text": "甲"}, {"label": "B", "text": "乙"}],
            "student_answer": "",
            "student_steps": ["a， B,a"],
        },
        token=token,
    )
    assert selected["student_answer"] == "A、B" and selected["student_steps"] == []
    request(endpoint, "DELETE", path, token=token)
    request(endpoint, "POST", path + "/draft", {}, token=token, expected=409)
    request(endpoint, "POST", path + "/confirm", {}, token=token, expected=409)
    print(
        "Cangjie OCR edits passed: permissions, revision ordering, history, invalidation, choice normalization and atomic confirmation"
    )
