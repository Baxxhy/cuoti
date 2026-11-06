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
        raw=db.query("SELECT CAST(0.4 AS FLOAT) AS score,CAST('2026-01-01 00:00:00.000000' AS DATETIME(6)) AS observed").rows[0]
        assert raw=={'score':'0.4','observed':'2026-01-01 00:00:00.000000'}
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
        from sczx_api.memory_sources import update_valid
        from sczx_api.rows import row_json
        update=row_json('cognitive_updates',db.query("SELECT * FROM cognitive_updates WHERE question_id=? AND entity_type='mastery'",[question_id]).rows[0])
        assert update_valid(db,update,user['id'],'数学') is True
        assert update_valid(db,update,'another-user','数学') is False
        db.query("UPDATE questions SET title='仅改标题' WHERE id=?",[question_id])
        assert update_valid(db,update,user['id'],'数学') is True
        db.query("UPDATE questions SET student_answer='已改变答案' WHERE id=?",[question_id])
        assert update_valid(db,update,user['id'],'数学') is False


def test_tutor_activity_full_and_compressed_learning_flows(client,monkeypatch):
    import json
    from sczx_api import analysis,tutor_start,tutor_answer,tutor_transfer,tutor_variants,tutor_teach_back,learning_evidence
    user=client.post('/api/v1/auth/register',json={'email':'activity@example.com','password':'secret'}).json()['data']
    headers={'Authorization':'Bearer '+user['access_token']}
    record={'subject':'数学','problem_type':'方程','known_conditions':['x+1=2'],'goal':'求x','knowledge_points':['方程'],'prerequisites':[],'final_answer':'1','answer_verified':True,'reference_steps':['x=1']}
    monkeypatch.setattr(analysis,'compute',lambda p:{'analysis':record,'reference_math_valid':[True]})
    monkeypatch.setattr(tutor_answer,'compute',lambda p:{'correct':True,'can_update_learning':True,'feedback':'对'})
    monkeypatch.setattr(tutor_teach_back,'compute',lambda p:{'passed':True,'matched_concepts':['方程'],'feedback':'依据清楚'})
    monkeypatch.setattr(tutor_variants,'variant_retrieval',lambda *args:{'references':[],'status':'unavailable'})
    def variant(p):
        if p['operation']=='validate_variant':return {'valid':True}
        return {'variant':{'question_text':'解方程x+2=4','answer':'2','explanation':'两边减2','reference_solution':['x=4-2','x=2'],'options':[]},'generation':{},'verified':True}
    monkeypatch.setattr(tutor_variants,'compute',variant)
    def grade(p):return {'correct':p['answer']=='2','can_update_learning':p['answer']!='unreliable','feedback':'核对计算'}
    monkeypatch.setattr(tutor_transfer,'compute',grade)
    def cognition(p,timeout=200):
        return {'mastery':{**p['mastery_values'],'mastery_score':.6,'confidence':.7,'evidence_count':1,'update_reason':'受控验收'},'misconception':{**p['misconception_values'],'probability':.3,'evidence_count':2}}
    monkeypatch.setattr(learning_evidence,'compute',cognition)
    brief={'topic':'方程','correct_answer':'A','key_explanation':'移项','option_explanations':[],'check':{'id':'target-check','type':'single_choice','title':'核对','question':'哪个条件','options':[],'correct_answers':['A'],'hint':'看条件'}}
    monkeypatch.setattr(tutor_start,'compute',lambda p:{'brief':brief})
    for compressed,fail_far in [(False,True),(False,False),(True,False)]:
        body={'question_text':'解方程x+1=2','student_steps':['x=3']}
        if compressed:body.update(question_type='单选题',options=[{'label':'A','text':'1'},{'label':'B','text':'3'}])
        question_id=client.post('/api/v1/questions/manual',headers=headers,json=body).json()['data']['id']
        assert client.post('/api/v1/questions/'+question_id+'/analyze',headers=headers).status_code==200
        started=client.post('/api/v1/tutor/sessions',headers=headers,json={'question_id':question_id})
        assert started.status_code==200,started.text
        value=started.json()['data'];path='/api/v1/tutor/sessions/'+value['id']
        def answer(value,text,**extra):
            result=client.post(path+'/activity/answer',headers=headers,json={'activity_id':value['activity']['id'],'answer':text,**extra})
            assert result.status_code==200,result.text
            return result.json()['data']
        assert client.post(path+'/activity/answer',headers=headers,json={'activity_id':'stale','answer':'x'}).status_code==409
        assert client.post(path+'/activity/answer',headers=headers,json={'activity_id':value['activity']['id'],'answer':'x','elapsed_seconds':-1}).status_code==422
        assert client.post(path+'/activity/answer',headers=headers,json={'activity_id':value['activity']['id'],'answer':'x','handwriting_recognition':{}}).status_code==422
        if compressed:
            value=answer(value,'continue')
            assert value['stage']=='near_transfer'
        else:
            value=answer(value,'key');value=answer(value,'reference')
            assert value['stage_status']=='passed' and value['activity'] is None
            assert client.post(path+'/advance',headers=headers,json={'target_stage':'teach_back'}).status_code==200
            value=client.get(path,headers=headers).json()['data']
            value=answer(value,'两边同时减1，等式仍成立')
            assert value['stage']=='near_transfer'
        # Help is recorded but does not spend an attempt; ungradable input also leaves attempts unchanged.
        if fail_far:
            value=answer(value,'不会写')
            assert value['assisted'] is True and '可以按这个顺序写' in value['turns'][-1]['content']
            assert value['turns'][-2]['metadata_json']['attempt_consumed'] is False
            value=answer(value,'unreliable')
            with Database.from_environment() as db:
                state=json.loads(db.query('SELECT state FROM tutor_sessions WHERE id=?',[value['id']]).rows[0]['state'])
                assert state['near_attempts']==0
                assert db.query('SELECT COUNT(*) AS n FROM variant_attempts a JOIN variant_questions v ON a.variant_id=v.id WHERE v.session_id=?',[value['id']]).rows[0]['n']=='0'
        value=answer(value,'2')
        if not compressed:
            assert value['stage']=='far_transfer'
            value=answer(value,'wrong' if fail_far else '2')
            if fail_far:value=answer(value,'wrong')
        assert value['stage']=='finished' and value['status']=='completed' and value['activity'] is None
        assert value['state']['mastery_proven'] is (not compressed and not fail_far)
        finished=client.post(path+'/finish',headers=headers).json()['data']
        assert finished['review']['interval_days']==(1 if fail_far else 15)
        with Database.from_environment() as db:
            assert db.query('SELECT COUNT(*) AS n FROM review_plans WHERE question_id=?',[question_id]).rows[0]['n']=='1'
            assert len(db.query('SELECT id FROM cognitive_updates WHERE question_id=?',[question_id]).rows)==2
        assert client.post(path+'/activity/answer',headers=headers,json={'activity_id':'done','answer':'2'}).status_code==409


def test_handwriting_upload_context_ownership_and_retained_failure(client,tmp_path,monkeypatch):
    import base64,hashlib,json
    from sczx_api import analysis,handwriting,tutor_variants
    from sczx_api.practice_context import source_version
    from sczx_api.rows import row_json
    from sczx_api.security import new_id
    user=client.post('/api/v1/auth/register',json={'email':'handwriting@example.com','password':'secret'}).json()['data']
    other=client.post('/api/v1/auth/register',json={'email':'handwriting-other@example.com','password':'secret'}).json()['data']
    headers={'Authorization':'Bearer '+user['access_token']};outsider={'Authorization':'Bearer '+other['access_token']}
    question_id=client.post('/api/v1/questions/manual',headers=headers,json={'question_text':'x+1=2','student_steps':['x=3']}).json()['data']['id']
    record={'subject':'数学','problem_type':'方程','known_conditions':['x+1=2'],'goal':'求x','knowledge_points':['方程'],'prerequisites':[],'final_answer':'1','answer_verified':True,'reference_steps':['x=1']}
    monkeypatch.setattr(analysis,'compute',lambda p:{'analysis':record,'reference_math_valid':[True]})
    client.post('/api/v1/questions/'+question_id+'/analyze',headers=headers)
    session=client.post('/api/v1/tutor/sessions',headers=headers,json={'question_id':question_id}).json()['data']
    monkeypatch.setenv('SCZX_MEDIA_ROOT',str(tmp_path/'media'))
    image=b'normalized-handwriting'
    def computed(payload):
        if payload['operation']=='normalize':return {'image_base64':base64.b64encode(image).decode(),'sha256':hashlib.sha256(image).hexdigest()}
        if payload['operation']=='validate_handwriting':return {'validated':True}
        return {'recognition':{'answer':'1','steps':['x=1']}}
    monkeypatch.setattr(handwriting,'compute',computed)
    monkeypatch.setattr(tutor_variants,'compute',lambda p:{'valid':True})
    url='/api/v1/answers/handwriting';files={'file':('work.png',b'uploaded','image/png')}
    fields={'context_type':'tutor','context_id':session['id'],'activity_id':session['activity']['id']}
    assert client.post(url,headers=headers,files=files,data=fields).status_code==422
    assert client.post(url,headers=outsider,files=files,data=fields).status_code==404
    variant_id,plan_id=new_id(),new_id()
    with Database.from_environment() as db:
        db.query("INSERT INTO variant_questions (id,question_id,session_id,transfer_type,question_text,answer,explanation,reference_solution,verified,generation_metadata,created_at,updated_at) VALUES (?,?,?,'near','x+2=4','2','移项',JSON_ARRAY('x=2'),1,JSON_OBJECT(),UTC_TIMESTAMP(),UTC_TIMESTAMP())",[variant_id,question_id,session['id']])
        db.query("UPDATE tutor_sessions SET stage='near_transfer',state=JSON_SET(state,'$.near_variant_id',?,'$.near_variant_options',JSON_ARRAY()) WHERE id=?",[variant_id,session['id']])
        db.query("INSERT INTO review_plans (id,user_id,question_id,due_at,interval_days,reason,status,created_at,updated_at) VALUES (?,?,?,UTC_TIMESTAMP(),1,'复习','pending',UTC_TIMESTAMP(),UTC_TIMESTAMP())",[plan_id,user['id'],question_id])
    fields['activity_id']='near-variant-'+variant_id
    uploaded=client.post(url,headers=headers,files=files,data=fields)
    assert uploaded.status_code==200,uploaded.text
    result=uploaded.json()['data']
    assert result['recognition']['answer']=='1'
    assert client.get(result['image_url']).content==image
    verified=handwriting.validate_handwriting({'handwriting_image_url':result['image_url'],'handwriting_recognition':result['recognition']},user['id'],session['id'])
    assert verified['recognition']['validated'] is True
    with pytest.raises(Exception):handwriting.validate_handwriting({'handwriting_image_url':result['image_url']},other['id'],session['id'])
    review={'context_type':'review','context_id':plan_id}
    assert client.post(url,headers=headers,files=files,data=review).status_code==200
    with Database.from_environment() as db:
        question=row_json('questions',db.query('SELECT * FROM questions WHERE id=?',[question_id]).rows[0])
        metadata={'mode':'reinforce','source_version':source_version(db,question),'options':[]}
        db.query("UPDATE tutor_sessions SET stage='standalone_practice' WHERE id=?",[session['id']])
        db.query('UPDATE variant_questions SET generation_metadata=? WHERE id=?',[json.dumps(metadata),variant_id])
    practice={'context_type':'practice','context_id':variant_id,'mistake_id':question_id,'mode':'reinforce'}
    assert client.post(url,headers=headers,files=files,data=practice).status_code==200
    def failure(payload):
        if payload['operation']=='normalize':return computed(payload)
        raise RuntimeError('controlled recognition failure')
    monkeypatch.setattr(handwriting,'compute',failure)
    before=set((tmp_path/'media').rglob('*.jpg'))
    failed=client.post(url,headers=headers,files=files,data=review)
    assert failed.status_code==503 and '照片已保留' in failed.json()['detail']
    assert len(set((tmp_path/'media').rglob('*.jpg'))-before)==1


