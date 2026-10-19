"""Independent, persisted page-audit fixtures; analysis is controlled test data."""
from uuid import uuid4

from smoke_cangjie_accounts import request
from smoke_cangjie_detail import fixture_insert


def redesign_fixture(endpoint, env, query):
    email = f"routes-{uuid4().hex}@example.test"
    password = "RouteAudit-" + uuid4().hex
    actor = request(endpoint, "POST", "/api/v1/auth/register", {
        "email": email, "password": password, "name": "全站页面验收", "grade": "初一",
    })
    question = request(endpoint, "POST", "/api/v1/questions/manual", {
        "question_text": "解方程：2x+3=11", "student_answer": "x=7",
        "student_steps": ["2x=11+3", "x=7"], "subject": "数学", "grade": "初一",
    }, token=actor["access_token"])
    insert = fixture_insert(env, query)
    analysis = insert("problem_analyses", question_id=question["id"], subject="数学",
                      final_answer="x=4", verified=True, knowledge_points=["等式的性质"])
    insert("reference_steps", analysis_id=analysis, step_index=0, text="2x=8")
    insert("reference_steps", analysis_id=analysis, step_index=1, text="x=4")
    insert("diagnoses", question_id=question["id"], first_error_step=0,
           error_type="sign_error", root_misconception="移项需要改变符号")
    return {"QA_ROUTE_EMAIL": email, "QA_ROUTE_PASSWORD": password,
            "QA_ROUTE_QUESTION_ID": question["id"]}
