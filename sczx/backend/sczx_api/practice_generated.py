import json
from fastapi import HTTPException
from .algorithm import compute
from .learning_evidence import apply_evidence,knowledge_point
from .practice_context import source_version,equivalent
from .rows import row_json
from .security import new_id
from .tutor_core import knowledge
from .tutor_variants import data_snapshot
from .manual_questions import answer_text


def payload(question,variant):
    meta=variant['generation_metadata'] or {}
    return {'question_id':variant['id'],'stem':variant['question_text'],'subject':question['subject'],'grade':question['grade'],'question_type':meta.get('question_type'),'options':meta.get('options') or [],'images':[],'mode':meta.get('mode'),'generated':True,'recommendation':'根据这道错题练习相同的方法'}


def generate(db,owner,question,mode,force):
    version=source_version(db,question);qid=question['id'];previous=None
    rows=db.query("SELECT v.* FROM variant_questions v JOIN tutor_sessions s ON s.id=v.session_id WHERE s.user_id=? AND v.question_id=? AND s.stage='standalone_practice' ORDER BY v.created_at DESC LIMIT 20",[owner,qid]).rows
    for row in rows:
        item=row_json('variant_questions',row);meta=item['generation_metadata'] or {}
        if meta.get('source_version')==version and meta.get('mode')==mode and item['verified'] is True:
            if previous is None:previous=item
            if not force:
                result=payload(question,item);sessions=db.query('SELECT state FROM tutor_sessions WHERE id=?',[item['session_id']]).rows
                if sessions:
                    state=json.loads(sessions[0]['state'])
                    if 'receipt' in state:result.update(previous_result=state['receipt'],previous_answer=state['answer'])
                return result
    original=question['question_text']+'\n选项：'+json.dumps(question['options'],ensure_ascii=False,separators=(',',':'))+'\n年级：'+(question['grade'] or '')
    if previous:original+='\n请勿重复此前练习：'+previous['question_text']
    snapshot=data_snapshot(db,qid,owner)
    try:computed=compute({'operation':'generate_practice','text':original,'subject':question['subject'],'question_type':question['question_type'],'transfer_type':'far' if mode=='variation' else 'near','knowledge_points':knowledge(snapshot)})
    except HTTPException:computed={}
    if computed.get('verified') is not True:
        if previous:return {**payload(question,previous),'recommendation':'再练一次，巩固这道题的方法'}
        raise HTTPException(503,'类似题暂未通过核对，请稍后重试。原错题和学习记录已保留。')
    variant=computed['variant'];meta=computed.get('generation') or {};options=variant.get('options') or []
    meta.update(options=options,mode=mode,source_version=version,question_type=question['question_type'] if options else '综合题')
    with db.transaction():
        rows=db.query("SELECT * FROM questions WHERE id=? AND user_id=? AND status<>'archived' FOR UPDATE",[qid,owner]).rows
        if not rows or source_version(db,row_json('questions',rows[0]))!=version:raise HTTPException(409,'原题已更新，请重新获取练习')
        sid=new_id();vid=new_id()
        db.query("INSERT INTO tutor_sessions (id,user_id,question_id,stage,hint_level,turn_count,mastery_score,state,status,created_at,updated_at) VALUES (?,?,?,'standalone_practice',0,0,0,JSON_OBJECT(),'standalone',UTC_TIMESTAMP(),UTC_TIMESTAMP())",[sid,owner,qid])
        db.query('INSERT INTO variant_questions (id,question_id,session_id,transfer_type,question_text,answer,explanation,reference_solution,verified,generation_metadata,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,1,?,UTC_TIMESTAMP(),UTC_TIMESTAMP())',[vid,qid,sid,'far' if mode=='variation' else 'near',variant['question_text'],answer_text(variant['answer']),variant['explanation'],json.dumps(variant['reference_solution'],ensure_ascii=False),json.dumps(meta,ensure_ascii=False)])
        return payload(question,row_json('variant_questions',db.query('SELECT * FROM variant_questions WHERE id=?',[vid]).rows[0]))


def attempt_generated(db,owner,mistake,variant,mode,answer,duration):
    meta=variant['generation_metadata'] or {};vid=variant['id'];sid=variant['session_id']
    if meta.get('mode')!=mode or meta.get('source_version')!=source_version(db,mistake):raise HTTPException(409,'原题或练习目标已更新，请重新获取练习')
    rows=db.query('SELECT state FROM tutor_sessions WHERE id=? FOR UPDATE',[sid]).rows;previous=json.loads(rows[0]['state']) if rows else {}
    if equivalent(previous.get('answer'),answer) and (previous.get('receipt') or {}).get('can_update_learning') is True:return previous['receipt']
    grading=compute({'operation':'grade_answer','text':variant['question_text'],'answer':answer,'expected':variant['answer'],'subject':mistake['subject'],'question_type':meta.get('question_type'),'options':meta.get('options') or [],'reference_solution':variant['reference_solution']})
    decisive=grading.get('can_update_learning') is True and variant['verified'] is True;seen=previous.get('answer_revealed') is True
    prior=db.query('SELECT id FROM variant_attempts WHERE variant_id=? AND user_id=? LIMIT 1',[vid,owner]).rows
    point=knowledge_point(db,mistake)
    old=db.query('SELECT mastery_score FROM mastery_states WHERE user_id=? AND subject=? AND knowledge_point=? LIMIT 1',[owner,mistake['subject'],point]).rows
    before=row_json('mastery_states',old[0])['mastery_score'] if old else 0.;mastery=None
    saved={'answer':answer,'grading':grading,'duration_seconds':duration,'answer_revealed':True}
    db.query('UPDATE tutor_sessions SET state=?,updated_at=UTC_TIMESTAMP() WHERE id=?',[json.dumps(saved,ensure_ascii=False),sid])
    if decisive:
        aid=new_id();db.query('INSERT INTO variant_attempts (id,variant_id,user_id,answer,correct,elapsed_seconds,hint_level,created_at,updated_at) VALUES (?,?,?,?,?,?,0,UTC_TIMESTAMP(),UTC_TIMESTAMP())',[aid,vid,owner,answer_text(answer),int(grading['correct']),duration])
        if not prior and not seen:
            evidence={'near_transfer' if mode=='reinforce' else 'far_transfer':grading['correct'],'hint_level':0,'strategy':'generated_practice','variant_id':vid,'practice_attempt_id':aid}
            mastery=(apply_evidence(db,owner,mistake,evidence).get('mastery_after') or {}).get('mastery_score')
    result={k:grading[k] for k in ['verdict','confidence','evidence','feedback']}
    result.update(correct=grading['correct'] if decisive else None,can_update_learning=decisive,answer=variant['answer'],solution=variant['explanation'],mastery_before=before,mastery=mastery,grading_method=grading['method'])
    if seen:result['learning_note']='已看过参考答案，这次练习不重复计入掌握情况。'
    saved['receipt']=result;db.query('UPDATE tutor_sessions SET state=?,updated_at=UTC_TIMESTAMP() WHERE id=?',[json.dumps(saved,ensure_ascii=False),sid]);return result