def test_direct_variant_attempt_uncertain_retry_and_completion(client,monkeypatch):
    import json
    from sczx_api import analysis,variant_attempt,tutor_variants,learning_evidence
    from sczx_api.security import new_id
    user=client.post('/api/v1/auth/register',json={'email':'variant-attempt@example.com','password':'secret'}).json()['data']
    headers={'Authorization':'Bearer '+user['access_token']}
    question_id=client.post('/api/v1/questions/manual',headers=headers,json={'question_text':'x+1=2','student_steps':['x=3']}).json()['data']['id']
    record={'subject':'数学','problem_type':'方程','known_conditions':[],'goal':'求x','knowledge_points':['方程'],'prerequisites':[],'final_answer':'1','answer_verified':True,'reference_steps':['x=1']}
    monkeypatch.setattr(analysis,'compute',lambda p:{'analysis':record,'reference_math_valid':[True]})
    client.post('/api/v1/questions/'+question_id+'/analyze',headers=headers)
    session=client.post('/api/v1/tutor/sessions',headers=headers,json={'question_id':question_id}).json()['data'];variant_id=new_id()
    with Database.from_environment() as db:
        db.query("INSERT INTO variant_questions (id,question_id,session_id,transfer_type,question_text,answer,explanation,reference_solution,verified,generation_metadata,created_at,updated_at) VALUES (?,?,?,'near','x+2=4','2','移项',JSON_ARRAY('x=2'),1,JSON_OBJECT(),UTC_TIMESTAMP(),UTC_TIMESTAMP())",[variant_id,question_id,session['id']])
        db.query("UPDATE tutor_sessions SET stage='near_transfer',state=JSON_SET(state,'$.near_variant_id',?) WHERE id=?",[variant_id,session['id']])
    grading={'correct':False,'can_update_learning':False,'verdict':'review_required','feedback':'需要核对'}
    monkeypatch.setattr(variant_attempt,'compute',lambda p:grading)
    path='/api/v1/variants/'+variant_id+'/attempt'
    uncertain=client.post(path,headers=headers,json={'answer':'可能是2'})
    assert uncertain.status_code==200 and uncertain.json()['data']['attempt'] is None
    assert uncertain.json()['data']['correct'] is None and uncertain.json()['data']['mastery'] is None
    grading.update(can_update_learning=True,verdict='confirmed_incorrect')
    for _ in range(2):assert client.post(path,headers=headers,json={'answer':'3'}).status_code==200
    with Database.from_environment() as db:
        state=json.loads(db.query('SELECT state FROM tutor_sessions WHERE id=?',[session['id']]).rows[0]['state'])
        assert state['near_confirmation'] and state['near_attempts']==2 and state['assisted'] is True
    monkeypatch.setattr(tutor_variants,'variant_retrieval',lambda *args:{'references':[],'status':'unavailable'})
    monkeypatch.setattr(tutor_variants,'compute',lambda p:{'variant':{'question_text':'x+3=5','answer':'2','explanation':'移项','reference_solution':['x=2'],'options':[]},'generation':{},'verified':True})
    grading.update(correct=True,verdict='confirmed_correct')
    near=client.post(path,headers=headers,json={'answer':'2','elapsed_seconds':2.9,'hint_level':1.8})
    assert near.status_code==200 and near.json()['data']['stage']=='far_transfer'
    assert near.json()['data']['attempt']['elapsed_seconds']==2 and near.json()['data']['attempt']['hint_level']==1
    with Database.from_environment() as db:
        state=json.loads(db.query('SELECT state FROM tutor_sessions WHERE id=?',[session['id']]).rows[0]['state'])
    assert client.post(path,headers=headers,json={'answer':'2'}).status_code==409
    monkeypatch.setattr(learning_evidence,'compute',lambda p,timeout=200:{'mastery':{**p['mastery_values'],'mastery_score':.7,'evidence_count':1,'update_reason':'受控验收'},'misconception':{**p['misconception_values'],'probability':.3,'evidence_count':2}})
    far=client.post('/api/v1/variants/'+state['far_variant_id']+'/attempt',headers=headers,json={'answer':'2'})
    assert far.status_code==200,far.text
    assert far.json()['data']['stage']=='finished' and far.json()['data']['mastery'] is not None
    with Database.from_environment() as db:
        assert db.query('SELECT interval_days FROM review_plans WHERE question_id=?',[question_id]).rows[0]['interval_days']=='3'


def test_visualization_uses_original_specs_and_persists_observations(client,monkeypatch):
    from sczx_api import analysis,visualizations
    from pathlib import Path
    monkeypatch.syspath_prepend(str(Path('sczx/algorithms').resolve()))
    from learning_core.services.visualizations import recommended_visualization,visualization_spec,visualization_catalog
    from learning_core.schemas import VisualizationPayload
    def compute(payload):
        kind=recommended_visualization(payload['subject'],payload['question_type'],payload['teach_back_points'])
        spec=None
        if kind:
            raw=visualization_spec(kind);raw['parameters'].update(payload['visualization_values'])
            spec=VisualizationPayload.model_validate(raw).model_dump(mode='json')
        return {'catalog':visualization_catalog(),'spec':spec}
    monkeypatch.setattr(visualizations,'compute',compute)
    catalog=client.get('/api/v1/visualizations/types')
    assert catalog.status_code==200 and catalog.json()['data']==visualization_catalog()
    user=client.post('/api/v1/auth/register',json={'email':'visual@example.com','password':'secret'}).json()['data']
    other=client.post('/api/v1/auth/register',json={'email':'visual-other@example.com','password':'secret'}).json()['data']
    headers={'Authorization':'Bearer '+user['access_token']};outsider={'Authorization':'Bearer '+other['access_token']}
    question_id=client.post('/api/v1/questions/manual',headers=headers,json={'question_text':'解方程x+1=2','student_steps':['x=3']}).json()['data']['id']
    record={'subject':'数学','problem_type':'方程','known_conditions':[],'goal':'求x','knowledge_points':['一元一次方程'],'prerequisites':[],'final_answer':'1','answer_verified':True,'reference_steps':['x=1']}
    monkeypatch.setattr(analysis,'compute',lambda p:{'analysis':record,'reference_math_valid':[True]})
    client.post('/api/v1/questions/'+question_id+'/analyze',headers=headers)
    session=client.post('/api/v1/tutor/sessions',headers=headers,json={'question_id':question_id}).json()['data']
    path='/api/v1/tutor/sessions/'+session['id']+'/visualization'
    assert client.get(path,headers=outsider).status_code==404
    response=client.get(path,headers=headers)
    assert response.status_code==200,response.text
    assert response.json()['data']['spec']['type']=='equation_balance'
    assert client.post(path,headers=headers,json={'values':[]}).status_code==422
    saved=client.post(path,headers=headers,json={'values':{},'observation':'等式两边做相同操作仍然平衡'})
    assert saved.status_code==200,saved.text
    visual=saved.json()['data']
    detail=client.get('/api/v1/visualizations/'+visual['id'],headers=headers)
    assert detail.status_code==200 and detail.json()['data']['interactions'][0]['observation']=='等式两边做相同操作仍然平衡'
    assert client.get('/api/v1/visualizations/'+visual['id'],headers=outsider).status_code==404
    with Database.from_environment() as db:
        assert db.query("SELECT COUNT(*) AS n FROM agent_tool_calls c JOIN agent_runs r ON r.id=c.agent_run_id WHERE r.session_id=? AND c.tool_name='observe_visualization'",[session['id']]).rows[0]['n']=='1'
        db.query("UPDATE questions SET status='archived' WHERE id=?",[question_id])
    assert client.post(path,headers=headers,json={}).status_code==409
    assert client.get(path,headers=headers).status_code==200


