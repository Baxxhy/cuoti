from __future__ import annotations

import json
import os
import time

from fastapi import HTTPException, Request

from .database import Database
from .security import create_token, hash_password, new_id, read_token, verify_password


def secret():
    value = os.environ.get('SCZX_AUTH_SECRET', '')
    if len(value.encode()) < 32:
        raise RuntimeError('SCZX_AUTH_SECRET 至少需要32个字符')
    return value


async def read_json(request: Request, max_bytes=65536, default_empty=False):
    data = bytearray()
    async for chunk in request.stream():
        data.extend(chunk)
        if len(data) > max_bytes:
            raise HTTPException(413, '请求内容过大')
    try:
        if default_empty and not data:
            return {}
        value = json.loads(data)
        if not isinstance(value, dict):
            raise ValueError
        return value
    except (ValueError, UnicodeError):
        raise HTTPException(422, '请输入有效的 JSON 对象') from None


def text_field(data, key, limit, *, trim=True, fallback=None):
    if key not in data:
        if fallback is None:
            raise HTTPException(422, f'缺少 {key}')
        value = fallback
    else:
        value = data[key]
        if not isinstance(value, str):
            raise HTTPException(422, f'{key} 必须是文字')
    if trim:
        value = value.strip()
    if not 0 < len(value) <= limit:
        raise HTTPException(422, f'{key} 长度不正确')
    return value


def email_field(data):
    value = text_field(data, 'email', 190)
    value = ''.join(c.lower() if 'A' <= c <= 'Z' else c for c in value)
    parts = value.split('@')
    if (len(parts) != 2 or not all(parts) or '.' not in parts[1]
            or parts[1].startswith('.') or parts[1].endswith('.')
            or any(c.isspace() for c in value)):
        raise HTTPException(422, '请输入正确的邮箱')
    return value


def user_json(row):
    result = {key: row[key] for key in ['id', 'email', 'name', 'role', 'created_at', 'updated_at']}
    for key in ['created_at', 'updated_at']:
        result[key] = result[key].replace(' ', 'T') + '+00:00'
    return result


def session(row):
    result = user_json(row)
    result['access_token'] = create_token(row['id'], secret(), row['password_hash'], int(time.time()) + 2592000)
    return result


def current_user(request, db):
    auth = request.headers.get('authorization', '')
    if auth.startswith('Bearer '):
        token = auth[7:].strip(' \t\r\n\v\f')
        user_id = read_token(token, secret())
        if user_id:
            rows = db.query('SELECT * FROM users WHERE id = ?', [user_id]).rows
            if (len(rows) == 1 and rows[0]['role'] in ['student', 'admin']
                    and read_token(token, secret(), rows[0]['password_hash']) == user_id):
                return rows[0]
    raise HTTPException(401, '请先使用账号和密码登录')


async def register(request):
    data = await read_json(request)
    email = email_field(data)
    password = text_field(data, 'password', 256, trim=False)
    name = text_field(data, 'name', 100, fallback='智维同学')
    grade = text_field(data, 'grade', 30, fallback='初二')
    hashed, user_id = hash_password(password), new_id()
    with Database.from_environment() as db:
        try:
            with db.transaction():
                db.query("INSERT INTO users (id,email,name,role,password_hash,created_at,updated_at) VALUES (?,?,?,'student',?,UTC_TIMESTAMP(),UTC_TIMESTAMP())", [user_id, email, name, hashed])
                db.query("INSERT INTO student_profiles (id,user_id,grade,learning_goal,preferences,created_at,updated_at) VALUES (?,?,?,'修复错误思维',JSON_OBJECT(),UTC_TIMESTAMP(),UTC_TIMESTAMP())", [new_id(), user_id, grade])
        except Exception as error:
            if getattr(error, 'args', [None])[0] == 1062:
                raise HTTPException(409, '这个邮箱已经注册，请直接登录') from None
            raise
        return session(db.query('SELECT * FROM users WHERE id = ?', [user_id]).rows[0])


async def login(request):
    data = await read_json(request)
    email = email_field(data)
    password = text_field(data, 'password', 256, trim=False)
    with Database.from_environment() as db:
        rows = db.query('SELECT * FROM users WHERE email = ?', [email]).rows
        if not rows or rows[0]['role'] not in ['student', 'admin'] or not verify_password(password, rows[0]['password_hash']):
            raise HTTPException(401, '账号或密码不正确')
        return session(rows[0])


async def reset_password(request):
    data = await read_json(request)
    email = email_field(data)
    previous = text_field(data, 'current_password', 256, trim=False)
    replacement = text_field(data, 'new_password', 256, trim=False)
    hashed = hash_password(replacement)
    with Database.from_environment() as db, db.transaction():
        rows = db.query('SELECT * FROM users WHERE email = ? FOR UPDATE', [email]).rows
        if not rows or not verify_password(previous, rows[0]['password_hash']):
            raise HTTPException(401, '账号或当前密码不正确，无法修改密码')
        db.query('UPDATE users SET password_hash = ?, updated_at = UTC_TIMESTAMP() WHERE id = ?', [hashed, rows[0]['id']])
    return {'email': email, 'reset': True}


async def me(request):
    with Database.from_environment() as db:
        user = current_user(request, db)
        if request.method == 'GET':
            return user_json(user)
        data = await read_json(request)
        if any(key not in ['name', 'email', 'grade', 'current_password'] for key in data):
            raise HTTPException(422, '请求包含不支持的字段')
        name = text_field(data, 'name', 100) if 'name' in data else user['name']
        email = email_field(data) if 'email' in data else user['email']
        grade = text_field(data, 'grade', 30) if 'grade' in data else ''
        if grade and (user['role'] != 'student' or grade not in ['初一', '初二', '初三', '高一', '高二', '高三']):
            raise HTTPException(422, '请选择有效年级')
        try:
            with db.transaction():
                existing = db.query('SELECT * FROM users WHERE id=? FOR UPDATE', [user['id']]).rows[0]
                if email != existing['email']:
                    password = text_field(data, 'current_password', 256, trim=False)
                    if not verify_password(password, existing['password_hash']):
                        raise HTTPException(422, '当前密码不正确，邮箱未修改')
                db.query('UPDATE users SET name=?,email=?,updated_at=UTC_TIMESTAMP() WHERE id=?', [name, email, user['id']])
                if grade:
                    db.query("UPDATE student_profiles SET grade=?,preferences=JSON_SET(COALESCE(preferences,JSON_OBJECT()),'$.experience_version',COALESCE(JSON_EXTRACT(preferences,'$.experience_version'),0)+1),updated_at=UTC_TIMESTAMP() WHERE user_id=?", [grade, user['id']])
                return user_json(db.query('SELECT * FROM users WHERE id=?', [user['id']]).rows[0])
        except Exception as error:
            if getattr(error, 'args', [None])[0] == 1062:
                raise HTTPException(409, '这个邮箱已被使用，请换一个邮箱') from None
            raise
