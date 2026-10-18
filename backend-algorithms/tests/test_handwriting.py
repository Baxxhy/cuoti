import asyncio
import json

import httpx
from app.providers.api_pool import ApiPoolProvider
from fastapi.testclient import TestClient
from service import create_app
from test_service import HEADERS, SECRET, image_input


def test_handwriting_transcription_and_validation(tmp_path):
    pool = tmp_path / "pool.json"
    pool.write_text(
        json.dumps(
            [
                {
                    "base_url": "http://handwriting.test/v1",
                    "api_key": "fixture",
                    "model": "Qwen",
                }
            ]
        )
    )
    provider = ApiPoolProvider(pool)
    asyncio.run(provider._client.aclose())
    recognized = {
        "final_answer": "x=5",
        "steps": ["3x=15", "x=5"],
        "transcription": "3x=15，x=5",
        "confidence": 0.9,
        "uncertain": False,
    }

    def upstream(request):
        body = json.loads(request.content)
        assert body["model"] == "Qwen"
        assert "不解题" in body["messages"][0]["content"]
        return httpx.Response(
            200, json={"choices": [{"message": {"content": json.dumps(recognized)}}]}
        )

    provider._client = httpx.AsyncClient(transport=httpx.MockTransport(upstream))
    app = create_app(secret=SECRET, pool_path=pool)
    app.state.provider = provider
    with TestClient(app) as client:
        response = client.post(
            "/v1/compute",
            headers=HEADERS,
            json={
                "operation": "recognize_handwriting",
                "image_base64": image_input(),
                "text": "解方程3x+4=19",
            },
        )
        assert response.status_code == 200, response.text
        assert response.json()["result"]["recognition"] == recognized
        for recognition, expected_status in [
            (recognized, 200),
            ({"confidence": 2}, 422),
            ({"answer": "invented"}, 422),
        ]:
            response = client.post(
                "/v1/compute",
                headers=HEADERS,
                json={"operation": "validate_handwriting", "recognition": recognition},
            )
            assert response.status_code == expected_status
        assert (
            client.post(
                "/v1/compute",
                headers=HEADERS,
                json={"operation": "recognize_handwriting"},
            ).status_code
            == 422
        )
