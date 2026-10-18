"""Release input partitions on an isolated real MySQL database, no real model calls."""
import json
import re
from itertools import product
from pathlib import Path

from smoke_cangjie_accounts import request
from smoke_cangjie_detail import fixture_insert
from smoke_cangjie_experience import experience_fixtures


def release_inputs(endpoint, env, query):
    fixture = experience_fixtures(endpoint, env, query)
    token, owner = fixture['user']['access_token'], fixture['user']['id']
    qid = fixture['ids'][0]
    failures = []
    count = 0

    def check(label, method, path, payload):
        nonlocal count
        count += 1
        result = request(endpoint, method, path, payload, token=token, expected=(200, 422))
        if isinstance(result, dict):
            failures.append(label)
            print('unexpected acceptance: '+label, flush=True)

    diagnosis = '/api/v1/questions/'+qid+'/diagnosis'
    for value in [-1, 2, 3, 99, 2147483647, 2147483648, 0.5, True, False, '0', [], {}, '']:
        check('diagnosis-step-'+repr(value), 'PATCH', diagnosis, {'first_error_step':value})
    for value in ['', ' ', 'not-a-cause', 'sign_error ', 'SIGN_ERROR', "'; DROP TABLE diagnoses; --", None, 5, True, [], {}]:
        check('diagnosis-type-'+repr(value), 'PATCH', diagnosis, {'error_type':value})
    for payload in [{}, {'user_confirmed':True}, {'question_id':qid}, {'made_up':'ignored'}]:
        check('diagnosis-no-edit-'+str(count), 'PATCH', diagnosis, payload)
    for value in [None, [], {}, 123, True, 'x'*12001]:
        check('diagnosis-root-'+str(count), 'PATCH', diagnosis, {'root_misconception':value})
    for value in [-0.1, 1.1, 'NaN', 'Infinity', [], {}, None]:
        check('diagnosis-confidence-'+str(count), 'PATCH', diagnosis, {'confidence':value})

    before = request(endpoint, 'GET', diagnosis, token=token)
    check('diagnosis-mixed-invalid-atomic', 'PATCH', diagnosis,
          {'first_error_step':99, 'root_misconception':'must-not-save'})
    after = request(endpoint, 'GET', diagnosis, token=token)
    if before != after:
        failures.append('diagnosis-invalid-request-mutated-record')

    manual = '/api/v1/questions/manual'
    for value in ['', ' ', '\t\n', '\u3000', '\xa0', '\u2003', None, True, 9, [], {}, '题'*12001]:
        check('manual-stem-'+str(count), 'POST', manual, {'question_text':value})
    for value in ['', ' ', '\u3000', '\xa0', None, True, 9, [], {}, '步'*12001]:
        check('manual-step-'+str(count), 'POST', manual, {'question_text':'输入边界题'+str(count), 'student_steps':[value]})
    for value in [None, 'AB', ['A'], [{'label':'A','text':'1'}, {'label':'A','text':'2'}]]:
        check('manual-options-'+str(count), 'POST', manual,
              {'question_text':'选项边界', 'question_type':'单选题', 'options':value})

    edit = request(endpoint, 'POST', manual, {'question_text':'不能被空输入清除的原题'}, token=token)
    for value in ['', ' ', '\t\n', '\u3000', '\xa0']:
        check('edit-empty-stem-'+str(count), 'PATCH', '/api/v1/questions/'+edit['id'], {'question_text':value})
    choices = request(endpoint, 'POST', manual, {
        'question_text':'选项编辑边界', 'question_type':'单选题',
        'options':[{'label':'A','text':'1'},{'label':'B','text':'2'}],
    }, token=token)
    for options in [[], [{'label':'A','text':'1'}], [{'label':'A','text':'1'},{'label':'A','text':'2'}]]:
        check('edit-choice-shape-'+str(count), 'PATCH', '/api/v1/questions/'+choices['id'], {'options':options})

    preferences = '/api/v1/student-preferences'
    base = {'subject':'数学','minutes':10,'goal':'understand','version':0}
    for field, values in {
        'minutes':[-1,0,1,5.5,30,True,False,None,'10',[],{}],
        'subject':['', ' ', '未设置', None,1,True,[],{}],
        'goal':['', 'other',None,1,True,[],{}],
    }.items():
        for value in values:
            check('preferences-'+field+'-'+str(count), 'PATCH', preferences, {**base, field:value})
    assert request(endpoint, 'GET', preferences, token=token)['version'] == 0
    valid_preferences = 0
    for valid_preferences, (subject, minutes, goal) in enumerate(product(['数学','英语','物理'], [5,10,20], ['understand','practice','review']), start=1):
        saved = request(endpoint, 'PATCH', preferences,
                        {'subject':subject,'minutes':minutes,'goal':goal,'version':valid_preferences-1}, token=token)
        assert saved['version'] == valid_preferences
        assert (saved['subject'],saved['minutes'],saved['goal']) == (subject,minutes,goal)
        assert request(endpoint, 'GET', preferences, token=token) == saved
    constants = (Path(__file__).resolve().parents[1]/'frontend/src/constants/education.js').read_text()
    codes = re.findall(r'^  (\w+):', constants.split('ERROR_TYPE_LABELS = {',1)[1].split('\n}',1)[0], re.MULTILINE)
    for code in codes:
        corrected = request(endpoint, 'PATCH', diagnosis,
                            {'error_type':code,'first_error_step':None if code in ('exact','equivalent') else 0}, token=token)
        assert corrected['error_type'] == code
    corrected = request(endpoint, 'PATCH', diagnosis, {'first_error_step':1}, token=token)
    assert corrected['first_error_text'] == 'x=7'
    snapshot = request(endpoint, 'GET', diagnosis, token=token)
    assert request(endpoint, 'PATCH', diagnosis, {'error_type':'exact','first_error_step':0}, token=token, expected=422) == 422
    assert request(endpoint, 'GET', diagnosis, token=token) == snapshot
    cleared = request(endpoint, 'PATCH', diagnosis, {'error_type':'exact'}, token=token)
    assert cleared['first_error_step'] is None and cleared['first_error_text'] == ''
    legacy = {'verification_method':'qwen_proposal_sympy_check', 'root_cause_confirmed':True,
              'status':'confirmed','confidence':0.95}
    entry = fixture_insert(env, query)('diagnosis_evidence', diagnosis_id=cleared['id'],
                                      kind='counterfactual_validation', content='历史验证声明测试', metadata_json=legacy)
    for path in [diagnosis, '/api/v1/questions/'+qid]:
        value = request(endpoint, 'GET', path, token=token)
        counter = value.get('diagnosis',value)['counterfactual']
        assert counter['legacy_review_required'] and not counter['root_cause_confirmed']
    cached = request(endpoint, 'POST', diagnosis+'/counterfactual', {}, token=token)
    assert cached['legacy_review_required'] and not cached['root_cause_confirmed']
    assert json.loads(query(env, "SELECT metadata_json FROM diagnosis_evidence WHERE id='"+entry+"'")) == legacy
    shifted = '/api/v1/questions/'+fixture['ids'][1]+'/diagnosis'
    request(endpoint, 'PATCH', shifted, {'first_error_step':1}, token=token)
    shifted_id = request(endpoint, 'GET', shifted, token=token)['id']
    fixture_insert(env, query)('diagnosis_evidence', diagnosis_id=shifted_id,
        kind='counterfactual_validation', content='原首错证据夹具', metadata_json={
            'suspected_step':0,'status':'confirmed','root_cause_confirmed':True,
            'validation_scope':'polynomial_real_solution_set_and_preserved_prefix',
            'verification_method':'reference_repair_sympy_check'})
    for path in [shifted, '/api/v1/questions/'+fixture['ids'][1]]:
        value = request(endpoint, 'GET', path, token=token)
        counter = value.get('diagnosis',value)['counterfactual']
        assert counter['stale_after_correction'] and not counter['root_cause_confirmed']
    cached = request(endpoint, 'POST', shifted+'/counterfactual', {}, token=token)
    assert cached['stale_after_correction'] and not cached['root_cause_confirmed']
    raw = json.loads(query(env, "SELECT metadata_json FROM diagnosis_evidence WHERE diagnosis_id='"+shifted_id+"' AND kind='counterfactual_validation' LIMIT 1"))
    assert 'stale_after_correction' not in raw
    assert query(env, "SELECT COUNT(*) FROM cognitive_updates WHERE user_id='"+owner+"'").strip() == '0'
    print(json.dumps({'suite':'release-inputs','invalid_requests':count,
                      'valid_preference_combinations':valid_preferences,'valid_diagnosis_types':len(codes),
                      'unexpected_acceptance':failures}, ensure_ascii=False), flush=True)
    assert not failures, f'{len(failures)} input partition failures; see labelled cases above'