def test_tutor_dialogue_memory_tools_stage_gate_and_stale_snapshot(client,monkeypatch):
    import json
    from sczx_api import analysis,tutor_dialogue
    from sczx_api.learning_memory import learning_memory
    from sczx_api.rows import row_json
    from sczx_api.security import new_id
    user=client.post('/api/v1/auth/register',json={'email':'dialogue@example.com','password':'secret'}).json()['data']
    headers={'Authorization':'Bearer '+user['access_token']}
    question_id=client.post('/api/v1/questions/manual',headers=headers,json={'question_text':'解方程x+1=2','student_steps':['x=3']}).json()['data']['id']
    record={'subject':'数学','problem_type':'方程','known_conditions':[],'goal':'求x','knowledge_points':['方程'],'prerequisites':[],'final_answer':'1','answer_verified':True,'reference_steps':['x=1']}
    monkeypatch.setattr(analysis,'compute',lambda p:{'analysis':record,'reference_math_valid':[True]})
    client.post('/api/v1/questions/'+question_id+'/analyze',headers=headers)
    session=client.post('/api/v1/tutor/sessions',headers=headers,json={'question_id':question_id}).json()['data']
    mastery_id=new_id();card_id=new_id()
    with Database.from_environment() as db:
        db.query("INSERT INTO mastery_states (id,user_id,subject,knowledge_point,mastery_score,confidence,evidence_count,near_transfer_rate,far_transfer_rate,forgetting_risk,update_reason,created_at,updated_at) VALUES (?,?,'数学','方程',0.4,0.3,1,0,0,0.5,'旧估计',UTC_TIMESTAMP(),UTC_TIMESTAMP())",[mastery_id,user['id']])
        db.query("INSERT INTO review_plans (id,user_id,question_id,due_at,interval_days,reason,status,created_at,updated_at) VALUES (?,?,?,UTC_TIMESTAMP(),1,'复习','pending',UTC_TIMESTAMP(),UTC_TIMESTAMP())",[new_id(),user['id'],question_id])
        db.query("INSERT INTO knowledge_points (id,code,subject,name,content,created_at,updated_at) VALUES (?,'sczx.dialogue.equation','数学','方程',JSON_OBJECT('grade','初一'),UTC_TIMESTAMP(),UTC_TIMESTAMP())",[card_id])
        question=row_json('questions',db.query('SELECT * FROM questions WHERE id=?',[question_id]).rows[0])
        memory=learning_memory(db,user['id'],question)
        assert {e['classification'] for e in memory['snapshot']['entries']}=={'estimate','reminder'}
        assert memory['legacy_rows']['mastery'][0]['id']==mastery_id
    calls=[];stale=False
    def compute(payload):
        calls.append(payload['operation'])
        if payload['operation']=='tutor_dialogue_prepare':
            assert payload['dialogue_context']['memory_snapshot']['entries']
            return {'plan':{'tool_name':'knowledge_search','memory_source_ids':[e['ref'] for e in payload['dialogue_context']['memory_snapshot']['entries']]},'knowledge_query':'方程'}
        assert payload['dialogue_cards'] and payload['dialogue_context']['reference_steps']==['x=1']
        if stale:
            with Database.from_environment() as db:db.query("UPDATE questions SET student_answer='已修改' WHERE id=?",[question_id])
        plan=payload['dialogue_preparation']['plan']
        return {'reply':'等式两边同时减1。','graph':{'branch':'condition_hint','strategy':'micro_activity','next_goal':'核对条件','mastery_proven':False,'stage':'far_transfer','hint_level':1},'agent':{'tool':{'evidence':{'source':'knowledge'},'executed':True,'consumed_input':{'query':'方程'}},'verification':{'status':'verified'},'planner_status':'ready','observation':{},'plan':plan},'knowledge_sources':[{'code':'sczx.dialogue.equation'}]}
    monkeypatch.setattr(tutor_dialogue,'compute',compute)
    path='/api/v1/tutor/sessions/'+session['id']+'/turns'
    assert client.post(path,headers=headers,json={'message':' '}).status_code==422
    first=client.post(path,headers=headers,json={'message':'为什么移项'})
    assert first.status_code==200,first.text
    assert first.json()['data']['stage']=='understanding' and first.json()['data']['message']=='等式两边同时减1。'
    assert calls==['tutor_dialogue_prepare','tutor_dialogue_finish']
    assert client.post(path,headers=headers,json={'message':'为什么移项'}).status_code==200
    with Database.from_environment() as db:
        stored=db.query('SELECT state,turn_count,stage FROM tutor_sessions WHERE id=?',[session['id']]).rows[0]
        assert stored['turn_count']=='2' and stored['stage']=='understanding'
        assert json.loads(stored['state'])['repeated_count']==1
        runs=db.query("SELECT result FROM agent_runs WHERE session_id=? ORDER BY created_at DESC",[session['id']]).rows
        audited=[json.loads(r['result']) for r in runs if 'memory_manifest' in r['result']]
        assert len(audited)==2 and len(audited[0]['memory_manifest'])==2
        before=db.query('SELECT COUNT(*) AS n FROM tutor_turns WHERE session_id=?',[session['id']]).rows[0]['n']
    stale=True
    conflict=client.post(path,headers=headers,json={'message':'继续解释'})
    assert conflict.status_code==409 and '已变化' in conflict.json()['detail']
    with Database.from_environment() as db:
        assert db.query('SELECT COUNT(*) AS n FROM tutor_turns WHERE session_id=?',[session['id']]).rows[0]['n']==before
        db.query('UPDATE mastery_states SET updated_at=UTC_TIMESTAMP()-INTERVAL 31 DAY WHERE id=?',[mastery_id])
        assert learning_memory(db,user['id'],question)['legacy_rows']['mastery']==[]
        db.query("UPDATE tutor_sessions SET stage='finished' WHERE id=?",[session['id']])
    assert client.post(path,headers=headers,json={'message':'继续'}).status_code==409


def test_dashboard_analytics_and_error_sources_use_original_statistics(client):
    import json
    from sczx_api.security import new_id
    user=client.post('/api/v1/auth/register',json={'email':'dashboard@example.com','password':'secret'}).json()['data']
    other=client.post('/api/v1/auth/register',json={'email':'dashboard-other@example.com','password':'secret'}).json()['data']
    headers={'Authorization':'Bearer '+user['access_token']};outsider={'Authorization':'Bearer '+other['access_token']}
    empty=client.get('/api/v1/dashboard',headers=headers).json()['data']
    assert empty['weekly_questions']==empty['estimated_minutes']==0 and empty['continue_learning'] is None
    assert empty['discoveries']==[] and empty['grade']=='初二'
    assert client.get('/api/v1/dashboard').status_code==401
    question_ids=[]
    for text in ['求 X？','求x','较早的题']:
        question_ids.append(client.post('/api/v1/questions/manual',headers=headers,json={'question_text':text}).json()['data']['id'])
    session_id=new_id();plan_id=new_id()
    with Database.from_environment() as db:
        for index,question_id in enumerate(question_ids):
            age=[0,1,8][index]
            db.query('UPDATE questions SET created_at=TIMESTAMP(DATE(UTC_TIMESTAMP()+INTERVAL 8 HOUR))-INTERVAL 7 HOUR-INTERVAL ? DAY WHERE id=?',[age,question_id])
        db.query('UPDATE questions SET updated_at=UTC_TIMESTAMP()+INTERVAL 1 SECOND WHERE id=?',[question_ids[0]])
        for age,score in [(1,.3),(0,.8)]:
            db.query("INSERT INTO mastery_states (id,user_id,subject,knowledge_point,mastery_score,confidence,evidence_count,near_transfer_rate,far_transfer_rate,forgetting_risk,update_reason,created_at,updated_at) VALUES (?,?,'数学','方程',?,0.5,1,0,0,0.5,'学习更新',UTC_TIMESTAMP(),UTC_TIMESTAMP()-INTERVAL ? DAY)",[new_id(),user['id'],score,age])
        for label,probability in [('移项符号看错',.8),('移项忘记变号',.6)]:
            db.query("INSERT INTO misconception_states (id,user_id,subject,code,label,probability,evidence_count,status,related_question_count,successful_strategy,failed_strategy,first_seen_at,created_at,updated_at) VALUES (?,?,'数学',?,?,?,1,'active',1,'micro_activity','guided',UTC_TIMESTAMP(),UTC_TIMESTAMP(),UTC_TIMESTAMP())",[new_id(),user['id'],new_id(),label,probability])
        db.query("INSERT INTO tutor_sessions (id,user_id,question_id,stage,hint_level,turn_count,mastery_score,state,status,created_at,updated_at) VALUES (?,?,?,'teach_back_retry',0,0,0,JSON_OBJECT(),'active',UTC_TIMESTAMP(),UTC_TIMESTAMP())",[session_id,user['id'],question_ids[0]])
        db.query("INSERT INTO review_plans (id,user_id,question_id,due_at,interval_days,reason,status,created_at,updated_at) VALUES (?,?,?,UTC_TIMESTAMP()-INTERVAL 1 DAY,1,'复习','pending',UTC_TIMESTAMP(),UTC_TIMESTAMP())",[plan_id,user['id'],question_ids[0]])
        for score in [.25,.75]:
            db.query("INSERT INTO cognitive_updates (id,user_id,question_id,entity_type,entity_key,old_value,new_value,evidence,reason,created_at,updated_at) VALUES (?,?,?,'mastery','方程',0,?,JSON_OBJECT(),'学习',UTC_TIMESTAMP(),UTC_TIMESTAMP())",[new_id(),user['id'],question_ids[0],score])
        for index,question_id in enumerate(question_ids[:2]):
            db.query("INSERT INTO diagnoses (id,question_id,first_error_step,first_error_text,error_type,root_misconception,propagated_errors,strategy_candidates,confidence,error_location,missing_prerequisites,recommended_strategy,user_confirmed,correction,created_at,updated_at) VALUES (?,?,NULL,'','sign_error','移项符号',JSON_ARRAY(),JSON_ARRAY(),0.8,'',JSON_ARRAY(),'核对符号',0,JSON_OBJECT(),UTC_TIMESTAMP(),UTC_TIMESTAMP())",[new_id(),question_id])
    dashboard=client.get('/api/v1/dashboard',headers=headers)
    assert dashboard.status_code==200,dashboard.text
    value=dashboard.json()['data']
    assert value['weekly_questions']==2 and value['streak_days']==2 and value['today_reviews']==1
    assert value['mastered_points']==1 and value['estimated_minutes']==6
    assert value['continue_learning']['session_id']==session_id and value['continue_learning']['next_step']=='补充说明关键理由'
    assert len(value['mastery'])==len(value['misconceptions'])==1 and value['misconceptions'][0]['label']=='移项符号'
    analytics=client.get('/api/v1/analytics/overview?days=2',headers=headers)
    assert analytics.status_code==200,analytics.text
    data=analytics.json()['data']
    assert data['summary']=={'knowledge_count':1,'misconception_count':1,'evidence_count':2}
    assert data['trend'][0]['score']==50.0 and data['misconceptions'][0]['successful_strategy']=='小步练习'
    for days in ['0','366','abc','1.5','']:
        assert client.get('/api/v1/analytics/overview?days='+days,headers=headers).status_code==422
    assert client.get('/api/v1/analytics/overview?days=0&days=1',headers=headers).status_code==200
    sources=client.get('/api/v1/analytics/error-sources?subject=数学',headers=headers)
    assert sources.status_code==200,sources.text
    assert len(sources.json()['data']['sources'])==1
    assert sources.json()['data']['sources'][0]['due_review_id']==plan_id
    assert client.get('/api/v1/analytics/error-sources?subject=语文',headers=headers).json()['data']['sources']==[]
    assert client.get('/api/v1/analytics/overview',headers=outsider).json()['data']['summary']['evidence_count']==0
    graph=client.get('/api/v1/analytics/cognition-graph',headers=headers)
    assert graph.status_code==200,graph.text
    projected=graph.json()['data']
    assert projected['evidence_count']==2 and projected['filters']=={'subject':None,'days':90}
    assert {n['category'] for n in projected['nodes']}=={'knowledge','question','misconception','strategy'}
    assert len([n for n in projected['nodes'] if n['category']=='question'])==1
    visible_ids={n['id'] for n in projected['nodes']}
    assert all(link['source'] in visible_ids and link['target'] in visible_ids for link in projected['links'])
    assert any(link['relation']=='提供掌握证据' for link in projected['links'])
    assert client.get('/api/v1/analytics/cognition-graph?subject=语文',headers=headers).json()['data']['nodes']==[]
    assert client.get('/api/v1/analytics/cognition-graph?days=3651',headers=headers).status_code==422
    assert client.get('/api/v1/analytics/cognition-graph',headers=outsider).json()['data']['nodes']==[]
    with Database.from_environment() as db:
        db.query("UPDATE tutor_sessions SET state=JSON_OBJECT('question_changed',CAST('true' AS JSON)) WHERE id=?",[session_id])
    assert client.get('/api/v1/dashboard',headers=headers).json()['data']['continue_learning'] is None


