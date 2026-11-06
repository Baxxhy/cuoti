from contextlib import asynccontextmanager

import pymysql
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.routing import Match
from .preferences import student_preferences
from .questions import list_questions
from .question_detail import read_question, archive_question
from .question_edit import edit_question
from .manual_questions import create_manual_question
from .ingest import ingest_question
from .recognition import recover_jobs
from .jobs import get_job, retry_job
from .crop import crop_question, start_recognition
from .ocr_edits import save_ocr_edits
from .media import serve_media
from .analysis import analyze_question, submit_work
from .diagnosis import diagnose_question, get_diagnosis
from .diagnosis_edit import correct_diagnosis, counterfactual_question
from .tutor_start import start_tutor
from .tutor_read import read_tutor
from .tutor_variants import tutor_variant
from .tutor_navigation import navigate_tutor
from .tutor_teach_back import teach_back
from .tutor_completion import finish_tutor
from .tutor_answer import answer_activity
from .handwriting import upload_handwriting
from .variant_attempt import variant_attempt
from .visualizations import session_visualization, visualization_types, read_visualization
from .tutor_dialogue import tutor_dialogue
from .dashboard import dashboard
from .insights import analytics, error_sources
from .knowledge import knowledge_cards, read_knowledge_card
from .cognition_graph import cognition_graph
from .reviews import list_reviews, attempt_review, grade_review
from .review_search import search_reviews, saved_filters
from .study_bank import study_bank
from .practice_images import serve_practice_image
from .study_sessions import sessions, session_api
from .knowledge_lessons import personal_framework, knowledge_lessons
from .system import system_api
from .voice import transcribe, synthesize
from .admin import admin_api

from . import accounts
from .database import Database
from .security import new_id


def envelope(data):
    return {'success': True, 'data': data, 'error': None, 'request_id': new_id()}


@asynccontextmanager
async def lifespan(app):
    accounts.secret()
    recover_jobs()
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
            methods = [m for m in ['GET', 'HEAD', 'PATCH', 'POST', 'DELETE'] if m in matched.methods]
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


@app.post('/api/v1/questions/manual')
async def manual_question(request: Request):
    return envelope(await create_manual_question(request))


@app.post('/api/v1/questions/ingest')
async def ingest(request: Request, background: BackgroundTasks):
    return envelope(await ingest_question(request, background))


@app.get('/api/v1/jobs/{job_id}')
async def job(request: Request):
    return envelope(await get_job(request))


@app.post('/api/v1/jobs/{job_id}/retry')
async def retry(request: Request, background: BackgroundTasks):
    return envelope(await retry_job(request, background))


@app.api_route('/api/v1/questions/{question_id}', methods=['GET', 'PATCH', 'DELETE'])
async def question(request: Request):
    handler = {'GET': read_question, 'PATCH': edit_question, 'DELETE': archive_question}[request.method]
    return envelope(await handler(request))


@app.post('/api/v1/questions/{question_id}/crop')
async def crop(request: Request, background: BackgroundTasks):
    return envelope(await crop_question(request, background))


@app.post('/api/v1/questions/{question_id}/ocr')
async def ocr(request: Request, background: BackgroundTasks):
    return envelope(await start_recognition(request, background, synchronous=True))


@app.post('/api/v1/questions/{question_id}/reprocess')
async def reprocess(request: Request, background: BackgroundTasks):
    return envelope(await start_recognition(request, background))


@app.post('/api/v1/questions/{question_id}/draft')
async def draft(request: Request):
    return envelope(await save_ocr_edits(request, False))


@app.post('/api/v1/questions/{question_id}/confirm')
async def confirm(request: Request):
    return envelope(await save_ocr_edits(request, True))


@app.post('/api/v1/questions/{question_id}/analyze')
async def analyze(request: Request):
    return envelope(await analyze_question(request))


@app.post('/api/v1/questions/{question_id}/student-work')
async def student_work(request: Request):
    return envelope(await submit_work(request))


@app.post('/api/v1/questions/{question_id}/diagnose')
async def diagnose(request: Request):
    return envelope(await diagnose_question(request))


@app.api_route('/api/v1/questions/{question_id}/diagnosis', methods=['GET', 'PATCH'])
async def diagnosis(request: Request):
    handler = get_diagnosis if request.method == 'GET' else correct_diagnosis
    return envelope(await handler(request))


@app.post('/api/v1/questions/{question_id}/diagnosis/counterfactual')
async def counterfactual(request: Request):
    return envelope(await counterfactual_question(request))


@app.post('/api/v1/tutor/sessions')
async def tutor_start(request: Request):
    return envelope(await start_tutor(request))


@app.get('/api/v1/tutor/sessions/{session_id}')
async def tutor_read(request: Request):
    return envelope(await read_tutor(request))


@app.post('/api/v1/tutor/sessions/{session_id}/variant')
async def variant(request: Request):
    return envelope(await tutor_variant(request))


@app.post('/api/v1/tutor/sessions/{session_id}/advance')
async def tutor_advance(request: Request):
    return envelope(await navigate_tutor(request, False))


@app.post('/api/v1/tutor/sessions/{session_id}/rewind')
async def tutor_rewind(request: Request):
    return envelope(await navigate_tutor(request, True))


@app.post('/api/v1/tutor/sessions/{session_id}/teach-back')
async def tutor_teach_back(request: Request):
    return envelope(await teach_back(request))


