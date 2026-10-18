from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time


def hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 210_000)
    return (
        f"pbkdf2_sha256${base64.urlsafe_b64encode(salt).decode()}${base64.urlsafe_b64encode(digest).decode()}"
    )


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, salt_text, expected_text = encoded.split("$", 2)
        if algorithm != "pbkdf2_sha256":
            return False
        salt = base64.urlsafe_b64decode(salt_text)
        actual = hash_password(password, salt).split("$", 2)[2]
        return hmac.compare_digest(actual, expected_text)
    except (TypeError, ValueError):
        return False


def create_access_token(
    user_id: str,
    secret: str,
    lifetime_seconds: int = 60 * 60 * 24 * 30,
    *,
    credential: str | None = None,
) -> str:
    claims = {"sub": user_id, "exp": int(time.time()) + lifetime_seconds}
    if credential is not None:
        claims["credential"] = credential_tag(credential, secret)
    payload = (
        base64.urlsafe_b64encode(json.dumps(claims, separators=(",", ":")).encode()).decode().rstrip("=")
    )
    signature = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).digest()
    return f"{payload}.{base64.urlsafe_b64encode(signature).decode().rstrip('=')}"


def credential_tag(credential: str, secret: str) -> str:
    # A keyed tag invalidates sessions after a password change without exposing
    # the stored password hash or requiring a database schema change.
    return hmac.new(secret.encode(), f"credential:v1:{credential}".encode(), hashlib.sha256).hexdigest()


def read_access_token(token: str, secret: str, *, credential: str | None = None) -> str | None:
    try:
        payload, signature = token.split(".", 1)
        expected = (
            base64.urlsafe_b64encode(
                hmac.new(secret.encode(), payload.encode(), hashlib.sha256).digest(),
            )
            .decode()
            .rstrip("=")
        )
        if not hmac.compare_digest(signature, expected):
            return None
        padded = payload + "=" * (-len(payload) % 4)
        data = json.loads(base64.urlsafe_b64decode(padded))
        if credential is not None and not hmac.compare_digest(
            str(data.get("credential", "")),
            credential_tag(credential, secret),
        ):
            return None
        return str(data["sub"]) if int(data["exp"]) > int(time.time()) else None
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None
