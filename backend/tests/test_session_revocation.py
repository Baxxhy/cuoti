import pytest
from fastapi import HTTPException

from app.auth import create_access_token, read_access_token
from app.config import settings
from app.models import User
from app.services.access_control import authenticated_account


class AccountDB:
    def __init__(self, account):
        self.account = account

    async def get(self, _model, user_id):
        return self.account if user_id == self.account.id else None


@pytest.mark.asyncio
async def test_password_change_invalidates_all_existing_sessions():
    account = User(id="student", password_hash="original-password-hash")
    db = AccountDB(account)
    old = create_access_token(account.id, settings.auth_secret, credential=account.password_hash)
    assert await authenticated_account("Bearer " + old, db) is account
    account.password_hash = "changed-password-hash"
    with pytest.raises(HTTPException) as error:
        await authenticated_account("Bearer " + old, db)
    assert error.value.status_code == 401
    fresh = create_access_token(account.id, settings.auth_secret, credential=account.password_hash)
    assert await authenticated_account("Bearer " + fresh, db) is account


@pytest.mark.asyncio
async def test_legacy_unbound_tokens_require_a_new_login():
    account = User(id="student", password_hash="stored-hash")
    old = create_access_token(account.id, settings.auth_secret)
    with pytest.raises(HTTPException) as error:
        await authenticated_account("Bearer " + old, AccountDB(account))
    assert error.value.status_code == 401


def test_credentials_are_bound_without_exposing_the_stored_hash():
    import base64

    token = create_access_token("student", "test-secret", credential="private-password-hash")
    decoded = base64.urlsafe_b64decode(token.split(".")[0] + "==").decode()
    assert "private-password-hash" not in decoded
    assert read_access_token(token, "test-secret", credential="private-password-hash") == "student"
    assert read_access_token(token, "test-secret", credential="other-hash") is None
