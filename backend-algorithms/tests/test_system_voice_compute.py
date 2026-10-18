import asyncio
import base64
import json
from pathlib import Path
from types import SimpleNamespace

import httpx
from app.providers.api_pool import ApiPoolProvider
from fastapi.testclient import TestClient
from service import create_app

SECRET = "system-voice-test-" + "x" * 32
HEADERS = {"Authorization": "Bearer " + SECRET}


def test_system_state_and_explicit_pool_probe(tmp_path):
    missing = create_app(secret=SECRET, pool_path=tmp_path / "missing.json")
    with TestClient(missing) as client:
        response = client.post(
            "/v1/compute", headers=HEADERS, json={"operation": "system_state"}
        )
        assert response.status_code == 200
        assert response.json()["result"]["provider"]["last_status"] == "unavailable"
        assert response.json()["result"]["voice"]["loaded"] is False
        assert (
            client.post(
                "/v1/compute",
                headers=HEADERS,
                json={"operation": "system_state", "probe_provider": True},
            ).status_code
            == 503
        )
    pool = tmp_path / "pool.json"
    pool.write_text(
        json.dumps(
            [
                {
                    "base_url": "http://pool.test/v1",
                    "api_key": "fixture-credential-private",
                    "model": "Qwen",
                }
            ]
        )
    )
    provider = ApiPoolProvider(pool)
    asyncio.run(provider._client.aclose())
    calls = []

    def upstream(request):
        calls.append(json.loads(request.content))
        assert calls[-1]["model"] == "Qwen"
        return httpx.Response(200, json={"choices": [{"message": {"content": "5"}}]})

    provider._client = httpx.AsyncClient(transport=httpx.MockTransport(upstream))
    app = create_app(secret=SECRET, pool_path=pool)
    app.state.provider = provider
    with TestClient(app) as client:
        passive = client.post(
            "/v1/compute", headers=HEADERS, json={"operation": "system_state"}
        )
        assert passive.status_code == 200 and not calls
        active = client.post(
            "/v1/compute",
            headers=HEADERS,
            json={"operation": "system_state", "probe_provider": True},
        )
        assert active.status_code == 200 and len(calls) == 2
        assert active.json()["result"]["provider"]["last_status"] == "ok"
        assert "fixture-credential-private" not in active.text
        client.post(
            "/v1/compute",
            headers=HEADERS,
            json={"operation": "system_state", "probe_provider": True},
        )
        assert len(calls) == 2


def test_original_voice_provider_through_compute(tmp_path, monkeypatch):
    app = create_app(secret=SECRET, pool_path=tmp_path / "missing.json")
    paths = []

    class Model:
        def transcribe(self, path, **kwargs):
            paths.append(Path(path))
            assert (
                paths[-1].read_bytes() == b"audio-fixture"
                and kwargs["language"] == "zh"
            )
            return [SimpleNamespace(text=" 根据条件求解 ", end=1.5)], SimpleNamespace(
                language="zh", language_probability=0.99
            )

    class Speech:
        def __init__(self, text, voice):
            assert text == "根据条件求解" and voice == "zh-CN-XiaoxiaoNeural"

        async def save(self, path):
            paths.append(Path(path))
            paths[-1].write_bytes(b"ID3-speech-fixture")

    app.state.voice_provider._model = Model()
    monkeypatch.setattr("app.services.voice.edge_tts.Communicate", Speech)
    with TestClient(app) as client:
        stt = client.post(
            "/v1/compute",
            headers=HEADERS,
            json={
                "operation": "voice_transcribe",
                "audio_base64": base64.b64encode(b"audio-fixture").decode(),
                "audio_suffix": ".wav",
            },
        )
        assert stt.status_code == 200, stt.text
        assert stt.json()["result"]["text"] == "根据条件求解"
        assert stt.json()["result"]["metadata"]["model"] == "faster-whisper-small"
        tts = client.post(
            "/v1/compute",
            headers=HEADERS,
            json={"operation": "voice_synthesize", "text": "根据条件求解"},
        )
        assert tts.status_code == 200, tts.text
        assert (
            base64.b64decode(tts.json()["result"]["audio_base64"])
            == b"ID3-speech-fixture"
        )
        assert not any(path.exists() for path in paths)
        invalid = client.post(
            "/v1/compute",
            headers=HEADERS,
            json={"operation": "voice_transcribe", "audio_base64": "invalid"},
        )
        assert invalid.status_code == 502 and "audio-fixture" not in invalid.text
