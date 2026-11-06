from fastapi import HTTPException
from .learning_evidence import apply_evidence,knowledge_point
from .rows import row_json
from .security import new_id
from .task_policy import object_value


def apply_aemt(db,task,result,budget,transfer_eligible):
    state=object_value(result,'checkpoint')
    if state.get('workflow_version')!='langgraph-learning-v1':return
    attempt=object_value(result,'attempt');grading=object_value(attempt,'grading');phase=attempt.get('phase','');verdict=attempt.get('verdict','')
    if phase not in ['independent','contrast'] or verdict not in ['confirmed_correct','confirmed_incorrect'] or grading.get('can_update_learning') is not True:return
    if phase=='contrast' and verdict=='confirmed_correct' and not transfer_eligible and attempt.get('assisted') is not True:return
    action=object_value(task,'pending_action')
    if action.get('kind')!='answer' or attempt.get('answer','')!=action.get('text',''):raise HTTPException(503,'作答证据与提交不一致')
    if object_value(task,'checkpoint').get('phase','')!=phase or grading.get('verdict','')!=verdict or (grading.get('correct') is True)!=(verdict=='confirmed_correct'):raise HTTPException(503,'作答核验与当前步骤不一致')
    owner=task['user_id'];qid=task['question_id'];request_id=task['active_request'];tid=task['id']
    if db.query("SELECT id FROM cognitive_updates WHERE user_id=? AND question_id=? AND entity_type='mastery' AND JSON_UNQUOTE(JSON_EXTRACT(evidence,'$.learning_task_id'))=? AND JSON_UNQUOTE(JSON_EXTRACT(evidence,'$.action_request_id'))=? LIMIT 1",[owner,qid,tid,request_id]).rows:return
    rows=db.query('SELECT * FROM questions WHERE id=? AND user_id=?',[qid,owner]).rows
    if not rows:raise HTTPException(409,'题目来源已变化')
    question=row_json('questions',rows[0]);revealed=phase in (state.get('revealed_phases') or []);hints=object_value(state,'hints').get(phase) or [];assisted=attempt.get('assisted') is True
    if revealed or assisted and not hints:return
    event={'event_id':tid+':'+request_id,'verdict':verdict,'scope':'contrast_question' if phase=='contrast' else 'original_question','hint_used':assisted and bool(hints),'solution_seen':revealed or assisted and not hints,'student_confirmed':True,'source_current':True,'grading_reliable':True,'option_count':len(question['options'])}
    elapsed=db.query('SELECT GREATEST(0,COALESCE(TIMESTAMPDIFF(SECOND,last_evidence_at,UTC_TIMESTAMP()),0)) AS seconds FROM mastery_states WHERE user_id=? AND subject=? AND knowledge_point=? ORDER BY updated_at DESC,id DESC LIMIT 1',[owner,question['subject'],knowledge_point(db,question)]).rows
    days=float(elapsed[0]['seconds'])/86400 if elapsed else 0.
    event.update(days_since_last=days,delayed_similar=phase=='contrast' and not assisted and days>=1,occurred_at=db.query("SELECT DATE_FORMAT(UTC_TIMESTAMP(),'%Y-%m-%dT%H:%i:%sZ') AS instant").rows[0]['instant'])
    evidence={'aemt_event':event,'learning_task_id':tid,'action_request_id':request_id,'strategy':'aemt_assistance_aware','hint_level':1 if assisted else 0}
    if phase=='contrast' and not assisted:evidence['near_transfer']=verdict=='confirmed_correct'
    budget.check('before_aemt');apply_evidence(db,owner,question,evidence,timeout=budget.timeout_seconds(5,reserve_seconds=1))
    if not db.query("SELECT id FROM review_plans WHERE user_id=? AND question_id=? AND status='pending' LIMIT 1",[owner,qid]).rows:
        interval=1 if assisted or verdict=='confirmed_incorrect' else 3
        db.query("INSERT INTO review_plans (id,user_id,question_id,due_at,interval_days,reason,status,created_at,updated_at) VALUES (?,?,?,TIMESTAMPADD(DAY,?,UTC_TIMESTAMP()),?,'根据本次作答安排复习','pending',UTC_TIMESTAMP(),UTC_TIMESTAMP())",[new_id(),owner,qid,interval,interval])
    budget.check('after_aemt')
