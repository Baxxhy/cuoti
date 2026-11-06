"""Real MySQL acceptance isolated from every existing application database."""
import os
import shutil
import subprocess
import time
from pathlib import Path

import pymysql
import pytest
from fastapi.testclient import TestClient

from sczx_api.main import app
from sczx_api.schema import initialize_database
from sczx_api.database import Database


@pytest.fixture(scope='module')
def client(tmp_path_factory):
    binary = shutil.which('mysqld')
    assert binary, 'MySQL is required for backend parity checks'
    root = tmp_path_factory.mktemp('sczx_mysql')
    datadir, socket = root / 'data', root / 'mysql.sock'
    datadir.mkdir()
    logfile = root / 'mysql.log'
    with logfile.open('wb') as log:
        subprocess.run([binary, '--no-defaults', '--initialize-insecure', '--user=root', f'--datadir={datadir}', '--innodb-buffer-pool-size=32M', '--innodb-log-file-size=16M'], stdout=log, stderr=log, check=True, timeout=60)
        process = subprocess.Popen([binary, '--no-defaults', '--user=root', f'--datadir={datadir}', f'--socket={socket}', f'--pid-file={root / "mysql.pid"}', '--skip-networking', '--mysqlx=OFF', '--innodb-buffer-pool-size=32M', '--innodb-log-file-size=16M'], stdout=log, stderr=log)
        keys = ['SCZX_DB_NAME', 'SCZX_DB_USER', 'SCZX_DB_PASSWORD', 'SCZX_DB_SOCKET', 'SCZX_AUTH_SECRET']
        saved = {key: os.environ.get(key) for key in keys}
        try:
            deadline = time.monotonic() + 40
            while True:
                try:
                    connection = pymysql.connect(unix_socket=str(socket), user='root', charset='utf8mb4', autocommit=True)
                    break
                except pymysql.MySQLError:
                    if process.poll() is not None or time.monotonic() >= deadline:
                        raise RuntimeError(f'Isolated MySQL failed; inspect {logfile}') from None
                    time.sleep(.2)
            with connection:
                with connection.cursor() as cursor:
                    cursor.execute('CREATE DATABASE sczx_test_accounts CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci')
            os.environ.update(SCZX_DB_NAME='sczx_test_accounts', SCZX_DB_USER='root', SCZX_DB_PASSWORD='', SCZX_DB_SOCKET=str(socket), SCZX_AUTH_SECRET='sczx-isolated-contract-test-secret-000000')
            initialize_database()
            with TestClient(app) as web:
                yield web
        finally:
            process.terminate()
            try:
                process.wait(timeout=20)
            except subprocess.TimeoutExpired:
                process.kill(); process.wait()
            for key, value in saved.items():
                if value is None: os.environ.pop(key, None)
                else: os.environ[key] = value


