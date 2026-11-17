import asyncio
import logging
from contextlib import AsyncExitStack, asynccontextmanager
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException

from .accounts import router as account_router
from .config import Settings
from .database import Database
from .dataset_images import router as dataset_images_router
from .diagnostics import router as diagnostic_router
from .handwriting import router as handwriting_router
from .insights import router as insight_router
from .journey import router as journey_router
from .learning_tasks import router as task_router
from .lessons import router as lesson_router
from .media import MediaStore
from .media import router as media_router
from .practice import router as practice_router
from .protocol import ApiError
from .question_routes import router as question_router
from .questions import Questions
from .recognition import ComputeBridge, RecognitionJobs
from .review_filters import router as review_filter_router
from .reviews import router as review_router
from .study_bank import router as study_bank_router
from .study_sessions import router as study_session_router
from .task_images import router as task_images_router
from .task_records import router as task_records_router
from .task_worker import LearningTaskWorker
from .tutor_answers import router as answer_router
from .tutor_dialogue import router as dialogue_router
from .tutoring import router as tutoring_router
from .variant_attempts import router as variant_attempt_router

logger = logging.getLogger("cuoti.backend")


class RequestMiddleware:
    def __init__(self, app, max_bytes, compute_max_bytes):
        self.app = app
        self.max_bytes = max_bytes
        self.compute_max_bytes = compute_max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        request_id = str(uuid4())
        scope.setdefault("state", {})["request_id"] = request_id
        started = perf_counter()
        # Native routing resolves reserved literal paths before parameter paths.
        if (
            scope["path"] in ["/api/v1/questions/manual", "/api/v1/questions/ingest"]
            and scope["method"] != "POST"
        ):
            response = JSONResponse(
                {"detail": "请求方法不支持"},
                status_code=405,
                headers={
                    "Allow": "POST",
                    "X-Request-ID": request_id,
                    "Cache-Control": "no-store",
                },
            )
            return await response(scope, receive, send)
        # Bound request memory before dispatch, including chunked uploads.
        limit = (
            self.compute_max_bytes if scope["path"] == "/v1/compute" else self.max_bytes
        )
        chunks = []
        length = 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            body = message.get("body", b"")
            length += len(body)
            if length > limit:
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
    algorithm_app = None
    compute_max_bytes = settings.max_request_bytes
    if len(settings.algorithm_secret.get_secret_value()) >= 32:
        from service import MAX_REQUEST_BYTES
        from service import create_app as create_algorithm_app

        compute_max_bytes = MAX_REQUEST_BYTES

        algorithm_app = create_algorithm_app(
            secret=settings.algorithm_secret.get_secret_value(),
            pool_path=Path(settings.api_pool_path) if settings.api_pool_path else None,
        )

    @asynccontextmanager
    async def lifespan(app):
        try:
            async with AsyncExitStack() as stack:
                if algorithm_app is not None:
                    await stack.enter_async_context(
                        algorithm_app.router.lifespan_context(algorithm_app)
                    )
                compute = (
                    ComputeBridge(
                        algorithm_app,
                        settings.algorithm_secret.get_secret_value(),
                        settings.compute_timeout,
                    )
                    if algorithm_app is not None
                    else None
                )
                app.state.compute = compute
                app.state.questions.compute = compute
                app.state.recognition = RecognitionJobs(app.state.questions, compute)
                worker = LearningTaskWorker(app.state.questions)
                app.state.learning_task_worker = worker
                if settings.learning_task_worker_enabled:
                    worker.start()
                try:
                    await asyncio.to_thread(app.state.recognition.recover)
                    yield
                finally:
                    await asyncio.to_thread(worker.close)
                    await asyncio.to_thread(app.state.recognition.close)
                    if compute is not None:
                        await compute.close()
        finally:
            database.close()

    app = FastAPI(title="错题帮 Python 后端", lifespan=lifespan, redirect_slashes=False)
    app.state.settings = settings
    app.state.database = database
    app.state.algorithm_app = algorithm_app
    root = Path(settings.media_root) if settings.media_root else Path("media")
    if not root.is_absolute():
        root = Path(settings.project_root) / "backend-cangjie" / root
    bank = (
        Path(settings.question_bank_root)
        if settings.question_bank_root
        else Path("data/question_bank_assets")
    )
    if not bank.is_absolute():
        bank = Path(settings.project_root) / bank
    settings.question_bank_root = str(bank)
    app.state.media = MediaStore(root, settings.auth_secret.get_secret_value())
    app.state.questions = Questions(database, app.state.media, settings)
    app.include_router(account_router)
    app.include_router(question_router)
    app.include_router(diagnostic_router)
    app.include_router(insight_router)
    app.include_router(lesson_router)
    app.include_router(handwriting_router)
    app.include_router(study_bank_router)
    app.include_router(study_session_router)
    app.include_router(review_filter_router)
    app.include_router(review_router)
    app.include_router(practice_router)
    app.include_router(dataset_images_router)
    app.include_router(variant_attempt_router)
    app.include_router(journey_router)
    app.include_router(task_router)
    app.include_router(task_records_router)
    app.include_router(task_images_router)
    app.include_router(tutoring_router)
    app.include_router(answer_router)
    app.include_router(dialogue_router)
    app.include_router(media_router)
    if algorithm_app is not None:
        # Reuse the existing authenticated compute handler and its provider lifecycle.
        app.router.routes.extend(
            route for route in algorithm_app.routes if route.path == "/v1/compute"
        )
    app.add_middleware(
        RequestMiddleware,
        max_bytes=settings.max_request_bytes,
        compute_max_bytes=compute_max_bytes,
    )

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
        headers = dict(error.headers or {})
        if error.status_code == 405:
            allowed = set()
            for route in [
                *request.app.routes,
                *account_router.routes,
                *question_router.routes,
                *diagnostic_router.routes,
                *insight_router.routes,
                *lesson_router.routes,
                *tutoring_router.routes,
                *answer_router.routes,
                *dialogue_router.routes,
                *media_router.routes,
                *journey_router.routes,
                *task_router.routes,
                *task_records_router.routes,
                *task_images_router.routes,
                *dataset_images_router.routes,
                *practice_router.routes,
                *variant_attempt_router.routes,
                *review_filter_router.routes,
                *review_router.routes,
                *handwriting_router.routes,
                *study_bank_router.routes,
                *study_session_router.routes,
            ]:
                pattern = getattr(route, "path_regex", None)
                if pattern is not None and pattern.fullmatch(request.url.path):
                    allowed.update(route.methods or [])
            headers["Allow"] = ", ".join(sorted(allowed))
        detail = error.detail if isinstance(error.detail, str) else "请求未完成"
        return error_response(
            request, error.status_code, messages.get(error.status_code, detail), headers
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
        except (SQLAlchemyError, RuntimeError, ApiError):
            return JSONResponse({"status": "database_unavailable"}, status_code=503)
        return {"database": "mysql", "status": "database_ready", "ai": "not_connected"}

    return app
