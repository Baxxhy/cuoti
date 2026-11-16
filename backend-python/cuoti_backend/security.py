"""Cangjie-compatible hashes and two-part signed sessions."""

import base64
import hashlib
import hmac
import json
import secrets
import time


def encode(value: bytes, *, padded: bool = True):
    result = base64.urlsafe_b64encode(value).decode("ascii")
    return result if padded else result.rstrip("=")


def decode(value: str):
    return base64.b64decode(
        value + "=" * (-len(value) % 4), altchars=b"-_", validate=True
    )


def hash_password(password: str, salt: bytes | None = None):
    salt = secrets.token_bytes(16) if salt is None else salt
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 210000, dklen=32)
    return f"pbkdf2_sha256${encode(salt)}${encode(digest)}"


def verify_password(password: str, encoded: str):
    try:
        kind, raw_salt, _ = encoded.split("$")
        salt = decode(raw_salt)
        return (
            kind == "pbkdf2_sha256"
            and len(salt) == 16
            and hmac.compare_digest(
                hash_password(password, salt).encode(), encoded.encode()
            )
        )
    except (ValueError, UnicodeError):
        return False


def signature(secret: str, value: str):
    return hmac.digest(secret.encode(), value.encode(), "sha256")


def credential_tag(password_hash: str, secret: str):
    return signature(secret, "credential:v1:" + password_hash).hex()


def create_token(
    user_id: str, secret: str, password_hash: str, expires: int | None = None
):
    claims = {
        "sub": user_id,
        "exp": int(time.time()) + 2592000 if expires is None else expires,
        "credential": credential_tag(password_hash, secret),
    }
    payload = encode(
        json.dumps(claims, ensure_ascii=False, separators=(",", ":")).encode(),
        padded=False,
    )
    return payload + "." + encode(signature(secret, payload), padded=False)


def read_token(token: str, secret: str, password_hash: str | None = None):
    try:
        if len(token.encode()) > 8192:
            return None
        payload, supplied = token.split(".")
        expected = encode(signature(secret, payload), padded=False)
        if not hmac.compare_digest(expected.encode(), supplied.encode()):
            return None
        claims = json.loads(decode(payload))
        user_id, expires = claims["sub"], claims["exp"]
        if type(expires) is not int or expires <= int(time.time()):
            return None
        if not isinstance(user_id, str) or not 1 <= len(user_id.encode()) <= 36:
            return None
        if password_hash is not None and not hmac.compare_digest(
            str(claims.get("credential", "")).encode(),
            credential_tag(password_hash, secret).encode(),
        ):
            return None
        return user_id
    except (ValueError, TypeError, KeyError, UnicodeError):
        return None
