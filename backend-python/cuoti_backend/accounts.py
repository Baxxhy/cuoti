import json
from datetime import timezone
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .account_schemas import (
    GRADES,
    Credentials,
    PasswordChange,
    PreferencePatch,
    ProfilePatch,
    Registration,
    UserOutput,
    text_field,
)
from .database import get_session
from .models import StudentProfile, User
from .protocol import ApiError, envelope
from .security import create_token, hash_password, read_token, verify_password

router = APIRouter(prefix="/api/v1")
Db = Annotated[Session, Depends(get_session)]


def auth_secret(request):
    secret = request.app.state.settings.auth_secret.get_secret_value()
    if len(secret.encode()) < 32:
        raise ApiError(503, "账号认证密钥未配置")
    return secret


def current_user(request: Request, db: Session):
    secret = auth_secret(request)
    authorization = request.headers.get("authorization", "")
    token = (
        authorization[7:].strip(" \t\r\n\v\f")
        if authorization.startswith("Bearer ")
        else ""
    )
    user_id = read_token(token, secret)
    user = db.get(User, user_id) if user_id else None
    if (
        user is None
        or user.role not in ["student", "admin"]
        or read_token(token, secret, user.password_hash) != user.id
    ):
        raise ApiError(401, "请先使用账号和密码登录")
    return user


def require_role(user, role):
    if user.role != role:
        raise ApiError(
            403,
            "仅学生可以修改本人的学习方向" if role == "student" else "请使用管理员账号",
        )


def user_output(user):
    return UserOutput(
        id=user.id,
        email=user.email,
        name=user.name,
        role=user.role,
        created_at=user.created_at.replace(tzinfo=timezone.utc).isoformat(),
        updated_at=user.updated_at.replace(tzinfo=timezone.utc).isoformat(),
    ).model_dump()


def session_output(user, secret):
    return {
        **user_output(user),
        "access_token": create_token(user.id, secret, user.password_hash),
    }


async def json_body(request: Request):
    raw = await request.body()
    if len(raw) > 65536:
        raise ApiError(413, "请求内容过大")
    try:
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise TypeError
        return value
    except (ValueError, TypeError, UnicodeError):
        raise ApiError(422, "请输入有效的 JSON 对象") from None


Body = Annotated[dict, Depends(json_body)]


def duplicate_email(error, message):
    if getattr(error.orig, "args", (None,))[0] == 1062:
        raise ApiError(409, message) from None
    raise error


@router.post("/auth/register")
def register(request: Request, body: Body, db: Db):
    secret = auth_secret(request)
    value = Registration.model_validate(body)
    user = User(
        id=str(uuid4()),
        email=value.email,
        name=value.name,
        role="student",
        password_hash=hash_password(value.password),
    )
    try:
        with db.begin():
            db.add(user)
            db.flush()
            db.add(
                StudentProfile(
                    id=str(uuid4()),
                    user_id=user.id,
                    grade=value.grade,
                    learning_goal="修复错误思维",
                    preferences={},
                )
            )
            db.flush()
            result = session_output(user, secret)
    except IntegrityError as error:
        duplicate_email(error, "这个邮箱已经注册，请直接登录")
    return envelope(request, result)


@router.post("/auth/login")
def login(request: Request, body: Body, db: Db):
    secret = auth_secret(request)
    value = Credentials.model_validate(body)
    with db.begin():
        user = db.scalar(select(User).where(User.email == value.email))
        if (
            user is None
            or user.role not in ["student", "admin"]
            or not verify_password(value.password, user.password_hash)
        ):
            raise ApiError(401, "账号或密码不正确")
        result = session_output(user, secret)
    return envelope(request, result)


