"""Native practice authorization, signed images, handwriting and learning evidence."""

import hashlib
import hmac
import json
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import uuid4

from smoke_cangjie_accounts import request
from smoke_cangjie_detail import fixture_insert
from smoke_cangjie_handwriting import handwriting


def practice(endpoint, env, query, token, other, state):
    insert = fixture_insert(env, query)
    owner = request(endpoint, "GET", "/api/v1/auth/me", token=token)["id"]
    mistake = request(
        endpoint,
        "POST",
        "/api/v1/questions/manual",
        {
            "question_text": "解方程 2x+3=11",
            "subject": "练习验证学科",
            "knowledge_points": ["原题知识"],
            "student_answer": "x=5",
        },
        token=token,
    )
    mid = mistake["id"]
    mistake = request(endpoint, "GET", "/api/v1/questions/" + mid, token=token)
    works = [str(uuid4())]
    query(
        env,
        f"INSERT INTO student_works (id,user_id,question_id,answer,explanation,created_at,updated_at) VALUES ('{works[0]}','{owner}','{mid}','x=5','',UTC_TIMESTAMP(),UTC_TIMESTAMP())",
    )
    fields = (
        "question_text",
        "student_answer",
        "subject",
        "grade",
        "title",
        "formulas",
        "options",
        "question_type",
        "knowledge_points",
    )
    content = {key: mistake[key] for key in fields}
    content["student_work_revisions"] = query(
        env, f"SELECT id FROM student_works WHERE question_id='{mid}' ORDER BY id"
    ).splitlines()
    fingerprint = hashlib.sha256(
        json.dumps(content, ensure_ascii=False, sort_keys=True).encode()
    ).hexdigest()
    source = insert("dataset_sources", key="practice-" + uuid4().hex, name="练习回归")
    knowledge = insert(
        "knowledge_points",
        code="practice-" + uuid4().hex,
        name="一元一次方程",
        subject=mistake["subject"],
    )
    insert("diagnoses", question_id=mid, error_type="exact", root_misconception="")
    root = Path(env["CANGJIE_QUESTION_BANK_ROOT"])
    root.mkdir(parents=True, exist_ok=True)
    picture = root / "真实题图.png"
    picture.write_bytes(b"practice-picture-bytes")
    escaped = root.parent / "outside.txt"
    escaped.write_bytes(b"must-not-be-served")
    (root / "link.txt").symlink_to(escaped)
    qid = insert(
        "dataset_questions",
        dataset_source_id=source,
        source_item_id="practice",
        subject=mistake["subject"],
        grade_band="初中",
        question_text="求解 3x=15",
        question_type="填空题",
        answer=json.dumps("x=5"),
        has_answer=True,
        solution="3x=15\nx=5",
        usable_for_practice=True,
        usable_for_auto_grade=True,
        content_hash=uuid4().hex,
        image_paths=[
            str(picture),
            str(escaped),
            str(root / "../outside.txt"),
            str(root / "link.txt"),
        ],
    )
    recommendation = insert(
        "practice_recommendations",
        user_id=owner,
        mistake_id=mid,
        dataset_question_id=qid,
        mode="reinforce",
        retrieval_trace={
            "source_question_fingerprint": fingerprint,
            "target_knowledge_id": knowledge,
        },
    )

    def signed(index, *, expiry=None):
        path = f"/api/v1/practice/questions/{qid}/images/{index}"
        expiry = expiry if expiry is not None else int(time.time()) + 3600
        signature = hmac.new(
            env["CANGJIE_AUTH_SECRET"].encode(),
            f"media:v1:{expiry}:{path}".encode(),
            hashlib.sha256,
        ).hexdigest()
        return path + f"?expires={expiry}&signature={signature}"

    def image(path, status, method="GET", headers=None):
        try:
            response = urlopen(
                Request(endpoint + path, method=method, headers=headers or {}),
                timeout=15,
            )
        except HTTPError as error:
            response = error
        with response:
            assert response.status == status, (response.status, response.read())
            return response.read(), response.headers

    image(f"/api/v1/practice/questions/{qid}/images/0", 403)
    image(signed(0, expiry=int(time.time()) - 1), 403)
    assert image(signed(0), 200)[0] == picture.read_bytes()
    assert image(signed(0), 200, "HEAD")[0] == b""
    assert image(signed(0), 206, headers={"Range": "bytes=0-7"})[0] == b"practice"
    for index in [-1, 1, 2, 3, 9]:
        image(signed(index), 404)
    base = {
        "mistake_id": mid,
        "question_id": qid,
        "mode": "reinforce",
        "student_answer": "x=5",
    }
    route = "/api/v1/practice/attempt"
    request(endpoint, "POST", route, base, expected=401)
    request(endpoint, "POST", route, base, token=other, expected=404)
    request(endpoint, "POST", route, {**base, "mode": "bad"}, token=token, expected=422)
    request(
        endpoint,
        "POST",
        route,
        {**base, "duration_seconds": 7201},
        token=token,
        expected=422,
    )
    query(
        env,
        f"UPDATE practice_recommendations SET retrieval_trace=JSON_OBJECT() WHERE id='{recommendation}'",
    )
    request(endpoint, "POST", route, base, token=token, expected=409)
    trace = (
        json.dumps(
            {
                "source_question_fingerprint": fingerprint,
                "target_knowledge_id": knowledge,
            }
        )
        .encode()
        .hex()
    )
    query(
        env,
        f"UPDATE practice_recommendations SET retrieval_trace=CONVERT(0x{trace} USING utf8mb4) WHERE id='{recommendation}'",
    )
    written = handwriting(
        endpoint,
        env,
        token,
        other,
        {
            "id": qid,
            "activity": {"id": "practice"},
            "upload_fields": {"mistake_id": mid, "mode": "reinforce"},
            "answer_fields": base,
        },
        state,
        kind="practice",
    )
    before = query(
        env, f"SELECT COUNT(*) FROM cognitive_updates WHERE question_id='{mid}'"
    )
    undecided = request(
        endpoint, "POST", route, {**base, "student_answer": ""}, token=token
    )
    assert (
        undecided["correct"] is None
        and undecided["mastery"] is None
        and not undecided["can_update_learning"]
    )
    assert (
        query(env, f"SELECT COUNT(*) FROM cognitive_updates WHERE question_id='{mid}'")
        == before
    )
    assert (
        query(
            env,
            f"SELECT COUNT(*) FROM dataset_practice_attempts WHERE mistake_id='{mid}'",
        )
        == "0"
    )
    # A failed attempt write must roll back all learning evidence.
    query(
        env,
        f"ALTER TABLE dataset_practice_attempts ADD CONSTRAINT practice_rollback CHECK (mistake_id<>'{mid}')",
    )
    try:
        request(endpoint, "POST", route, {**base, **written}, token=token, expected=503)
        assert (
            query(
                env, f"SELECT COUNT(*) FROM cognitive_updates WHERE question_id='{mid}'"
            )
            == before
        )
    finally:
        query(env, "ALTER TABLE dataset_practice_attempts DROP CHECK practice_rollback")
    result = request(
        endpoint,
        "POST",
        route,
        {**base, **written, "duration_seconds": 12},
        token=token,
    )
    assert result["correct"] is True and result["can_update_learning"]
    assert (
        result["answer"] == "x=5"
        and result["mastery_before"] == 0
        and result["mastery"] == 0.12
    )
    assert (
        query(
            env,
            f"SELECT knowledge_point FROM mastery_states WHERE user_id='{owner}' AND subject='练习验证学科'",
        )
        == "一元一次方程"
    )
    assert (
        query(env, f"SELECT COUNT(*) FROM cognitive_updates WHERE question_id='{mid}'")
        == "2"
    )
    assert (
        query(
            env,
            f"SELECT code FROM misconception_states WHERE user_id='{owner}' AND subject='练习验证学科'",
        )
        == "unclassified"
    )
    assert (
        query(
            env,
            f"SELECT COUNT(*) FROM dataset_practice_attempts WHERE mistake_id='{mid}' AND knowledge_id='{knowledge}' AND duration_seconds=12 AND JSON_UNQUOTE(student_answer)='x=5' AND JSON_EXTRACT(grading_details,'$.independent_answer')=true",
        )
        == "1"
    )
    from smoke_cangjie_learning_memory import practice_memory

    practice_memory(endpoint, env, query, token, state, mid, qid, insert)
    request(endpoint, "POST", route, base, token=token, expected=409)
    query(
        env,
        f"UPDATE dataset_questions SET options=JSON_ARRAY(JSON_OBJECT('key','A','text','甲'),JSON_OBJECT('key','B','text','乙')),answer=JSON_ARRAY('A','B') WHERE id='{qid}'",
    )
    insert(
        "practice_recommendations",
        user_id=owner,
        mistake_id=mid,
        dataset_question_id=qid,
        mode="variation",
        retrieval_trace={
            "source_question_fingerprint": fingerprint,
            "target_knowledge_id": knowledge,
        },
    )
    varied = request(
        endpoint,
        "POST",
        route,
        {**base, "mode": "variation", "student_answer": ["B", "A"]},
        token=token,
    )
    assert (
        varied["correct"] is True
        and varied["mastery_before"] == 0.12
        and varied["mastery"] == 0.3
    )
    assert (
        query(
            env,
            f"SELECT JSON_TYPE(student_answer) FROM dataset_practice_attempts WHERE mistake_id='{mid}' AND mode='variation'",
        )
        == "ARRAY"
    )
    query(env, f"DELETE FROM dataset_practice_attempts WHERE mistake_id='{mid}'")
    query(env, f"UPDATE questions SET student_answer='changed' WHERE id='{mid}'")
    request(endpoint, "POST", route, base, token=token, expected=409)
    print(
        "Cangjie practice passed: original fingerprint, signed images, path confinement, handwriting, grading, evidence, stale guards and rollback"
    )
