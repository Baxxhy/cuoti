import json
from pathlib import Path

from app.services.cognition_rules import compute_cognition


def test_cognition_preserves_original_results():
    vectors = json.loads(
        (Path(__file__).parent / "fixtures/cognition_vectors.json").read_text()
    )
    assert len(vectors) == 54
    for vector in vectors:
        actual = compute_cognition(
            vector["mastery"],
            vector["misconception"],
            vector["evidence"],
            vector["label"],
        )
        assert list(actual) == vector["expected"], vector


def test_cognition_internal_http_is_pure(tmp_path):
    from fastapi.testclient import TestClient
    from service import create_app

    secret = "cognition-internal-test-" + "x" * 32
    vector = json.loads(
        (Path(__file__).parent / "fixtures/cognition_vectors.json").read_text()
    )[0]
    app = create_app(secret=secret, pool_path=tmp_path / "missing.json")
    with TestClient(app) as client:
        response = client.post(
            "/v1/compute",
            headers={"Authorization": "Bearer " + secret},
            json={
                "operation": "cognition_update",
                "mastery_values": vector["mastery"],
                "misconception_values": vector["misconception"],
                "learning_evidence": vector["evidence"],
                "misconception_label": vector["label"],
            },
        )
        assert response.status_code == 200, response.text
        result = response.json()["result"]
        assert [result["mastery"], result["misconception"]] == vector["expected"]
        assert app.state.provider is None
