from urllib.parse import urlsplit

import httpx
import pytest
from fastapi import FastAPI

from app.local_secret import load_local_secret
from app.media import SignedStaticFiles, sign_media_url, valid_media_url


def test_signed_media_links_expire_and_cannot_be_used_for_another_file():
    url = urlsplit(sign_media_url("/uploads/question/original.png", "secret", now=100))
    assert valid_media_url(url.path, url.query, "secret", now=101)
    assert not valid_media_url("/uploads/other/original.png", url.query, "secret", now=101)
    assert not valid_media_url(url.path, url.query, "other-secret", now=101)
    assert not valid_media_url(url.path, url.query, "secret", now=14500)
    assert not valid_media_url(url.path, "expires=invalid", "secret", now=101)


def test_user_controlled_visualization_and_metadata_cannot_mint_media_links():
    from app.main import envelope

    payload = {
        "spec": {"parameters": {"url": "/reports/another-paper-question.pdf"}},
        "images": ["/uploads/other/original.jpg"],
        "image_url": "/uploads/other/work.jpg",
    }
    assert envelope(payload)["data"] == payload
    assert "signature=" not in str(envelope(payload))


@pytest.mark.asyncio
async def test_static_media_enforces_signature_with_real_asgi_mount(tmp_path):
    (tmp_path / "image.png").write_bytes(b"example")
    app = FastAPI()
    app.mount("/uploads", SignedStaticFiles(directory=tmp_path, secret="secret"))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.get("/uploads/image.png")).status_code == 403
        response = await client.get(sign_media_url("/uploads/image.png", "secret"))
        assert response.status_code == 200
        assert response.content == b"example"


def test_local_secret_survives_restart_and_is_not_world_readable(tmp_path):
    path = tmp_path / "auth-secret"
    secret = load_local_secret(path)
    assert len(secret) >= 32
    assert load_local_secret(path) == secret
    assert path.stat().st_mode & 0o077 == 0


def test_question_bank_image_links_can_load_without_bearer_in_image_tag():
    from app.main import _practice_recommendation_payload
    from app.models import DatasetQuestion

    question = DatasetQuestion(id="q1", image_paths=["data/question_bank_assets/figure.jpg"], options=[])
    data = _practice_recommendation_payload(question, "reinforce", {}, [])
    parts = urlsplit(data["images"][0])
    from app.config import settings

    assert valid_media_url(parts.path, parts.query, settings.auth_secret)
    assert not valid_media_url("/api/v1/practice/questions/q2/images/0", parts.query, settings.auth_secret)
