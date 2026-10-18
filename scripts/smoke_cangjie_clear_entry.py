"""An isolated learner for the correct-answer browser entry scenario.

The native ingestion learner is intentionally reused by memory mutation tests.
Its context may legitimately change while a browser task computes. This fixture
tests the stable correct-answer entry, without weakening the production guard.
"""
from uuid import uuid4

from smoke_cangjie_accounts import request
from smoke_cangjie_detail import fixture_insert


def clear_entry_fixture(endpoint, env, query):
    assert env['CANGJIE_DB_NAME'].startswith('zhiwei_cangjie_test')
    user = request(endpoint, 'POST', '/api/v1/auth/register', {
        'email': f'clear-entry-{uuid4().hex}@example.test',
        'password': 'Clear-entry-' + uuid4().hex,
        'name': '正确作答入口验收', 'grade': '初一',
    })
    token = user['access_token']
    question = request(endpoint, 'POST', '/api/v1/questions/manual', {
        'question_text': '解方程：2x+3=11', 'subject': '数学', 'grade': '初一',
        'student_answer': 'x=4', 'student_steps': ['2x=8', 'x=4'],
    }, token=token)
    insert = fixture_insert(env, query)
    analysis = insert('problem_analyses', question_id=question['id'], subject='数学', final_answer='x=4')
    insert('reference_steps', analysis_id=analysis, step_index=0, text='2x=8')
    insert('reference_steps', analysis_id=analysis, step_index=1, text='x=4')
    insert('diagnoses', question_id=question['id'], error_type='exact', first_error_step=None, root_misconception='')
    return question['id'], token
