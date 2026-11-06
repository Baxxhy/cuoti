import pytest
from sczx_api.tutor_core import teaching_policy, transition, previous_stage, canonical_stage, understanding_plan, public_activity, public_progress


def test_policy_routes_short_and_full_questions():
    assert teaching_policy('单选题',True,True,'A')['mode']=='compressed'
    assert teaching_policy('综合题',False,True,'1')['mode']=='full'
    assert teaching_policy('综合题',False,False,'1')['mode']=='compressed'
    assert teaching_policy('填空题',False,False,'')['mode']=='full'
    assert teaching_policy('other',True,False,'A')['question_type']=='choice'


def test_stage_gates_and_legacy_aliases():
    assert canonical_stage('teach_back_retry')=='teach_back'
    assert canonical_stage('near_remediation')=='near_transfer'
    assert transition('understanding','understanding_advance',True)=='teach_back'
    with pytest.raises(ValueError,match='需要先通过理解检查'): transition('understanding','understanding_advance',False)
    assert transition('teach_back','teach_back_fail',False)=='teach_back'
    assert transition('far_transfer','far_pass',True)=='finished'
    assert previous_stage('near_transfer')=='teach_back'
    with pytest.raises(ValueError): previous_stage('finished')


def test_activities_preserve_tex_and_hide_grading_keys():
    formula='$'+'x'*60+'$'
    plan=understanding_plan('方程','数学','综合题',['方程'],[formula])
    assert plan[1]['options'][0]['label']==formula
    shown=public_activity(plan[0],1)
    assert 'correct_answers' not in shown and 'hint' not in shown
    assert shown['attempt']==1 and shown['max_attempts']==2
    assert public_progress({'understood':False,'understanding_plan':plan,'private_answer':'secret'})=={'understood':False}
    cube=understanding_plan('正方体展开图','数学','综合题',[],[])
    assert cube[0]['question'] != plan[0]['question']
    assert len(cube) == 3
