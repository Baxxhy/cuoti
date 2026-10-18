"""Legacy unit tests use a disposable pool and never the operator's credentials."""
import asyncio
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory

import httpx
import pytest

_pool_directory = TemporaryDirectory(prefix="zhiwei-unit-pool-")
_pool_path = Path(_pool_directory.name) / "pool.json"
_pool_path.write_text(json.dumps({"entries": [{
    "base_url": "https://api.chat.csu.edu.cn/v1",
    "api_key": "unit-test-no-network",
    "model": "Qwen",
}]}))
# This must precede app.main imports during test collection. The environment
# belongs to this pytest process, never the running business/algorithm services.
os.environ["API_POOL_PATH"] = str(_pool_path)
os.environ["AI_PROBE_ON_STARTUP"] = "false"


@pytest.fixture(scope="session", autouse=True)
def isolated_default_ai_client():
    from app.main import provider

    def unexpected_request(_request):
        pytest.fail("Unit tests must provide an explicit AI response; real model access is disabled")

    original = provider._client
    provider._client = httpx.AsyncClient(transport=httpx.MockTransport(unexpected_request))
    yield
    asyncio.run(provider._client.aclose())
    asyncio.run(original.aclose())
    _pool_directory.cleanup()
