import hashlib
import json
import threading
import time
import pymysql
from fastapi import HTTPException
from .algorithm import compute
from .database import Database
from .learning_evidence import apply_evidence
from .memory_sources import task_snapshot
from .practice_context import equivalent
from .rows import row_json
from .security import new_id
from .task_context import context
from .task_core import task_row,validate_version
from .task_images import compute_action,save_result as save_image_result,retain_for_support
from .task_mastery import apply_aemt
from .task_planning import validate_recommendation
from .task_policy import TaskBudget,TaskBudgetExceeded,at_limit,stop_at_limit,stopped_view,object_value
from .task_sources import source,attempt_source,TaskSourceError


def lease_valid(task,lease):return task['status']=='running' and task.get('lease_token')==lease and task.get('cancel_requested') is not True


def preparation_failure(db,task,reason):
    view=stopped_view('暂时未能准备题目，内容已保留，可以重试');view['secondary_actions']=['resume'];photo=object_value(object_value(task,'student_view'),'handwriting')
    if photo:view['handwriting']=photo
    db.query("UPDATE learning_tasks SET status='failed',version=version+1,student_view=?,exit_reason=?,lease_token=NULL,lease_until=NULL,updated_at=UTC_TIMESTAMP(6) WHERE id=?",[json.dumps(view,ensure_ascii=False),reason,task['id']])
    db.query("UPDATE learning_task_actions SET status='failed',updated_at=UTC_TIMESTAMP(6) WHERE task_id=? AND status='pending'",[task['id']])


def claim(task_id,budget):
    with Database.from_environment() as db:
        rows=db.query('SELECT user_id,question_id FROM learning_tasks WHERE id=?',[task_id]).rows
        if not rows:return None
        owner=rows[0]['user_id'];qid=rows[0]['question_id']
        with db.transaction():
            snapshot=task_snapshot(db,qid,owner,lock=True);task=task_row(db,task_id,owner,True)
            claimable=db.query("SELECT id FROM learning_tasks WHERE id=? AND cancel_requested=0 AND (status='queued' OR (status='running' AND lease_until<UTC_TIMESTAMP(6)))",[task_id]).rows
            if not claimable or not validate_version(db,task,snapshot):return None
            if at_limit(task):stop_at_limit(db,task,'retry_budget' if task['run_count']>=72 else 'round_budget');return None
            db.query('UPDATE learning_tasks SET run_count=run_count+1 WHERE id=?',[task_id]);lease=new_id()
            try:captured=source(db,task,snapshot)
            except TaskSourceError as error:
                db.query("UPDATE learning_tasks SET status='failed',version=version+1,student_view=?,exit_reason=?,lease_token=NULL,lease_until=NULL,updated_at=UTC_TIMESTAMP(6) WHERE id=?",[json.dumps(stopped_view('任务来源无法核对，请结束本次学习后回原题重开；旧记录仍保留'),ensure_ascii=False),error.reason,task_id])
                db.query("UPDATE learning_task_actions SET status='failed',updated_at=UTC_TIMESTAMP(6) WHERE task_id=? AND status='pending'",[task_id]);return None
            try:
                domain=context(db,captured,owner);domain.update(source_snapshot_id=task_id,action_id=task_id+':'+(task.get('active_request') or ''))
            except pymysql.MySQLError as error:preparation_failure(db,task,'prepare_database_'+str(error.args[0]));return None
            except Exception:preparation_failure(db,task,'prepare_context_invalid');return None
            try:budget.check('prepare')
            except TaskBudgetExceeded:stop_at_limit(db,task,'prepare_budget');return None
            db.query("UPDATE learning_tasks SET status='running',lease_token=?,lease_until=UTC_TIMESTAMP(6)+INTERVAL 90 SECOND,updated_at=UTC_TIMESTAMP(6) WHERE id=?",[lease,task_id])
            return {'task':task,'context':domain,'lease':lease}


