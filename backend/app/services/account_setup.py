"""Operator-only account setup; no demo records or existing credentials are changed."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import hash_password
from app.models import StudentProfile, User
from app.request_validation import RegisterRequest

ROLES = ("student", "admin")


async def create_account(
    db: AsyncSession, *, email: str, name: str, role: str, password: str, grade: str = "初二"
) -> User:
    if role not in ROLES:
        raise ValueError("账号身份无效")
    fields = RegisterRequest(email=email, name=name, password=password, grade=grade)
    if len(password) < 8:
        raise ValueError("运营账号密码至少需要 8 个字符")
    normalized_email = fields.email.lower()
    if await db.scalar(select(User.id).where(User.email == normalized_email)):
        raise ValueError("该邮箱已存在；不会覆盖身份、密码或学习数据")
    user = User(email=normalized_email, name=fields.name, role=role, password_hash=hash_password(password))
    db.add(user)
    await db.flush()
    if role == "student":
        db.add(StudentProfile(user_id=user.id, grade=fields.grade))
    await db.commit()
    return user