def test_register_duplicate_login_and_me(client):
    payload = {'email': 'Student@Example.com', 'password': ' password ', 'name': ' 初中同学 ', 'grade': '初二'}
    response = client.post('/api/v1/auth/register', json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data['success'] is True and data['error'] is None and data['request_id']
    user = data['data']
    assert user['email'] == 'student@example.com' and user['name'] == '初中同学'
    assert user['role'] == 'student' and 'password_hash' not in user
    assert user['created_at'].endswith('+00:00')
    duplicate = client.post('/api/v1/auth/register', json=payload)
    assert duplicate.status_code == 409
    assert duplicate.json()['detail'] == '这个邮箱已经注册，请直接登录'
    assert client.post('/api/v1/auth/login', json={'email': payload['email'], 'password': 'password'}).status_code == 401
    login = client.post('/api/v1/auth/login', json={'email': payload['email'], 'password': payload['password']})
    assert login.status_code == 200
    headers = {'Authorization': 'Bearer ' + login.json()['data']['access_token']}
    assert client.get('/api/v1/auth/me', headers=headers).json()['data']['id'] == user['id']
    assert client.get('/api/v1/auth/me').status_code == 401
    assert client.get('/readyz').json()['status'] == 'database_ready'


def test_profile_email_requires_password_and_reset_revokes_token(client):
    payload = {'email': 'another@example.com', 'password': 'old-password'}
    user = client.post('/api/v1/auth/register', json=payload).json()['data']
    headers = {'Authorization': 'Bearer ' + user['access_token']}
    assert client.patch('/api/v1/auth/me', headers=headers, json={'email': 'changed@example.com'}).status_code == 422
    wrong = client.patch('/api/v1/auth/me', headers=headers, json={'email': 'changed@example.com', 'current_password': 'wrong'})
    assert wrong.status_code == 422
    assert wrong.json()['detail'] == '当前密码不正确，邮箱未修改'
    patched = client.patch('/api/v1/auth/me', headers=headers, json={'name': '新名字', 'grade': '初三', 'email': 'changed@example.com', 'current_password': 'old-password'})
    assert patched.status_code == 200 and patched.json()['data']['name'] == '新名字'
    with Database.from_environment() as db:
        profile = db.query('SELECT grade,preferences FROM student_profiles WHERE user_id=?', [user['id']]).rows[0]
        assert profile['grade'] == '初三' and 'experience_version' in profile['preferences']
    reset = client.post('/api/v1/auth/reset-password', json={'email': 'changed@example.com', 'current_password': 'old-password', 'new_password': 'new-password'})
    assert reset.status_code == 200
    assert client.get('/api/v1/auth/me', headers=headers).status_code == 401
    assert client.post('/api/v1/auth/login', json={'email': 'changed@example.com', 'password': 'old-password'}).status_code == 401
    assert client.post('/api/v1/auth/login', json={'email': 'changed@example.com', 'password': 'new-password'}).status_code == 200


def test_invalid_json_and_transaction_rollback(client):
    assert client.post('/api/v1/auth/register', content='[]').status_code == 422
    assert client.post('/api/v1/auth/register', content='x' * 65537).status_code == 413
    with Database.from_environment() as db:
        before = db.query('SELECT COUNT(*) AS n FROM users').rows[0]['n']
        with pytest.raises(RuntimeError):
            with db.transaction():
                db.query("INSERT INTO users (id,email,name,role,password_hash,created_at,updated_at) VALUES ('rollback','rollback@example.com','test','student','test',UTC_TIMESTAMP(),UTC_TIMESTAMP())")
                raise RuntimeError('rollback')
        assert db.query('SELECT COUNT(*) AS n FROM users').rows[0]['n'] == before


def test_preferences_version_conflict_and_persistence(client):
    user = client.post('/api/v1/auth/register', json={'email': 'prefs@example.com', 'password': 'secret'}).json()['data']
    headers = {'Authorization': 'Bearer ' + user['access_token']}
    original = client.get('/api/v1/student-preferences', headers=headers).json()['data']
    assert original == {'grade': '初二', 'subject': '', 'minutes': 10, 'goal': 'understand', 'version': 0}
    changes = {'grade': '高一', 'subject': '数学', 'minutes': 20, 'goal': 'practice', 'version': 0}
    updated = client.patch('/api/v1/student-preferences', json=changes, headers=headers)
    assert updated.status_code == 200 and updated.json()['data']['version'] == 1
    stale = client.patch('/api/v1/student-preferences', json=changes, headers=headers)
    assert stale.status_code == 409 and stale.json()['detail'] == '学习方向已变化，请重新读取后保存'
    persisted = client.get('/api/v1/student-preferences', headers=headers).json()['data']
    assert persisted['grade'] == '高一' and persisted['minutes'] == 20
    wrong = client.post('/api/v1/auth/me', headers=headers, json={})
    assert wrong.status_code == 405 and wrong.json()['detail'] == '请求方法不支持'
    assert wrong.headers['allow'] == 'GET, PATCH'


def test_question_list_search_deduplication_and_ownership(client):
    from sczx_api.security import new_id
    user = client.post('/api/v1/auth/register', json={'email': 'questions@example.com', 'password': 'secret'}).json()['data']
    other = client.post('/api/v1/auth/register', json={'email': 'other-questions@example.com', 'password': 'secret'}).json()['data']
    headers = {'Authorization': 'Bearer ' + user['access_token']}
    rows = [
        (new_id(), user['id'], '数学', '求 X？', 'confirmed', '2026-01-01 00:00:00'),
        (new_id(), user['id'], '数学', '求x', 'confirmed', '2026-01-02 00:00:00'),
        (new_id(), user['id'], '语文', '阅读文本', 'confirmed', '2026-01-03 00:00:00'),
        (new_id(), user['id'], '数学', '归档题', 'archived', '2026-01-04 00:00:00'),
        (new_id(), other['id'], '数学', '别人的题', 'confirmed', '2026-01-05 00:00:00'),
    ]
    with Database.from_environment() as db:
        for question_id, owner, subject, text, status, created in rows:
            db.query("INSERT INTO questions (id,user_id,subject,title,question_text,status,confirmed,favorite,tags,formulas,options,question_type,knowledge_points,created_at,updated_at) VALUES (?,?,?,?,?,?,1,0,JSON_ARRAY(),JSON_ARRAY(),JSON_ARRAY(),'综合题',JSON_ARRAY(),?,?)", [question_id, owner, subject, text, text, status, created, created])
    assert client.get('/api/v1/questions').status_code == 401
    response = client.get('/api/v1/questions', headers=headers)
    assert response.status_code == 200, response.text
    items = response.json()['data']
    assert [item['id'] for item in items] == [rows[2][0], rows[1][0]]
    assert items[0]['diagnosis_summary'] == '等待完成错因诊断'
    assert items[0]['review_due_at'] is None and items[0]['thumbnail_url'] is None
    assert items[0]['mastery_score'] == 0 and items[0]['mastery_status'] == '需要巩固'
    assert items[0]['confirmed'] is True and items[0]['knowledge_points'] == []
    filtered = client.get('/api/v1/questions?subject=语文&subject=数学', headers=headers).json()['data']
    assert [item['id'] for item in filtered] == [rows[1][0]]
    assert len(client.get('/api/v1/questions?search=阅读', headers=headers).json()['data']) == 1
    assert client.get('/api/v1/questions?search=计算错误', headers=headers).json()['data'] == []
    assert client.get('/api/v1/questions?search=归档题', headers=headers).json()['data'] == []


def test_question_detail_assets_and_archive_preserve_data(client):
    from sczx_api.security import new_id, valid_media
    from urllib.parse import urlsplit, parse_qs
    user = client.post('/api/v1/auth/register', json={'email': 'detail@example.com', 'password': 'secret'}).json()['data']
    other = client.post('/api/v1/auth/register', json={'email': 'detail-other@example.com', 'password': 'secret'}).json()['data']
    headers = {'Authorization': 'Bearer ' + user['access_token']}
    outsider = {'Authorization': 'Bearer ' + other['access_token']}
    question_id, review_id = new_id(), new_id()
    with Database.from_environment() as db:
        db.query("INSERT INTO questions (id,user_id,subject,title,question_text,status,confirmed,favorite,tags,formulas,options,question_type,knowledge_points,created_at,updated_at) VALUES (?,?,'数学','几何题','几何题','confirmed',1,0,JSON_ARRAY(),JSON_ARRAY(),JSON_ARRAY(),'综合题',JSON_ARRAY(),UTC_TIMESTAMP(),UTC_TIMESTAMP())", [question_id, user['id']])
        for kind, bbox in [('original', '[]'), ('crop', '[0.1,0.2,0.8,0.9]'), ('question_figure', '[]')]:
            db.query("INSERT INTO question_assets (id,question_id,kind,path,sha256,bbox,created_at,updated_at) VALUES (?,?,?,?,?,?,UTC_TIMESTAMP(),UTC_TIMESTAMP())", [new_id(), question_id, kind, f'uploads/{question_id}/{kind}.png', '0' * 64, bbox])
        db.query("INSERT INTO review_plans (id,user_id,question_id,due_at,interval_days,reason,status,created_at,updated_at) VALUES (?,?,?,UTC_TIMESTAMP(),1,'复习','pending',UTC_TIMESTAMP(),UTC_TIMESTAMP())", [review_id, user['id'], question_id])
    path = '/api/v1/questions/' + question_id
    assert client.get(path).status_code == 401
    assert client.get(path, headers=outsider).status_code == 404
    assert client.delete(path, headers=outsider).status_code == 404
    response = client.get(path, headers=headers)
    assert response.status_code == 200, response.text
    data = response.json()['data']
    assert data['crop_box'] == pytest.approx([.1, .2, .7, .7])
    assert len(data['assets']) == 3 and len(data['question_figures']) == 1
    assert data['student_working_figures'] == [] and data['teacher_annotation_regions'] == []
    for key in ['analysis', 'diagnosis', 'ocr', 'processing_job']:
        assert data[key] is None
    assert data['reference_steps'] == data['student_steps'] == data['teacher_marks'] == data['ocr_runs'] == []
    for asset in data['assets']:
        url = urlsplit(asset['url']); query = parse_qs(url.query)
        assert valid_media(url.path, query['expires'][0], query['signature'][0], os.environ['SCZX_AUTH_SECRET'])
    assert client.patch(path, headers=outsider, json={'title': '越权'}).status_code == 404
    favorite = client.patch(path, headers=headers, json={'favorite': 'yes', 'unknown': 'ignored'})
    assert favorite.status_code == 200 and favorite.json()['data']['favorite'] is True
    with Database.from_environment() as db:
        assert db.query('SELECT status FROM review_plans WHERE id=?', [review_id]).rows[0]['status'] == 'pending'
    invalid = client.patch(path, headers=headers, json={'question_type': '单选题', 'options': [{'label': 'A', 'text': '一个'}]})
    assert invalid.status_code == 422
    edited = client.patch(path, headers=headers, json={'question_text': ' 修改后的几何题 ', 'tags': [' 重点 '], 'grade': None})
    assert edited.status_code == 200, edited.text
    assert edited.json()['data']['question_text'] == '修改后的几何题'
    assert edited.json()['data']['tags'] == ['重点'] and edited.json()['data']['grade'] is None
    with Database.from_environment() as db:
        assert db.query('SELECT status FROM review_plans WHERE id=?', [review_id]).rows[0]['status'] == 'cancelled'
        db.query("UPDATE review_plans SET status='pending' WHERE id=?", [review_id])
    assert client.delete(path, headers=headers).json()['data'] == {'deleted': True}
    assert client.patch(path, headers=headers, json={'title': '归档后修改'}).status_code == 409
    wrong_method = client.post(path, headers=headers)
    assert wrong_method.status_code == 405 and wrong_method.headers['allow'] == 'GET, PATCH, DELETE'
    assert client.get(path, headers=headers).json()['data']['status'] == 'archived'
    assert client.get('/api/v1/questions', headers=headers).json()['data'] == []
    with Database.from_environment() as db:
        assert db.query('SELECT status FROM review_plans WHERE id=?', [review_id]).rows[0]['status'] == 'cancelled'
        assert db.query('SELECT COUNT(*) AS n FROM question_assets WHERE question_id=?', [question_id]).rows[0]['n'] == '3'


def test_manual_question_work_steps_validation_and_study_snapshot(client, tmp_path, monkeypatch):
    import json
    from sczx_api.security import new_id
    user = client.post('/api/v1/auth/register', json={'email': 'manual@example.com', 'password': 'secret'}).json()['data']
    headers = {'Authorization': 'Bearer ' + user['access_token']}
    url = '/api/v1/questions/manual'
    body = {'question_text': ' 求解 x+1=2 ', 'student_answer': ' 3 ', 'student_steps': [' x+1=2 ', '所以x等于3']}
    response = client.post(url, headers=headers, json=body)
    assert response.status_code == 200, response.text
    saved = response.json()['data']
    detail = client.get('/api/v1/questions/' + saved['id'], headers=headers).json()['data']
    assert detail['question_text'] == '求解 x+1=2' and detail['subject'] == '数学'
    assert detail['student_answer'] == '3' and detail['confirmed'] is True
    assert [s['text'] for s in detail['student_steps']] == ['x+1=2', '所以x等于3']
    assert detail['student_steps'][0]['formula'] == 'x+1=2'
    assert detail['student_steps'][1]['formula'] == ''
    for changes in [{'question_type': '填空题'}, {'student_answer': None}, {'student_steps': [' ']}, {'question_type': '单选题', 'options': [{'label': 'A', 'text': '1'}, {'label': 'A', 'text': '2'}]}]:
        assert client.post(url, headers=headers, json={**body, **changes}).status_code == 422
    assert client.post(url, json=body).status_code == 401
    session_id, item_id = new_id(), new_id()
    bank, media = tmp_path / 'bank', tmp_path / 'media'
    bank.mkdir(); image = bank / 'figure.png'; image.write_bytes(b'\x89PNG\r\n\x1a\nfixture')
    monkeypatch.setenv('SCZX_QUESTION_BANK_ROOT', str(bank))
    monkeypatch.setenv('SCZX_MEDIA_ROOT', str(media))
    snapshot = {'id': new_id(), 'question_text': '服务器题目', 'subject': '数学', 'grade': '初二', 'question_type': 'single_choice', 'options': ['选项一', '选项二'], 'image_paths': [str(image)], 'quality_status': 'ready', 'source_metadata': {}, 'knowledge_points': ['方程']}
    with Database.from_environment() as db:
        db.query("INSERT INTO study_sessions (id,user_id,mode,title,subject,grade_band,status,duration_seconds,created_at,updated_at) VALUES (?,?,'practice','练习','数学','初中','submitted',0,UTC_TIMESTAMP(),UTC_TIMESTAMP())", [session_id, user['id']])
        db.query('INSERT INTO study_session_items (id,session_id,position,snapshot,student_answer,grading) VALUES (?,?,0,?,?,?)', [item_id, session_id, json.dumps(snapshot), json.dumps('B'), json.dumps({'correct': False})])
    request = {'study_session_id': session_id, 'study_item_id': item_id, 'question_text': '客户端伪造', 'image_paths': ['/etc/passwd']}
    first = client.post(url, headers=headers, json=request)
    assert first.status_code == 200, first.text
    question_id = first.json()['data']['id']
    again = client.post(url, headers=headers, json=request)
    assert again.json()['data']['id'] == question_id
    detail = client.get('/api/v1/questions/' + question_id, headers=headers).json()['data']
    assert detail['question_text'] == '服务器题目' and detail['student_answer'] == 'B'
    assert detail['question_type'] == '单选题' and detail['options'][0] == {'label': 'A', 'text': '选项一'}
    assert detail['knowledge_points'] == ['方程'] and detail['tags'] == ['study-item:' + item_id]
    assert len(detail['question_figures']) == 1
    assert (media / detail['question_figures'][0]['path']).read_bytes() == image.read_bytes()
    with Database.from_environment() as db:
        db.query("UPDATE study_sessions SET status='active' WHERE id=?", [session_id])
    assert client.post(url, headers=headers, json=request).status_code == 409
    failed_item = new_id()
    failed_snapshot = {**snapshot, 'image_paths': [str(image), str(bank / 'missing.png')]}
    with Database.from_environment() as db:
        db.query("UPDATE study_sessions SET status='submitted' WHERE id=?", [session_id])
        db.query('INSERT INTO study_session_items (id,session_id,position,snapshot,student_answer,grading) VALUES (?,?,1,?,?,?)', [failed_item, session_id, json.dumps(failed_snapshot), json.dumps('B'), json.dumps({'correct': False})])
        before = db.query('SELECT COUNT(*) AS n FROM questions').rows[0]['n']
    files_before = set(media.rglob('*.png'))
    failed = client.post(url, headers=headers, json={'study_session_id': session_id, 'study_item_id': failed_item})
    assert failed.status_code == 404, failed.text
    assert set(media.rglob('*.png')) == files_before
    with Database.from_environment() as db:
        assert db.query('SELECT COUNT(*) AS n FROM questions').rows[0]['n'] == before


def test_ingest_recognition_failure_retry_stale_and_recovery(client, tmp_path, monkeypatch):
    import base64
    import hashlib
    from sczx_api import ingest, recognition
    user = client.post('/api/v1/auth/register', json={'email': 'ocr@example.com', 'password': 'secret'}).json()['data']
    headers = {'Authorization': 'Bearer ' + user['access_token']}
    monkeypatch.setenv('SCZX_MEDIA_ROOT', str(tmp_path / 'media'))
    original = b'\x89PNG\r\n\x1a\noriginal-file'
    normalized = b'normalized-jpeg-bytes'
    def asset(data, kind):
        return {'kind': kind, 'image_base64': base64.b64encode(data).decode(), 'sha256': hashlib.sha256(data).hexdigest()}
    monkeypatch.setattr(ingest, 'compute', lambda payload: asset(normalized, 'original'))
    record = {'question_text': '求解 x+1=2', 'student_answer': '3', 'subject': '数学', 'grade': '初二', 'question_type': '综合题', 'options': [], 'recognition_confidence': .9, 'student_steps': [{'index': 1, 'text': 'x + 1 = 2'}], 'teacher_annotations': [{'type': 'cross', 'text': '错'}]}
    def compute(payload):
        if payload['operation'] == 'preprocess': return {'assets': [asset(b'clean', 'clean')]}
        return {'recognition': record, 'assets': [], 'duration_ms': 10}
    monkeypatch.setattr(recognition, 'compute', compute)
    files = {'file': ('原图.png', original, 'image/png')}
    deferred = client.post('/api/v1/questions/ingest', headers=headers, files=files, data={'defer_processing': 'true'})
    assert deferred.status_code == 200, deferred.text
    result = deferred.json()['data']
    assert result['job_id'] is None and result['status'] == 'awaiting_crop'
    detail = client.get('/api/v1/questions/' + result['question_id'], headers=headers).json()['data']
    assets = {a['kind']: a for a in detail['assets']}
    assert (tmp_path / 'media' / assets['uploaded_original']['path']).read_bytes() == original
    assert (tmp_path / 'media' / assets['original']['path']).read_bytes() == normalized
    started = client.post('/api/v1/questions/ingest', headers=headers, files=files)
    assert started.status_code == 200, started.text
    result = started.json()['data']; job_path = '/api/v1/jobs/' + result['job_id']
    job = client.get(job_path, headers=headers).json()['data']
    assert job['status'] == 'completed' and job['progress'] == 100
    detail = client.get('/api/v1/questions/' + result['question_id'], headers=headers).json()['data']
    assert detail['question_text'] == record['question_text'] and detail['status'] == 'needs_confirmation'
    assert detail['student_steps'][0]['step_index'] == 0 and detail['student_steps'][0]['source'] == 'qwen_crop'
    assert detail['teacher_marks'][0]['comment'] == '错' and detail['ocr']['stream'] == 'qwen_crop'
    assert client.post(job_path + '/retry', headers=headers).status_code == 409
    monkeypatch.setattr(recognition, 'compute', lambda payload: (_ for _ in ()).throw(RuntimeError('offline')))
    failed = client.post('/api/v1/questions/ingest', headers=headers, files=files).json()['data']
    failed_job = '/api/v1/jobs/' + failed['job_id']
    assert client.get(failed_job, headers=headers).json()['data']['status'] == 'failed'
    monkeypatch.setattr(recognition, 'compute', compute)
    assert client.post(failed_job + '/retry', headers=headers).status_code == 200
    assert client.get(failed_job, headers=headers).json()['data']['status'] == 'completed'
    def stale_compute(payload):
        if payload['operation'] == 'recognize':
            with Database.from_environment() as db:
                db.query("UPDATE questions SET question_text='学生已修改' WHERE status='processing' AND user_id=?", [user['id']])
        return compute(payload)
    monkeypatch.setattr(recognition, 'compute', stale_compute)
    stale = client.post('/api/v1/questions/ingest', headers=headers, files=files).json()['data']
    stale_job = client.get('/api/v1/jobs/' + stale['job_id'], headers=headers).json()['data']
    assert stale_job['status'] == 'cancelled'
    assert client.get('/api/v1/questions/' + stale['question_id'], headers=headers).json()['data']['question_text'] == '学生已修改'
    assert not list((tmp_path / 'media' / 'uploads' / stale['question_id'] / 'derived').glob('*'))
    with Database.from_environment() as db:
        db.query("UPDATE processing_jobs SET status='running' WHERE id=?", [failed['job_id']])
        db.query("UPDATE questions SET status='processing' WHERE id=?", [failed['question_id']])
    recognition.recover_jobs()
    recovered = client.get(failed_job, headers=headers).json()['data']
    assert recovered['status'] == 'failed' and '服务重启' in recovered['error']
    assert client.post('/api/v1/questions/ingest', headers=headers, files=files, data={'defer_processing': 'invalid'}).status_code == 422
    assert client.post('/api/v1/questions/ingest', headers=headers, files={'file': ('empty.png', b'', 'image/png')}).status_code == 422


def test_crop_resume_confirm_and_ocr_endpoints(client, tmp_path, monkeypatch):
    import base64
    import hashlib
    from sczx_api import ingest, crop
    user = client.post('/api/v1/auth/register', json={'email': 'crop@example.com', 'password': 'secret'}).json()['data']
    headers = {'Authorization': 'Bearer ' + user['access_token']}
    monkeypatch.setenv('SCZX_MEDIA_ROOT', str(tmp_path / 'media'))
    data = b'image-content'
    def asset(kind): return {'kind': kind, 'image_base64': base64.b64encode(data).decode(), 'sha256': hashlib.sha256(data).hexdigest(), 'geometry': {'width': 100, 'height': 100}}
    monkeypatch.setattr(ingest, 'compute', lambda payload: asset('original'))
    monkeypatch.setattr(crop, 'compute', lambda payload: asset('crop'))
    monkeypatch.setattr(crop, 'run_recognition', lambda *args: None)
    result = client.post('/api/v1/questions/ingest', headers=headers, files={'file': ('q.png', data, 'image/png')}, data={'defer_processing': 'true'}).json()['data']
    path = '/api/v1/questions/' + result['question_id']
    assert client.post(path + '/ocr', headers=headers).status_code == 422
    assert client.post(path + '/confirm', headers=headers).status_code == 422
    for box in [[0, 0, 0, 1], [-.1, 0, 1, 1], [True, 0, 1, 1], [0, 0, 1.1, 1], [0, 0, 1]]:
        assert client.post(path + '/crop', headers=headers, json={'box': box}).status_code == 422
    box = [.1, .2, .6, .7]
    cropped = client.post(path + '/crop', headers=headers, json={'box': box})
    assert cropped.status_code == 200, cropped.text
    saved = cropped.json()['data']
    assert saved['original_preserved'] is True and saved['status'] == 'pending'
    detail = client.get(path, headers=headers).json()['data']
    assert detail['crop_box'] == pytest.approx(box)
    resumed = client.post(path + '/crop', headers=headers, json={'box': box}).json()['data']
    assert resumed['job_id'] == saved['job_id'] and resumed['resumed'] is True
    assert client.post(path + '/crop', headers=headers, json={'box': [0, 0, 1, 1]}).status_code == 409
    assert client.post(path + '/reprocess', headers=headers).json()['data']['resumed'] is True
    draft = client.post(path + '/draft', headers=headers, json={'question_text': '计算题', 'student_steps': [{'text': 'x = 1', 'bbox': [0, '0.1', 1, 1], 'confidence': '0.9'}], 'teacher_marks': ['已核对']})
    assert draft.status_code == 200, draft.text
    value = draft.json()['data']
    assert value['status'] == 'ocr_draft' and value['confirmed'] is False
    assert value['student_steps'][0]['text'] == 'x = 1' and value['teacher_marks'][0]['comment'] == '已核对'
    job = client.get('/api/v1/jobs/' + saved['job_id'], headers=headers).json()['data']
    assert job['status'] == 'cancelled' and '人工核对' in job['error']
    confirmed = client.post(path + '/confirm', headers=headers)
    assert confirmed.status_code == 200 and confirmed.json()['data']['confirmed'] is True
    assert confirmed.json()['data']['status'] == 'confirmed'
    choice = client.post(path + '/confirm', headers=headers, json={'question_type': 'multiple_choice', 'options': [{'label': 'A', 'text': '一'}, {'label': 'B', 'text': '二'}], 'student_answer': '', 'student_steps': ['a，b']})
    assert choice.status_code == 200, choice.text
    assert choice.json()['data']['student_answer'] == 'A、B' and choice.json()['data']['student_steps'] == []
    asynchronous = client.post(path + '/reprocess', headers=headers).json()['data']
    assert asynchronous['job_id']
    synchronous = client.post(path + '/ocr', headers=headers).json()['data']
    assert synchronous['resumed'] is True and synchronous['job']['id'] == asynchronous['job_id']
    assert synchronous['question']['id'] == result['question_id']


def test_signed_media_head_ranges_etag_and_symlink_rejection(client, tmp_path, monkeypatch):
    from sczx_api.security import media_url
    monkeypatch.setenv('SCZX_MEDIA_ROOT', str(tmp_path))
    (tmp_path / 'uploads').mkdir()
    (tmp_path / 'uploads' / 'image.png').write_bytes(b'0123456789')
    url = media_url('/uploads/image.png', os.environ['SCZX_AUTH_SECRET'])
    assert client.get('/uploads/image.png').status_code == 403
    response = client.get(url)
    assert response.status_code == 200 and response.content == b'0123456789'
    assert response.headers['content-type'] == 'image/png' and response.headers['accept-ranges'] == 'bytes'
    tag = response.headers['etag']
    head = client.head(url)
    assert head.status_code == 200 and head.content == b'' and head.headers['content-length'] == '10'
    assert client.get(url, headers={'If-None-Match': 'W/' + tag}).status_code == 304
    ranged = client.get(url, headers={'Range': 'bytes=2-4'})
    assert ranged.status_code == 206 and ranged.content == b'234'
    assert ranged.headers['content-range'] == 'bytes 2-4/10'
    assert client.get(url, headers={'Range': 'bytes=-3'}).content == b'789'
    assert client.get(url, headers={'Range': 'bytes=2-4', 'If-Range': 'changed'}).content == b'0123456789'
    assert client.get(url, headers={'Range': 'bytes=0-1,4-5'}).status_code == 200
    invalid = client.get(url, headers={'Range': 'bytes=99-'})
    assert invalid.status_code == 416 and invalid.headers['content-range'] == 'bytes */10'
    assert client.post(url).status_code == 405 and client.post(url).headers['allow'] == 'GET, HEAD'
    outside = tmp_path / 'outside.txt'; outside.write_text('private')
    (tmp_path / 'uploads' / 'link.png').symlink_to(outside)
    link = media_url('/uploads/link.png', os.environ['SCZX_AUTH_SECRET'])
    assert client.get(link).status_code == 404


def test_analysis_diagnosis_evidence_and_work_invalidation(client, monkeypatch):
    import json
    from sczx_api import analysis, diagnosis
    from sczx_api.security import new_id
    user = client.post('/api/v1/auth/register', json={'email': 'analysis@example.com', 'password': 'secret'}).json()['data']
    headers = {'Authorization': 'Bearer ' + user['access_token']}
    question = client.post('/api/v1/questions/manual', headers=headers, json={'question_text': '一元一次方程x+1=2', 'student_answer': '3', 'student_steps': ['x=3']}).json()['data']
    question_id = question['id']; path = '/api/v1/questions/' + question_id
    card_id = new_id()
    with Database.from_environment() as db:
        db.query("INSERT INTO knowledge_points (id,code,subject,name,content,created_at,updated_at) VALUES (?,?,'数学','一元一次方程',?,UTC_TIMESTAMP(),UTC_TIMESTAMP())", [card_id, 'sczx.equation', json.dumps({'grade': '初一', 'related_knowledge': ['方程']})])
    record = {'subject': '数学', 'problem_type': '方程', 'known_conditions': ['x+1=2'], 'goal': '求x', 'knowledge_points': ['一元一次方程'], 'prerequisites': [], 'final_answer': '1', 'answer_verified': True, 'reference_steps': ['x+1=2', 'x=1']}
    monkeypatch.setattr(analysis, 'compute', lambda payload: {'analysis': record, 'reference_math_valid': [True, True]})
    result = client.post(path + '/analyze', headers=headers)
    assert result.status_code == 200, result.text
    assert result.json()['data']['verified'] is True and result.json()['data']['reference_steps'] == record['reference_steps']
    detail = client.get(path, headers=headers).json()['data']
    assert detail['status'] == 'analyzed' and len(detail['reference_steps']) == 2
    with Database.from_environment() as db:
        links = db.query('SELECT role,mapping_method FROM user_question_knowledge_links WHERE question_id=?', [question_id]).rows
        assert links == [{'role': 'primary', 'mapping_method': 'exact_label'}]
    def compute(payload):
        assert payload['diagnostic_cards'][0]['id'] == card_id
        entry = {'index': 0, 'reference_step_id': payload['reference_steps'][0]['id'], 'student_step_id': payload['student_records'][0]['id'], 'reference_text': 'x+1=2', 'student_text': 'x=3', 'alignment': 'calculation_error', 'equivalent': False, 'uses_condition': True, 'is_first_error': True, 'propagated': False, 'math_valid': False}
        return {'diagnosis': {'first_error_step': 0, 'first_error_text': 'x=3', 'error_type': 'calculation_error', 'root_misconception': '移项计算错误', 'propagated_errors': [], 'strategy_candidates': [], 'confidence': .9, 'error_location': '第一步', 'missing_prerequisites': ['方程'], 'recommended_strategy': '移项'}, 'alignment': [entry], 'counterfactual': {'status': 'partial', 'suspected_step': 0, 'root_cause_confirmed': False, 'recovered_steps': 0, 'conclusion': '需核对'}, 'evidence_diagnosis': {'algorithm': 'test', 'verified': False, 'reason': '测试证据'}}
    monkeypatch.setattr(diagnosis, 'compute', compute)
    diagnosed = client.post(path + '/diagnose', headers=headers)
    assert diagnosed.status_code == 200, diagnosed.text
    value = diagnosed.json()['data']
    assert value['error_type'] == 'calculation_error' and len(value['evidence']) == 1
    stored = client.get(path + '/diagnosis', headers=headers).json()['data']
    assert stored['id'] == value['id'] and len(stored['evidence']) == 1
    assert stored['evidence_diagnosis']['algorithm'] == 'test'
    assert stored['counterfactual']['conclusion'] == '需核对'
    cached = client.post(path + '/diagnosis/counterfactual', headers=headers)
    assert cached.status_code == 200 and cached.json()['data']['conclusion'] == '需核对'
    assert client.patch(path + '/diagnosis', headers=headers, json={'first_error_step': 99}).status_code == 422
    assert client.patch(path + '/diagnosis', headers=headers, json={'error_type': 'made_up'}).status_code == 422
    corrected = client.patch(path + '/diagnosis', headers=headers, json={'first_error_step': 0, 'root_misconception': '学生修正原因', 'confidence': '0.8'})
    assert corrected.status_code == 200, corrected.text
    assert corrected.json()['data']['user_confirmed'] is True
    assert corrected.json()['data']['first_error_text'] == 'x=3'
    assert client.patch(path + '/diagnosis', headers=headers, json={'error_type': 'exact', 'first_error_step': 0}).status_code == 422
    cleared = client.patch(path + '/diagnosis', headers=headers, json={'error_type': 'equivalent'})
    assert cleared.status_code == 200 and cleared.json()['data']['first_error_step'] is None
    stale_counter = client.post(path + '/diagnosis/counterfactual', headers=headers).json()['data']
    assert stale_counter['stale_after_correction'] is True
    assert stale_counter['verification_method'] == 'previous_diagnosis_evidence'
    with Database.from_environment() as db:
        assert db.query('SELECT COUNT(*) AS n FROM diagnosis_evidence WHERE diagnosis_id=?', [value['id']]).rows[0]['n'] == '3'
    def invalid_evidence(payload):
        result = compute(payload); result['alignment'][0]['student_step_id'] = new_id(); return result
    monkeypatch.setattr(diagnosis, 'compute', invalid_evidence)
    rejected = client.post(path + '/diagnose', headers=headers)
    assert rejected.status_code == 503 and rejected.json()['detail'] == '诊断证据不属于当前作答'
    assert client.get(path + '/diagnosis', headers=headers).json()['data']['id'] == value['id']
    def stale_analysis(payload):
        with Database.from_environment() as db:
            db.query("UPDATE questions SET student_answer='改了答案' WHERE id=?", [question_id])
        return {'analysis': record, 'reference_math_valid': [True, True]}
    monkeypatch.setattr(analysis, 'compute', stale_analysis)
    assert client.post(path + '/analyze', headers=headers).status_code == 409
    work = client.post(path + '/student-work', headers=headers, json={'answer': '1', 'explanation': '重新作答', 'steps': ['x = 1']})
    assert work.status_code == 200 and work.json()['data']['explanation'] == '重新作答'
    detail = client.get(path, headers=headers).json()['data']
    assert detail['analysis'] is None and detail['diagnosis'] is None and detail['status'] == 'confirmed'
    assert detail['student_answer'] == '1' and detail['student_steps'][0]['text'] == 'x = 1'


def test_tutor_start_full_and_compressed_state_persistence(client, monkeypatch):
    import json
    from sczx_api import analysis, tutor_start
    user=client.post('/api/v1/auth/register',json={'email':'tutor-start@example.com','password':'secret'}).json()['data']
    headers={'Authorization':'Bearer '+user['access_token']}
    question=client.post('/api/v1/questions/manual',headers=headers,json={'question_text':'解方程x+1=2','student_steps':['x=3']}).json()['data']
    question_id=question['id']; path='/api/v1/questions/'+question_id
    assert client.post('/api/v1/tutor/sessions',headers=headers,json={'question_id':question_id}).status_code==409
    record={'subject':'数学','problem_type':'方程','known_conditions':['x+1=2'],'goal':'求x','knowledge_points':['方程'],'prerequisites':[],'final_answer':'1','answer_verified':True,'reference_steps':['x=1']}
    monkeypatch.setattr(analysis,'compute',lambda payload:{'analysis':record,'reference_math_valid':[True]})
    assert client.post(path+'/analyze',headers=headers).status_code==200
    response=client.post('/api/v1/tutor/sessions',headers=headers,json={'question_id':question_id})
    assert response.status_code==200,response.text
    full=response.json()['data']
    assert full['stage']=='understanding' and full['teaching_policy']['mode']=='full'
    assert full['activity']['id']=='understanding-1' and full['activity']['options']
    assert 'correct_answers' not in full['activity'] and 'understanding_plan' not in full['state']
    assert full['turns'][0]['role']=='assistant' and full['question']['id']==question_id
    with Database.from_environment() as db:
        saved=json.loads(db.query('SELECT state FROM tutor_sessions WHERE id=?',[full['id']]).rows[0]['state'])
        assert saved['understanding_plan'][0]['correct_answers']==['key']
        assert db.query('SELECT COUNT(*) AS n FROM agent_runs WHERE session_id=?',[full['id']]).rows[0]['n']=='1'
    with Database.from_environment() as db:
        db.query("UPDATE questions SET question_type='单选题',options=? WHERE id=?",[json.dumps([{'label':'A','text':'1'},{'label':'B','text':'3'}]),question_id])
    brief={'topic':'方程','correct_answer':'A','key_explanation':'移项','option_explanations':[],'check':{'id':'check','type':'single_choice','title':'核对','question':'选哪项','options':[],'correct_answers':['A']}}
    monkeypatch.setattr(tutor_start,'compute',lambda payload:{'brief':brief})
    response=client.post('/api/v1/tutor/sessions',headers=headers,json={'question_id':question_id})
    assert response.status_code==200,response.text
    compressed=response.json()['data']
    assert compressed['teaching_policy']['mode']=='compressed' and compressed['activity']['id']=='answer-reveal'
    assert compressed['answer_reveal']['correct_answer']=='A'
    assert 'teaching_brief' not in compressed['state']
    def stale_brief(payload):
        with Database.from_environment() as db: db.query("UPDATE questions SET student_answer='changed' WHERE id=?",[question_id])
        return {'brief':brief}
    monkeypatch.setattr(tutor_start,'compute',stale_brief)
    assert client.post('/api/v1/tutor/sessions',headers=headers,json={'question_id':question_id}).status_code==409


def test_tutor_resume_legacy_stages_and_variant_validation(client,monkeypatch):
    import json
    from sczx_api import analysis,tutor_variants
    user=client.post('/api/v1/auth/register',json={'email':'tutor-resume@example.com','password':'secret'}).json()['data']
    other=client.post('/api/v1/auth/register',json={'email':'tutor-resume-other@example.com','password':'secret'}).json()['data']
    headers={'Authorization':'Bearer '+user['access_token']};outsider={'Authorization':'Bearer '+other['access_token']}
    question=client.post('/api/v1/questions/manual',headers=headers,json={'question_text':'解方程x+1=2','student_steps':['x=3']}).json()['data']
    question_id=question['id']
    record={'subject':'数学','problem_type':'方程','known_conditions':['x+1=2'],'goal':'求x','knowledge_points':['方程'],'prerequisites':[],'final_answer':'1','answer_verified':True,'reference_steps':['x=1']}
    monkeypatch.setattr(analysis,'compute',lambda payload:{'analysis':record,'reference_math_valid':[True]})
    client.post('/api/v1/questions/'+question_id+'/analyze',headers=headers)
    session=client.post('/api/v1/tutor/sessions',headers=headers,json={'question_id':question_id}).json()['data']
    path='/api/v1/tutor/sessions/'+session['id']
    assert client.get(path,headers=outsider).status_code==404
    resumed=client.get(path,headers=headers)
    assert resumed.status_code==200 and resumed.json()['data']['activity']==session['activity']
    assert client.post(path+'/advance',headers=headers,json={'target_stage':'teach_back'}).status_code==409
    assert client.post(path+'/advance',headers=headers,json={'target_stage':'near_transfer'}).status_code==422
    with Database.from_environment() as db:
        db.query("UPDATE tutor_sessions SET state=JSON_SET(state,'$.understanding_passed',CAST('true' AS JSON)) WHERE id=?",[session['id']])
    advanced=client.post(path+'/advance',headers=headers,json={'target_stage':'teach_back'})
    assert advanced.status_code==200 and advanced.json()['data']['stage']=='teach_back'
    rewound=client.post(path+'/rewind',headers=headers)
    assert rewound.status_code==200 and rewound.json()['data']['stage']=='understanding'
    assert rewound.json()['data']['stage_status']=='passed'
    assert client.post(path+'/rewind',headers=headers).status_code==409
    assert client.post(path+'/variant',headers=headers).status_code==409
    with Database.from_environment() as db:
        state=json.loads(db.query('SELECT state FROM tutor_sessions WHERE id=?',[session['id']]).rows[0]['state'])
        state.pop('understanding_plan');state.pop('assisted');state.pop('understanding_passed')
        db.query("UPDATE tutor_sessions SET stage='teach_back_retry',state=? WHERE id=?",[json.dumps(state),session['id']])
    legacy=client.get(path,headers=headers).json()['data']
    assert legacy['stage']=='teach_back' and legacy['activity']['type']=='teach_back'
    assert legacy['state']['assisted'] is False and 'understanding_plan' not in legacy['state']
    with Database.from_environment() as db:
        db.query("UPDATE tutor_sessions SET stage='near_remediation' WHERE id=?",[session['id']])
    calls=[]
    def computed(payload):
        calls.append(payload['operation'])
        if payload['operation']=='validate_variant':return {'valid':True}
        return {'variant':{'question_text':'解方程x+2=4','answer':'2','explanation':'移项','reference_solution':['x=2'],'options':[]},'generation':{'method':'controlled'},'verified':True}
    monkeypatch.setattr(tutor_variants,'compute',computed)
    monkeypatch.setattr(tutor_variants,'variant_retrieval',lambda *args:{'references':[],'status':'unavailable'})
    transferred=client.get(path,headers=headers)
    assert transferred.status_code==200,transferred.text
    data=transferred.json()['data']
    assert data['stage']=='near_transfer' and data['activity']['question']=='解方程x+2=4'
    variant_id=data['activity']['variant_id']
    assert 'answer' not in data['activity'] and 'correct_answers' not in data['activity']
    assert 'near_variant_id' not in data['state']
    direct=client.post(path+'/variant',headers=headers,json={'transfer_type':'near'})
    assert direct.status_code==200 and direct.json()['data']['id']==variant_id
    assert 'answer' not in direct.json()['data'] and calls==['generate_variant','validate_variant']
    def invalid_then_generate(payload):
        if payload['operation']=='validate_variant':return {'valid':False}
        return computed(payload)
    monkeypatch.setattr(tutor_variants,'compute',invalid_then_generate)
    replacement=client.post(path+'/variant',headers=headers,json={'transfer_type':'near'})
    assert replacement.status_code==200 and replacement.json()['data']['id']!=variant_id
    with Database.from_environment() as db:
        stored=json.loads(db.query('SELECT state FROM tutor_sessions WHERE id=?',[session['id']]).rows[0]['state'])
        assert variant_id in stored['invalidated_variant_ids']
        db.query("UPDATE questions SET status='archived' WHERE id=?",[question_id])
        stored['near_variant_id']=None
        db.query('UPDATE tutor_sessions SET state=? WHERE id=?',[json.dumps(stored),session['id']])
    assert client.post(path+'/variant',headers=headers).status_code==409


def test_teach_back_retry_assistance_pass_and_transaction_rollback(client,monkeypatch):
    import json
    from sczx_api import analysis,tutor_teach_back,tutor_variants
    user=client.post('/api/v1/auth/register',json={'email':'teach-back@example.com','password':'secret'}).json()['data']
    headers={'Authorization':'Bearer '+user['access_token']}
    question_id=client.post('/api/v1/questions/manual',headers=headers,json={'question_text':'解方程x+1=2','student_steps':['x=3']}).json()['data']['id']
    record={'subject':'数学','problem_type':'方程','known_conditions':['x+1=2'],'goal':'求x','knowledge_points':['方程'],'prerequisites':[],'final_answer':'1','answer_verified':True,'reference_steps':['x=1']}
    monkeypatch.setattr(analysis,'compute',lambda payload:{'analysis':record,'reference_math_valid':[True]})
    client.post('/api/v1/questions/'+question_id+'/analyze',headers=headers)
    def start():
        session=client.post('/api/v1/tutor/sessions',headers=headers,json={'question_id':question_id}).json()['data']
        return session,'/api/v1/tutor/sessions/'+session['id']
    session,path=start()
    assert client.post(path+'/teach-back',headers=headers,json={'explanation':'移项'}).status_code==409
    with Database.from_environment() as db:
        db.query("UPDATE tutor_sessions SET stage='teach_back' WHERE id=?",[session['id']])
    assessment={'passed':False,'feedback':'请补充依据','matched_concepts':[]}
    monkeypatch.setattr(tutor_teach_back,'compute',lambda payload:assessment)
    first=client.post(path+'/teach-back',headers=headers,json={'explanation':'先算答案'})
    assert first.status_code==200,first.text
    assert first.json()['data']=={'passed':False,'assisted':False,'branch':'teach_back_fail','stage':'teach_back','feedback':'请补充依据','next_goal':'补充一个关键理由'}
    def unavailable(payload):raise RuntimeError('controlled unavailable')
    monkeypatch.setattr(tutor_variants,'compute',unavailable)
    monkeypatch.setattr(tutor_variants,'variant_retrieval',lambda *args:{'references':[],'status':'unavailable'})
    # The API sanitizes a failed computation; its transaction must preserve retry count and turns.
    with Database.from_environment() as db:
        before=db.query('SELECT COUNT(*) AS n FROM tutor_turns WHERE session_id=?',[session['id']]).rows[0]['n']
    with pytest.raises(RuntimeError,match='controlled unavailable'):
        client.post(path+'/teach-back',headers=headers,json={'explanation':'还是不明白'})
    with Database.from_environment() as db:
        state=json.loads(db.query('SELECT state FROM tutor_sessions WHERE id=?',[session['id']]).rows[0]['state'])
        assert state['teach_back_attempts']==1
        assert db.query('SELECT COUNT(*) AS n FROM tutor_turns WHERE session_id=?',[session['id']]).rows[0]['n']==before
    def generate(payload):
        return {'variant':{'question_text':'解方程x+2=4','answer':'2','explanation':'移项','reference_solution':['x=2'],'options':[]},'generation':{},'verified':True}
    monkeypatch.setattr(tutor_variants,'compute',generate)
    second=client.post(path+'/teach-back',headers=headers,json={'explanation':'还是不明白'})
    assert second.status_code==200,second.text
    assert second.json()['data']['stage']=='near_transfer' and second.json()['data']['assisted'] is True
    with Database.from_environment() as db:
        state=json.loads(db.query('SELECT state FROM tutor_sessions WHERE id=?',[session['id']]).rows[0]['state'])
        assert state['teach_back'] is False and state['assisted'] is True and state['teach_back_attempts']==2
        assert state['near_variant_id']
    passed_session,passed_path=start()
    with Database.from_environment() as db:
        db.query("UPDATE tutor_sessions SET stage='teach_back' WHERE id=?",[passed_session['id']])
    assessment.update(passed=True,feedback='讲清楚了',matched_concepts=['方程'])
    passed=client.post(passed_path+'/teach-back',headers=headers,json={'explanation':'两边同时减1，等式仍成立'})
    assert passed.status_code==200 and passed.json()['data']['passed'] is True
    assert passed.json()['data']['assisted'] is False and passed.json()['data']['stage']=='near_transfer'
    assert client.post(passed_path+'/teach-back',headers=headers,json={'explanation':12}).status_code==422


def test_tutor_finish_evidence_review_and_idempotency(client,monkeypatch):
    import json
    from sczx_api import analysis,learning_evidence
    user=client.post('/api/v1/auth/register',json={'email':'finish@example.com','password':'secret'}).json()['data']
    headers={'Authorization':'Bearer '+user['access_token']}
    question_id=client.post('/api/v1/questions/manual',headers=headers,json={'question_text':'解方程x+1=2','student_steps':['x=1']}).json()['data']['id']
    record={'subject':'数学','problem_type':'方程','known_conditions':['x+1=2'],'goal':'求x','knowledge_points':['方程'],'prerequisites':[],'final_answer':'1','answer_verified':True,'reference_steps':['x=1']}
    monkeypatch.setattr(analysis,'compute',lambda payload:{'analysis':record,'reference_math_valid':[True]})
    client.post('/api/v1/questions/'+question_id+'/analyze',headers=headers)
    session=client.post('/api/v1/tutor/sessions',headers=headers,json={'question_id':question_id}).json()['data']
    path='/api/v1/tutor/sessions/'+session['id']
    assert client.post(path+'/finish',headers=headers).status_code==409
    def cognition(payload,timeout=200):
        assert payload['operation']=='cognition_update' and payload['learning_evidence']['far_transfer'] is True
        return {'mastery':{**payload['mastery_values'],'mastery_score':.8,'confidence':.7,'evidence_count':1,'near_transfer_rate':1.,'far_transfer_rate':1.,'forgetting_risk':.2,'update_reason':'独立练习通过'},'misconception':{**payload['misconception_values'],'probability':.2,'evidence_count':2,'related_question_count':1,'status':'improving'}}
    monkeypatch.setattr(learning_evidence,'compute',cognition)
    with Database.from_environment() as db:
        db.query("UPDATE tutor_sessions SET stage='finished',state=JSON_SET(state,'$.teach_back',CAST('true' AS JSON),'$.near_transfer',CAST('true' AS JSON),'$.far_transfer',CAST('true' AS JSON)) WHERE id=?",[session['id']])
    completed=client.post(path+'/finish',headers=headers)
    assert completed.status_code==200,completed.text
    result=completed.json()['data']
    assert result['session']['status']=='completed' and result['session']['state']['mastery_proven'] is True
    assert result['mastery']['knowledge_point']=='方程'
    assert result['review']['interval_days']==15
    repeat=client.post(path+'/finish',headers=headers)
    assert repeat.status_code==200 and repeat.json()['data']['mastery'] is None
    assert repeat.json()['data']['review']['id']==result['review']['id']
    with Database.from_environment() as db:
        updates=db.query('SELECT evidence FROM cognitive_updates WHERE question_id=?',[question_id]).rows
        assert len(updates)==2
        evidence=json.loads(updates[0]['evidence'])
        assert evidence['memory_source']['rule_version']=='learning-memory-v1'
        assert len(evidence['memory_source']['question_version'])==64
        assert evidence['tutor_session_id']==session['id']
        assert db.query('SELECT COUNT(*) AS n FROM review_plans WHERE question_id=?',[question_id]).rows[0]['n']=='1'