def failure(task_id,owner,qid,lease,reason='computation_unavailable'):
    try:
        with Database.from_environment() as db:
            with db.transaction():
                snapshot=task_snapshot(db,qid,owner,lock=True);task=task_row(db,task_id,owner,True)
                if not lease_valid(task,lease) or not validate_version(db,task,snapshot):return
                view=stopped_view('这次没能核对完成，内容已保留，可以稍后继续');photo=object_value(object_value(task,'student_view'),'handwriting')
                if photo:view['handwriting']=photo
                view['secondary_actions']=['resume']+(['use_text'] if object_value(task,'pending_action').get('kind')=='recognize_handwriting' else [])
                db.query("UPDATE learning_tasks SET status='failed',version=version+1,student_view=?,lease_token=NULL,lease_until=NULL,exit_reason=?,updated_at=UTC_TIMESTAMP(6) WHERE id=?",[json.dumps(view,ensure_ascii=False),reason,task_id])
                db.query("UPDATE learning_task_actions SET status='failed',updated_at=UTC_TIMESTAMP(6) WHERE task_id=? AND request_id=? AND status='pending'",[task_id,task['active_request']])
    except Exception:pass  # Lease expiry permits recovery; no credentials enter logs.


def save_result(db,task,result,budget,memory,domain):
    tid=task['id'];owner=task['user_id'];request_id=task['active_request'];traces=result.get('traces') or []
    if len(traces)>3 or result.get('status') not in ['waiting_student','needs_review','completed']:raise HTTPException(503,'学习任务结果格式不正确')
    validate_recommendation(result,domain);manifest=[];valid_refs=[]
    for entry in memory.get('entries') or []:
        manifest.append({k:entry[k] for k in ['ref','version','classification','observed_at','expires_at','question_id','source_refs']});valid_refs.append(entry['ref'])
    for trace in traces:
        if any(not any(equivalent(ref,valid) for valid in valid_refs) for ref in trace.get('memory_refs') or []):raise HTTPException(503,'学习规划引用了无效记忆')
    attempt=result.get('attempt')
    if isinstance(attempt,dict):
        bound=attempt_source(db,task,attempt.get('phase',''));attempt['source']=bound
        for trace in traces:
            if trace.get('tool_name') in ['check_step','grade_answer']:
                evidence=object_value(trace,'evidence');evidence['source']=bound;trace['evidence']=evidence
    for index,trace in enumerate(traces):
        tool=trace['tool_name'];validation=trace['validation']
        if tool not in ['check_step','grade_answer','knowledge_search','step_alignment','compare_variant','recognize_handwriting','inspect_figure','visualization'] or validation not in ['verified','rejected','needs_review','not_applicable']:raise HTTPException(503,'学习任务工具结果不正确')
        run_id=new_id();run={'task_id':tid,'request_id':request_id,'trace':trace,'native_elapsed_ms':budget.elapsed_ms(),'elapsed_ms':result['elapsed_ms'],'usage':result['usage'],'memory_rule':'learning-memory-v1','memory_manifest':manifest}
        db.query("INSERT INTO agent_runs (id,session_id,agent_name,status,result,created_at,updated_at) VALUES (?,?,'learning_task','completed',?,UTC_TIMESTAMP(6),UTC_TIMESTAMP(6))",[run_id,task['session_id'],json.dumps(run,ensure_ascii=False)])
        input_data={'task_id':tid,'request_id':request_id,'student_action':task['pending_action']}
        db.query('INSERT INTO agent_tool_calls (id,agent_run_id,tool_name,input_json,output_json,created_at,updated_at) VALUES (?,?,?,?,?,UTC_TIMESTAMP(6),UTC_TIMESTAMP(6))',[new_id(),run_id,tool,json.dumps(input_data,ensure_ascii=False),json.dumps(trace,ensure_ascii=False)])
        db.query('INSERT INTO learning_task_steps (id,task_id,request_id,step_no,plan_version,tool_name,validation,agent_run_id,trace,created_at) VALUES (?,?,?,?,?,?,?,?,?,UTC_TIMESTAMP(6))',[new_id(),tid,request_id,index,task['version']*3+index,tool,validation,run_id,json.dumps(trace,ensure_ascii=False)])
    state=object_value(result,'checkpoint');eligible=result.get('learning_eligible') is True and task['learning_applied'] is not True and result['status']=='completed'
    contrast=object_value(state,'contrast').get('question','')
    if contrast and (state.get('contrast_passed') is True or object_value(state,'assistance').get('contrast') is True):
        subject=db.query('SELECT subject FROM questions WHERE id=?',[task['question_id']]).rows[0]['subject'];contrast_hash=hashlib.sha256((subject+'|'+contrast).encode()).hexdigest()
        db.query('INSERT IGNORE INTO learning_task_exposures (user_id,contrast_hash,task_id,created_at) VALUES (?,?,?,UTC_TIMESTAMP(6))',[owner,contrast_hash,tid])
        exposure=db.query('SELECT task_id FROM learning_task_exposures WHERE user_id=? AND contrast_hash=? FOR UPDATE',[owner,contrast_hash]).rows
        if not exposure or exposure[0]['task_id']!=tid:eligible=False
    if eligible and db.query("SELECT t.id FROM learning_tasks t JOIN questions q ON q.id=t.question_id WHERE t.user_id=? AND q.subject=(SELECT subject FROM questions WHERE id=?) AND JSON_UNQUOTE(JSON_EXTRACT(t.checkpoint,'$.contrast.question'))=? AND (JSON_UNQUOTE(JSON_EXTRACT(t.checkpoint,'$.contrast_passed'))='true' OR JSON_UNQUOTE(JSON_EXTRACT(t.checkpoint,'$.assistance.contrast'))='true') LIMIT 1",[owner,task['question_id'],object_value(state,'contrast').get('question')]).rows:eligible=False
    if eligible:
        if object_value(task,'pending_action').get('kind')!='answer':raise HTTPException(503,'缺少学生确认的实际作答')
        if not isinstance(attempt,dict):raise HTTPException(503,'缺少学习证据')
        grading=object_value(attempt,'grading')
        if attempt.get('phase')!='contrast' or attempt.get('verdict')!='confirmed_correct' or attempt.get('assisted') is True or grading.get('can_update_learning') is not True or state.get('contrast_passed') is not True:raise HTTPException(503,'学习证据未达到更新条件')
        question=row_json('questions',db.query('SELECT * FROM questions WHERE id=? AND user_id=?',[task['question_id'],owner]).rows[0])
        evidence={'near_transfer':True,'hint_level':0,'strategy':'verified_condition_contrast','learning_task_id':tid,'action_request_id':request_id}
        if state.get('workflow_version')!='langgraph-learning-v1':
            budget.check('before_learning');apply_evidence(db,owner,question,evidence,timeout=budget.timeout_seconds(5,reserve_seconds=1));budget.check('after_learning')
        if not db.query("SELECT id FROM review_plans WHERE user_id=? AND question_id=? AND status='pending' LIMIT 1",[owner,task['question_id']]).rows:
            db.query("INSERT INTO review_plans (id,user_id,question_id,due_at,interval_days,reason,status,created_at,updated_at) VALUES (?,?,?,UTC_TIMESTAMP()+INTERVAL 3 DAY,3,'单条件对照已独立完成，稍后再确认稳定性','pending',UTC_TIMESTAMP(),UTC_TIMESTAMP())",[new_id(),owner,task['question_id']])
    apply_aemt(db,task,result,budget,eligible)
    if request_id!='__initial__':db.query("UPDATE learning_task_actions SET result=?,status='applied',updated_at=UTC_TIMESTAMP(6) WHERE task_id=? AND request_id=? AND status='pending'",[json.dumps(result,ensure_ascii=False),tid,request_id])
    budget.check('before_checkpoint');next_step=new_id();view=object_value(result,'student_view');save_image_result(db,task,view,next_step);retain_for_support(db,task,result,view,next_step)
    db.query('UPDATE learning_tasks SET status=?,version=version+1,step_id=?,checkpoint=?,student_view=?,learning_applied=?,lease_token=NULL,lease_until=NULL,exit_reason=?,updated_at=UTC_TIMESTAMP(6) WHERE id=?',[result['status'],next_step,json.dumps(state,ensure_ascii=False),json.dumps(view,ensure_ascii=False),1 if eligible or task['learning_applied'] is True else 0,result['exit_reason'],tid])
    budget.check('after_checkpoint')
    db.query("UPDATE agent_runs r JOIN learning_task_steps s ON s.agent_run_id=r.id SET r.result=JSON_SET(r.result,'$.native_elapsed_ms',CAST(? AS UNSIGNED)) WHERE s.task_id=? AND s.request_id=?",[budget.elapsed_ms(),tid,request_id]);budget.check('after_audit')


