"""A high-ranked geometry distractor must not train a linear-equation target."""

import json
from pathlib import Path
from uuid import uuid4

from smoke_cangjie_accounts import request
from smoke_cangjie_detail import fixture_insert


def alignment(endpoint, env, query):
    insert = fixture_insert(env, query)
    user = request(
        endpoint,
        "POST",
        "/api/v1/auth/register",
        {
            "email": f"alignment-{uuid4().hex}@example.test",
            "name": "相关性核验",
            "password": "alignment-test-password",
        },
    )
    token = user["access_token"]
    owner = user["id"]
    original = request(
        endpoint,
        "POST",
        "/api/v1/questions/manual",
        {"question_text": "解方程：2*x+3=11", "subject": "数学", "grade": "初一"},
        token=token,
    )
    mid = original["id"]
    knowledge = insert(
        "knowledge_points",
        subject="数学",
        code="ZZ-alignment-" + uuid4().hex,
        name="一元一次方程",
    )
    source = insert(
        "dataset_sources", key="alignment-" + uuid4().hex, name="隔离相关性核验"
    )

    def candidate(stem):
        return insert(
            "dataset_questions",
            dataset_source_id=source,
            source_item_id=uuid4().hex,
            subject="数学",
            grade="初一",
            grade_band="初中",
            question_text=stem,
            question_type="填空题",
            answer=json.dumps("x=5"),
            has_answer=True,
            usable_for_practice=True,
            usable_for_auto_grade=True,
            content_hash=uuid4().hex,
        )

    bad = candidate("比较甲乙丙三人行进路线长度的大小关系")
    good = candidate("解方程：3*x+4=19")
    fixture = Path(env["CANGJIE_TEST_RETRIEVAL_STATE"])

    def hits(ids):
        fixture.write_text(
            json.dumps(
                {
                    "hits": [
                        {"id": value, "dense_rank": index + 1, "sparse_rank": index + 1}
                        for index, value in enumerate(ids)
                    ]
                }
            )
        )

    def snapshot():
        return query(
            env,
            f"SELECT (SELECT COUNT(*) FROM cognitive_updates WHERE user_id='{owner}'),(SELECT COUNT(*) FROM mastery_states WHERE user_id='{owner}'),(SELECT COUNT(*) FROM dataset_practice_attempts WHERE user_id='{owner}'),(SELECT COUNT(*) FROM review_plans WHERE user_id='{owner}')",
        )

    body = {"mistake_id": mid, "mode": "reinforce", "debug": True}
    try:
        hits([bad, good])
        selected = request(
            endpoint, "POST", "/api/v1/practice/recommend", body, token=token
        )
        assert selected["question_id"] == good
        assert "answer" not in selected
        trace = json.loads(
            query(
                env,
                f"SELECT retrieval_trace FROM practice_recommendations WHERE user_id='{owner}' AND dataset_question_id='{good}'",
            )
        )
        insert(
            "practice_recommendations",
            user_id=owner,
            mistake_id=mid,
            dataset_question_id=bad,
            mode="variation",
            retrieval_trace=trace,
        )
        hits([bad])
        before = snapshot()
        request(
            endpoint,
            "POST",
            "/api/v1/practice/recommend",
            {**body, "mode": "variation"},
            token=token,
            expected=404,
        )
        request(
            endpoint,
            "POST",
            "/api/v1/practice/attempt",
            {
                "mistake_id": mid,
                "question_id": bad,
                "mode": "variation",
                "student_answer": "x=5",
            },
            token=token,
            expected=409,
        )
        assert snapshot() == before
        # An already-served valid question changed into geometry must also be rejected.
        query(
            env,
            f"UPDATE dataset_questions SET question_text='比较三人路线长度' WHERE id='{good}'",
        )
        request(
            endpoint,
            "POST",
            "/api/v1/practice/attempt",
            {
                "mistake_id": mid,
                "question_id": good,
                "mode": "reinforce",
                "student_answer": "x=5",
            },
            token=token,
            expected=409,
        )
        assert snapshot() == before
        query(
            env,
            f"UPDATE dataset_questions SET question_text='解方程：3*x+4=19' WHERE id='{good}'",
        )
        insert(
            "problem_analyses",
            question_id=mid,
            subject="数学",
            final_answer="x=4",
            knowledge_points=["一元一次方程"],
        )
        result = request(
            endpoint,
            "POST",
            "/api/v1/practice/attempt",
            {
                "mistake_id": mid,
                "question_id": good,
                "mode": "reinforce",
                "student_answer": "x=5",
            },
            token=token,
        )
        assert result["correct"] is True and result["can_update_learning"] is True
        assert (
            query(
                env,
                f"SELECT knowledge_point FROM mastery_states WHERE user_id='{owner}'",
            )
            == "一元一次方程"
        )
        details = json.loads(
            query(
                env,
                f"SELECT grading_details FROM dataset_practice_attempts WHERE user_id='{owner}' AND dataset_question_id='{good}'",
            )
        )
        assert details["alignment_method"] == "symbolic_linear"
        assert (
            details["alignment_proof"]["context"]["source"]
            != trace["alignment_proof"]["context"]["source"]
        )
        missing = request(
            endpoint,
            "POST",
            "/api/v1/questions/manual",
            {"question_text": "内容还未核对", "subject": "数学"},
            token=token,
        )
        request(
            endpoint,
            "POST",
            "/api/v1/practice/recommend",
            {"mistake_id": missing["id"], "mode": "reinforce"},
            token=token,
            expected=422,
        )
        print(
            "Cangjie practice alignment passed: high-ranked distractor rejected, legacy cache rejected, changed candidate rejected, no learning writes on rejection, aligned attempt retained and missing target explicit"
        )
    finally:
        hits([])
        # The mapping suite creates its own identically named card later.
        # Keep this fixture's private card out of all subsequent scenarios.
        query(
            env,
            f"DELETE FROM dataset_practice_attempts WHERE user_id='{owner}' AND knowledge_id='{knowledge}'",
        )
        query(env, f"DELETE FROM knowledge_points WHERE id='{knowledge}'")
