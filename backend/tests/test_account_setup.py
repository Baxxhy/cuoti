from unittest.mock import AsyncMock

import pytest

from app.auth import verify_password
from app.models import GuardianStudentLink, StudentProfile, User
from app.services.account_setup import create_account, link_guardian


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
            db, email="teacher@example.com", name="教师", role="teacher", password="A-valid-password"
        )
    assert not db.added
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["student", "teacher", "guardian", "admin"])
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
async def test_guardian_link_is_idempotent_and_rejects_wrong_roles():
    guardian = User(id="guardian", role="guardian")
    student = User(id="student", role="student")
    db = SetupDB([guardian, student, None])
    assert await link_guardian(db, guardian_email="g@example.com", student_email="s@example.com")
    assert isinstance(db.added[0], GuardianStudentLink)
    db.commit.assert_awaited_once()
    duplicate = SetupDB([guardian, student, "existing-link"])
    assert not await link_guardian(duplicate, guardian_email="g@example.com", student_email="s@example.com")
    assert not duplicate.added
    wrong = SetupDB([User(role="teacher"), student])
    with pytest.raises(ValueError, match="身份不符"):
        await link_guardian(wrong, guardian_email="g@example.com", student_email="s@example.com")
    assert not wrong.added
