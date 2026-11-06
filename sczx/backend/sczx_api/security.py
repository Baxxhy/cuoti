"""Wire-compatible original password hashes, credential-bound tokens and media signatures."""
import base64
import hashlib
import hmac
import json
import secrets
import time
import uuid
from urllib.parse import quote


def new_id():
    return str(uuid.uuid4())


def b64(data):
    return base64.urlsafe_b64encode(data).decode('ascii')


def hash_password(password, salt=None):
    salt = secrets.token_bytes(16) if salt is None else salt
    derived = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 210000, dklen=32)
    return f'pbkdf2_sha256${b64(salt)}${b64(derived)}'


def verify_password(password, encoded):
    try:
        name, salt, _ = encoded.split('$')
        if name != 'pbkdf2_sha256':
            return False
        salt = base64.urlsafe_b64decode(salt)
        return len(salt) == 16 and hmac.compare_digest(hash_password(password, salt), encoded)
    except (ValueError, TypeError):
        return False


def signature(secret, text):
    return hmac.new(secret.encode(), text.encode(), hashlib.sha256).digest()


def credential_tag(credential, secret):
    return signature(secret, 'credential:v1:' + credential).hex()


def create_token(user_id, secret, credential, expires_at):
    claims = {'sub': user_id, 'exp': expires_at, 'credential': credential_tag(credential, secret)}
    payload = b64(json.dumps(claims, ensure_ascii=False, separators=(',', ':')).encode()).rstrip('=')
    return payload + '.' + b64(signature(secret, payload)).rstrip('=')


def read_token(token, secret, credential=None):
    try:
        if len(token.encode()) > 8192:
            return None
        payload, signed = token.split('.')
        if not hmac.compare_digest(signed, b64(signature(secret, payload)).rstrip('=')):
            return None
        claims = json.loads(base64.urlsafe_b64decode(payload + '=' * (-len(payload) % 4)))
        user_id, expiry = claims['sub'], claims['exp']
        if not isinstance(user_id, str) or not isinstance(expiry, int) or isinstance(expiry, bool):
            return None
        if expiry <= int(time.time()) or not user_id or len(user_id.encode()) > 36:
            return None
        if credential is not None and not hmac.compare_digest(claims.get('credential', ''), credential_tag(credential, secret)):
            return None
        return user_id
    except (ValueError, TypeError, KeyError, UnicodeError):
        return None


def media_url(path, secret, now=None):
    if not path.startswith(('/uploads/', '/reports/', '/api/v1/practice/questions/')):
        return path
    expires = int(time.time() if now is None else now) + 14400
    digest = signature(secret, f'media:v1:{expires}:{path}').hex()
    return f'{quote(path, safe="/-._~")}?expires={expires}&signature={digest}'


def valid_media(path, expires, signed, secret, now=None):
    try:
        now = int(time.time() if now is None else now)
        expires = int(expires)
        if not now < expires <= now + 14400:
            return False
        return hmac.compare_digest(signature(secret, f'media:v1:{expires}:{path}').hex(), signed)
    except (ValueError, TypeError):
        return False