def test_knowledge_search_unicode_filters_and_relations(client):
    import json
    from sczx_api.security import new_id
    first,second=new_id(),new_id()
    with Database.from_environment() as db:
        for card_id,code,name,grade in [(first,'sczx.search.one','特殊知识甲','初一'),(second,'sczx.search.two','特殊知识乙','高一')]:
            db.query("INSERT INTO knowledge_points (id,code,subject,name,content,created_at,updated_at) VALUES (?,?,'数学',?,?,UTC_TIMESTAMP(),UTC_TIMESTAMP())",[card_id,code,name,json.dumps({'grade':grade,'common_misconceptions':['特殊误区']})])
        db.query("INSERT INTO knowledge_relations (id,source_id,target_id,relation_type,created_at,updated_at) VALUES (?,?,?,'prerequisite',UTC_TIMESTAMP(),UTC_TIMESTAMP())",[new_id(),second,first])
    found=client.get('/api/v1/knowledge/cards',params={'q':'特殊知识，其他词','subject':'数学','grade':'初一','misconception':'特殊误区'})
    assert found.status_code==200 and [c['id'] for c in found.json()['data']]==[first]
    assert client.get('/api/v1/knowledge/cards',params={'q':'特殊知识','grade':'高一'}).json()['data'][0]['id']==second
    card=client.get('/api/v1/knowledge/cards/sczx.search.two')
    assert card.status_code==200 and card.json()['data']['prerequisites'][0]['id']==first
    assert client.get('/api/v1/knowledge/cards/'+first).json()['data']['next_knowledge'][0]['id']==second
    assert client.get('/api/v1/knowledge/cards/missing-card').status_code==404


def test_review_attempt_receipts_supersession_grading_and_source_changes(client,monkeypatch):
    from sczx_api import analysis,reviews
    from sczx_api.security import new_id
    user=client.post('/api/v1/auth/register',json={'email':'reviews@example.com','password':'secret'}).json()['data']
    other=client.post('/api/v1/auth/register',json={'email':'reviews-other@example.com','password':'secret'}).json()['data']
    headers={'Authorization':'Bearer '+user['access_token']};outsider={'Authorization':'Bearer '+other['access_token']}
    question_id=client.post('/api/v1/questions/manual',headers=headers,json={'question_text':'x+1=2','student_answer':'原来的答案'}).json()['data']['id']
    record={'subject':'数学','problem_type':'方程','known_conditions':[],'goal':'求x','knowledge_points':['方程'],'prerequisites':[],'final_answer':'1','answer_verified':True,'reference_steps':['x=1']}
    monkeypatch.setattr(analysis,'compute',lambda p:{'analysis':record,'reference_math_valid':[True]})
    client.post('/api/v1/questions/'+question_id+'/analyze',headers=headers)
    plan_id=new_id()
    with Database.from_environment() as db:
        db.query("INSERT INTO review_plans (id,user_id,question_id,due_at,interval_days,reason,status,created_at,updated_at) VALUES (?,?,?,UTC_TIMESTAMP()-INTERVAL 1 DAY,1,'again','pending',UTC_TIMESTAMP(),UTC_TIMESTAMP())",[plan_id,user['id'],question_id])
    due=client.get('/api/v1/reviews/today',headers=headers)
    assert due.status_code==200,due.text
    plan=due.json()['data'][0];version=plan['source_version']
    assert 'student_answer' not in plan['question'] and '1 天后' in plan['reason']
    calls=[]
    def compute(p):
        calls.append(p);decisive=p['answer']!='maybe';correct=p['answer']=='1'
        return {'correct':correct,'can_update_learning':decisive,'verdict':'review_required' if not decisive else 'confirmed_correct' if correct else 'confirmed_incorrect','score':1.0 if correct else 0.0,'feedback':'核对计算','matched_points':[]}
    monkeypatch.setattr(reviews,'compute',compute)
    path='/api/v1/reviews/'+plan_id
    assert client.post(path+'/attempt',headers=outsider,json={'answer':'1'}).status_code==404
    assert client.post(path+'/attempt',headers=headers,json={'answer':'1','source_version':'old'}).status_code==409
    request={'answer':'maybe','request_id':'attempt-one','source_version':version}
    first=client.post(path+'/attempt',headers=headers,json=request)
    assert first.status_code==200,first.text
    uncertain=first.json()['data'];assert uncertain['correct'] is None and uncertain['can_update_learning'] is False
    assert client.post(path+'/attempt',headers=headers,json=request).json()['data']['attempt_id']==uncertain['attempt_id'] and len(calls)==1
    assert client.post(path+'/attempt',headers=headers,json={**request,'answer':'1'}).status_code==409
    assert client.post(path+'/grade',headers=headers,json={'attempt_id':uncertain['attempt_id'],'grade':'easy'}).status_code==409
    current=client.post(path+'/attempt',headers=headers,json={'answer':'1','request_id':'attempt-two','source_version':version}).json()['data']
    assert current['correct'] is True
    assert client.post(path+'/attempt',headers=headers,json=request).status_code==409
    assert client.post(path+'/grade',headers=headers,json={'attempt_id':uncertain['attempt_id']}).status_code==409
    due=client.get('/api/v1/reviews/today',headers=headers).json()['data'][0]
    assert due['pending_attempt']['attempt_id']==current['attempt_id']
    assert client.post(path+'/grade',headers=headers,json={'attempt_id':current['attempt_id'],'grade':'invalid'}).status_code==422
    graded=client.post(path+'/grade',headers=headers,json={'attempt_id':current['attempt_id'],'grade':'good'})
    assert graded.status_code==200,graded.text
    next_plan=graded.json()['data']['next_plan']
    assert next_plan['interval_days']==7 and graded.json()['data']['record']['correct'] is True
    assert client.post(path+'/grade',headers=headers,json={'attempt_id':current['attempt_id']}).status_code==409
    history=client.get('/api/v1/reviews/history',headers=headers).json()['data']
    assert len(history)==1 and history[0]['grade']=='good' and history[0]['question']['id']==question_id
    from sczx_api.learning_memory import learning_memory
    from sczx_api.rows import row_json
    with Database.from_environment() as db:
        source=row_json('questions',db.query('SELECT * FROM questions WHERE id=?',[question_id]).rows[0])
        events=[e for e in learning_memory(db,user['id'],source)['snapshot']['entries'] if e['kind']=='review_record']
        assert len(events)==1 and events[0]['outcome']=='correct' and events[0]['classification']=='verified_event'
    assert client.get('/api/v1/reviews/history',headers=outsider).json()['data']==[]
    for answer,grade,days in [('0','easy',4),('1','hard',2),('0','again',1)]:
        path='/api/v1/reviews/'+next_plan['id']
        attempt=client.post(path+'/attempt',headers=headers,json={'answer':answer}).json()['data']
        result=client.post(path+'/grade',headers=headers,json={'attempt_id':attempt['attempt_id'],'grade':grade})
        assert result.status_code==200,result.text
        next_plan=result.json()['data']['next_plan'];assert next_plan['interval_days']==days
    path='/api/v1/reviews/'+next_plan['id']
    attempt=client.post(path+'/attempt',headers=headers,json={'answer':'1'}).json()['data']
    with Database.from_environment() as db:db.query("UPDATE questions SET student_answer='新作答' WHERE id=?",[question_id])
    assert client.post(path+'/grade',headers=headers,json={'attempt_id':attempt['attempt_id']}).status_code==409
    with Database.from_environment() as db:
        source=row_json('questions',db.query('SELECT * FROM questions WHERE id=?',[question_id]).rows[0])
        assert not [e for e in learning_memory(db,user['id'],source)['snapshot']['entries'] if e['kind']=='review_record']


