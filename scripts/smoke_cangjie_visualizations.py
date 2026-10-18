"""Interactive visualization configuration, persistence and observation records."""

import sys
from pathlib import Path

from smoke_cangjie_accounts import request
from smoke_cangjie_detail import fixture_insert


def visualizations(endpoint, env, query, token, other):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
    from app.services.visualizations import visualization_catalog, visualization_spec

    insert = fixture_insert(env, query)
    owner = request(endpoint, "GET", "/api/v1/auth/me", token=token)["id"]
    root = "/api/v1/visualizations"
    assert request(endpoint, "GET", root + "/types") == visualization_catalog()
    request(endpoint, "POST", root + "/types", {}, expected=405)

    def session(points):
        question = request(
            endpoint,
            "POST",
            "/api/v1/questions/manual",
            {"question_text": "互动演示功能验证", "question_type": "综合题"},
            token=token,
        )
        insert(
            "problem_analyses",
            question_id=question["id"],
            subject="数学",
            final_answer="x=4",
            knowledge_points=points,
        )
        sid = insert(
            "tutor_sessions",
            question_id=question["id"],
            user_id=owner,
            stage="understanding",
            state={},
        )
        return sid, question

    sid, question = session(["一元一次方程"])
    path = "/api/v1/tutor/sessions/" + sid + "/visualization"
    request(endpoint, "GET", path, expected=401)
    request(endpoint, "GET", path, token=other, expected=404)
    response = request(endpoint, "GET", path, token=token)
    assert response == {
        "question": {
            "id": question["id"],
            "title": "互动演示功能验证",
            "question_text": "互动演示功能验证",
        },
        "spec": visualization_spec("equation_balance"),
    }
    request(endpoint, "POST", path, {"values": []}, token=token, expected=422)
    request(endpoint, "POST", path, {"observation": []}, token=token, expected=422)
    before = query(
        env, f"SELECT COUNT(*) FROM visualization_specs WHERE session_id='{sid}'"
    ).strip()
    assert before == "0"
    values = {"left": 6, "right": 6}
    observation = "等式两边做相同的操作后仍然相等。"
    saved = request(
        endpoint,
        "POST",
        path,
        {"values": values, "observation": observation},
        token=token,
    )
    expected = visualization_spec("equation_balance")
    expected["parameters"].update(values)
    assert saved["spec"] == expected
    read = request(endpoint, "GET", root + "/" + saved["id"], token=token)
    assert read["spec"] == expected and len(read["interactions"]) == 1
    assert (
        read["interactions"][0]["values"] == values
        and read["interactions"][0]["observation"] == observation
    )
    request(endpoint, "GET", root + "/" + saved["id"], token=other, expected=404)
    request(endpoint, "GET", root + "/missing", token=token, expected=404)
    assert (
        query(
            env,
            f"SELECT COUNT(*) FROM agent_tool_calls t JOIN agent_runs r ON r.id=t.agent_run_id WHERE r.session_id='{sid}' AND t.tool_name='observe_visualization'",
        ).strip()
        == "1"
    )
    # An observation-free save persists the spec, without manufacturing evidence.
    quiet = request(endpoint, "POST", path, {}, token=token)
    assert (
        request(endpoint, "GET", root + "/" + quiet["id"], token=token)["interactions"]
        == []
    )
    assert request(endpoint, "GET", path, token=token)["spec"] == visualization_spec(
        "equation_balance"
    )
    unsupported, _ = session(["英语语法"])
    request(
        endpoint,
        "GET",
        "/api/v1/tutor/sessions/" + unsupported + "/visualization",
        token=token,
        expected=404,
    )
    query(
        env,
        "ALTER TABLE agent_tool_calls ADD CONSTRAINT cj_visual_rollback CHECK (tool_name <> 'observe_visualization' OR JSON_UNQUOTE(JSON_EXTRACT(output_json,'$.observation')) <> 'visual-rollback-probe')",
    )
    try:
        request(
            endpoint,
            "POST",
            path,
            {"values": values, "observation": "visual-rollback-probe"},
            token=token,
            expected=503,
        )
        assert (
            query(
                env,
                f"SELECT COUNT(*) FROM visualization_specs WHERE session_id='{sid}'",
            ).strip()
            == "2"
        )
        assert (
            query(
                env,
                f"SELECT COUNT(*) FROM visualization_interactions i JOIN visualization_specs v ON v.id=i.visualization_id WHERE v.session_id='{sid}'",
            ).strip()
            == "1"
        )
    finally:
        query(env, "ALTER TABLE agent_tool_calls DROP CHECK cj_visual_rollback")
    query(env, f"UPDATE questions SET status='archived' WHERE id='{question['id']}'")
    request(endpoint, "POST", path, {}, token=token, expected=409)
    print(
        "Cangjie visualizations passed: original configuration, parameter save, observation, reads, ownership and atomic rollback"
    )
