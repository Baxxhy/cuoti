import copy
import pytest
from fastapi import HTTPException
from sczx_api.task_policy import TaskBudget,TaskBudgetExceeded,at_limit,visual_values,validate_visual_action
from sczx_api.task_sources import source_equal
from sczx_api.task_planning import bank_row,validate_recommendation


def test_deadline_shared_across_stages_and_reserves_commit_time():
    now=[100.]
    budget=TaskBudget(started=60,clock=lambda:now[0])
    assert budget.elapsed_ms()==40000 and budget.timeout_seconds(40,reserve_seconds=1)==4
    now[0]=104.1
    with pytest.raises(TaskBudgetExceeded,match='结果未提交') as failure:budget.timeout_seconds(5,reserve_seconds=1)
    assert failure.value.stage=='remaining_budget'
    now[0]=106.
    with pytest.raises(TaskBudgetExceeded) as failure:budget.check('before_commit')
    assert failure.value.stage=='before_commit'
    for rounds,runs,expected in [(23,71,False),(24,2,True),(3,72,True)]:
        assert at_limit({'run_count':runs,'checkpoint':{'rounds':rounds}}) is expected


def test_original_source_numeric_transport_rule_keeps_bools_and_order_distinct():
    original={'steps':[{'id':'s1','confidence':1.,'confirmed':True}]}
    assert source_equal(original,{'steps':[{'confirmed':True,'confidence':1,'id':'s1'}]})
    for step in [{'id':'s2','confidence':1,'confirmed':True},{'id':'s1','confidence':.9,'confirmed':True},{'id':'s1','confidence':1,'confirmed':1}]:
        assert not source_equal(original,{'steps':[step]})
    assert not source_equal([1,2],[2,1]) and not source_equal('1',1)
    assert not source_equal(9007199254740993,9007199254740992)


def test_visual_admission_uses_current_phase_bounds_and_slider_step():
    task={'student_view':{'input_kind':'text'},'checkpoint':{'phase':'repair','visual_open':True,'visualization':{'source_phase':'repair','spec':{'interactive_variables':[{'name':'delta','min':-1,'max':1,'step':.25}]}}}}
    values=visual_values({'visual_values':{'delta':.5}})
    validate_visual_action(task,{'visual_values':{'delta':.5}},'observe_visualization',values)
    for raw in [None,{'delta':True},{'unknown':0},{'delta':float('nan')},{'delta':100000001},{'a':1,'b':2,'k':3,'h':4}]:
        with pytest.raises(HTTPException) as error:visual_values({'visual_values':raw})
        assert error.value.status_code==422
    for values in [{},{'k':.5},{'delta':1.25},{'delta':.1}]:
        with pytest.raises(HTTPException):validate_visual_action(task,{'visual_values':values},'observe_visualization',values)
    for kind in ['answer','close_visualization']:
        with pytest.raises(HTTPException):validate_visual_action(task,{'visual_values':{}},kind,{})
    old=copy.deepcopy(task);old['checkpoint']['phase']='contrast'
    with pytest.raises(HTTPException) as error:validate_visual_action(old,{},'close_visualization',{})
    assert error.value.status_code==409


def test_recommendation_stays_inside_server_owned_candidates():
    assert bank_row({'id':'bank-1','subject':'数学','recent_n':'2','recent_pass':'1'})=={'id':'bank-1','subject':'数学'}
    domain={'practice_candidates':[{'id':'q1','source':'dataset','just_mastered':False},{'id':'q2','source':'notebook'},{'id':'q3','source':'dataset','just_mastered':True}]}
    def result(qid='q1',source='dataset',alternatives=()):return {'student_view':{'recommendation':{'question_id':qid,'question_source':source,'alternatives':list(alternatives)}}}
    validate_recommendation(result(alternatives=['q2']),domain)
    for value in [result('outside'),result(source='notebook'),result(alternatives=['outside']),result(alternatives=['q1']),result(alternatives=['q3']),result('q3')]:
        with pytest.raises(HTTPException) as error:validate_recommendation(value,domain)
        assert error.value.status_code==503