def test_review_search_paging_and_saved_filter_limits(client):
    from sczx_api.security import new_id
    user=client.post('/api/v1/auth/register',json={'email':'review-search@example.com','password':'secret'}).json()['data']
    other=client.post('/api/v1/auth/register',json={'email':'review-search-other@example.com','password':'secret'}).json()['data']
    headers={'Authorization':'Bearer '+user['access_token']};outsider={'Authorization':'Bearer '+other['access_token']}
    question_id=client.post('/api/v1/questions/manual',headers=headers,json={'question_text':'计算x%表达式','student_answer':'不能提前显示'}).json()['data']['id']
    with Database.from_environment() as db:
        for _ in range(24):db.query("INSERT INTO review_plans (id,user_id,question_id,due_at,interval_days,reason,status,created_at,updated_at) VALUES (?,?,?,UTC_TIMESTAMP()-INTERVAL 1 DAY,1,'需巩固','pending',UTC_TIMESTAMP(),UTC_TIMESTAMP())",[new_id(),user['id'],question_id])
    response=client.get('/api/v1/reviews/search',headers=headers,params={'q':'x%','scope':'today','subject':'数学'})
    assert response.status_code==200,response.text
    value=response.json()['data']
    assert value['total']==24 and len(value['items'])==20 and value['page_size']==20
    assert 'student_answer' not in value['items'][0] and value['items'][0]['is_due'] is True
    assert value['items'][0]['grade']==''
    page=client.get('/api/v1/reviews/search?page=2',headers=headers).json()['data']
    assert len(page['items'])==4 and page['total']==24
    assert client.get('/api/v1/reviews/search?scope=completed',headers=headers).json()['data']['total']==0
    assert client.get('/api/v1/reviews/search?subject=英语',headers=headers).json()['data']['total']==0
    assert client.get('/api/v1/reviews/search',headers=outsider).json()['data']['total']==0
    for query in ['scope=invalid','page=0','page=10001','page=1.5','q='+'字'*101]:
        assert client.get('/api/v1/reviews/search?'+query,headers=headers).status_code==422
    url='/api/v1/reviews/filters';body={'name':' 方程复习 ','q':' x% ','subject':'数学','scope':'today'}
    first=client.post(url,headers=headers,json=body)
    assert first.status_code==200,first.text
    item=first.json()['data'][0]
    assert item['name']=='方程复习' and item['q']=='x%'
    assert client.post(url,headers=headers,json=body).json()['data']==[item]
    assert client.get(url,headers=outsider).json()['data']==[]
    for index in range(19):assert client.post(url,headers=headers,json={'name':f'范围{index}'}).status_code==200
    full=client.get(url,headers=headers).json()['data']
    assert len(full)==20
    assert client.post(url,headers=headers,json={'name':'超出上限'}).status_code==409
    assert len(client.post(url,headers=headers,json=body).json()['data'])==20
    assert client.delete(url+'/'+item['id'],headers=outsider).status_code==404
    assert client.delete(url+'/'+item['id'],headers=headers).json()['data']=={'deleted':True}
    assert len(client.get(url,headers=headers).json()['data'])==19


def test_study_bank_grade_shuffle_public_images_and_facets(client,tmp_path,monkeypatch):
    import json,hashlib
    from sczx_api.security import new_id,media_url
    user=client.post('/api/v1/auth/register',json={'email':'bank@example.com','password':'secret','grade':'初二'}).json()['data']
    headers={'Authorization':'Bearer '+user['access_token']};source_id=new_id();bank=tmp_path/'bank';bank.mkdir()
    stem=bank/'stem.png';answer_image=bank/'answer.png';stem.write_bytes(b'stem-image');answer_image.write_bytes(b'answer-image')
    monkeypatch.setenv('SCZX_QUESTION_BANK_ROOT',str(bank))
    def insert(db,index,subject,grade,band,text,**changes):
        item={'id':new_id(),'dataset_source_id':source_id,'source_item_id':str(index),'split':'test','subject':subject,'grade':grade,'grade_band':band,'title':text,'question_text':text,'question_type':'综合题','options':[],'answer':'1','solution':'参考过程','knowledge_points':[],'image_paths':[],'difficulty':'medium','content_hash':hashlib.sha256(str(index).encode()).hexdigest(),'source_metadata':{},'has_answer':1,'has_solution':1,'answer_verified':1,'quality_status':'ready','usable_for_practice':1,'usable_for_auto_grade':1}
        item.update(changes);keys=list(item)
        params=[json.dumps(item[k],ensure_ascii=False) if k in ['options','answer','knowledge_points','image_paths','source_metadata'] else item[k] for k in keys]
        db.query('INSERT INTO dataset_questions ('+','.join('`'+k+'`' for k in keys)+',created_at,updated_at) VALUES ('+','.join('?' for _ in keys)+',UTC_TIMESTAMP(),UTC_TIMESTAMP())',params)
        return item['id']
    with Database.from_environment() as db:
        db.query("INSERT INTO dataset_sources (id,`key`,name,version,homepage,license,local_path,total_items,imported_items,source_metadata,created_at,updated_at) VALUES (?,'sczx-bank-test','测试题源','1','','public','',0,0,JSON_OBJECT(),UTC_TIMESTAMP(),UTC_TIMESTAMP())",[source_id])
        for index in range(26):insert(db,index,'英语','八年级','初中',f'English passage {index}')
        plain=insert(db,30,'数学','初二','初中','解方程x+1=2')
        pictured=insert(db,31,'数学','初二','初中','图示<ImageHere>求x',answer='答案<ImageHere>',solution='',image_paths=[str(stem),str(answer_image)])
        insert(db,32,'语文','初二','初中','文章全文\n\n阅读小问',source_metadata={'passage_id':'sample'})
        insert(db,33,'数学','初二','初中','二次函数的最值')
        senior=insert(db,34,'数学','高三','高中','高中数学题')
        insert(db,35,'英语','','初中','没有具体年级')
    assert client.get('/api/v1/study-bank').status_code==401
    first=client.get('/api/v1/study-bank?shuffle_seed=123',headers=headers)
    assert first.status_code==200,first.text
    value=first.json()['data']
    assert value['total']==29 and value['grade']=='初二' and value['scope_label']=='初二'
    assert {q['subject'] for q in value['questions'][:3]}=={'英语','数学','语文'}
    assert all('answer' not in q and 'solution' not in q for q in value['questions'])
    assert sum(f['count'] for f in value['facets'])==29 and value['sources'][0]['count']==29
    again=client.get('/api/v1/study-bank?shuffle_seed=123',headers=headers).json()['data']
    assert [q['id'] for q in again['questions']]==[q['id'] for q in value['questions']]
    second=client.get('/api/v1/study-bank?shuffle_seed=123&page=2',headers=headers).json()['data']
    assert len(second['questions'])==9 and not ({q['id'] for q in value['questions']} & {q['id'] for q in second['questions']})
    math=client.get('/api/v1/study-bank?subject=数学',headers=headers).json()['data']
    assert math['total']==2 and {q['id'] for q in math['questions']}=={plain,pictured}
    image_question=client.get('/api/v1/study-bank?search=图示',headers=headers).json()['data']['questions'][0]
    assert len(image_question['image_urls'])==len(image_question['preview_image_urls'])==1
    assert client.get(image_question['image_urls'][0]).content==b'stem-image'
    assert client.head(image_question['image_urls'][0]).headers['content-length']=='10'
    assert client.get(image_question['image_urls'][0],headers={'Range':'bytes=0-3'}).content==b'stem'
    assert client.get(f'/api/v1/practice/questions/{pictured}/images/0').status_code==403
    bad=media_url(f'/api/v1/practice/questions/{pictured}/images/99',os.environ['SCZX_AUTH_SECRET'])
    assert client.get(bad).status_code==404
    chinese=client.get('/api/v1/study-bank?subject=语文',headers=headers).json()['data']['questions'][0]
    assert chinese['preview_text']=='阅读理解：阅读小问'
    for query in ['page=0','shuffle_seed=-1','shuffle_seed=2147483648','search='+'字'*101]:
        assert client.get('/api/v1/study-bank?'+query,headers=headers).status_code==422
    with Database.from_environment() as db:db.query("UPDATE student_profiles SET grade='高一' WHERE user_id=?",[user['id']])
    senior_bank=client.get('/api/v1/study-bank',headers=headers).json()['data']
    assert senior_bank['scope_label']=='高中' and [q['id'] for q in senior_bank['questions']]==[senior]


