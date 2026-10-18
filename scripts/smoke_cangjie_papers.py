"""Paper creation, selection, editing, three export formats and downloads."""

import io
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from openpyxl import load_workbook
from smoke_cangjie_accounts import request
from smoke_cangjie_detail import fixture_insert


def papers(endpoint, env, query, token, other):
    insert = fixture_insert(env, query)
    owner = request(endpoint, "GET", "/api/v1/auth/me", token=token)["id"]
    subject = "组卷验证学科"

    def create_question(text, day):
        question = request(
            endpoint,
            "POST",
            "/api/v1/questions/manual",
            {"question_text": text, "subject": subject, "question_type": "综合题"},
            token=token,
        )
        query(
            env,
            f"UPDATE questions SET created_at='2026-01-{day:02} 00:00:00' WHERE id='{question['id']}'",
        )
        aid = insert(
            "problem_analyses",
            question_id=question["id"],
            subject=subject,
            final_answer="5",
            knowledge_points=["组卷回归知识点"],
        )
        insert(
            "reference_steps", analysis_id=aid, step_index=0, text="根据题目条件计算。"
        )
        return question["id"]

    first = create_question("组卷题甲：2+3=?", 2)
    second = create_question("=SUM(2,3)", 3)
    create_question("组卷题甲：2+3=?", 1)
    insert(
        "mastery_states",
        user_id=owner,
        subject=subject,
        knowledge_point="组卷回归知识点",
        mastery_score=0.4,
    )
    insert(
        "diagnoses",
        question_id=first,
        error_type="calculation",
        root_misconception="计算失误",
    )
    insert(
        "review_plans",
        user_id=owner,
        question_id=first,
        due_at="2026-01-01 00:00:00",
        status="pending",
    )
    base = "/api/v1/papers"
    candidates = request(
        endpoint,
        "GET",
        base + "/candidates?" + urlencode({"subject": subject}),
        token=token,
    )
    assert [q["id"] for q in candidates] == [second, first]
    assert candidates[0]["mastery_score"] == 0.4
    due = request(
        endpoint,
        "GET",
        base
        + "/candidates?"
        + urlencode(
            {"subject": subject, "due_review": "true", "error_type": "calculation"}
        ),
        token=token,
    )
    assert [q["id"] for q in due] == [first]
    assert (
        request(
            endpoint,
            "GET",
            base + "/candidates?" + urlencode({"subject": subject}),
            token=other,
        )
        == []
    )
    request(
        endpoint,
        "GET",
        base + "/candidates?mastery_min=0.9&mastery_max=0.1",
        token=token,
        expected=422,
    )
    request(
        endpoint,
        "POST",
        base,
        {"question_ids": [first], "default_score": 0},
        token=token,
        expected=422,
    )
    automatic = request(
        endpoint,
        "POST",
        base,
        {
            "title": "自动筛题",
            "filters": {"subject": subject},
            "limit": 1,
            "default_score": 15,
        },
        token=token,
    )
    selected = request(endpoint, "GET", base + "/" + automatic["id"], token=token)
    assert (
        len(selected["items"]) == 1
        and selected["items"][0]["question_id"] == second
        and selected["items"][0]["score"] == 15
    )
    paper = request(
        endpoint,
        "POST",
        base,
        {
            "title": "我的专项卷",
            "question_ids": [first, second],
            "items": [{"question_id": first, "score": 20}],
        },
        token=token,
    )
    path = base + "/" + paper["id"]
    request(endpoint, "GET", path, token=other, expected=404)
    request(endpoint, "PATCH", path, {"title": "篡改"}, token=other, expected=404)
    assert not request(endpoint, "DELETE", path, token=other)["deleted"]
    request(
        endpoint, "POST", base, {"question_ids": [first]}, token=other, expected=404
    )
    changed = request(
        endpoint,
        "PATCH",
        path,
        {
            "title": "重新排序",
            "items": [
                {"question_id": second, "score": 30},
                {"question_id": first, "score": 25},
            ],
        },
        token=token,
    )
    assert [i["question_id"] for i in changed["items"]] == [second, first]
    assert [i["score"] for i in changed["items"]] == [30, 25]
    request(
        endpoint,
        "PATCH",
        path,
        {"title": "不能保存", "items": [{"question_id": "missing"}]},
        token=token,
        expected=404,
    )
    assert request(endpoint, "GET", path, token=token)["title"] == "重新排序"
    request(
        endpoint, "POST", path + "/export", {"kind": "bad"}, token=token, expected=422
    )

    def download(route, account=None, expected=200):
        headers = {"Authorization": "Bearer " + account} if account else {}
        try:
            response = urlopen(Request(endpoint + route, headers=headers), timeout=20)
        except HTTPError as error:
            response = error
        with response:
            data = response.read()
            assert response.status == expected, (response.status, data[:200])
            return data, response.headers

    download(path + "/download", token, expected=404)
    for kind in ["question", "answer", "excel"]:
        exported = request(
            endpoint, "POST", path + "/export", {"kind": kind}, token=token
        )
        data, headers = download(path + "/download?kind=" + kind, token)
        signed, _ = download(exported["url"])
        assert signed == data and "attachment" in headers["Content-Disposition"]
        if kind == "excel":
            workbook = load_workbook(io.BytesIO(data))
            assert (
                workbook.active["A2"].value == "=SUM(2,3)"
                and workbook.active["A2"].data_type == "s"
            )
        else:
            assert data.startswith(b"%PDF-") and len(data) > 1000
    assert len(request(endpoint, "GET", path, token=token)["exports"]) == 3
    download(path + "/download", other, expected=404)
    assert any(
        p["id"] == paper["id"] for p in request(endpoint, "GET", base, token=token)
    )
    assert request(endpoint, "DELETE", path, token=token)["deleted"]
    assert not request(endpoint, "DELETE", path, token=token)["deleted"]
    request(endpoint, "GET", path, token=token, expected=404)
    assert (
        query(
            env, f"SELECT COUNT(*) FROM paper_items WHERE paper_id='{paper['id']}'"
        ).strip()
        == "0"
    )
    assert (
        query(
            env, f"SELECT COUNT(*) FROM export_jobs WHERE paper_id='{paper['id']}'"
        ).strip()
        == "0"
    )
    print(
        "Cangjie papers passed: filters, deduplication, scores, edit rollback, ownership, PDF/answer/Excel exports and downloads"
    )
