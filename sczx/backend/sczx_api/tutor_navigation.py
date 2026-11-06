import json
from fastapi import HTTPException
from .accounts import current_user,read_json
from .database import Database
from .rows import row_json
from .security import new_id
from .tutor_core import canonical_stage,previous_stage,transition
from .tutor_read import session_payload
from .tutor_start import record_tool
from .tutor_variants import data_snapshot


async def navigate_tutor(request,rewind):
    session_id=request.path_params['session_id']
    with Database.from_environment() as db:
        user=current_user(request,db);body={} if rewind else await read_json(request)
        with db.transaction():
            rows=db.query('SELECT * FROM tutor_sessions WHERE id=? AND user_id=?',[session_id,user['id']]).rows
            if not rows:raise HTTPException(404,'教学会话不存在或无权访问')
            session=row_json('tutor_sessions',rows[0]);state=session['state'] if isinstance(session['state'],dict) else {};session['state']=state
            value=data_snapshot(db,session['question_id'],user['id'])
            if value['question']['status']=='archived' or state.get('question_changed') is True:raise HTTPException(409,'题目已变化或归档，请重新开始学习')
            current=canonical_stage(session['stage']);compressed=state.get('teaching_policy',{}).get('mode')=='compressed'
            try:
                if rewind:target='understanding' if compressed and current=='near_transfer' else previous_stage(current)
                else:
                    if body.get('target_stage')!='teach_back':raise HTTPException(422,'只支持进入讲清阶段')
                    target=transition(current,'understanding_advance',state.get('understanding_passed') is True)
            except ValueError as error:raise HTTPException(409,str(error)) from None
            branch=f'rewind_{current}_to_{target}' if rewind else 'understanding_advance'
            tool_input={'from':current};output={'to':target};message='现在请用自己的话讲一遍：用了什么规则，为什么能用，又怎样得到结论。'
            if not rewind:
                state['next_goal']='用自己的话说明规则、依据和结论';tool_input['event']='understanding_advance'
                db.query("INSERT INTO tutor_turns (id,session_id,role,content,stage,metadata_json,created_at,updated_at) VALUES (?,?,'assistant',?,'teach_back',?,UTC_TIMESTAMP(6),UTC_TIMESTAMP(6))",[new_id(),session_id,message,json.dumps({'branch':'understanding_advance','explicit_transition':True})])
            else:
                if current in ['teach_back','near_transfer']:state.update(teach_back=None,teach_back_passed=None,teach_back_attempts=0)
                if current=='teach_back':state.update(understanding_passed=True,understood=True,next_goal='回顾已经理解的关键点')
                else:
                    state.update(near_transfer=None,near_confirmation=None,far_transfer=None,near_attempts=0,far_attempts=0,next_goal='重新用自己的话说清关键判断' if current=='near_transfer' else '重新完成一道相似题')
                    if compressed and current=='near_transfer':state.update(understanding_passed=False,understood=False,answer_reveal_acknowledged=False,targeted_check_pending=False,next_goal='重新查看答案讲解')
                label='理解' if target=='understanding' else '讲清' if target=='teach_back' else '练习'
                state['activity_feedback']=f'已返回“{label}”。'
            state['branch']=branch;session['stage']=target
            db.query('UPDATE tutor_sessions SET stage=?,state=?,updated_at=UTC_TIMESTAMP() WHERE id=?',[target,json.dumps(state,ensure_ascii=False),session_id])
            record_tool(db,session_id,'rewind_tutor_stage' if rewind else 'transition_tutor_stage',tool_input,output,{**output,'branch':branch})
            if rewind:
                saved=row_json('tutor_sessions',db.query('SELECT * FROM tutor_sessions WHERE id=?',[session_id]).rows[0])
                return session_payload(db,saved,value)
            return {'stage':target,'message':message,'next_goal':state['next_goal']}
