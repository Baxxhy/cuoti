"""Run existing browser flows against the live isolated Cangjie backend."""

import json
import socket
import subprocess
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import urlopen
from uuid import uuid4

from smoke_cangjie_accounts import request
from smoke_cangjie_detail import fixture_insert
from smoke_cangjie_questions import query


def browser(endpoint, env):
    project = Path(__file__).resolve().parents[1]
    before_learning = query(
        env,
        "SELECT (SELECT COUNT(*) FROM users),(SELECT COUNT(*) FROM mastery_states),(SELECT COUNT(*) FROM cognitive_updates)",
    )
    subprocess.run(
        ["bash", "scripts/cangjie.sh", "seed-knowledge"],
        cwd=project,
        env=env,
        check=True,
    )
    seeded = query(env, "SELECT id FROM knowledge_points WHERE code='curr.数学.高一.1'")
    assert seeded
    relations = query(env, "SELECT COUNT(*) FROM knowledge_relations")
    subprocess.run(
        ["bash", "scripts/cangjie.sh", "seed-knowledge"],
        cwd=project,
        env=env,
        check=True,
    )
    assert (
        query(env, "SELECT id FROM knowledge_points WHERE code='curr.数学.高一.1'")
        == seeded
    )
    assert query(env, "SELECT COUNT(*) FROM knowledge_relations") == relations
    assert (
        query(
            env,
            "SELECT (SELECT COUNT(*) FROM users),(SELECT COUNT(*) FROM mastery_states),(SELECT COUNT(*) FROM cognitive_updates)",
        )
        == before_learning
    )
    print(
        "Cangjie public knowledge passed: original content, repeat-safe IDs/relations and no student learning writes"
    )
    with urlopen(endpoint + "/livez", timeout=5) as response:
        assert json.load(response)["service"] == "zhiwei-cangjie"
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        frontend_port = listener.getsockname()[1]
    task_email = f"task-browser-{uuid4()}@minddimension.local"
    task_password = "TaskBrowser-" + uuid4().hex
    actor = request(
        endpoint,
        "POST",
        "/api/v1/auth/register",
        {
            "email": task_email,
            "password": task_password,
            "name": "任务验收学生",
            "grade": "初一",
        },
    )
    token = actor["access_token"]
    question = request(
        endpoint,
        "POST",
        "/api/v1/questions/manual",
        {
            "question_text": "解方程：2x+3=11",
            "student_answer": "x=7",
            "student_steps": ["2x=11+3", "x=7"],
            "subject": "数学",
            "grade": "初一",
        },
        token=token,
    )
    insert = fixture_insert(env, query)
    analysis = insert(
        "problem_analyses",
        question_id=question["id"],
        subject="数学",
        final_answer="x=4",
        knowledge_points=["等式的性质"],
    )
    insert("reference_steps", analysis_id=analysis, step_index=0, text="2x=8")
    insert("reference_steps", analysis_id=analysis, step_index=1, text="x=4")
    insert(
        "diagnoses",
        question_id=question["id"],
        first_error_step=0,
        root_misconception="等式两边要保持相等",
    )
    visual_email = f"visual-browser-{uuid4()}@minddimension.local"
    visual_password = "VisualBrowser-" + uuid4().hex
    visual_actor = request(
        endpoint,
        "POST",
        "/api/v1/auth/register",
        {
            "email": visual_email,
            "password": visual_password,
            "name": "函数图示验收",
            "grade": "初三",
        },
    )
    visual_question = request(
        endpoint,
        "POST",
        "/api/v1/questions/manual",
        {"question_text": "函数：y=x^2-2x+1", "subject": "数学", "grade": "初三"},
        token=visual_actor["access_token"],
    )
    insert(
        "problem_analyses",
        question_id=visual_question["id"],
        subject="数学",
        final_answer="顶点(1,0)",
        knowledge_points=["二次函数"],
    )
    insert(
        "diagnoses",
        question_id=visual_question["id"],
        root_misconception="顶点式的参数关系",
        first_error_step=0,
    )
    draft_email = f"draft-browser-{uuid4()}@minddimension.local"
    draft_password = "DraftBrowser-" + uuid4().hex
    draft_actor = request(
        endpoint,
        "POST",
        "/api/v1/auth/register",
        {
            "email": draft_email,
            "password": draft_password,
            "name": "双设备任务验收",
            "grade": "初一",
        },
    )
    draft_question = request(
        endpoint,
        "POST",
        "/api/v1/questions/manual",
        {
            "question_text": "解方程：2x+3=11",
            "subject": "数学",
            "grade": "初一",
            "student_answer": "x=7",
            "student_steps": ["2x=11+3", "x=7"],
        },
        token=draft_actor["access_token"],
    )
    insert(
        "problem_analyses",
        question_id=draft_question["id"],
        subject="数学",
        final_answer="x=4",
        knowledge_points=["等式的性质"],
    )
    insert(
        "diagnoses",
        question_id=draft_question["id"],
        first_error_step=0,
        root_misconception="移项符号",
    )
    budget_email = f"budget-browser-{uuid4()}@minddimension.local"
    budget_password = "BudgetBrowser-" + uuid4().hex
    budget_actor = request(
        endpoint,
        "POST",
        "/api/v1/auth/register",
        {
            "email": budget_email,
            "password": budget_password,
            "name": "预算恢复验收",
            "grade": "初一",
        },
    )
    budget_question = request(
        endpoint,
        "POST",
        "/api/v1/questions/manual",
        {
            "subject": "数学",
            "grade": "初一",
            "question_text": "解方程：2x+3=11",
            "student_steps": ["2x=14"],
        },
        token=budget_actor["access_token"],
    )
    insert(
        "problem_analyses",
        question_id=budget_question["id"],
        subject="数学",
        final_answer="x=4",
    )
    insert(
        "diagnoses",
        question_id=budget_question["id"],
        first_error_step=0,
        root_misconception="移项符号",
    )
    from smoke_cangjie_learning_tasks import task_request, wait_task

    budget_task = wait_task(
        endpoint,
        task_request(
            endpoint,
            "/api/v1/learning-tasks",
            budget_actor["access_token"],
            {"question_id": budget_question["id"], "request_id": str(uuid4())},
            status=202,
        )["id"],
        budget_actor["access_token"],
    )
    query(
        env,
        f"UPDATE learning_tasks SET checkpoint=JSON_SET(checkpoint,'$.rounds',24) WHERE id='{budget_task['id']}'",
    )
    # Role identities exist only in this disposable database. Public registration
    # remains student-only; the fixture grants roles through its local DB access.
    roles = {}
    for role in ("teacher", "guardian", "admin"):
        email = f"role-browser-{role}-{uuid4().hex}@example.test"
        password = "RoleBrowser-" + uuid4().hex
        user = request(
            endpoint,
            "POST",
            "/api/v1/auth/register",
            {"email": email, "password": password, "name": "角色验收" + role},
        )
        query(env, f"UPDATE users SET role='{role}' WHERE id='{user['id']}'")
        roles[role] = {"email": email, "password": password, "id": user["id"]}
    insert(
        "guardian_student_links",
        guardian_id=roles["guardian"]["id"],
        student_id=actor["id"],
    )
    insert("tutor_sessions", user_id=actor["id"], question_id=question["id"])
    role_env = {"QA_ROLE_TESTS": "1"}
    for role, account in roles.items():
        role_env[f"QA_{role.upper()}_EMAIL"] = account["email"]
        role_env[f"QA_{role.upper()}_PASSWORD"] = account["password"]
    from smoke_cangjie_clear_entry import clear_entry_fixture
    from smoke_cangjie_experience import experience_fixtures
    experience = experience_fixtures(endpoint, env, query)
    clear_question, clear_token = clear_entry_fixture(endpoint, env, query)
    from smoke_cangjie_personas import persona_fixtures
    personas = persona_fixtures(endpoint, env, query)
    browser_env = {
        **env,
        **role_env,
        **personas,
        "ZHIWEI_BACKEND_KIND": "cangjie",
        "QA_ENTRY_CLEAR_QUESTION_ID": clear_question,
        "QA_ENTRY_CLEAR_TOKEN": clear_token,
        "QA_EXPERIENCE_EMAIL": experience['user']['email'],
        "QA_EXPERIENCE_PASSWORD": experience['password'],
        "QA_EXPERIENCE_QUESTION_ID": experience['ids'][0],
        "QA_BUDGET_EMAIL": budget_email,
        "QA_BUDGET_PASSWORD": budget_password,
        "QA_BUDGET_QUESTION_ID": budget_question["id"],
        "QA_BUDGET_TASK_ID": budget_task["id"],
        "QA_DRAFT_EMAIL": draft_email,
        "QA_DRAFT_PASSWORD": draft_password,
        "QA_DRAFT_QUESTION_ID": draft_question["id"],
        "QA_VISUAL_EMAIL": visual_email,
        "QA_VISUAL_PASSWORD": visual_password,
        "QA_VISUAL_QUESTION_ID": visual_question["id"],
        "QA_TASK_EMAIL": task_email,
        "QA_TASK_PASSWORD": task_password,
        "QA_TASK_QUESTION_ID": question["id"],
        "ZHIWEI_BACKEND_PORT": str(urlsplit(endpoint).port),
        "ZHIWEI_BACKEND_URL": endpoint,
        "ZHIWEI_API_URL": endpoint + "/api/v1",
        "ZHIWEI_FRONTEND_PORT": str(frontend_port),
        "ZHIWEI_FRONTEND_URL": f"http://127.0.0.1:{frontend_port}",
    }
    subprocess.run(
        ["pnpm", "--dir", "frontend", "run", "test:e2e"],
        cwd=Path(__file__).resolve().parents[1],
        env=browser_env,
        check=True,
    )
    print(
        "Cangjie browser passed: existing frontend flows used isolated native backend"
    )
