"""Analysis persistence, semantic mappings and concurrent edit protection."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

from smoke_cangjie_accounts import request
from smoke_cangjie_detail import fixture_insert


def analysis(
    endpoint, env, query, token, other_token, state, started, release, image_bytes
):
    insert = fixture_insert(env, query)

    def create(subject="数学"):
        return request(
            endpoint,
            "POST",
            "/api/v1/questions/manual",
            {
                "question_text": "解方程：2*x+3=11",
                "subject": subject,
                "student_answer": "3",
                "student_steps": ["x=3"],
            },
            token=token,
        )

    def route(q):
        return f"/api/v1/questions/{q['id']}"

    q = create()
    path = route(q)
    request(endpoint, "POST", path + "/analyze", expected=401)
    request(endpoint, "POST", path + "/analyze", token=other_token, expected=404)
    query(env, f"UPDATE questions SET confirmed=0 WHERE id='{q['id']}'")
    request(endpoint, "POST", path + "/analyze", token=token, expected=409)
    request(endpoint, "POST", path + "/confirm", {}, token=token)
    request(endpoint, "PATCH", path, {"knowledge_points": ["一次方程"]}, token=token)
    exact = insert(
        "knowledge_points",
        code=f"exact-{uuid4()}",
        subject="数学",
        name="方程求解",
        content={"related_knowledge": ["求解等式"]},
    )
    contained = insert(
        "knowledge_points",
        code=f"contained-{uuid4()}",
        subject="数学",
        name="一元一次方程",
        content={},
    )
    prereq = insert(
        "knowledge_points",
        code=f"pre-{uuid4()}",
        subject="数学",
        name="等式性质",
        content={"related_knowledge": ["等式的性质"]},
    )
    insert(
        "knowledge_points",
        code=f"other-{uuid4()}",
        subject="物理",
        name="方程求解",
        content={},
    )
    root = Path(env["CANGJIE_MEDIA_ROOT"])
    image_path = f"uploads/{q['id']}/analysis.jpg"
    (root / image_path).parent.mkdir(parents=True)
    (root / image_path).write_bytes(image_bytes)
    for kind in ("crop", "question_figure"):
        insert(
            "question_assets",
            question_id=q["id"],
            kind=kind,
            path=image_path,
            sha256="fixture",
        )
    old = insert("problem_analyses", question_id=q["id"], subject="数学")
    state["analysis"] = True
    state["analysis_result"] = {
        "subject": "数学",
        "problem_type": "综合题",
        "known_conditions": ["2x+3=11"],
        "goal": "求 x",
        "knowledge_points": ["求解等式", "不存在的标签"],
        "prerequisites": ["等式的性质", "方程求解"],
        "reference_steps": ["2*x=8", "x=4"],
        "final_answer": "x=999",
    }
    state["mode"] = "good"
    try:
        result = request(endpoint, "POST", path + "/analyze", token=token)
        assert result["final_answer"] == "x=4" and result["verified"] is True
        assert result["reference_steps"] == ["2*x=8", "x=4"]
        assert state["analysis_images"] == 1
        assert (
            query(env, f"SELECT COUNT(*) FROM problem_analyses WHERE id='{old}'") == "0"
        )
        detail = request(endpoint, "GET", path, token=token)
        assert detail["status"] == "analyzed"
        assert [s["math_valid"] for s in detail["reference_steps"]] == [True, True]
        assert [s["uses_condition"] for s in detail["reference_steps"]] == [True, False]
        links = query(
            env,
            f"SELECT knowledge_point_id,role,mapping_method FROM user_question_knowledge_links WHERE question_id='{q['id']}'",
        )
        assert f"{exact}\tprimary\texact_label" in links
        assert f"{contained}\tprimary\tcontained_label" in links
        assert f"{prereq}\tprerequisite\texact_label" in links
        assert len(links.splitlines()) == 3
        state["analysis_result"]["reference_steps"] = ["forced-analysis-failure"]
        query(
            env,
            "ALTER TABLE reference_steps ADD CONSTRAINT analysis_failure CHECK (text <> 'forced-analysis-failure')",
        )
        try:
            request(endpoint, "POST", path + "/analyze", token=token, expected=503)
            assert (
                request(endpoint, "GET", path, token=token)["analysis"]["id"]
                == result["id"]
            )
            assert (
                query(
                    env,
                    f"SELECT COUNT(*) FROM user_question_knowledge_links WHERE question_id='{q['id']}'",
                )
                == "3"
            )
        finally:
            query(env, "ALTER TABLE reference_steps DROP CHECK analysis_failure")
            state["analysis_result"]["reference_steps"] = ["2*x=8", "x=4"]
        for action in ("edit", "steps", "submission", "archive"):
            item = create()
            item_path = route(item)
            started.clear()
            release.clear()
            state["mode"] = "block"
            expected = 404 if action == "archive" else 409
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(
                    request,
                    endpoint,
                    "POST",
                    item_path + "/analyze",
                    token=token,
                    expected=expected,
                )
                try:
                    assert started.wait(10)
                    if action == "edit":
                        request(
                            endpoint,
                            "PATCH",
                            item_path,
                            {"question_text": "新的题干"},
                            token=token,
                        )
                    elif action == "submission":
                        request(
                            endpoint,
                            "POST",
                            item_path + "/student-work",
                            {"steps": ["新作答"]},
                            token=token,
                        )
                    elif action == "steps":
                        request(
                            endpoint,
                            "POST",
                            item_path + "/draft",
                            {"student_steps": ["修订步骤"]},
                            token=token,
                        )
                        request(
                            endpoint, "POST", item_path + "/confirm", {}, token=token
                        )
                    else:
                        request(endpoint, "DELETE", item_path, token=token)
                finally:
                    release.set()
                assert future.result() == expected
            assert (
                query(
                    env,
                    f"SELECT COUNT(*) FROM problem_analyses WHERE question_id='{item['id']}'",
                )
                == "0"
            )
        state["mode"] = "fail"
        physics = create("物理")
        request(
            endpoint, "POST", route(physics) + "/analyze", token=token, expected=503
        )
        assert (
            query(
                env,
                f"SELECT COUNT(*) FROM problem_analyses WHERE question_id='{physics['id']}'",
            )
            == "0"
        )
    finally:
        release.set()
        state["analysis"] = False
        state["mode"] = "good"
    print(
        "Cangjie analysis passed: permissions, confirmation, multimodal input, math, knowledge links, rollback and stale-result protection"
    )
