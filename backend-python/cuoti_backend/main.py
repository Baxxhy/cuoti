import logging
from contextlib import asynccontextmanager
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException

from .config import Settings
from .database import Database
from .protocol import ApiError

logger = logging.getLogger("cuoti.backend")


class RequestMiddleware:
    def __init__(self, app, max_bytes):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        request_id = str(uuid4())
        scope.setdefault("state", {})["request_id"] = request_id
        started = perf_counter()
        # Bound request memory before dispatch, including chunked uploads.
        chunks = []
        length = 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            body = message.get("body", b"")
            length += len(body)
            if length > self.max_bytes:
                response = JSONResponse(
                    {"detail": "请求内容过大"},
                    status_code=413,
                    headers={"X-Request-ID": request_id},
                )
                return await response(scope, receive, send)
            chunks.append(body)
            if not message.get("more_body", False):
                break
        consumed = False

        async def replay():
            nonlocal consumed
            if consumed:
                return await receive()
            consumed = True
            return {
                "type": "http.request",
                "body": b"".join(chunks),
                "more_body": False,
            }

        async def send_response(message):
            if message["type"] == "http.response.start":
                headers = message.setdefault("headers", [])
                if not any(key.lower() == b"x-request-id" for key, _ in headers):
                    headers.append((b"x-request-id", request_id.encode()))
                if scope["path"].startswith("/api/"):
                    headers.append((b"cache-control", b"no-store"))
                logger.info(
                    "request_id=%s method=%s status=%s elapsed_ms=%.1f",
                    request_id,
                    scope["method"],
                    message["status"],
                    (perf_counter() - started) * 1000,
                )
            await send(message)

        await self.app(scope, replay, send_response)


def create_app(settings: Settings | None = None):
    settings = settings or Settings.load()
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    logger.setLevel(settings.log_level)
    database = Database(settings)

    @asynccontextmanager
    async def lifespan(app):
        try:
            yield
        finally:
            database.close()

    app = FastAPI(title="错题帮 Python 后端", lifespan=lifespan, redirect_slashes=False)
    app.state.settings = settings
    app.state.database = database
    app.add_middleware(RequestMiddleware, max_bytes=settings.max_request_bytes)

    def error_response(request, status, message, headers=None):
        return JSONResponse(
            {"detail": message},
            status_code=status,
            headers={"X-Request-ID": request.state.request_id, **(headers or {})},
        )

    @app.exception_handler(ApiError)
    async def business_error(request, error):
        return error_response(request, error.status, error.message)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, error):
        return error_response(request, 422, "请求参数格式不正确")

    @app.exception_handler(HTTPException)
    async def http_error(request, error):
        messages = {404: "资源不存在", 405: "请求方法不支持"}
        return error_response(
            request,
            error.status_code,
            messages.get(error.status_code, "请求未完成"),
            error.headers,
        )

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request, error):
        return error_response(request, 503, "数据库暂时不可用，请稍后重试")

    @app.exception_handler(Exception)
    async def unexpected_error(request, error):
        logger.error(
            "request_id=%s failure=%s", request.state.request_id, type(error).__name__
        )
        return error_response(request, 500, "请求未完成，请稍后重试")

    @app.get("/livez")
    def live():
        return {"service": "cuoti-python", "status": "alive", "version": "0.1.0"}

    @app.get("/readyz")
    def ready():
        try:
            app.state.database.probe()
        except (SQLAlchemyError, RuntimeError):
            return JSONResponse({"status": "database_unavailable"}, status_code=503)
        return {"database": "mysql", "status": "database_ready", "ai": "not_connected"}

    return app
