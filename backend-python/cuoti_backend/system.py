"""Existing public system status and provider checks, without exposing secrets."""

from fastapi import APIRouter, Request

from .protocol import ApiError, envelope
from .question_data import rows

router = APIRouter(prefix="/api/v1/system")


def state(request, probe=False):
    compute = request.app.state.questions.compute
    if compute is None:
        raise ApiError(503, "内部算法服务未配置")
    return compute.compute("system_state", probe_provider=probe)


@router.get("/health")
def health(request: Request):
    with request.app.state.database.session() as db:
        rows(db, "SELECT COUNT(*) AS total FROM users")
    provider = state(request)["provider"]
    return envelope(
        request,
        {
            "status": "healthy",
            "database": "mysql",
            "ai": provider["last_status"],
            "image_recognition": provider.get("vision_entries", 0) > 0,
        },
    )


@router.get("/providers")
def providers(request: Request):
    return envelope(request, state(request)["provider"])


@router.post("/providers/probe")
def probe(request: Request):
    return envelope(request, state(request, True)["provider"])


@router.get("/voice")
def voice(request: Request):
    return envelope(request, state(request)["voice"])
