from app.services.pedagogy import SUBJECT_PEDAGOGY, evaluate_teach_back
from fastapi.testclient import TestClient
from service import create_app


def test_teach_back_uses_original_python_without_provider(tmp_path):
    secret = "teach-back-compute-" + "x" * 32
    app = create_app(secret=secret, pool_path=tmp_path / "missing.json")
    with TestClient(app) as client:
        for subject in [*SUBJECT_PEDAGOGY, "未知学科"]:
            for explanation, points in [
                ("", []),
                ("不会", []),
                (
                    "根据一次方程的等式性质，先移项再求解，所以需要检查结果。",
                    ["一次方程"],
                ),
                (
                    "根据这个原理，先观察条件再解释结果，所以答案可以验证。",
                    ["　", {"name": "原理"}, "观察"],
                ),
                ("First, observe the条件；然后再根据证据说明结论。", ["证据"]),
            ]:
                references = ["根据条件列式", "", "求出结果"]
                response = client.post(
                    "/v1/compute",
                    headers={"Authorization": "Bearer " + secret},
                    json={
                        "operation": "evaluate_teach_back",
                        "text": explanation,
                        "subject": subject,
                        "question_type": "综合题",
                        "teach_back_points": points,
                        "reference_solution": references,
                    },
                )
                assert response.status_code == 200, response.text
                assert response.json()["result"] == evaluate_teach_back(
                    explanation, subject, "综合题", points, references
                )
        assert app.state.provider is None
        assert (
            client.post(
                "/v1/compute", json={"operation": "evaluate_teach_back"}
            ).status_code
            == 401
        )
        response = client.post(
            "/v1/compute",
            headers={"Authorization": "Bearer " + secret},
            json={"operation": "evaluate_teach_back", "teach_back_points": ["x"] * 101},
        )
        assert response.status_code == 422