def run_task(task_id,budget=None):
    owner=qid=lease='';stage='claim';budget=budget or TaskBudget()
    try:
        prepared=claim(task_id,budget)
        if prepared is None:return
        before=prepared['task'];owner=before['user_id'];qid=before['question_id'];lease=prepared['lease']
        budget.check('claimed');stage='image_input'
        payload={'operation':'learning_task','task_context':prepared['context'],'task_checkpoint':before['checkpoint'],'task_action':compute_action(before)}
        stage='compute';seconds=budget.timeout_seconds(40,reserve_seconds=5)
        if seconds<2:raise TaskBudgetExceeded('compute_reserve')
        payload['task_budget_ms']=38000 if seconds>38 else (seconds-1)*1000
        result=compute(payload,timeout=seconds,budget=budget);budget.check('computed');stage='commit'
        with Database.from_environment() as db:
            with db.transaction():
                snapshot=task_snapshot(db,qid,owner,lock=True);current=task_row(db,task_id,owner,True)
                if not lease_valid(current,lease) or not validate_version(db,current,snapshot):return
                domain=context(db,source(db,current,snapshot),owner);domain.update(source_snapshot_id=task_id,action_id=task_id+':'+(current.get('active_request') or ''))
                if not equivalent(prepared['context'],domain):raise HTTPException(409,'学习依据已更新，需要重新核对')
                budget.check('validated');save_result(db,current,result,budget,object_value(domain,'memory_snapshot'),domain);budget.check('before_commit')
    except TaskBudgetExceeded as error:
        if lease:failure(task_id,owner,qid,lease,'budget_'+error.stage)
    except pymysql.MySQLError as error:
        if lease:failure(task_id,owner,qid,lease,stage+'_database_'+str(error.args[0]))
    except HTTPException as error:
        if lease:failure(task_id,owner,qid,lease,stage+'_api_'+str(error.status_code))
    except Exception:
        if lease:failure(task_id,owner,qid,lease,stage+'_runtime')


class WorkerPool:
    def __init__(self,count=2,poll_interval=1):
        if count not in [0,1,2]:raise ValueError('SCZX_TASK_WORKERS 只允许0、1或2')
        self.stop_event=threading.Event();self.poll_interval=poll_interval
        self.threads=[threading.Thread(target=self.loop,name='sczx-learning-task-'+str(i),daemon=True) for i in range(count)]

    def start(self):
        for thread in self.threads:thread.start()
        return self

    def stop(self):
        self.stop_event.set();deadline=time.monotonic()+2
        for thread in self.threads:thread.join(timeout=max(0,deadline-time.monotonic()))

    def loop(self):
        while not self.stop_event.is_set():
            try:
                with Database.from_environment() as db:
                    rows=db.query("SELECT id FROM learning_tasks WHERE cancel_requested=0 AND (status='queued' OR (status='running' AND lease_until<UTC_TIMESTAMP(6))) ORDER BY created_at,id LIMIT 1").rows
                    if rows:run_task(rows[0]['id'])
                    else:self.stop_event.wait(self.poll_interval)
            except Exception:self.stop_event.wait(2)
