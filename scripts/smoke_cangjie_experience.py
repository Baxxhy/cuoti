"""Student preferences and source projection on disposable, real MySQL only."""
from datetime import datetime, timezone
from urllib.parse import quote
from uuid import uuid4

from smoke_cangjie_accounts import request
from smoke_cangjie_detail import fixture_insert


def experience_fixtures(endpoint, env, query):
    assert env['CANGJIE_DB_NAME'].startswith('zhiwei_cangjie_test')
    insert = fixture_insert(env, query)
    now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
    password = 'Experience-' + uuid4().hex
    user = request(endpoint, 'POST', '/api/v1/auth/register', {
        'email': f'experience-{uuid4().hex}@example.test', 'password': password,
        'name': '产品验收同学', 'grade': '初一',
    })
    token = user['access_token']
    ids = []
    for stem in ['解方程：2x+3=11', '解方程2x+3=11，并验算所得结果']:
        question = request(endpoint, 'POST', '/api/v1/questions/manual', {
            'question_text': stem, 'student_answer': 'x=7',
            'student_steps': ['2x=11+3', 'x=7'], 'subject': '数学', 'grade': '初一',
        }, token=token)
        qid = question['id']; ids.append(qid)
        analysis = insert('problem_analyses', question_id=qid, subject='数学',
                          final_answer='x=4', knowledge_points=['等式的性质'])
        ref = insert('reference_steps', analysis_id=analysis, step_index=1, text='2x=8')
        insert('reference_steps', analysis_id=analysis, step_index=0, text='x=4')
        diagnosis = insert('diagnoses', question_id=qid, first_error_step=0,
                           error_type='sign_error', root_misconception='移项时应改变符号',
                           created_at=now, updated_at=now)
        step = query(env, "SELECT s.id FROM student_steps s JOIN student_works w ON w.id=s.work_id WHERE w.question_id='" + qid + "' ORDER BY s.step_index LIMIT 1").strip()
        insert('diagnosis_evidence', diagnosis_id=diagnosis, kind='step_alignment',
               student_step_id=step, reference_step_id=ref, content='移项符号核对',
               metadata_json={'student_step_id':step,'reference_step_id':ref,'reason':'等式两边应同时减去3','is_first_error':True})
    return {'user':user,'password':password,'ids':ids}


def experience(endpoint, env, query):
    fixture = experience_fixtures(endpoint, env, query)
    token = fixture['user']['access_token']; qid = fixture['ids'][0]
    path = '/api/v1/student-preferences'
    request(endpoint,'GET',path,expected=401)
    initial = request(endpoint,'GET',path,token=token)
    assert initial == {'grade':'初一','subject':'','minutes':10,'goal':'understand','version':0}
    body = {'subject':'数学','minutes':5,'goal':'practice','version':0}
    saved = request(endpoint,'PATCH',path,body,token=token)
    assert saved['subject']=='数学' and saved['minutes']==5 and saved['version']==1
    assert request(endpoint,'GET',path,token=token)==saved
    request(endpoint,'PATCH',path,body,token=token,expected=409)
    request(endpoint,'PATCH',path,{**body,'version':1,'minutes':5.5},token=token,expected=422)
    request(endpoint,'PATCH',path,{**body,'version':1,'subject':'不存在'},token=token,expected=422)
    request(endpoint,'PATCH',path,{**body,'version':1,'user_id':fixture['user']['id']},token=token,expected=422)
    projection='/api/v1/analytics/error-sources?days=90'
    request(endpoint,'GET',projection,expected=401)
    sources=request(endpoint,'GET',projection,token=token)
    assert {source['id'] for source in sources['sources']}==set(fixture['ids'])
    assert all(source['diagnosis']['root_misconception']=='移项时应改变符号' for source in sources['sources'])
    assert request(endpoint,'GET',projection+'&subject='+quote('物理'),token=token)['sources']==[]
    request(endpoint,'GET','/api/v1/analytics/error-sources?days=0',token=token,expected=422)
    other=request(endpoint,'POST','/api/v1/auth/register',{'email':f'other-{uuid4().hex}@example.test','password':'Other-123456','grade':'高一'})
    assert request(endpoint,'GET',projection,token=other['access_token'])['sources']==[]
    request(endpoint,'GET','/api/v1/questions/'+qid,token=other['access_token'],expected=404)
    request(endpoint,'DELETE','/api/v1/questions/'+qid,token=token)
    assert qid not in {source['id'] for source in request(endpoint,'GET',projection,token=token)['sources']}
    assert query(env,"SELECT COUNT(*) FROM cognitive_updates WHERE user_id='"+fixture['user']['id']+"'").strip()=='0'
    print('Student experience passed: MySQL preferences/version conflict, bounded source projection, user isolation and archive removal; no learning evidence from reads/settings')
