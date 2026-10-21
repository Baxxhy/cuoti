from unittest.mock import AsyncMock

import pytest

from app.auth import verify_password
from app.models import StudentProfile
from app.services.account_setup import create_account


class SetupDB:
    def __init__(self, results):
        self.scalar = AsyncMock(side_effect=results)
        self.added = []
        self.commit = AsyncMock()

    def add(self, row):
        self.added.append(row)

    async def flush(self):
        for row in self.added:
            if not row.id:
                row.id = "new-user"


@pytest.mark.asyncio
async def test_existing_account_is_never_overwritten():
    db = SetupDB(["existing-user"])
    with pytest.raises(ValueError, match="不会覆盖"):
        await create_account(
            db, email="teacher@example.com", name="教师", role="admin", password="A-valid-password"
        )
    assert not db.added
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["student", "admin"])
async def test_real_account_has_requested_role_hashed_password_and_only_student_profile(role):
    db = SetupDB([None])
    user = await create_account(
        db, email=" Person@Example.com ", name=" 教师 ", role=role, password="A-valid-password", grade="高一"
    )
    assert user.email == "person@example.com" and user.name == "教师" and user.role == role
    assert user.password_hash != "A-valid-password" and verify_password(
        "A-valid-password", user.password_hash
    )
    profiles = [row for row in db.added if isinstance(row, StudentProfile)]
    assert len(profiles) == (1 if role == "student" else 0)
    if profiles:
        assert profiles[0].grade == "高一" and profiles[0].user_id == user.id
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["teacher", "guardian"])
async def test_removed_identity_cannot_be_created(role):
    db = SetupDB([])
    with pytest.raises(ValueError, match="身份无效"):
        await create_account(
            db, email="removed@example.com", name="移除身份", role=role, password="A-valid-password"
        )
    assert not db.added
