import asyncio
import json

import httpx
import pytest

from learning_core.providers.api_pool import ApiPoolProvider


def test_luna_env_credential_and_payload(tmp_path, monkeypatch):
    monkeypatch.setenv("XIAOJING_API_KEY", "fixture-secret")
    config = tmp_path / "pool.json"
    config.write_text(json.dumps({"apis": [{"base_url": "https://xiaojing.test/v1", "api_key_env": "XIAOJING_API_KEY", "model": "gpt-6-luna"}]}))

    async def run():
        provider = ApiPoolProvider(config)
        await provider.close()
        def upstream(request):
            body = json.loads(request.content)
            assert body["model"] == "gpt-6-luna"
            assert "chat_template_kwargs" not in body
            assert "temperature" not in body
            assert request.headers["authorization"] == "Bearer fixture-secret"
            return httpx.Response(200, json={"choices": [{"message": {"content": '{"ok":true}'}}]})
        provider._client = httpx.AsyncClient(transport=httpx.MockTransport(upstream))
        try:
            result = await provider._request_entry(provider.entries[0], [{"role": "user", "content": "Return JSON"}], json_mode=True)
            assert json.loads(result) == {"ok": True}
            health = provider.health_check()
            assert health["logical_model"] == "gpt-6-luna"
            assert "fixture-secret" not in json.dumps(health)
        finally:
            await provider.close()
    asyncio.run(run())


def test_missing_env_credential_rejected(tmp_path, monkeypatch):
    monkeypatch.delenv("XIAOJING_API_KEY", raising=False)
    config = tmp_path / "pool.json"
    config.write_text(json.dumps([{"base_url": "https://xiaojing.test/v1", "api_key_env": "XIAOJING_API_KEY", "model": "gpt-6-luna"}]))
    with pytest.raises(ValueError, match="没有可用条目"):
        ApiPoolProvider(config)
