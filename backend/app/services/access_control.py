"""Shared resource checks for the student API, including legacy endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import read_access_token
from app.config import settings
from app.db import get_db
from app.media import is_media_path, valid_media_url
from app.models import (
    Paper,
    ProcessingJob,
    Question,
    ReviewPlan,
    TutorSession,
    User,
    VariantQuestion,
    VisualizationSpec,
)

PUBLIC_API_PATHS = {
    "/api/v1/auth/login",
    "/api/v1/auth/register",
    "/api/v1/auth/reset-password",
    "/api/v1/system/health",
    "/api/v1/system/providers",
    "/api/v1/system/voice",
}


async def authenticated_account(
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> User:
    token = authorization.removeprefix("Bearer ").strip() if authorization else ""
    user_id = read_access_token(token, settings.auth_secret) if token else None
    user = await db.get(User, user_id) if user_id else None
    if (
        user is None
        or not user.password_hash
        or read_access_token(
            token,
            settings.auth_secret,
            credential=user.password_hash,
        )
        != user.id
    ):
        raise HTTPException(401, "请先使用账号和密码登录")
    return user


async def owned_resource(db: AsyncSession, model: Any, resource_id: str, user: User) -> Any:
    row = await db.get(model, resource_id)
    if row is None or row.user_id != user.id:
        raise HTTPException(404, "内容不存在或无权访问")
    return row


async def authorize_api_request(
    request: Request,
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> None:
    path = request.url.path
    if path in PUBLIC_API_PATHS:
        return
    if (
        path.startswith("/api/v1/practice/questions/")
        and is_media_path(path)
        and valid_media_url(
            path,
            request.url.query,
            settings.auth_secret,
        )
    ):
        return
    user = await authenticated_account(authorization, db)
    params = request.path_params
    if path.startswith("/api/v1/questions/") and "question_id" in params:
        await owned_resource(db, Question, params["question_id"], user)
    elif path.startswith("/api/v1/jobs/"):
        job = await db.get(ProcessingJob, params["job_id"])
        if job is None:
            raise HTTPException(404, "任务不存在")
        await owned_resource(db, Question, job.question_id, user)
    elif path.startswith("/api/v1/papers/") and "paper_id" in params:
        await owned_resource(db, Paper, params["paper_id"], user)
    elif path.startswith("/api/v1/reviews/") and "plan_id" in params:
        await owned_resource(db, ReviewPlan, params["plan_id"], user)
    elif path.startswith("/api/v1/tutor/sessions/"):
        session = await owned_resource(db, TutorSession, params["session_id"], user)
        if (session.state or {}).get("question_changed"):
            raise HTTPException(409, "题目或作答已修改，请重新分析并开始新的学习")
    elif path.startswith(("/api/v1/variants/", "/api/v1/visualizations/")):
        resource_id = params.get("variant_id") or params.get("visualization_id")
        if resource_id:
            row: VariantQuestion | VisualizationSpec | None
            if "variant_id" in params:
                row = await db.get(VariantQuestion, resource_id)
            else:
                row = await db.get(VisualizationSpec, resource_id)
            if row is None:
                raise HTTPException(404, "内容不存在")
            session = await owned_resource(db, TutorSession, row.session_id, user)
            if (session.state or {}).get("question_changed"):
                raise HTTPException(409, "题目或作答已修改，请重新开始学习")
