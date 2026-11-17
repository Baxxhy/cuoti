import io
import os
from pathlib import Path
from uuid import uuid4

import pytest
from cuoti_backend.question_data import rows
from openpyxl import load_workbook
from test_questions_mysql import (
    question_app as question_app,  # noqa: PLC0414 -- Export a shared pytest fixture.
)

pytestmark = [
    pytest.mark.mysql,
    pytest.mark.skipif(
        os.environ.get("CUOTI_TEST_MYSQL") != "1",
        reason="local MySQL check not enabled",
    ),
]


def test_papers_candidates_edit_export_download_and_isolation(question_app):
    _, client, student, _ = question_app
    _, headers = student()
    _, other = student()
    qid = client.post(
        "/api/v1/questions/manual",
        headers=headers,
        json={
            "question_text": "3x+2=17",
            "correct_answer": "5",
            "explanation": "3x=15\nx=5",
            "knowledge_points": ["一元一次方程"],
        },
    ).json()["data"]["id"]
    base = "/api/v1/papers"
    candidates = client.get(base + "/candidates?knowledge_point=方程", headers=headers)
    assert candidates.status_code == 200, candidates.text
    assert candidates.json()["data"][0]["id"] == qid
    assert client.get(base + "/candidates", headers=other).json()["data"] == []
    assert (
        client.get(base + "/candidates?mastery_min=2", headers=headers).status_code
        == 422
    )
    created = client.post(
        base,
        headers=headers,
        json={"title": "我的导出测试", "question_ids": [qid], "default_score": "12"},
    )
    assert created.status_code == 200, created.text
    pid = created.json()["data"]["id"]
    path = base + "/" + pid
    assert client.get(path, headers=other).status_code == 404
    assert client.get(base, headers=other).json()["data"] == []
    assert client.get(path + "/download", headers=headers).status_code == 404
    detail = client.get(path, headers=headers).json()["data"]
    assert (
        detail["items"][0]["score"] == 12
        and detail["items"][0]["analysis_ready"] is True
    )
    changed = client.patch(
        path,
        headers=headers,
        json={"title": "新试卷", "items": [{"question_id": qid, "score": 20}]},
    )
    assert (
        changed.status_code == 200 and changed.json()["data"]["items"][0]["score"] == 20
    )
    for kind in ["question", "answer", "excel"]:
        exported = client.post(path + "/export", headers=headers, json={"kind": kind})
        assert exported.status_code == 200, exported.text
        job = exported.json()["data"]
        assert client.get(job["url"], headers=other).status_code == 404
        signed = client.get(job["url"], headers=headers)
        downloaded = client.get(path + "/download?kind=" + kind, headers=headers)
        assert downloaded.status_code == 200 and downloaded.content == signed.content
        assert "attachment" in downloaded.headers["content-disposition"]
        assert (
            client.get(path + "/download?kind=" + kind, headers=other).status_code
            == 404
        )
        if kind == "excel":
            book = load_workbook(io.BytesIO(downloaded.content))
            assert any(
                "3x+2=17" in str(cell.value) for row in book.active for cell in row
            )
        else:
            assert downloaded.content.startswith(b"%PDF-")
    if os.environ.get("CUOTI_LEGACY_URL"):
        import httpx

        for endpoint in [base, base + "/candidates?knowledge_point=方程", path]:
            old = httpx.get(
                os.environ["CUOTI_LEGACY_URL"] + endpoint,
                headers=headers,
                trust_env=False,
                timeout=15,
            )
            assert old.status_code == 200, old.text
            before, after = (
                old.json()["data"],
                client.get(endpoint, headers=headers).json()["data"],
            )

            # Signed media links carry the read time; compare their original paths.
            def normalize(value):
                if isinstance(value, dict):
                    return {key: normalize(item) for key, item in value.items()}
                if isinstance(value, list):
                    return [normalize(item) for item in value]
                return (
                    value.split("?", 1)[0]
                    if isinstance(value, str) and value.startswith("/reports/")
                    else value
                )

            assert normalize(before) == normalize(after)
    assert client.delete(path, headers=other).json()["data"]["deleted"] is False
    assert client.delete(path, headers=headers).json()["data"]["deleted"] is True
    assert client.delete(path, headers=headers).json()["data"]["deleted"] is False


def test_export_missing_analysis_hash_and_transaction_cleanup(
    question_app, monkeypatch
):
    from cuoti_backend import paper_exports
    from cuoti_backend.protocol import ApiError

    app, client, student, _ = question_app
    user, headers = student()
    qid = client.post(
        "/api/v1/questions/manual", headers=headers, json={"question_text": "3x=15"}
    ).json()["data"]["id"]
    created = client.post(
        "/api/v1/papers", headers=headers, json={"filters": {}, "limit": 1}
    )
    assert created.status_code == 200
    pid = created.json()["data"]["id"]
    path = "/api/v1/papers/" + pid
    assert (
        client.post(
            path + "/export", headers=headers, json={"kind": "answer"}
        ).status_code
        == 409
    )
    assert (
        client.post(path + "/export", headers=headers, json={"kind": "bad"}).status_code
        == 422
    )
    assert (
        client.patch(
            path, headers=headers, json={"items": [{"question_id": str(uuid4())}]}
        ).status_code
        == 404
    )
    assert (
        client.get(path, headers=headers).json()["data"]["items"][0]["question_id"]
        == qid
    )
    original = app.state.questions.compute.compute

    def corrupt(operation, **values):
        result = original(operation, **values)
        if operation == "render_paper":
            result["sha256"] = "0" * 64
        return result

    with monkeypatch.context() as patch:
        patch.setattr(app.state.questions.compute, "compute", corrupt)
        assert (
            client.post(
                path + "/export", headers=headers, json={"kind": "excel"}
            ).status_code
            == 503
        )
    assert not list(Path(app.state.settings.media_root).rglob("*.xlsx"))

    def fail_insert(*a, **kw):
        raise ApiError(503, "模拟导出记录保存失败")

    with monkeypatch.context() as patch:
        patch.setattr(paper_exports, "insert", fail_insert)
        assert (
            client.post(
                path + "/export", headers=headers, json={"kind": "excel"}
            ).status_code
            == 503
        )
    assert not list(Path(app.state.settings.media_root).rglob("*.xlsx"))
    with app.state.database.session() as db:
        assert not rows(db, "SELECT id FROM export_jobs WHERE paper_id=?", [pid])
        assert rows(
            db, "SELECT id FROM papers WHERE id=? AND user_id=?", [pid, user["id"]]
        )
