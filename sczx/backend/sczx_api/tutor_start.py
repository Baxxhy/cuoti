from fastapi import HTTPException

from .accounts import current_user, read_json, secret
from .algorithm import compute
from .database import Database
from .diagnosis import diagnosis_snapshot, diagnosis_fingerprint
from .question_detail import query_array
from .question_edit import text
from .rows import row_json
from .security import new_id, media_url
from .tutor_core import initial_state, teaching_policy, knowledge, public_progress, public_activity, visualization
import json


def start_snapshot(db, question_id, owner):
    value = diagnosis_snapshot(db,question_id,owner)
    analysis = value['analysis']
    if not isinstance(analysis,dict) or not analysis['final_answer'].strip() or analysis['final_answer'].startswith('需要根据完整题目'):
        raise HTTPException(409,'请先完成题目分析，再开始学习')
    return value


def opening_activity(state):
    if state.get('understanding_passed') is True: return None
    if state.get('teaching_policy',{}).get('mode')=='compressed':
        if not state.get('answer_reveal_acknowledged'):
            return {'id':'answer-reveal','type':'explanation','title':'先看清这次错在哪','question':'','options':[],'attempt':1,'max_attempts':1,'feedback':'','teaching':''}
        if state.get('targeted_check_pending'):
            check = state.get('teaching_brief',{}).get('check',{})
            return public_activity(check,state.get('activity_attempts',{}).get(check.get('id',''),0)+1,state.get('activity_feedback',''))
        return None
    plan=state.get('understanding_plan',[])
    if not plan: return None
    index=max(0,min(state.get('understanding_index',0),len(plan)-1)); source=plan[index]
    return public_activity(source,state.get('activity_attempts',{}).get(source['id'],0)+1,state.get('activity_feedback',''))


def opening_payload(db, session, value):
    state, question = session['state'], value['question']
    result = dict(session); points = knowledge(value)
    result.update(state=public_progress(state),stage_status='active',activity=opening_activity(state),assisted=state.get('assisted') is True,teaching_policy=state.get('teaching_policy',{'mode':'full'}),answer_reveal=state.get('answer_reveal'),completion_summary=state.get('completion_summary',''),knowledge_title=' · '.join(points[:2]) or question['title'],visualization_available=visualization(question['subject'],question['question_type'],points) is not None)
    figures = db.query("SELECT path FROM question_assets WHERE question_id=? AND kind IN ('question_figure','crop') ORDER BY (kind='question_figure') DESC,created_at DESC,id DESC LIMIT 1",[question['id']]).rows
    result['question']={'id':question['id'],'text':question['question_text'],'figure_url':media_url('/'+figures[0]['path'],secret()) if figures else None}
    result['turns']=query_array(db,'tutor_turns','SELECT * FROM tutor_turns WHERE session_id=? ORDER BY created_at,id',session['id'])
    return result


def record_tool(db, session_id, name, tool_input, output, run_result):
    run_id = new_id()
    db.query("INSERT INTO agent_runs (id,session_id,agent_name,status,result,created_at,updated_at) VALUES (?,?,'mindtrace_tutor','completed',?,UTC_TIMESTAMP(),UTC_TIMESTAMP())",[run_id,session_id,json.dumps(run_result,ensure_ascii=False)])
    db.query('INSERT INTO agent_tool_calls (id,agent_run_id,tool_name,input_json,output_json,created_at,updated_at) VALUES (?,?,?,?,?,UTC_TIMESTAMP(),UTC_TIMESTAMP())',[new_id(),run_id,name,json.dumps(tool_input,ensure_ascii=False),json.dumps(output,ensure_ascii=False)])


async def start_tutor(request):
    with Database.from_environment() as db:
        user=current_user(request,db); body=await read_json(request)
        question_id=text(body['question_id'],36,1) if 'question_id' in body else ''
        with db.transaction(): value=start_snapshot(db,question_id,user['id'])
        question,analysis=value['question'],value['analysis']; steps=[s['text'] for s in value['steps']]
        policy=teaching_policy(question['question_type'],bool(question['options']),bool(steps),analysis['final_answer'])
        brief=None
        if policy['mode']=='compressed':
            payload={'operation':'teaching_brief','text':question['question_text'],'student_answer':question['student_answer'],'options':question['options'],'question_type':policy['question_type'],'correct_answer':analysis['final_answer'],'student_steps':steps,'knowledge_points':knowledge(value),'diagnosis':value['diagnosis'] or {}}
            brief=compute(payload)['brief']
            if not isinstance(brief,dict): raise HTTPException(503,'教学简报不完整')
        state=initial_state(value,policy,brief)
        with db.transaction():
            current=start_snapshot(db,question_id,user['id'])
            if diagnosis_fingerprint(current)!=diagnosis_fingerprint(value): raise HTTPException(409,'题目或诊断已变化，请重新开始学习')
            session_id=new_id(); opening='先看清正确答案和刚才选项的关键差别。' if policy['mode']=='compressed' else '我们先只解决一个小问题。选出你认为正确的答案就可以。'
            db.query("INSERT INTO tutor_sessions (id,user_id,question_id,stage,hint_level,turn_count,mastery_score,state,status,created_at,updated_at) VALUES (?,?,?,'understanding',0,0,0,?,'active',UTC_TIMESTAMP(),UTC_TIMESTAMP())",[session_id,user['id'],question_id,json.dumps(state,ensure_ascii=False)])
            db.query("INSERT INTO tutor_turns (id,session_id,role,content,stage,metadata_json,created_at,updated_at) VALUES (?,?,'assistant',?,'understanding',?,UTC_TIMESTAMP(6),UTC_TIMESTAMP(6))",[new_id(),session_id,opening,json.dumps({'branch':'opening','next_goal':'解释首错步骤'},ensure_ascii=False)])
            diagnosis_id=(value['diagnosis'] or {}).get('id')
            record_tool(db,session_id,'diagnosis_lookup',{'question_id':question_id},{'diagnosis_id':diagnosis_id},{'branch':'opening','diagnosis_id':diagnosis_id})
            session=row_json('tutor_sessions',db.query('SELECT * FROM tutor_sessions WHERE id=?',[session_id]).rows[0])
            return opening_payload(db,session,value)
