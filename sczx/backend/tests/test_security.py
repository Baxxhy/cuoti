import base64
import hashlib
import hmac
import json
import time
from sczx_api.security import hash_password, verify_password, create_token, read_token, media_url, valid_media
from sczx_api.database import bind_sql
from sczx_api.accounts import email_field, text_field
from fastapi import HTTPException
import pytest


def test_original_pbkdf2_encoding():
    salt = bytes(range(16))
    expected = 'pbkdf2_sha256$' + base64.urlsafe_b64encode(salt).decode() + '$' + base64.urlsafe_b64encode(hashlib.pbkdf2_hmac('sha256', '密码 A'.encode(), salt, 210000, dklen=32)).decode()
    assert hash_password('密码 A', salt) == expected
    assert verify_password('密码 A', expected)
    assert not verify_password('密码 A ', expected)


def test_token_credential_binding_expiry_and_forgery():
    token = create_token('student-1', 's' * 32, 'old-hash', int(time.time()) + 100)
    assert read_token(token, 's' * 32, 'old-hash') == 'student-1'
    assert read_token(token, 's' * 32, 'new-hash') is None
    assert read_token(token + 'a', 's' * 32) is None
    assert read_token(create_token('student-1', 's' * 32, 'h', 1), 's' * 32) is None
    payload, signed = token.split('.')
    assert signed == base64.urlsafe_b64encode(hmac.new(b's' * 32, payload.encode(), hashlib.sha256).digest()).decode().rstrip('=')


def test_media_signature_matches_original_protocol():
    path = '/uploads/a/原图.png'
    url = media_url(path, 'secret', now=100)
    signed = hmac.new(b'secret', f'media:v1:14500:{path}'.encode(), hashlib.sha256).hexdigest()
    assert url.endswith('expires=14500&signature=' + signed)
    assert '%E5%8E%9F' in url
    assert valid_media(path, 14500, signed, 'secret', now=100)
    assert not valid_media(path + 'x', 14500, signed, 'secret', now=100)
    assert not valid_media(path, 14500, signed, 'secret', now=14500)


def test_sql_parameter_conversion_preserves_literals_and_percent():
    assert bind_sql("SELECT '?' AS sample WHERE id=? AND name LIKE '%?%' AND score>10%3") == "SELECT '?' AS sample WHERE id=%s AND name LIKE '%%?%%' AND score>10%%3"


def test_request_fields_preserve_whitespace_and_original_errors():
    assert email_field({'email': ' User@Example.COM '}) == 'user@example.com'
    assert text_field({'password': ' a '}, 'password', 256, trim=False) == ' a '
    with pytest.raises(HTTPException) as error:
        email_field({'email': 'a b@example.com'})
    assert error.value.status_code == 422
    assert error.value.detail == '请输入正确的邮箱'


def test_original_cangjie_auth_golden_vectors(monkeypatch):
    from pathlib import Path
    from sczx_api import security
    vector = json.loads((Path(__file__).resolve().parents[2] / 'reference/backend-cangjie/tests/auth_vectors.json').read_text())
    assert hash_password(vector['password'], bytes(range(16))) == vector['encoded']
    assert security.credential_tag(vector['encoded'], vector['secret']) == vector['tag']
    payload = vector['token'].split('.')[0]
    expiry = json.loads(base64.urlsafe_b64decode(payload + '=' * (-len(payload) % 4)))['exp']
    monkeypatch.setattr(security.time, 'time', lambda: expiry - 1)
    assert read_token(vector['token'], vector['secret'], vector['encoded']) == vector['user_id']
    assert read_token(vector['token'], vector['secret'], 'changed') is None
