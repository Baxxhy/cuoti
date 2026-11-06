import json
from fastapi import HTTPException
from .accounts import current_user,read_json
from .database import Database
from .learning_evidence import apply_evidence
from .rows import row_json
from .security import new_id
from .tutor_core import canonical_stage,public_progress
from .tutor_start import record_tool
from .tutor_variants import data_snapshot


def complete_learning(db,session,value,insufficient):
    state=session['state'];question=value['question'];owner=session['user_id']
    evidence={k:state.get(k) for k in ['teach_back','near_transfer','far_transfer']}
    evidence.update(hint_level=session['hint_level'],strategy='assisted_progression' if state.get('assisted') is True else 'micro_activity',tutor_session_id=session['id'])
    updated=apply_evidence(db,owner,question,evidence);score=updated['mastery_after']['mastery_score']
    days=1 if insufficient else 3 if state.get('assisted') is True else 15
    plan_id=new_id()
    db.query("INSERT INTO review_plans (id,user_id,question_id,due_at,interval_days,reason,status,created_at,updated_at) VALUES (?,?,?,TIMESTAMPADD(DAY,?,UTC_TIMESTAMP()),?,?,'pending',UTC_TIMESTAMP(),UTC_TIMESTAMP())",[plan_id,owner,question['id'],days,days,'迁移练习还不稳定，已提高复习优先级' if insufficient else '本轮学习已完成，按掌握情况复习'])
    state['completion_summary']='这次换一种题目还不够稳定，我已经把它放到近期优先复习。' if insufficient else '本轮已经完成。下一次复习会根据这次是否需要提示来安排。'
    state['mastery_proven']=not insufficient and state.get('far_transfer') is True
    session.update(stage='finished',status='completed',mastery_score=score)
    db.query("UPDATE tutor_sessions SET status='completed',mastery_score=? WHERE id=?",[score,session['id']])
    output={'mastery':score,'interval_days':days,'priority':'high' if insufficient else 'normal'}
    record_tool(db,session['id'],'update_cognition',evidence,output,{**output,'branch':'activity_finish'})
    return {'mastery':updated['mastery_after'],'misconception':updated['misconception_after'],'review':row_json('review_plans',db.query('SELECT * FROM review_plans WHERE id=?',[plan_id]).rows[0])}


async def finish_tutor(request):
    session_id=request.path_params['session_id']
    with Database.from_environment() as db:
        user=current_user(request,db);await read_json(request,default_empty=True)
        with db.transaction():
            rows=db.query('SELECT * FROM tutor_sessions WHERE id=? AND user_id=? FOR UPDATE',[session_id,user['id']]).rows
            if not rows:raise HTTPException(404,'教学会话不存在或无权访问')
            session=row_json('tutor_sessions',rows[0]);session['stage']=canonical_stage(session['stage'])
            if session['stage']!='finished':raise HTTPException(409,'请先完成讲清、相似题和综合应用')
            if session['status']=='completed':
                plans=db.query('SELECT * FROM review_plans WHERE user_id=? AND question_id=? ORDER BY created_at DESC,id DESC LIMIT 1',[user['id'],session['question_id']]).rows
                return {'session':{**session,'state':public_progress(session['state'] if isinstance(session['state'],dict) else {})},'mastery':None,'review':row_json('review_plans',plans[0]) if plans else None}
            value=data_snapshot(db,session['question_id'],user['id']);state=session['state'] if isinstance(session['state'],dict) else {};session['state']=state
            if state.get('question_changed') is True or value['question']['status']=='archived':raise HTTPException(409,'题目已变化或归档，请重新开始学习')
            insufficient=state.get('transfer_insufficient') is True or state.get('far_transfer') is False
            learning=complete_learning(db,session,value,insufficient)
            db.query('UPDATE tutor_sessions SET stage=?,state=?,updated_at=UTC_TIMESTAMP() WHERE id=?',[session['stage'],json.dumps(state,ensure_ascii=False),session_id])
            saved=row_json('tutor_sessions',db.query('SELECT * FROM tutor_sessions WHERE id=?',[session_id]).rows[0])
            return {'session':{**saved,'state':public_progress(saved['state'])},'mastery':learning['mastery'],'review':learning['review']}
