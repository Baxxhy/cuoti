"""Independent students for browser role-play; never seed the application database."""
from uuid import uuid4

from smoke_cangjie_accounts import request
from smoke_cangjie_detail import fixture_insert
from smoke_cangjie_experience import experience_fixtures


def persona_fixtures(endpoint, env, query):
    repair = experience_fixtures(endpoint, env, query)
    insert = fixture_insert(env, query)
    diagnosis_id = query(env, "SELECT id FROM diagnoses WHERE question_id='"+repair['ids'][0]+"'").strip()
    query(env, "UPDATE diagnoses SET recommended_strategy='等式两边先减去3。' WHERE id='"+diagnosis_id+"'")
    insert('diagnosis_evidence', diagnosis_id=diagnosis_id,
           kind='counterfactual_validation', content='人工修正关联的隔离证据夹具',
           metadata_json={'suspected_step':0, 'status':'confirmed',
                          'root_cause_confirmed':True, 'corrected_step':'2x=8',
                          'verification_method':'reference_repair_sympy_check',
                          'validation_scope':'polynomial_real_solution_set_and_preserved_prefix'})
    password = 'Persona-' + uuid4().hex
    user = request(endpoint, 'POST', '/api/v1/auth/register', {
        'email': f'persona-review-{uuid4().hex}@example.test', 'password':password,
        'name':'模拟复习学生', 'grade':'初一',
    })
    review = {'user':user, 'password':password, 'ids':[]}
    # Keep the review fixtures pedagogically consistent. Multi-line process
    # grading still requires a provider; the focused browser submits a final
    # answer for rule grading after separately checking multi-line drafts.
    for stem, answer, correct, wrong in [
        ('解方程：2x+3=11', 'x=4', '2x=8', '2x=11+3'),
        ('解方程：3x+2=17', 'x=5', '3x=15', '3x=17+2'),
    ]:
        question = request(endpoint, 'POST', '/api/v1/questions/manual', {
            'question_text':stem, 'student_answer':'x=7', 'student_steps':[wrong, 'x=7'],
            'subject':'数学', 'grade':'初一',
        }, token=user['access_token'])
        qid = question['id']
        review['ids'].append(qid)
        analysis = insert('problem_analyses', question_id=qid, subject='数学',
                          final_answer=answer, verified=True, knowledge_points=['等式的性质'])
        insert('reference_steps', analysis_id=analysis, step_index=0, text=correct)
        insert('reference_steps', analysis_id=analysis, step_index=1, text=answer)
        insert('diagnoses', question_id=qid, first_error_step=0, error_type='sign_error',
               root_misconception='移项需要改变符号')
    plans = []
    for index, qid in enumerate(review['ids']):
        plans.append(insert('review_plans', user_id=review['user']['id'],
                            question_id=qid, due_at=f'2026-01-0{index+1} 00:00:00',
                            interval_days=1, status='pending', reason='again'))
    result = {}
    for name, actor in [('REPAIR', repair), ('REVIEW', review)]:
        result[f'QA_PERSONA_{name}_EMAIL'] = actor['user']['email']
        result[f'QA_PERSONA_{name}_PASSWORD'] = actor['password']
        for index, qid in enumerate(actor['ids']):
            result[f'QA_PERSONA_{name}_QUESTION_{index+1}'] = qid
    result['QA_PERSONA_REVIEW_PLAN_2'] = plans[1]
    return result


def verify_personas(endpoint, env, query):
    """Focused rerun using the same disposable MySQL/algorithm harness."""
    import socket
    import subprocess
    from pathlib import Path
    from urllib.parse import urlsplit

    root = Path(__file__).resolve().parents[1]
    subprocess.run(['bash', 'scripts/cangjie.sh', 'seed-knowledge'], cwd=root, env=env, check=True)
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        port = listener.getsockname()[1]
    browser_env = {**env, **persona_fixtures(endpoint, env, query),
                   'ZHIWEI_BACKEND_KIND':'cangjie',
                   'ZHIWEI_BACKEND_PORT':str(urlsplit(endpoint).port),
                   'ZHIWEI_BACKEND_URL':endpoint, 'ZHIWEI_API_URL':endpoint+'/api/v1',
                   'ZHIWEI_FRONTEND_PORT':str(port),
                   'ZHIWEI_FRONTEND_URL':f'http://127.0.0.1:{port}'}
    subprocess.run(['pnpm', '--dir', 'frontend', 'run', 'test:e2e', 'student-personas.spec.ts'],
                   cwd=root, env=browser_env, check=True)
    print('Three simulated student browser flows passed against disposable Cangjie/MySQL')
