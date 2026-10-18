"""Real native recommendation flow through isolated BGE and Qdrant HTTP fixtures."""

import json
from pathlib import Path
from uuid import uuid4

from smoke_cangjie_accounts import request
from smoke_cangjie_detail import fixture_insert


def retrieval(endpoint, env, query, token, other, state):
    insert = fixture_insert(env, query)
    fixture = Path(env["CANGJIE_TEST_RETRIEVAL_STATE"])

    def index(hits=(), unavailable=False):
        temporary = fixture.with_suffix(".new")
        temporary.write_text(
            json.dumps(
                {
                    "hits": [
                        {
                            "id": value,
                            "dense_rank": number + 1,
                            "sparse_rank": number + 1,
                        }
                        for number, value in enumerate(hits)
                    ],
                    "unavailable": unavailable,
                }
            )
        )
        temporary.replace(fixture)

    original = request(
        endpoint,
        "POST",
        "/api/v1/questions/manual",
        {
            "question_text": "解方程：2*x+3=11",
            "subject": "数学",
            "grade": "初一",
            "question_type": "综合题",
        },
        token=token,
    )
    mid = original["id"]
    owner = request(endpoint, "GET", "/api/v1/auth/me", token=token)["id"]
    analysis = insert(
        "problem_analyses",
        question_id=mid,
        subject="数学",
        final_answer="x=4",
        knowledge_points=["一元一次方程"],
    )
    insert("reference_steps", analysis_id=analysis, step_index=0, text="2x=8")
    insert(
        "diagnoses",
        question_id=mid,
        error_type="boundary_omission",
        root_misconception="遗漏等式条件",
    )
    kp = insert(
        "knowledge_points",
        subject="数学",
        code="000-RETR-" + uuid4().hex,
        name="一元一次方程",
    )
    source = insert("dataset_sources", key="retrieval-" + uuid4().hex, name="检索验证")

    def candidate(stem, answer, subject="数学"):
        qid = insert(
            "dataset_questions",
            dataset_source_id=source,
            source_item_id=uuid4().hex,
            subject=subject,
            grade="初一",
            grade_band="初中",
            question_type="填空题",
            question_text=stem,
            answer=json.dumps(answer),
            solution="根据等式条件移项求解。",
            knowledge_points=["一元一次方程"],
            has_answer=True,
            has_solution=True,
            answer_verified=True,
            usable_for_practice=True,
            usable_for_auto_grade=True,
            content_hash=uuid4().hex,
        )
        query(
            env,
            f"INSERT INTO question_knowledge_links (id,dataset_question_id,knowledge_point_id,role,confidence,mapping_method,created_at,updated_at) VALUES ('{uuid4()}','{qid}','{kp}','primary',1,'fixture',UTC_TIMESTAMP(),UTC_TIMESTAMP())",
        )
        return qid

    first = candidate("解方程：3*x+4=19", "x=5")
    second = candidate("求解方程：4*x-7=9", "x=4")
    duplicate = candidate("解方程：2*x+3=11", "x=4")
    foreign_subject = candidate("物理题：3*x+4=19", "x=5", "物理")
    wrong_grade = candidate("求解方程：7*x+1=22", "x=3")
    no_answer = candidate("求解方程：8*x+1=25", "")
    ungradable = candidate("求解方程：9*x+1=28", "x=3")
    query(
        env,
        f"UPDATE dataset_questions SET grade='高一',grade_band='高中' WHERE id='{wrong_grade}'",
    )
    query(
        env,
        f"UPDATE dataset_questions SET usable_for_auto_grade=0 WHERE id='{ungradable}'",
    )
    route = "/api/v1/practice/recommend"
    body = {"mistake_id": mid, "mode": "reinforce", "debug": True}
    request(endpoint, "POST", route, body, expected=401)
    request(endpoint, "POST", route, body, token=other, expected=404)
    request(endpoint, "POST", route, {**body, "mode": "bad"}, token=token, expected=422)
    try:
        assert (
            query(
                env,
                "SELECT DATETIME_PRECISION FROM information_schema.columns WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='practice_recommendations' AND COLUMN_NAME='created_at'",
            )
            == "6"
        )
        index(
            [
                duplicate,
                foreign_subject,
                first,
                second,
                wrong_grade,
                no_answer,
                ungradable,
            ]
        )
        chosen = request(endpoint, "POST", route, body, token=token)
        assert chosen["question_id"] in {first, second}
        assert chosen["debug"]["dense_rank"] in {3, 4} and chosen["debug"][
            "sparse_rank"
        ] in {3, 4}
        assert chosen["debug"]["target_knowledge_id"] == kp
        assert (
            chosen["debug"]["error_match"] == "boundary_omission"
            and "一元一次方程" in chosen["recommendation"]
        )
        assert "answer" not in chosen and "solution" not in chosen
        assert chosen["knowledge_points"][0]["id"] == kp
        saved = query(
            env,
            f"SELECT COUNT(*) FROM practice_recommendations WHERE mistake_id='{mid}'",
        )
        calls = fixture.with_suffix(".calls.jsonl")
        before = calls.read_text().count("\n")
        cached = request(endpoint, "POST", route, body, token=token)
        assert cached["question_id"] == chosen["question_id"]
        assert calls.read_text().count("\n") == before
        assert (
            query(
                env,
                f"SELECT COUNT(*) FROM practice_recommendations WHERE mistake_id='{mid}'",
            )
            == saved
        )
        next_question = request(
            endpoint, "POST", route, {**body, "force_new": True}, token=token
        )
        assert (
            next_question["question_id"] in {first, second}
            and next_question["question_id"] != chosen["question_id"]
        )
        cached_next = request(endpoint, "POST", route, body, token=token)
        assert cached_next["question_id"] == next_question["question_id"]
        request(
            endpoint,
            "POST",
            route,
            {**body, "force_new": True},
            token=token,
            expected=404,
        )
        answered = request(
            endpoint,
            "POST",
            "/api/v1/practice/attempt",
            {
                "mistake_id": mid,
                "question_id": next_question["question_id"],
                "mode": "reinforce",
                "student_answer": "x=5"
                if next_question["question_id"] == first
                else "x=4",
            },
            token=token,
        )
        assert answered["correct"] is True and answered["can_update_learning"]
        index(unavailable=True)
        request(
            endpoint,
            "POST",
            route,
            {**body, "force_new": True},
            token=token,
            expected=503,
        )
        index([])
        request(
            endpoint,
            "POST",
            route,
            {**body, "mode": "variation"},
            token=token,
            expected=404,
        )
        third = candidate("求未知数：6*x+2=20", "x=3")
        index([third])
        before_rows = query(
            env,
            f"SELECT COUNT(*) FROM practice_recommendations WHERE mistake_id='{mid}'",
        )
        query(
            env,
            f"ALTER TABLE practice_recommendations ADD CONSTRAINT retrieval_rollback CHECK (dataset_question_id<>'{third}')",
        )
        try:
            request(
                endpoint,
                "POST",
                route,
                {**body, "force_new": True},
                token=token,
                expected=503,
            )
            assert (
                query(
                    env,
                    f"SELECT COUNT(*) FROM practice_recommendations WHERE mistake_id='{mid}'",
                )
                == before_rows
            )
        finally:
            query(
                env,
                "ALTER TABLE practice_recommendations DROP CHECK retrieval_rollback",
            )
        recovered = request(
            endpoint, "POST", route, {**body, "force_new": True}, token=token
        )
        assert recovered["question_id"] == third
        recorded = [json.loads(line) for line in calls.read_text().splitlines()]
        assert any(item["path"] == "/embed" for item in recorded)
        assert any(item["path"] == "/rerank" for item in recorded)
        assert any(
            "prefetch" in item["body"]
            for item in recorded
            if item["path"].endswith("/points/query")
        )
        # A stored transfer question must be revalidated, even if its verified flag is true.
        sid = insert(
            "tutor_sessions",
            user_id=owner,
            question_id=mid,
            stage="near_transfer",
            state={"understanding_passed": True, "mastery_proven": False},
        )
        session_route = "/api/v1/tutor/sessions/" + sid
        state["variant"] = True
        state["variant_result"] = {
            "question_text": "解方程：5*x+2=27",
            "answer": "x=5",
            "reference_solution": ["5x=25", "x=5"],
            "explanation": "等式两边先减2，再除以5。",
        }
        index([first, second])
        generated = request(
            endpoint,
            "POST",
            session_route + "/variant",
            {"transfer_type": "near"},
            token=token,
        )
        current = generated["id"]
        metadata = json.loads(
            query(
                env,
                f"SELECT generation_metadata FROM variant_questions WHERE id='{current}'",
            )
        )
        assert (
            metadata["retrieval_pipeline"] == "bge_m3_qdrant_reranker"
            and metadata["retrieval_status"] == "ok"
        )
        assert metadata["retrieval_ids"] and set(metadata["retrieval_ids"]) <= {
            first,
            second,
        }
        reused = request(
            endpoint,
            "POST",
            session_route + "/variant",
            {"transfer_type": "near"},
            token=token,
        )
        assert reused["id"] == current
        query(
            env,
            f"UPDATE variant_questions SET answer='x=99',verified=1 WHERE id='{current}'",
        )
        restored = request(endpoint, "GET", session_route, token=token)
        assert restored["activity"]["variant_id"] != current
        session_state = json.loads(
            query(env, f"SELECT state FROM tutor_sessions WHERE id='{sid}'")
        )
        assert (
            current in session_state["invalidated_variant_ids"]
            and session_state["near_variant_id"] != current
        )
        # Index failures use the original generation fallback and are recorded honestly.
        index(unavailable=True)
        sid2 = insert(
            "tutor_sessions",
            user_id=owner,
            question_id=mid,
            stage="near_transfer",
            state={"understanding_passed": True},
        )
        fallback = request(
            endpoint,
            "POST",
            "/api/v1/tutor/sessions/" + sid2 + "/variant",
            {"transfer_type": "near"},
            token=token,
        )
        metadata = json.loads(
            query(
                env,
                f"SELECT generation_metadata FROM variant_questions WHERE id='{fallback['id']}'",
            )
        )
        assert metadata["retrieval_status"] == "unavailable"
        print(
            "Cangjie retrieval passed: BGE/Qdrant/reranker HTTP, native candidates, filtering, cache, exclusions, practice submission, variant revalidation, rollback and unavailable fallback"
        )
    finally:
        index([])
        state["variant"] = False