def test_study_sessions_save_submit_timeout_and_adaptive_selection(client,monkeypatch):
    import json,hashlib
    from sczx_api import study_sessions,adaptive_practice
    from sczx_api.security import new_id
    user=client.post('/api/v1/auth/register',json={'email':'study-session@example.com','password':'secret'}).json()['data']
    other=client.post('/api/v1/auth/register',json={'email':'study-session-other@example.com','password':'secret'}).json()['data']
    headers={'Authorization':'Bearer '+user['access_token']};outsider={'Authorization':'Bearer '+other['access_token']};source_id=new_id();question_ids=[]
    with Database.from_environment() as db:
        db.query("INSERT INTO dataset_sources (id,`key`,name,version,homepage,license,local_path,total_items,imported_items,source_metadata,created_at,updated_at) VALUES (?,'sczx-session-test','会话测试题','1','','public','',5,5,JSON_OBJECT(),UTC_TIMESTAMP(),UTC_TIMESTAMP())",[source_id])
        for index in range(5):
            item_id=new_id();question_ids.append(item_id)
            db.query("INSERT INTO dataset_questions (id,dataset_source_id,source_item_id,split,subject,grade,grade_band,title,question_text,question_type,options,answer,solution,knowledge_points,image_paths,difficulty,content_hash,source_metadata,has_answer,has_solution,answer_verified,quality_status,usable_for_practice,usable_for_auto_grade,created_at,updated_at) VALUES (?,?,?,'test','数学','初二','初中','基础计算',?,'综合题',JSON_ARRAY(),JSON_QUOTE('1'),'解题过程',JSON_ARRAY('基础运算'),JSON_ARRAY(),'medium',?,JSON_OBJECT(),1,1,1,'ready',1,1,UTC_TIMESTAMP(),UTC_TIMESTAMP())",[item_id,source_id,str(index),f'基础运算题{index}',hashlib.sha256(str(index).encode()).hexdigest()])
    monkeypatch.setattr(study_sessions,'compute',lambda p,timeout=200:{'correct':p['answer']=='1','can_update_learning':True,'feedback':'已判定'})
    url='/api/v1/study-sessions'
    assert client.post(url,headers=headers,json={'count':True}).status_code==422
    assert client.post(url,headers=headers,json={'question_ids':question_ids[:2]}).status_code==422
    created=client.post(url,headers=headers,json={'question_ids':[question_ids[0]],'source_id':source_id})
    assert created.status_code==200,created.text
    session=created.json()['data'];path=url+'/'+session['id'];item_id=session['items'][0]['id']
    assert session['question_count']==1 and 'answer' not in session['items'][0] and 'answer' not in session['items'][0]['question']
    assert client.get(path,headers=outsider).status_code==404
    payload={'version':1,'answers':[{'id':item_id,'answer':'wrong'}]}
    saved=client.patch(path,headers=headers,json=payload)
    assert saved.status_code==200 and saved.json()['data']['version']==2
    assert client.patch(path,headers=headers,json=payload).status_code==409
    assert client.patch(path,headers=headers,json={'version':2,'answers':[{'id':item_id,'answer':['A','A']}]}).status_code==422
    assert client.post(path+'/submit',headers=headers,json={'version':1}).status_code==409
    submitted=client.post(path+'/submit',headers=headers,json={'version':2})
    assert submitted.status_code==200,submitted.text
    result=submitted.json()['data'];assert result['status']=='submitted' and result['results']['score']==0
    assert result['items'][0]['answer']=='1' and result['items'][0]['grading']['correct'] is False
    assert client.post(path+'/submit',headers=headers,json={'version':1}).json()['data']['results']==result['results']
    assert client.patch(path,headers=headers,json={'version':3,'answers':[{'id':item_id,'answer':'1'}]}).status_code==409
    # User explicitly adds the marked-wrong item; session grading itself does not manufacture a mistake.
    with Database.from_environment() as db:assert db.query('SELECT COUNT(*) AS n FROM questions WHERE user_id=?',[user['id']]).rows[0]['n']=='0'
    mistake=client.post('/api/v1/questions/manual',headers=headers,json={'study_session_id':session['id'],'study_item_id':item_id})
    assert mistake.status_code==200,mistake.text
    assert client.get(path,headers=headers).json()['data']['items'][0]['mistake_id']==mistake.json()['data']['id']
    exam=client.post(url,headers=headers,json={'mode':'exam','source_id':source_id,'count':3,'minutes':1}).json()['data']
    exam_path=url+'/'+exam['id'];assert 0<exam['remaining_seconds']<=60
    answers=[{'id':item['id'],'answer':'1' if index==0 else None} for index,item in enumerate(exam['items'])]
    assert client.patch(exam_path,headers=headers,json={'version':1,'answers':answers}).status_code==200
    excluded_id=exam['items'][1]['question']['id']
    with Database.from_environment() as db:
        db.query("UPDATE dataset_questions SET quality_status='format_review' WHERE id=?",[excluded_id])
        db.query('UPDATE study_sessions SET deadline_at=UTC_TIMESTAMP(6)-INTERVAL 1 SECOND WHERE id=?',[exam['id']])
    assert client.patch(exam_path,headers=headers,json={'version':2,'answers':answers}).status_code==409
    finished=client.post(exam_path+'/submit',headers=headers,json={'version':2})
    assert finished.status_code==200,finished.text
    summary=finished.json()['data']['results']
    assert summary=={'correct':1,'pending':0,'excluded':1,'answered':1,'total':3,'score':5,'max_score':10}
    assert finished.json()['data']['items'][1]['unavailable'] is True and 'answer' not in finished.json()['data']['items'][1]
    seen=[]
    def select(payload):
        domain=payload['adaptive_practice'];seen.append(domain)
        return {'question_ids':[q['id'] for q in domain['candidates'][:domain['count']]],'method':'controlled'}
    monkeypatch.setattr(adaptive_practice,'compute',select)
    adaptive=client.post(url,headers=headers,json={'selection_strategy':'adaptive','source_id':source_id,'count':2})
    assert adaptive.status_code==200,adaptive.text
    assert adaptive.json()['data']['question_count']==2 and seen[0]['observations']
    monkeypatch.setattr(adaptive_practice,'compute',lambda p:{'question_ids':['outside-pool','outside-pool']})
    assert client.post(url,headers=headers,json={'selection_strategy':'adaptive','source_id':source_id,'count':2}).status_code==503
    assert client.get(url,headers=outsider).json()['data']==[]
    assert len(client.get(url,headers=headers).json()['data'])==3
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    chosen=next(q for q in question_ids if q!=excluded_id)
    concurrent=client.post(url,headers=headers,json={'question_ids':[chosen]}).json()['data']
    concurrent_path=url+'/'+concurrent['id'];concurrent_item=concurrent['items'][0]['id']
    assert client.patch(concurrent_path,headers=headers,json={'version':1,'answers':[{'id':concurrent_item,'answer':'1'}]}).status_code==200
    started,release=Event(),Event()
    def blocking_grade(payload,timeout=200):
        started.set()
        assert release.wait(10),'concurrent save must run while computation waits'
        return {'correct':True,'can_update_learning':True,'feedback':'旧判分'}
    monkeypatch.setattr(study_sessions,'compute',blocking_grade)
    with ThreadPoolExecutor(max_workers=1) as executor:
        pending=executor.submit(client.post,concurrent_path+'/submit',headers=headers,json={'version':2})
        try:
            assert started.wait(10)
            updated=client.patch(concurrent_path,headers=headers,json={'version':2,'answers':[{'id':concurrent_item,'answer':'新的答案'}]})
            assert updated.status_code==200,updated.text
        finally:release.set()
        rejected=pending.result(timeout=10)
    assert rejected.status_code==409 and '判分未保存' in rejected.json()['detail']
    persisted=client.get(concurrent_path,headers=headers).json()['data']
    assert persisted['status']=='active' and persisted['results'] is None and persisted['items'][0]['student_answer']=='新的答案'


