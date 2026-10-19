"""Public-bank practice and timed exams: native ownership, snapshots, answers, grading, deadlines."""

import json
from uuid import uuid4

from smoke_cangjie_accounts import request
from smoke_cangjie_detail import fixture_insert


def study(endpoint, env, query):
    assert env["CANGJIE_DB_NAME"].startswith("zhiwei_cangjie_test")
    insert = fixture_insert(env, query)
    source = insert("dataset_sources", key="study-" + uuid4().hex, name="练习验收题库")
    ids = []
    for number in range(1, 7):
        ids.append(
            insert(
                "dataset_questions",
                dataset_source_id=source,
                source_item_id=str(number),
                content_hash=uuid4().hex,
                subject="数学",
                grade="初一",
                grade_band="初中",
                question_text=f"计算：{number}+1等于多少？",
                question_type="multiple-choice",
                options=[
                    {"key": "A", "text": str(number + 1)},
                    {"key": "B", "text": str(number + 2)},
                ],
                answer=json.dumps("A"),
                solution=f"{number}+1={number + 1}",
                image_paths=[],
                has_answer=True,
                usable_for_practice=True,
                usable_for_auto_grade=True,
            )
        )
    insert(
        "dataset_questions",
        dataset_source_id=source,
        source_item_id="disabled",
        subject="数学",
        grade_band="初中",
        question_text="不可练题目",
        content_hash=uuid4().hex,
        usable_for_practice=False,
        usable_for_auto_grade=False,
    )
    email = "study-browser-" + uuid4().hex + "@example.test"
    password = "StudyBrowser-12345"
    actor = request(
        endpoint,
        "POST",
        "/api/v1/auth/register",
        {"email": email, "password": password, "name": "题库验收学生", "grade": "初一"},
    )
    other = request(
        endpoint,
        "POST",
        "/api/v1/auth/register",
        {
            "email": "study-other-" + uuid4().hex + "@example.test",
            "password": password,
            "name": "其他学生",
        },
    )
    token = actor["access_token"]
    foreign = other["access_token"]
    request(endpoint, "GET", "/api/v1/study-bank", expected=401)
    bank = request(
        endpoint, "GET", "/api/v1/study-bank?source_id=" + source, token=token
    )
    assert bank["total"] == 6 and len(bank["questions"]) == 6
    assert all(
        "answer" not in q and "solution" not in q and "source_metadata" not in q
        for q in bank["questions"]
    )
    assert all(q["source_name"] == "练习验收题库" for q in bank["questions"])
    filtered = request(
        endpoint,
        "GET",
        "/api/v1/study-bank?source_id=" + source + "&search=1%2B1",
        token=token,
    )
    assert filtered["total"] == 1 and filtered["questions"][0]["id"] == ids[0]
    empty = request(
        endpoint,
        "GET",
        "/api/v1/study-bank?source_id=" + source + "&grade_band=missing",
        token=token,
    )
    assert empty["total"] == 0 and empty["questions"] == []
    request(endpoint, "GET", "/api/v1/study-bank?page=0", token=token, expected=422)
    request(
        endpoint, "GET", "/api/v1/study-bank?subject=%27%20OR%201%3D1--", token=token
    )
    for payload in [
        {"count": 0},
        {"count": 21},
        {"count": True},
        {"minutes": 0},
        {"mode": "fake"},
        {"question_ids": "wrong"},
        {"question_ids": [ids[0], ids[1]]},
    ]:
        request(
            endpoint,
            "POST",
            "/api/v1/study-sessions",
            payload,
            token=token,
            expected=422,
        )
    session = request(
        endpoint,
        "POST",
        "/api/v1/study-sessions",
        {
            "mode": "practice",
            "source_id": source,
            "subject": "数学",
            "grade_band": "初中",
            "search": "1+1",
            "count": 1,
        },
        token=token,
    )
    assert session["items"][0]["question"]["id"] == ids[0]
    path = "/api/v1/study-sessions/" + session["id"]
    assert (
        session["question_count"] == 1
        and session["status"] == "active"
        and session["items"][0]["student_answer"] is None
    )
    assert (
        "answer" not in session["items"][0]
        and "answer" not in session["items"][0]["question"]
    )
    request(endpoint, "GET", path, token=foreign, expected=404)
    request(
        endpoint,
        "PATCH",
        path,
        {"version": 1, "answers": []},
        token=foreign,
        expected=404,
    )
    request(
        endpoint, "POST", path + "/submit", {"version": 1}, token=foreign, expected=404
    )
    item = session["items"][0]["id"]
    request(
        endpoint,
        "PATCH",
        path,
        {"version": 1, "answers": [{"id": "forged", "answer": ["A"]}]},
        token=token,
        expected=422,
    )
    saved = request(
        endpoint,
        "PATCH",
        path,
        {"version": 1, "answers": [{"id": item, "answer": ["A"]}]},
        token=token,
    )
    assert saved["version"] == 2 and saved["items"][0]["student_answer"] == ["A"]
    request(
        endpoint,
        "PATCH",
        path,
        {"version": 1, "answers": [{"id": item, "answer": ["B"]}]},
        token=token,
        expected=409,
    )
    assert request(endpoint, "GET", path, token=token)["items"][0][
        "student_answer"
    ] == ["A"]
    # The session retains the question served, even if the public bank changes.
    query(
        env,
        f"UPDATE dataset_questions SET answer=JSON_QUOTE('B'),question_text='已更新的题目' WHERE id='{ids[0]}'",
    )
    result = request(endpoint, "POST", path + "/submit", {"version": 2}, token=token)
    assert result["status"] == "submitted" and result["results"] == {
        "correct": 1,
        "pending": 0,
        "answered": 1,
        "total": 1,
        "score": 5,
        "max_score": 5,
    }
    assert (
        result["items"][0]["answer"] == "A"
        and "计算" in result["items"][0]["question"]["question_text"]
    )
    again = request(endpoint, "POST", path + "/submit", {"version": 1}, token=token)
    assert (
        again["version"] == result["version"] and again["results"] == result["results"]
    )
    request(
        endpoint,
        "PATCH",
        path,
        {"version": result["version"], "answers": [{"id": item, "answer": ["B"]}]},
        token=token,
        expected=409,
    )
    query(
        env, f"UPDATE dataset_questions SET answer=JSON_QUOTE('A') WHERE id='{ids[0]}'"
    )
    exam = request(
        endpoint,
        "POST",
        "/api/v1/study-sessions",
        {
            "mode": "exam",
            "source_id": source,
            "subject": "数学",
            "count": 5,
            "minutes": 10,
        },
        token=token,
    )
    assert exam["question_count"] == 5 and 0 < exam["remaining_seconds"] <= 600
    assert len({q["question"]["id"] for q in exam["items"]}) == 5
    exam_path = "/api/v1/study-sessions/" + exam["id"]
    payload = {
        "version": 1,
        "answers": [{"id": q["id"], "answer": ["A"]} for q in exam["items"]],
    }
    saved = request(endpoint, "PATCH", exam_path, payload, token=token)
    resumed = request(endpoint, "GET", exam_path, token=token)
    assert (
        all(q["student_answer"] == ["A"] for q in resumed["items"])
        and resumed["remaining_seconds"] <= 600
    )
    query(
        env,
        f"UPDATE study_sessions SET deadline_at=UTC_TIMESTAMP(6)-INTERVAL 1 SECOND WHERE id='{exam['id']}'",
    )
    assert request(endpoint, "GET", exam_path, token=token)["expired"] == 1
    payload["version"] = saved["version"]
    request(endpoint, "PATCH", exam_path, payload, token=token, expected=409)
    result = request(
        endpoint,
        "POST",
        exam_path + "/submit",
        {"version": saved["version"]},
        token=token,
    )
    assert result["results"]["correct"] == 5 and result["results"]["score"] == 25
    blank = request(
        endpoint,
        "POST",
        "/api/v1/study-sessions",
        {"mode": "practice", "question_ids": [ids[1]]},
        token=token,
    )
    result = request(
        endpoint,
        "POST",
        "/api/v1/study-sessions/" + blank["id"] + "/submit",
        {"version": 1},
        token=token,
    )
    assert (
        result["results"]["score"] == 0
        and result["results"]["answered"] == 0
        and result["results"]["pending"] == 0
    )
    assert len(request(endpoint, "GET", "/api/v1/study-sessions", token=token)) == 3
    assert request(endpoint, "GET", "/api/v1/study-sessions", token=foreign) == []
    assert (
        query(env, f"SELECT COUNT(*) FROM mastery_states WHERE user_id='{actor['id']}'")
        == "0"
    )
    assert (
        query(env, f"SELECT COUNT(*) FROM questions WHERE user_id='{actor['id']}'")
        == "0"
    )
    print(
        "Study bank passed: real sources/filtering, hidden answers, owner isolation, validation, durable drafts/CAS, frozen snapshots, idempotent grading, server deadlines, empty answers and no fabricated mastery",
        flush=True,
    )
    chemical_source = insert(
        "dataset_sources", key="study-chemical-" + uuid4().hex, name="化学排版验收题库"
    )
    insert(
        "dataset_questions",
        dataset_source_id=chemical_source,
        source_item_id="hydrate",
        content_hash=uuid4().hex,
        subject="化学",
        grade="高二",
        grade_band="高中",
        question_text=r"胆矾$${CuSO_{4}5H_{2}O}$$可写作$${[Cu(H_{2}O)_{4}]SO_{4}H_{2}O}$$，下列说法正确的是",
        question_type="multiple-choice",
        options=[
            {"key": "A", "text": r"所有氧原子都采取$${sp^{3}}$$杂化"},
            {"key": "B", "text": "氧原子存在配位键和氢键两种化学键"},
            {"key": "C", "text": r"$${Cu^{2+}}$$的价电子排布式为$${3d^{8}4s^{1}}$$"},
            {"key": "D", "text": "胆矾中的水在不同温度下会分步失去"},
        ],
        answer=json.dumps("D"),
        solution=r"水分步失去。独立公式：\[Cu^{2+}\]",
        has_answer=True,
        usable_for_practice=True,
        usable_for_auto_grade=True,
    )
    return {
        "QA_STUDY_CHEM_SOURCE": chemical_source,
        "QA_STUDY_EMAIL": email,
        "QA_STUDY_PASSWORD": password,
        "QA_STUDY_SOURCE": source,
    }
