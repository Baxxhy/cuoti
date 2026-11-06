import json
from fastapi import HTTPException
from .accounts import current_user,read_json
from .algorithm import compute
from .database import Database
from .manual_questions import answer_text
from .question_edit import number
from .rows import row_json
from .security import new_id
from .tutor_core import canonical_stage,activity
from .tutor_completion import complete_learning
from .tutor_start import record_tool
from .tutor_variants import data_snapshot,ensure_variant


async def variant_attempt(request):
    variant_id=request.path_params['variant_id']
    with Database.from_environment() as db:
        user=current_user(request,db);body=await read_json(request);answer=body.get('answer','')
        if not isinstance(answer,str):raise HTTPException(422,'answer 必须是文字')
        if len(answer)>12000:raise HTTPException(422,'answer 长度不正确')
        elapsed=number(body.get('elapsed_seconds',0))
        if not 0<=elapsed<=2147483647:raise HTTPException(422,'作答时长无效')
        with db.transaction():
            variants=db.query('SELECT v.* FROM variant_questions v JOIN tutor_sessions s ON s.id=v.session_id WHERE v.id=? AND s.user_id=?',[variant_id,user['id']]).rows
            if not variants:raise HTTPException(404,'迁移题不存在或无权访问')
            variant=row_json('variant_questions',variants[0]);session_id=variant['session_id']
            session=row_json('tutor_sessions',db.query('SELECT * FROM tutor_sessions WHERE id=?',[session_id]).rows[0]);state=session['state'] if isinstance(session['state'],dict) else {};session['state']=state
            transfer=variant['transfer_type'];session['stage']=canonical_stage(session['stage'])
            if session['stage']!=transfer+'_transfer':raise HTTPException(409,'这道练习与当前教学阶段不匹配')
            if state.get(transfer+'_variant_id') and state[transfer+'_variant_id']!=variant_id:raise HTTPException(409,'这道练习已经变化，请刷新')
            value=data_snapshot(db,session['question_id'],user['id']);question=value['question']
            if state.get('question_changed') is True or question['status']=='archived':raise HTTPException(409,'题目已变化或归档，请重新开始学习')
            hint=number(body.get('hint_level',session['hint_level']))
            if not 0<=hint<=2147483647:raise HTTPException(422,'提示等级无效')
            grading=compute({'operation':'grade_answer','text':variant['question_text'],'answer':answer,'expected':variant['answer'],'reference_solution':variant.get('reference_solution') or [],'subject':question['subject'],'question_type':question['question_type']})
            decisive=grading.get('can_update_learning') is True;correct=grading.get('correct') is True;feedback=grading['feedback'];branch=transfer+'_transfer_'+('review_required' if not decisive else 'pass' if correct else 'fail');attempt=None
            if decisive:
                attempt_id=new_id()
                db.query('INSERT INTO variant_attempts (id,variant_id,user_id,answer,correct,elapsed_seconds,hint_level,created_at,updated_at) VALUES (?,?,?,?,?,?,?,UTC_TIMESTAMP(),UTC_TIMESTAMP())',[attempt_id,variant_id,user['id'],answer,int(correct),int(elapsed),int(hint)])
                attempt=row_json('variant_attempts',db.query('SELECT * FROM variant_attempts WHERE id=?',[attempt_id]).rows[0]);count=state.get(transfer+'_attempts',0)+1;state[transfer+'_attempts']=count;state['branch']=branch
                if transfer=='near' and correct:
                    state['near_transfer']=True;session['stage']='far_transfer';ensure_variant(db,session,value,'far')
                elif transfer=='near' and count>=2:
                    state.update(near_transfer=False,assisted=True)
                    state['near_confirmation']=activity('near-remediation-'+variant_id,'看懂这一步就继续','根据刚才的讲解，这道题的参考结论是什么？',[('expected',answer_text(variant['answer'])),('unsure','我还不能确定')],['expected'],'',variant.get('explanation') or '先对照题目条件，再按顺序完成关键步骤。');feedback='先看这道题的简短讲解，再完成一个简单确认。'
                elif transfer=='far' and (correct or count>=2):
                    state['far_transfer']=correct
                    if not correct:state.update(transfer_insufficient=True,assisted=True)
                    complete_learning(db,session,value,not correct)
                    if not correct:feedback='这次换一种题目还不稳定，本轮先结束，并提高后续复习优先级。'
                db.query('UPDATE tutor_sessions SET stage=?,state=?,updated_at=UTC_TIMESTAMP() WHERE id=?',[session['stage'],json.dumps(state,ensure_ascii=False),session_id])
            user_meta={'branch':branch,'variant_id':variant_id};assistant_meta={'branch':branch}
            if not decisive:user_meta.update(grading=grading,attempt_consumed=False);assistant_meta['grading_verdict']=grading['verdict']
            else:assistant_meta['correct']=correct
            for role,content,stage,metadata in [('user',answer,transfer+'_transfer',user_meta),('assistant',feedback,session['stage'],assistant_meta)]:
                db.query('INSERT INTO tutor_turns (id,session_id,role,content,stage,metadata_json,created_at,updated_at) VALUES (?,?,?,?,?,?,UTC_TIMESTAMP(6),UTC_TIMESTAMP(6))',[new_id(),session_id,role,content,stage,json.dumps(metadata,ensure_ascii=False)])
            result={'attempt':attempt,'correct':correct if decisive else None,'branch':branch,'stage':session['stage'],'feedback':feedback,'grading':grading}
            if decisive:
                output={'correct':correct,'stage':session['stage']};record_tool(db,session_id,'grade_answer',{'variant_id':variant_id,'answer':answer},output,{**output,'branch':branch})
            for name,table in [('mastery','mastery_states'),('misconception','misconception_states')]:
                rows=db.query(f'SELECT * FROM {table} WHERE user_id=? ORDER BY updated_at DESC,id DESC LIMIT 1',[user['id']]).rows if decisive else []
                result[name]=row_json(table,rows[0]) if rows else None
            return result