def test_personal_framework_and_versioned_knowledge_lessons(client,monkeypatch):
    import json
    from fastapi import HTTPException
    from sczx_api import knowledge_lessons
    from sczx_api.security import new_id
    user=client.post('/api/v1/auth/register',json={'email':'lessons@example.com','password':'secret'}).json()['data']
    other=client.post('/api/v1/auth/register',json={'email':'lessons-other@example.com','password':'secret'}).json()['data']
    headers={'Authorization':'Bearer '+user['access_token']};outsider={'Authorization':'Bearer '+other['access_token']};anchor_id,prereq_id=new_id(),new_id()
    question_id=client.post('/api/v1/questions/manual',headers=headers,json={'question_text':'知识框架关联题'}).json()['data']['id']
    with Database.from_environment() as db:
        for card_id,code,name in [(anchor_id,'sczx.lesson.anchor','专用知识点'),(prereq_id,'sczx.lesson.base','专用先修')]:
            db.query("INSERT INTO knowledge_points (id,code,subject,name,content,created_at,updated_at) VALUES (?,?,'数学',?,?,UTC_TIMESTAMP(),UTC_TIMESTAMP())",[card_id,code,name,json.dumps({'grade':'初二','chapter':'第一章','definition':'原定义'})])
        db.query("INSERT INTO knowledge_relations (id,source_id,target_id,relation_type,created_at,updated_at) VALUES (?,?,?,'prerequisite',UTC_TIMESTAMP(),UTC_TIMESTAMP())",[new_id(),anchor_id,prereq_id])
        db.query("INSERT INTO user_question_knowledge_links (id,user_id,question_id,knowledge_point_id,role,confidence,mapping_method,evidence_text,created_at,updated_at) VALUES (?,?,?,?,'primary',1,'exact_label','测试关联',UTC_TIMESTAMP(),UTC_TIMESTAMP())",[new_id(),user['id'],question_id,anchor_id])
        db.query("UPDATE student_profiles SET preferences=JSON_OBJECT('focus_subject','物理') WHERE user_id=?",[user['id']])
    framework=client.get('/api/v1/knowledge/framework',headers=headers)
    assert framework.status_code==200,framework.text
    value=framework.json()['data'];node=next(n for n in value['nodes'] if n['code']=='sczx.lesson.anchor')
    assert node['question_count']==1 and node['grade']=='初二' and node['chapter']=='第一章'
    assert value['default_subject']=='物理' and value['default_grade']=='初二'
    assert {'code':'sczx.lesson.anchor','prerequisite_code':'sczx.lesson.base'} in value['relations']
    other_node=next(n for n in client.get('/api/v1/knowledge/framework',headers=outsider).json()['data']['nodes'] if n['code']=='sczx.lesson.anchor')
    assert other_node['question_count']==0 and other_node['mastery'] is None
    calls=[]
    def compute(payload,timeout=200):
        calls.append(payload)
        assert timeout==30 and payload['dialogue_cards'][1]['retrieval_role']=='prerequisite'
        return {'explanation':'依据定义逐步说明','check_question':'你能举例吗','can_update_learning':False}
    monkeypatch.setattr(knowledge_lessons,'compute',compute)
    url='/api/v1/knowledge/cards/sczx.lesson.anchor/lessons';body={'request_id':'lesson-1','prompt':' 为什么这样理解 '}
    assert client.post(url,headers=headers,json={'prompt':'缺少编号'}).status_code==422
    first=client.post(url,headers=headers,json=body)
    assert first.status_code==200,first.text
    saved=first.json()['data'];assert saved['prompt']=='为什么这样理解'
    assert client.post(url,headers=headers,json=body).json()['data']['id']==saved['id'] and len(calls)==1
    assert client.post(url,headers=headers,json={**body,'prompt':'不同问题'}).status_code==409
    second=client.post(url,headers=headers,json={'request_id':'lesson-2','prompt':'再举一个例子'})
    assert second.status_code==200 and calls[-1]['knowledge_history'][0]['question']=='为什么这样理解'
    assert client.get(url,headers=outsider).json()['data']==[]
    assert all(item['source_current'] is True for item in client.get(url,headers=headers).json()['data'])
    with Database.from_environment() as db:
        db.query('UPDATE knowledge_points SET updated_at=UTC_TIMESTAMP()+INTERVAL 1 DAY WHERE id=?',[anchor_id])
    assert client.post(url,headers=headers,json=body).json()['data']['id']==saved['id']
    with Database.from_environment() as db:
        db.query("UPDATE knowledge_points SET content=JSON_SET(content,'$.definition','新定义') WHERE id=?",[anchor_id])
    assert client.post(url,headers=headers,json=body).status_code==409
    assert all(item['source_current'] is False for item in client.get(url,headers=headers).json()['data'])
    third=client.post(url,headers=headers,json={'request_id':'lesson-3','prompt':'新定义怎么理解'})
    assert third.status_code==200 and calls[-1]['knowledge_history']==[]
    def unsafe(payload,timeout=200):return {'can_update_learning':True}
    monkeypatch.setattr(knowledge_lessons,'compute',unsafe)
    assert client.post(url,headers=headers,json={'request_id':'unsafe','prompt':'不能凭讲解加分'}).status_code==503
    def stale(payload,timeout=200):
        with Database.from_environment() as db:db.query("UPDATE knowledge_points SET content=JSON_SET(content,'$.definition','再次更新') WHERE id=?",[anchor_id])
        return {'explanation':'旧来源的结果','can_update_learning':False}
    monkeypatch.setattr(knowledge_lessons,'compute',stale)
    assert client.post(url,headers=headers,json={'request_id':'stale','prompt':'生成期间变更'}).status_code==409
    def offline(payload,timeout=200):raise HTTPException(503,'controlled')
    monkeypatch.setattr(knowledge_lessons,'compute',offline)
    unavailable=client.post(url,headers=headers,json={'request_id':'offline','prompt':'暂不可用'})
    assert unavailable.status_code==503 and '可以先查看知识卡' in unavailable.json()['detail']
    with Database.from_environment() as db:
        assert db.query('SELECT COUNT(*) AS n FROM knowledge_lessons WHERE user_id=?',[user['id']]).rows[0]['n']=='3'
        assert db.query('SELECT COUNT(*) AS n FROM mastery_states WHERE user_id=?',[user['id']]).rows[0]['n']=='0'
        db.query("UPDATE questions SET status='archived' WHERE id=?",[question_id])
    node=next(n for n in client.get('/api/v1/knowledge/framework',headers=headers).json()['data']['nodes'] if n['code']=='sczx.lesson.anchor')
    assert node['question_count']==0


def test_system_and_voice_context_files_failure_and_cleanup(client,tmp_path,monkeypatch):
    import base64,hashlib
    from fastapi import HTTPException
    from sczx_api import system,voice
    calls=[]
    def system_compute(p):
        calls.append(p)
        return {'provider':{'last_status':'ready','vision_entries':2},'voice':{'stt':'available','tts':'available'}}
    monkeypatch.setattr(system,'compute',system_compute)
    assert client.get('/api/v1/system/health').json()['data']=={'status':'healthy','database':'mysql','ai':'ready','image_recognition':True}
    assert client.get('/api/v1/system/providers').json()['data']['last_status']=='ready'
    assert client.post('/api/v1/system/providers/probe').status_code==200 and calls[-1]['probe_provider'] is True
    assert client.get('/api/v1/system/voice').json()['data']['tts']=='available'
    user=client.post('/api/v1/auth/register',json={'email':'voice@example.com','password':'secret'}).json()['data']
    other=client.post('/api/v1/auth/register',json={'email':'voice-other@example.com','password':'secret'}).json()['data']
    headers={'Authorization':'Bearer '+user['access_token']};outsider={'Authorization':'Bearer '+other['access_token']}
    question_id=client.post('/api/v1/questions/manual',headers=headers,json={'question_text':'语音作答题'}).json()['data']['id']
    with Database.from_environment() as db:work_id=db.query('SELECT id FROM student_works WHERE question_id=?',[question_id]).rows[0]['id']
    monkeypatch.setenv('SCZX_MEDIA_ROOT',str(tmp_path/'media'));audio=b'controlled-audio'
    def compute(p):
        if p['operation']=='voice_transcribe':return {'text':'我的解题说明','metadata':{'model':'test-stt','duration_ms':12}}
        return {'audio_base64':base64.b64encode(audio).decode(),'sha256':hashlib.sha256(audio).hexdigest(),'metadata':{'model':'test-tts','duration_ms':10}}
    monkeypatch.setattr(voice,'compute',compute)
    assert client.post('/api/v1/voice/synthesize',headers=headers,json={'text':' '}).status_code==400
    assert client.post('/api/v1/voice/synthesize',headers=outsider,json={'text':'朗读','question_id':question_id}).status_code==404
    spoken=client.post('/api/v1/voice/synthesize',headers=headers,json={'text':' 等式两边同时减一 ','question_id':question_id})
    assert spoken.status_code==200,spoken.text
    assert spoken.json()['data']['text']=='等式两边同时减一' and spoken.json()['data']['browser_fallback'] is False
    assert client.get(spoken.json()['data']['audio_url']).content==audio
    url=f'/api/v1/voice/transcribe?question_id={question_id}&work_id={work_id}'
    files={'file':('voice.ogg',b'original-voice','audio/ogg')}
    transcribed=client.post(url,headers=headers,files=files)
    assert transcribed.status_code==200,transcribed.text
    data=transcribed.json()['data']
    assert data['editable'] is True and data['bytes']==14 and data['audio_path'].endswith('.ogg')
    assert client.get(data['audio_url']).content==b'original-voice'
    with Database.from_environment() as db:assert db.query('SELECT explanation FROM student_works WHERE id=?',[work_id]).rows[0]['explanation']=='我的解题说明'
    assert client.post(url,headers=outsider,files=files).status_code==404
    assert client.post(url,headers=headers,files={'file':('empty.webm',b'','audio/webm')}).status_code==400
    def offline(p):raise HTTPException(503,'controlled unavailable')
    monkeypatch.setattr(voice,'compute',offline)
    before=set((tmp_path/'media').rglob('*.*'))
    failed=client.post(url,headers=headers,files=files)
    assert failed.status_code==502 and '转写失败' in failed.json()['detail']
    assert len(set((tmp_path/'media').rglob('*.*'))-before)==1
    with Database.from_environment() as db:
        assert db.query("SELECT COUNT(*) AS n FROM voice_records WHERE user_id=? AND status='failed'",[user['id']]).rows[0]['n']=='1'
    def bad_duration(p):
        result=compute(p);result['metadata']['duration_ms']=-1;return result
    monkeypatch.setattr(voice,'compute',bad_duration);before=set((tmp_path/'media').rglob('*.*'))
    assert client.post('/api/v1/voice/synthesize',headers=headers,json={'text':'测试回滚'}).status_code==422
    assert set((tmp_path/'media').rglob('*.*'))==before


