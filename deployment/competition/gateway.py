"""Same-origin H5 gateway; all business requests go to the Python backend."""

import os
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, Request
from starlette.responses import FileResponse, Response

ROOT = Path(os.environ.get("CUOTI_WEB_ROOT", "/opt/app/web")).resolve()
BACKEND = os.environ.get("CUOTI_BACKEND_INTERNAL_URL", "http://127.0.0.1:8002").rstrip(
    "/"
)


@asynccontextmanager
async def lifespan(app):
    async with httpx.AsyncClient(timeout=300, trust_env=False) as client:
        app.state.client = client
        yield


app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)


@app.api_route(
    "/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"]
)
async def route(path: str, request: Request):
    if path.startswith(("api/", "uploads/", "reports/")) or path in ("livez", "readyz"):
        hop = {
            "host",
            "connection",
            "transfer-encoding",
            "content-length",
            "accept-encoding",
        }
        headers = {
            key: value
            for key, value in request.headers.items()
            if key.lower() not in hop
        }
        try:
            result = await request.app.state.client.request(
                request.method,
                BACKEND + "/" + path,
                params=list(request.query_params.multi_items()),
                headers=headers,
                content=await request.body(),
            )
        except httpx.HTTPError:
            return Response("服务暂未就绪", status_code=503)
        return Response(
            result.content,
            result.status_code,
            {
                key: value
                for key, value in result.headers.items()
                if key.lower() not in hop and key.lower() != "content-encoding"
            },
        )
    target = (ROOT / path).resolve()
    if not target.is_relative_to(ROOT):
        return Response(status_code=403)
    if target.is_file():
        return FileResponse(target)
    return FileResponse(ROOT / "index.html")
