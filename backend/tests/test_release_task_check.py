"""A read-only release audit must never complete the task it is auditing."""
import importlib.util
import json
from pathlib import Path

import httpx
import pytest


@pytest.mark.parametrize('status', ['waiting_student', 'queued', 'running', 'stale', 'cancelled', 'failed', 'completed'])
def test_existing_task_audit_does_not_submit_or_rewrite_report(tmp_path, monkeypatch, status):
    source = Path(__file__).resolve().parents[2] / 'scripts/check_live_release_task.py'
    spec = importlib.util.spec_from_file_location('release_task_check', source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, '__file__', str(tmp_path / 'scripts/check_live_release_task.py'))
    runtime = tmp_path / '.runtime'
    runtime.mkdir()
    (runtime / 'student-personas-accounts.json').write_text(json.dumps([
        {'name': '乙', 'email': 'audit@example.test', 'password': 'test-only', 'question_id': 'q1'},
    ]))
    report = runtime / 'release-live-task.json'
    report.write_text(json.dumps({'task_id': 't1', 'steps': [{}, {}, {}], 'passed': True}))
    original = report.read_bytes()
    calls = []

    class Client:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def request(self, method, url, **kwargs):
            calls.append((method, url))
            if url == '/auth/login':
                data = {'access_token': 'test-only'}
            elif url == '/learning-tasks/t1':
                data = {'id': 't1', 'question_id': 'q1', 'status': status}
            elif url == '/learning-tasks/t1/history':
                data = {'items': [{'phase': phase, 'verdict': 'confirmed_correct'}
                                  for phase in ['repair', 'independent', 'contrast']]}
            elif url == '/questions/q1/journey':
                data = {'learning_tasks': {'repair_verified': True, 'original_independent': True, 'near_transfer': True},
                        'stages': [{'key': 'transfer', 'completed': False}]}
            elif url == '/questions/q1':
                data = {'student_answer': 'x=7'}
            else:
                pytest.fail('Unexpected request: ' + method + ' ' + url)
            return httpx.Response(200, json={'data': data})

    monkeypatch.setattr(module.httpx, 'Client', Client)
    if status == 'completed':
        module.main(verify_existing=True)
    else:
        with pytest.raises(RuntimeError, match='只读复核要求任务已完成'):
            module.main(verify_existing=True)
    assert report.read_bytes() == original
    assert all(method == 'GET' or (method, url) == ('POST', '/auth/login') for method, url in calls)
    if status != 'completed':
        assert calls == [('POST', '/auth/login'), ('GET', '/learning-tasks/t1')]