@app.post('/api/v1/tutor/sessions/{session_id}/finish')
async def tutor_finish(request: Request):
    return envelope(await finish_tutor(request))


@app.post('/api/v1/tutor/sessions/{session_id}/activity/answer')
async def tutor_answer(request: Request):
    return envelope(await answer_activity(request))


@app.post('/api/v1/answers/handwriting')
async def handwriting(request: Request):
    return envelope(await upload_handwriting(request))


@app.post('/api/v1/variants/{variant_id}/attempt')
async def variant_answer(request: Request):
    return envelope(await variant_attempt(request))


@app.api_route('/api/v1/tutor/sessions/{session_id}/visualization', methods=['GET', 'POST'])
async def tutor_visualization(request: Request):
    return envelope(await session_visualization(request))


@app.get('/api/v1/visualizations/types')
async def visual_types():
    return envelope(await visualization_types())


@app.get('/api/v1/visualizations/{visualization_id}')
async def visual_read(request: Request):
    return envelope(await read_visualization(request))


@app.post('/api/v1/tutor/sessions/{session_id}/turns')
async def tutor_turn(request: Request):
    return envelope(await tutor_dialogue(request))


@app.get('/api/v1/dashboard')
async def student_dashboard(request: Request):
    return envelope(await dashboard(request))


@app.get('/api/v1/analytics/overview')
async def student_analytics(request: Request):
    return envelope(await analytics(request))


@app.get('/api/v1/analytics/error-sources')
async def student_errors(request: Request):
    return envelope(await error_sources(request))


@app.get('/api/v1/knowledge/cards')
async def cards(request: Request):
    return envelope(await knowledge_cards(request))


@app.get('/api/v1/knowledge/cards/{code}')
async def card(request: Request):
    return envelope(await read_knowledge_card(request))


@app.get('/api/v1/analytics/cognition-graph')
async def student_cognition_graph(request: Request):
    return envelope(await cognition_graph(request))


@app.get('/api/v1/reviews/today')
async def today_reviews(request: Request):
    return envelope(await list_reviews(request))


@app.get('/api/v1/reviews/history')
async def review_history(request: Request):
    return envelope(await list_reviews(request, history=True))


@app.post('/api/v1/reviews/{plan_id}/attempt')
async def review_attempt(request: Request):
    return envelope(await attempt_review(request))


@app.post('/api/v1/reviews/{plan_id}/grade')
async def review_grade(request: Request):
    return envelope(await grade_review(request))


@app.get('/api/v1/reviews/search')
async def review_search(request: Request):
    return envelope(await search_reviews(request))


@app.api_route('/api/v1/reviews/filters', methods=['GET', 'POST'])
async def review_filters(request: Request):
    return envelope(await saved_filters(request))


@app.delete('/api/v1/reviews/filters/{filter_id}')
async def delete_review_filter(request: Request):
    return envelope(await saved_filters(request, deleting=True))


@app.get('/api/v1/study-bank')
async def bank(request: Request):
    return envelope(await study_bank(request))


@app.api_route('/api/v1/practice/questions/{question_id}/images/{image_index}', methods=['GET', 'HEAD'])
async def practice_image(request: Request):
    return await serve_practice_image(request)


@app.api_route('/api/v1/study-sessions', methods=['GET', 'POST'])
async def study_sessions(request: Request):
    return envelope(await sessions(request))


@app.api_route('/api/v1/study-sessions/{session_id}', methods=['GET', 'PATCH'])
async def study_session(request: Request):
    return envelope(await session_api(request))


@app.post('/api/v1/study-sessions/{session_id}/submit')
async def submit_study(request: Request):
    return envelope(await session_api(request, submitting=True))


@app.get('/api/v1/knowledge/framework')
async def knowledge_framework(request: Request):
    return envelope(await personal_framework(request))


@app.api_route('/api/v1/knowledge/cards/{code}/lessons', methods=['GET', 'POST'])
async def lessons(request: Request):
    return envelope(await knowledge_lessons(request))


@app.get('/api/v1/system/health')
async def system_health():
    return envelope(await system_api('health'))


@app.get('/api/v1/system/providers')
async def system_providers():
    return envelope(await system_api('providers'))


@app.post('/api/v1/system/providers/probe')
async def system_probe():
    return envelope(await system_api('probe'))


@app.get('/api/v1/system/voice')
async def system_voice():
    return envelope(await system_api('voice'))


@app.post('/api/v1/voice/transcribe')
async def voice_transcribe(request: Request):
    return envelope(await transcribe(request))


@app.post('/api/v1/voice/synthesize')
async def voice_synthesize(request: Request):
    return envelope(await synthesize(request))


@app.get('/api/v1/admin/workbench')
async def admin_workbench(request: Request):
    return envelope(await admin_api(request, 'workbench'))


@app.get('/api/v1/admin/students/{student_id}')
async def admin_student(request: Request):
    return envelope(await admin_api(request, 'student'))


@app.get('/api/v1/admin/sessions/{session_id}')
async def admin_session(request: Request):
    return envelope(await admin_api(request, 'session'))


@app.api_route('/uploads/{media_path:path}', methods=['GET', 'HEAD'])
@app.api_route('/reports/{media_path:path}', methods=['GET', 'HEAD'])
async def media(request: Request):
    return await serve_media(request)