@router.post("/auth/reset-password")
def reset_password(request: Request, body: Body, db: Db):
    auth_secret(request)
    value = PasswordChange.model_validate(body)
    replacement = hash_password(value.new_password)
    with db.begin():
        user = db.scalar(
            select(User).where(User.email == value.email).with_for_update()
        )
        if user is None or not verify_password(
            value.current_password, user.password_hash
        ):
            raise ApiError(401, "账号或当前密码不正确，无法修改密码")
        user.password_hash = replacement
        user.updated_at = func.utc_timestamp()
    return envelope(request, {"email": value.email, "reset": True})


@router.get("/auth/me")
def me(request: Request, db: Db):
    with db.begin():
        result = user_output(current_user(request, db))
    return envelope(request, result)


@router.patch("/auth/me")
def edit_me(request: Request, body: Body, db: Db):
    try:
        with db.begin():
            user = current_user(request, db)
            value = ProfilePatch.model_validate(body)
            user = db.scalar(
                select(User)
                .where(User.id == user.id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if value.grade is not None and (
                user.role != "student" or value.grade not in GRADES
            ):
                raise ApiError(422, "请选择有效年级")
            if value.email is not None and value.email != user.email:
                password = text_field(body, "current_password", 256, trim=False)
                if not verify_password(password, user.password_hash):
                    raise ApiError(422, "当前密码不正确，邮箱未修改")
                user.email = value.email
            if value.name is not None:
                user.name = value.name
            user.updated_at = func.utc_timestamp()
            if value.grade is not None:
                profile = db.scalar(
                    select(StudentProfile)
                    .where(StudentProfile.user_id == user.id)
                    .with_for_update()
                )
                if profile is not None:
                    preferences = dict(profile.preferences or {})
                    preferences["experience_version"] = (
                        preferences_output(profile)["version"] + 1
                    )
                    profile.grade = value.grade
                    profile.preferences = preferences
                    profile.updated_at = func.utc_timestamp()
            db.flush()
            db.refresh(user)
            result = user_output(user)
    except IntegrityError as error:
        duplicate_email(error, "这个邮箱已被使用，请换一个邮箱")
    return envelope(request, result)


def preferences_output(profile):
    preferences = profile.preferences if isinstance(profile.preferences, dict) else {}
    minutes = preferences.get("daily_minutes")
    version = preferences.get("experience_version")
    subject = preferences.get("focus_subject")
    goal = preferences.get("focus_goal")
    return {
        "grade": profile.grade,
        "subject": subject if isinstance(subject, str) else "",
        "minutes": minutes if type(minutes) is int and minutes > 0 else 10,
        "goal": goal if isinstance(goal, str) and goal else "understand",
        "version": version if type(version) is int else 0,
    }


@router.get("/student-preferences")
def get_preferences(request: Request, db: Db):
    with db.begin():
        user = current_user(request, db)
        require_role(user, "student")
        profile = db.scalar(
            select(StudentProfile).where(StudentProfile.user_id == user.id)
        )
        if profile is None:
            raise ApiError(404, "学生档案不存在")
        result = preferences_output(profile)
    return envelope(request, result)


@router.patch("/student-preferences")
def save_preferences(request: Request, body: Body, db: Db):
    with db.begin():
        user = current_user(request, db)
        require_role(user, "student")
        profile = db.scalar(
            select(StudentProfile)
            .where(StudentProfile.user_id == user.id)
            .with_for_update()
        )
        if profile is None:
            raise ApiError(404, "学生档案不存在")
        current = preferences_output(profile)
        if (
            type(body.get("version")) is not int
            or body["version"] != current["version"]
        ):
            raise ApiError(409, "学习方向已变化，请重新读取后保存")
        value = PreferencePatch.model_validate(body)
        preferences = dict(profile.preferences or {})
        preferences.update(
            focus_subject=value.subject,
            daily_minutes=value.minutes,
            focus_goal=value.goal,
            experience_version=value.version + 1,
        )
        profile.preferences = preferences
        if value.grade is not None:
            profile.grade = value.grade
        profile.updated_at = func.utc_timestamp()
        db.flush()
        result = preferences_output(profile)
    return envelope(request, result)
