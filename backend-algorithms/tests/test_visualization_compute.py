from app.services.visualizations import (
    recommended_visualization,
    visualization_catalog,
    visualization_spec,
)
from fastapi.testclient import TestClient
from service import create_app


def test_visualization_configuration_matches_original(tmp_path):
    secret = "visual-config-" + "x" * 32
    app = create_app(secret=secret, pool_path=tmp_path / "missing.json")
    with TestClient(app) as client:
        catalog = visualization_catalog()
        for item in catalog:
            response = client.post(
                "/v1/compute",
                headers={"Authorization": "Bearer " + secret},
                json={
                    "operation": "visualization_config",
                    "subject": "数学",
                    "question_type": "综合题",
                    "teach_back_points": [item["title"]],
                    "visualization_values": {"changed": 2},
                },
            )
            assert response.status_code == 200, response.text
            data = response.json()["result"]
            kind = recommended_visualization("数学", "综合题", [item["title"]])
            assert data["catalog"] == catalog and data["kind"] == kind
            if kind is not None:
                expected = visualization_spec(kind)
                expected["parameters"]["changed"] = 2
                assert data["spec"] == expected
            else:
                assert data["spec"] is None
        assert app.state.provider is None
        response = client.post(
            "/v1/compute",
            headers={"Authorization": "Bearer " + secret},
            json={"operation": "visualization_config", "visualization_values": []},
        )
        assert response.status_code == 422
