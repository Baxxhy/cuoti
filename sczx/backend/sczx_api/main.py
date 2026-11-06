from contextlib import asynccontextmanager

import pymysql
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.routing import Match
from .preferences import student_preferences
from .questions import list_questions
from .question_detail import read_question, archive_question
from .question_edit import edit_question

from . import accounts
from .database import Database
from .security import new_id


def envelope(data):
    return {'success': True, 'data': data, 'error': None, 'request_id': new_id()}


@asynccontextmanager
async def lifespan(app):
    accounts.secret()
    yield


app = FastAPI(title='SCZX', lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None, redirect_slashes=False)


@app.exception_handler(pymysql.MySQLError)
async def database_error(request, error):
    return JSONResponse({'detail': '数据库暂时不可用，请稍后重试'}, status_code=503)


@app.exception_handler(Exception)
async def unexpected_error(request, error):
    return JSONResponse({'detail': '请求未完成，请稍后重试'}, status_code=500)


@app.exception_handler(StarletteHTTPException)
async def http_error(request, error):
    detail = '请求方法不支持' if error.status_code == 405 else error.detail
    headers = error.headers
    if error.status_code == 405:
        matched = next((route for route in app.routes if route.matches(request.scope)[0] != Match.NONE), None)
        if matched:
            methods = [m for m in ['GET', 'PATCH', 'POST', 'DELETE'] if m in matched.methods]
            headers = {'Allow': ', '.join(methods)}
    return JSONResponse({'detail': detail}, status_code=error.status_code, headers=headers)


def account_route(path, methods, handler):
    async def endpoint(request: Request):
        return envelope(await handler(request))
    app.add_api_route('/api/v1/auth/' + path, endpoint, methods=methods, name=handler.__name__)


account_route('register', ['POST'], accounts.register)
account_route('login', ['POST'], accounts.login)
account_route('reset-password', ['POST'], accounts.reset_password)
account_route('me', ['GET', 'PATCH'], accounts.me)


@app.get('/livez')
async def livez():
    return {'service': 'sczx-python', 'status': 'alive', 'version': '0.1.0'}


@app.get('/readyz')
async def readyz():
    try:
        with Database.from_environment() as db:
            db.query('SELECT id FROM users LIMIT 1')
            versions = db.query("SELECT version FROM cangjie_schema_versions WHERE version = ?", ['010_study_sessions']).rows
            if len(versions) != 1:
                raise ValueError('schema incomplete')
        return {'database': 'mysql', 'schema': '010_study_sessions', 'status': 'database_ready', 'ai': 'not_connected'}
    except Exception:
        return JSONResponse({'status': 'database_unavailable'}, status_code=503)


@app.api_route('/api/v1/student-preferences', methods=['GET', 'PATCH'])
async def preferences(request: Request):
    return envelope(await student_preferences(request))


@app.get('/api/v1/questions')
async def questions(request: Request):
    return envelope(await list_questions(request))


@app.api_route('/api/v1/questions/{question_id}', methods=['GET', 'PATCH', 'DELETE'])
async def question(request: Request):
    handler = {'GET': read_question, 'PATCH': edit_question, 'DELETE': archive_question}[request.method]
    return envelope(await handler(request))
