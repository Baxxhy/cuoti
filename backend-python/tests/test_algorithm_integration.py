from cuoti_backend.config import Settings
from cuoti_backend.main import create_app
from fastapi.testclient import TestClient


def test_existing_compute_handler_and_secret():
    app = create_app(Settings(algorithm_secret="test-algorithm-secret-" * 3))
    with TestClient(app) as client:
        assert (
            client.post(
                "/v1/compute",
                json={"operation": "math_compare", "left": "x+x", "right": "2*x"},
            ).status_code
            == 401
        )
        response = client.post(
            "/v1/compute",
            headers={"Authorization": "Bearer " + "test-algorithm-secret-" * 3},
            json={"operation": "math_compare", "left": "x+x", "right": "2*x"},
        )
        assert response.status_code == 200
        assert response.json()["result"] == {"equivalent": True, "verified": True}
        assert app.state.algorithm_app.state.provider is None


def test_provider_lifecycle_is_closed():
    class Provider:
        closed = False

        async def close(self):
            self.closed = True

    app = create_app(Settings(algorithm_secret="test-algorithm-secret-" * 3))
    provider = Provider()
    with TestClient(app):
        app.state.algorithm_app.state.provider = provider
    assert provider.closed


def test_compute_preserves_original_body_limit():
    secret = "test-algorithm-secret-" * 3
    app = create_app(Settings(max_request_bytes=4, algorithm_secret=secret))
    with TestClient(app) as client:
        response = client.post(
            "/v1/compute",
            headers={"Authorization": "Bearer " + secret},
            json={"operation": "math_compare", "left": "2*x", "right": "x+x"},
        )
        assert response.status_code == 200
        assert client.post("/livez", content=b"12345").status_code == 413
