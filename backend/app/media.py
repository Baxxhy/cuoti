"""Short-lived links protect uploaded student work and generated reports."""

from __future__ import annotations

import hashlib
import hmac
import re
import time
from typing import Any
from urllib.parse import parse_qs, quote, unquote, urlsplit

from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException
from starlette.types import Scope

MEDIA_PREFIXES = ("/uploads/", "/reports/")
MEDIA_LIFETIME = 4 * 60 * 60


def is_media_path(path: str) -> bool:
    return path.startswith(MEDIA_PREFIXES) or bool(
        re.fullmatch(r"/api/v1/practice/questions/[^/]+/images/\d+", path)
    )


def signature(path: str, expires: int, secret: str) -> str:
    return hmac.new(secret.encode(), f"media:v1:{expires}:{path}".encode(), hashlib.sha256).hexdigest()


def sign_media_url(value: str, secret: str, *, now: int | None = None) -> str:
    parts = urlsplit(value)
    if parts.scheme or parts.netloc or not is_media_path(parts.path):
        return value
    path = unquote(parts.path)
    expires = (int(time.time()) if now is None else now) + MEDIA_LIFETIME
    return f"{quote(path, safe='/')}?expires={expires}&signature={signature(path, expires, secret)}"


def valid_media_url(path: str, query: str, secret: str, *, now: int | None = None) -> bool:
    params = parse_qs(query)
    try:
        expires = int(params.get("expires", [""])[0])
        supplied = params.get("signature", [""])[0]
    except (ValueError, IndexError):
        return False
    clock = int(time.time()) if now is None else now
    if expires <= clock or expires > clock + MEDIA_LIFETIME:
        return False
    return hmac.compare_digest(signature(path, expires, secret), supplied)


class SignedStaticFiles(StaticFiles):
    def __init__(self, *, secret: str, **kwargs: Any):
        super().__init__(**kwargs)
        self.secret = secret

    async def get_response(self, path: str, scope: Scope):
        request_path = scope["path"]
        query = scope.get("query_string", b"").decode("ascii", errors="replace")
        if not valid_media_url(request_path, query, self.secret):
            raise HTTPException(403, "资源链接已失效，请返回页面刷新")
        return await super().get_response(path, scope)