def test_admin_workbench_details_permissions_and_recursive_sanitization(client,monkeypatch):
    import json
    from sczx_api import admin,analysis
    from sczx_api.security import new_id
    student=client.post('/api/v1/auth/register',json={'email':'admin-student@example.com','password':'secret','name':'查看样例学生'}).json()['data']
    administrator=client.post('/api/v1/auth/register',json={'email':'admin-account@example.com','password':'secret'}).json()['data']
    student_headers={'Authorization':'Bearer '+student['access_token']};admin_headers={'Authorization':'Bearer '+administrator['access_token']}
    with Database.from_environment() as db:db.query("UPDATE users SET role='admin' WHERE id=?",[administrator['id']])
    question_id=client.post('/api/v1/questions/manual',headers=student_headers,json={'question_text':'管理员查看题','student_steps':['x=3']}).json()['data']['id']
    record={'subject':'数学','problem_type':'方程','known_conditions':[],'goal':'求x','knowledge_points':['方程'],'prerequisites':[],'final_answer':'1','answer_verified':True,'reference_steps':['x=1']}
    monkeypatch.setattr(analysis,'compute',lambda p:{'analysis':record,'reference_math_valid':[True]})
    client.post('/api/v1/questions/'+question_id+'/analyze',headers=student_headers)
    session=client.post('/api/v1/tutor/sessions',headers=student_headers,json={'question_id':question_id}).json()['data'];run_id=new_id()
    sensitive={'visible':'保留','nested':[{'password':'fake-private','api_key':'fake-key','access_token':'fake-token','chain_of_thought':'fake-reasoning','safe':'显示'}]}
    with Database.from_environment() as db:
        db.query("INSERT INTO agent_runs (id,session_id,agent_name,status,result,created_at,updated_at) VALUES (?,?,'mindtrace_tutor','completed',?,UTC_TIMESTAMP(),UTC_TIMESTAMP())",[run_id,session['id'],json.dumps({'branch':'guided_question','next_goal':'核对依据','observation':sensitive,'plan':{'raw_prompt':'fake-prompt','tool':'knowledge_search'},'verification':{'status':'checked'}})])
        db.query("INSERT INTO agent_tool_calls (id,agent_run_id,tool_name,input_json,output_json,created_at,updated_at) VALUES (?,?,'knowledge_search',?,?,UTC_TIMESTAMP(),UTC_TIMESTAMP())",[new_id(),run_id,json.dumps(sensitive),json.dumps({'safe':True,'authorization':'fake-auth'})])
        db.query("INSERT INTO tutor_turns (id,session_id,role,content,stage,metadata_json,created_at,updated_at) VALUES (?,?,'assistant','核对条件','understanding',?,UTC_TIMESTAMP(),UTC_TIMESTAMP())",[new_id(),session['id'],json.dumps(sensitive)])
        db.query("INSERT INTO review_plans (id,user_id,question_id,due_at,interval_days,reason,status,created_at,updated_at) VALUES (?,?,?,UTC_TIMESTAMP(),1,'复习','pending',UTC_TIMESTAMP(),UTC_TIMESTAMP())",[new_id(),student['id'],question_id])
    monkeypatch.setattr(admin,'compute',lambda p:{'provider':{'logical_model':'test-model','total_entries':2,'text_entries':2,'vision_entries':1,'last_status':'ready','api_key':'fake-private'},'voice':{'status':'ready','loaded':False,'stt_model':'test','tts_model':'test','secret':'fake-private'}})
    assert client.get('/api/v1/admin/workbench').status_code==401
    assert client.get('/api/v1/admin/workbench',headers=student_headers).status_code==403
    workbench=client.get('/api/v1/admin/workbench',headers=admin_headers)
    assert workbench.status_code==200,workbench.text
    value=workbench.json()['data']
    assert value['generated_at'].endswith('+00:00') and value['metrics']['students']>=1
    assert any(s['id']==student['id'] and s['question_count']==1 for s in value['students'])
    assert value['system']['provider']['status']=='ready'
    detail=client.get('/api/v1/admin/students/'+student['id'],headers=admin_headers)
    assert detail.status_code==200,detail.text
    assert detail.json()['data']['metrics']=={'questions':1,'sessions':1,'pending_reviews':1}
    assert detail.json()['data']['student']['name']=='查看样例学生'
    session_detail=client.get('/api/v1/admin/sessions/'+session['id'],headers=admin_headers)
    assert session_detail.status_code==200,session_detail.text
    result=session_detail.json()['data']
    run=next(r for r in result['trace'] if r['id']==run_id)
    assert run['agent']=='教学决策智能体' and run['decision']=='引导式提问'
    assert run['observation']=={'visible':'保留','nested':[{'safe':'显示'}]}
    assert run['actions'][0]['tool']=='知识检索' and run['actions'][0]['output']=={'safe':True}
    assert next(t for t in result['turns'] if t['content']=='核对条件')['decision']['nested']==[{'safe':'显示'}]
    serialized=json.dumps([value,detail.json()['data'],result],ensure_ascii=False)
    for hidden in ['fake-private','fake-key','fake-token','fake-reasoning','fake-prompt','fake-auth','password_hash','admin-student@example.com']:
        assert hidden not in serialized
    assert client.get('/api/v1/admin/students/'+student['id'],headers=student_headers).status_code==403
    assert client.get('/api/v1/admin/students/'+new_id(),headers=admin_headers).status_code==404
    assert client.get('/api/v1/admin/sessions/'+new_id(),headers=admin_headers).status_code==404


def test_papers_real_rendering_ownership_and_transaction_rollback(client,monkeypatch,tmp_path):
    from io import BytesIO
    from openpyxl import load_workbook
    from sczx_api import paper_exports,analysis
    monkeypatch.syspath_prepend(str(Path('sczx/algorithms').resolve()))
    from paper_export_compute import ExportQuestion,render_paper
    monkeypatch.setenv('SCZX_MEDIA_ROOT',str(tmp_path/'media'))
    def register(email):
        user=client.post('/api/v1/auth/register',json={'email':email,'password':'secret'}).json()['data']
        return {'Authorization':'Bearer '+user['access_token']}
    headers=register('paper-owner@example.com');other=register('paper-other@example.com')
    def question(auth,text):
        response=client.post('/api/v1/questions/manual',headers=auth,json={'question_text':text,'subject':'数学'})
        assert response.status_code==200,response.text
        return response.json()['data']['id']
    qid=question(headers,'求方程 x+1=2 的解');foreign=question(other,'其他学生的题')
    candidate=client.get('/api/v1/papers/candidates',headers=headers).json()['data']
    assert [q['id'] for q in candidate]==[qid]
    assert client.get('/api/v1/papers/candidates?mastery_min=2',headers=headers).status_code==422
    created=client.post('/api/v1/papers',headers=headers,json={'title':'错题巩固','default_score':15})
    assert created.status_code==200,created.text
    paper=created.json()['data'];url='/api/v1/papers/'+paper['id']
    detail=client.get(url,headers=headers).json()['data']
    assert detail['items'][0]['question_id']==qid and detail['items'][0]['score']==15
    assert detail['items'][0]['analysis_ready'] is False
    assert client.get(url,headers=other).status_code==404
    assert client.post(url+'/export',headers=headers,json={'kind':'answer'}).status_code==409
    failed=client.patch(url,headers=headers,json={'title':'不能留下的修改','items':[{'question_id':foreign}]})
    assert failed.status_code==404
    assert client.get(url,headers=headers).json()['data']['title']=='错题巩固'
    record={'subject':'数学','problem_type':'方程','known_conditions':[],'goal':'求x','knowledge_points':['方程'],'prerequisites':[],'final_answer':'1','answer_verified':True,'reference_steps':['x=2-1=1']}
    monkeypatch.setattr(analysis,'compute',lambda p:{'analysis':record,'reference_math_valid':[True]})
    assert client.post('/api/v1/questions/'+qid+'/analyze',headers=headers).status_code==200
    assert client.get(url,headers=headers).json()['data']['items'][0]['analysis_ready'] is True
    assert client.get('/api/v1/papers/candidates?knowledge_point=方程',headers=headers).json()['data'][0]['id']==qid
    assert client.get('/api/v1/papers/candidates?knowledge_point=几何',headers=headers).json()['data']==[]
    assert client.get('/api/v1/papers/candidates?due_review=true',headers=headers).json()['data']==[]
    assert client.get('/api/v1/papers/candidates?mastery_min=0.5',headers=headers).json()['data']==[]
    replacement=client.patch(url,headers=headers,json={'items':[{'question_id':qid,'score':20},{'question_id':qid,'score':5}]})
    assert replacement.status_code==200,replacement.text
    assert [i['score'] for i in replacement.json()['data']['items']]==[20,5]
    assert client.patch(url,headers=headers,json={'items':[{'question_id':qid,'score':101}]}).status_code==422
    def render(payload):
        assert payload['operation']=='render_paper'
        return render_paper(payload['paper_title'],payload['paper_kind'],[ExportQuestion.model_validate(q) for q in payload['paper_questions']])
    monkeypatch.setattr(paper_exports,'compute',render)
    for kind in ['question','answer','excel']:
        exported=client.post(url+'/export',headers=headers,json={'kind':kind})
        assert exported.status_code==200,exported.text
        job=exported.json()['data'];signed=client.get(job['url'])
        assert signed.status_code==200,signed.text
        download=client.get(url+'/download?kind='+kind,headers=headers)
        assert download.status_code==200 and download.content==signed.content
        assert client.get(url+'/download?kind='+kind,headers=other).status_code==404
        if kind=='excel':
            workbook=load_workbook(BytesIO(download.content))
            assert any('求方程 x+1=2 的解' in str(cell) for row in workbook.active.values for cell in row)
        else:assert download.content.startswith(b'%PDF-')
    assert len(client.get(url,headers=headers).json()['data']['exports'])==3
    def corrupted(payload):
        result=render(payload);result['sha256']='0'*64;return result
    monkeypatch.setattr(paper_exports,'compute',corrupted)
    before=set((tmp_path/'media').rglob('*.*'))
    assert client.post(url+'/export',headers=headers,json={}).status_code==503
    assert set((tmp_path/'media').rglob('*.*'))==before
    assert len(client.get(url,headers=headers).json()['data']['exports'])==3
    assert client.post(url+'/export',headers=headers,json={'kind':'invalid'}).status_code==422
    assert client.delete(url,headers=other).json()['data']=={'deleted':False}
    assert client.delete(url,headers=headers).json()['data']=={'deleted':True}
    assert client.delete(url,headers=headers).json()['data']=={'deleted':False}
    assert client.get(url,headers=headers).status_code==404
