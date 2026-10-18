"""List filtering, deduplication and learning summaries using isolated fixtures."""

from urllib.parse import urlencode
from uuid import uuid4

from smoke_cangjie_accounts import request
from smoke_cangjie_detail import fixture_insert


def question_list(endpoint, env, query):
    account = request(
        endpoint,
        "POST",
        "/api/v1/auth/register",
        {
            "email": f"list-{uuid4().hex}@example.test",
            "password": "test-password-123",
            "name": "列表测试",
        },
    )
    token, owner = account["access_token"], account["id"]
    path = "/api/v1/questions"
    assert request(endpoint, "GET", path, token=token) == []
    request(endpoint, "GET", path, expected=401)
    request(endpoint, "POST", path, token=token, expected=405)
    insert = fixture_insert(env, query)

    def create(text, day, subject="数学"):
        item = request(
            endpoint,
            "POST",
            path + "/manual",
            {"question_text": text, "subject": subject},
            token=token,
        )
        query(
            env,
            f"UPDATE questions SET created_at='2026-01-{day:02d} 00:00:00' WHERE id='{item['id']}'",
        )
        return item["id"]

    old = create("Ａ X，求解？", 1)
    new = create("ａ\u3000x:求解。", 2)
    science = create("计算电压", 3, "物理")
    tagged = create("标记题目", 4)
    pending1, pending2 = create("识别待定一", 5), create("识别待定二", 6)
    query(
        env,
        f"UPDATE questions SET question_text='' WHERE id IN ('{pending1}','{pending2}')",
    )
    archived = create("已归档", 7)
    request(endpoint, "DELETE", path + "/" + archived, token=token)
    query(
        env,
        f"UPDATE questions SET tags=JSON_ARRAY('重点标签'), knowledge_points=JSON_ARRAY('一元方程') WHERE id='{new}'",
    )
    query(
        env,
        f"UPDATE questions SET title='独特标题', tags=JSON_ARRAY('特别标签') WHERE id='{tagged}'",
    )
    insert(
        "diagnoses",
        question_id=new,
        error_type="sign_error",
        root_misconception="旧误解",
        first_error_text="独特步骤",
    )
    insert(
        "diagnoses",
        question_id=new,
        error_type="sign_error",
        root_misconception="漏掉负根",
        created_at="2026-01-02 00:00:00",
    )
    insert(
        "mastery_states",
        user_id=owner,
        subject="数学",
        knowledge_point="一元方程",
        mastery_score=0.8,
    )
    insert(
        "mastery_states",
        user_id=owner,
        subject="物理",
        knowledge_point="一元方程",
        mastery_score=0.1,
        updated_at="2026-01-02 00:00:00",
    )
    insert(
        "review_plans",
        user_id=owner,
        question_id=new,
        due_at="2026-02-03 00:00:00",
        status="pending",
    )
    insert(
        "review_plans",
        user_id=owner,
        question_id=new,
        due_at="2026-02-01 00:00:00",
        status="completed",
    )
    insert(
        "review_plans",
        user_id=owner,
        question_id=new,
        due_at="2026-02-02 00:00:00",
        status="pending",
    )
    insert("question_assets", question_id=new, kind="crop", path="uploads/new.png")
    insert(
        "question_assets",
        question_id=new,
        kind="question_figure",
        path="uploads/excluded.png",
        created_at="2026-01-03 00:00:00",
    )
    job = insert(
        "processing_jobs",
        question_id=new,
        kind="analyze",
        status="failed",
        error="测试错误",
    )

    def fetch(**params):
        return request(endpoint, "GET", path + "?" + urlencode(params), token=token)

    rows = fetch()
    assert [r["id"] for r in rows] == [pending2, pending1, tagged, science, new]
    row = rows[-1]
    assert row["diagnosis_summary"] == "漏掉负根"
    assert (
        abs(row["mastery_score"] - 0.8) < 1e-6 and row["mastery_status"] == "基本稳定"
    )
    assert row["review_due_at"] == "2026-02-02T00:00:00+00:00"
    assert row["thumbnail_url"].startswith("/uploads/new.png?expires=")
    assert row["latest_job_id"] == job and row["latest_job_status"] == "failed"
    assert rows[0]["diagnosis_summary"] == "等待完成错因诊断"
    assert rows[0]["mastery_score"] == 0 and rows[0]["mastery_status"] == "需要巩固"
    assert rows[0]["thumbnail_url"] is None and rows[0]["latest_job_id"] is None
    assert [r["id"] for r in fetch(subject="物理")] == [science]
    for search in (
        "求解",
        "重点标签",
        "一元方程",
        "漏掉负根",
        "旧误解",
        "独特步骤",
        "sign_error",
        "符号错误",
        "符号",
    ):
        assert [r["id"] for r in fetch(search=search)] == [new], search
    assert [r["id"] for r in fetch(search="独特标题")] == [tagged]
    assert [r["id"] for r in fetch(search="特别标签")] == [tagged]
    assert fetch(subject="物理", search="符号错误") == []
    assert fetch(search="' OR 1=1 --") == []
    assert fetch(search="不存在") == []
    # Preserve the original SQL LIKE wildcard behavior and last query value.
    assert [r["id"] for r in fetch(search="%")] == [r["id"] for r in rows]
    repeated = request(
        endpoint,
        "GET",
        path + "?" + urlencode([("subject", "数学"), ("subject", "物理")]),
        token=token,
    )
    assert [r["id"] for r in repeated] == [science]
    insert(
        "mastery_states",
        user_id=owner,
        subject="数学",
        knowledge_point="一元方程",
        mastery_score=0.6,
        updated_at="2026-02-01 00:00:00",
    )
    assert fetch(search="一元方程")[0]["mastery_status"] == "继续巩固"
    # A different account with newer evidence cannot alter this account's summary.
    other = request(
        endpoint,
        "POST",
        "/api/v1/auth/register",
        {
            "email": f"list-other-{uuid4().hex}@example.test",
            "password": "test-password-123",
            "name": "隔离账号",
        },
    )
    insert(
        "mastery_states",
        user_id=other["id"],
        subject="数学",
        knowledge_point="一元方程",
        mastery_score=0.1,
        updated_at="2026-03-01 00:00:00",
    )
    assert fetch(search="一元方程")[0]["mastery_status"] == "继续巩固"
    assert request(endpoint, "GET", path, token=other["access_token"]) == []
    assert old not in [r["id"] for r in fetch()]
    print(
        "Cangjie list passed: owner isolation, filtering, taxonomy, Unicode deduplication, ordering, learning and job summaries"
    )
