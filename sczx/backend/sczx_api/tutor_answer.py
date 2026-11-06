import json
from fastapi import HTTPException
from .accounts import current_user,read_json
from .algorithm import compute
from .database import Database
from .handwriting import validate_handwriting
from .manual_questions import answer_text
from .question_edit import text,number,flag
from .recognition import short_title
from .rows import row_json
from .security import new_id
from .tutor_core import canonical_stage,knowledge
from .tutor_read import session_activity,session_payload
from .tutor_teach_back import evaluate_teach_back
from .tutor_transfer import answer_transfer
from .tutor_variants import data_snapshot,ensure_variant


def summary(value,limit):
    return value if '$' in value or '\\' in value else short_title(value,limit)


def micro_passed(source,answer,question):
    expected=source.get('correct_answers',[])
    grade=compute({'operation':'grade_answer','text':source.get('question') or question['question_text'],'answer':answer,'expected':expected if source.get('type')=='multiple_choice' else expected[0] if expected else '', 'subject':question['subject'],'question_type':source['type'],'options':source.get('options',[])})
    return grade.get('correct') is True and grade.get('can_update_learning') is True


def answer_label(activity,answer):
    values=answer if isinstance(answer,list) else [answer];result=[]
    for value in values:
        raw=answer_text(value);label=raw
        for option in activity.get('options',[]):
            if option.get('value','')==raw:label=option.get('label','');break
        result.append(label)
    return '、'.join(result)


async def answer_activity(request):
    session_id=request.path_params['session_id']
    with Database.from_environment() as db:
        user=current_user(request,db);body=await read_json(request,2*1024*1024);answer=body.get('answer','')
        if isinstance(answer,list):
            if len(answer)>100:raise HTTPException(422,'选项数量过多')
            for item in answer:text(item,12000)
        else:text(answer,12000)
        working=text(body.get('working',''),12000,trim=True);elapsed=number(body.get('elapsed_seconds',0))
        if not 0<=elapsed<=2147483647:raise HTTPException(422,'作答时长无效')
        elapsed=int(elapsed);unknown=flag(body.get('unknown',False)) or answer_text(answer)=='__unknown__'
        with db.transaction():
            rows=db.query('SELECT * FROM tutor_sessions WHERE id=? AND user_id=?',[session_id,user['id']]).rows
            if not rows:raise HTTPException(404,'教学会话不存在或无权访问')
            session=row_json('tutor_sessions',rows[0]);state=session['state'] if isinstance(session['state'],dict) else {};session['state']=state
            stage=canonical_stage(session['stage']);session['stage']=stage
            if stage not in ['understanding','teach_back','near_transfer','far_transfer']:raise HTTPException(409,'当前阶段不能继续作答')
            value=data_snapshot(db,session['question_id'],user['id']);question=value['question']
            if state.get('question_changed') is True or question['status']=='archived':raise HTTPException(409,'题目已变化或归档，请重新开始学习')
            activity=session_activity(db,session,value)
            if not isinstance(activity,dict) or body.get('activity_id')!=activity['id']:raise HTTPException(409,'当前小任务已经变化，请刷新后继续')
            handwriting=validate_handwriting(body,user['id'],session_id)
            passed=False;feedback='';transfer={};compressed=state.get('teaching_policy',{}).get('mode')=='compressed'
            if stage in ['near_transfer','far_transfer']:
                transfer=answer_transfer(db,session,value,answer,unknown,elapsed);passed=transfer.get('passed') is True;feedback=transfer.get('feedback','')
            elif stage=='teach_back':
                assessment=evaluate_teach_back(answer_text(answer).strip(),question,knowledge(value),[r['text'] for r in value['references']])
                passed=assessment.get('passed') is True;count=state.get('teach_back_attempts',0)+1;state['teach_back_attempts']=count
                if passed or count>=2:
                    state.update(teach_back=passed,teach_back_passed=passed)
                    if not passed:state['assisted']=True
                    session['stage']='near_transfer';state['next_goal']='完成一道相似题'
                    feedback='讲清楚了，接着做一道相似题。' if passed else '这次还少一个关键点，我先记录下来，我们继续练一道相似题。'
                else:feedback=assessment['feedback']
            elif compressed and activity.get('type')=='explanation':
                state['answer_reveal_acknowledged']=True;passed=True
                if answer_text(answer)=='need_help':state['targeted_check_pending']=True;feedback='只确认一个易错点。'
                else:
                    state.update(understanding_passed=True,understood=True,near_transfer=None,next_goal='做一道相似题');session['stage']='near_transfer';feedback='好，直接练一道。'
            elif compressed and state.get('targeted_check_pending') is True:
                source=state.get('teaching_brief',{}).get('check',{});passed=not unknown and micro_passed(source,answer,question)
                attempts=state.setdefault('activity_attempts',{});key=source.get('id','');count=attempts.get(key,0)+1;attempts[key]=count
                if passed or count>=2 or unknown:
                    if not passed:state['assisted']=True
                    state.update(targeted_check_pending=False,understanding_passed=True,understood=True,near_transfer=None,next_goal='做一道相似题');session['stage']='near_transfer';feedback='答对了，练一道类似的。' if passed else '记住这个条件，我们直接练一道。'
                else:feedback=summary(source.get('hint') or '再用刚才的关键条件判断一次。',70)
            else:
                plan=state.get('understanding_plan',[]);index=state.get('understanding_index',0)
                if index<0 or index>=len(plan):raise HTTPException(409,'活动计划已变化，请刷新')
                source=plan[index]
                if state.get('understanding_confirmation') is True:
                    state.update(assisted=True,understanding_confirmation=False,understanding_index=index+1);passed=True;feedback='记住这个判断方法，我们继续下一个小问题。'
                else:
                    passed=not unknown and micro_passed(source,answer,question)
                    attempts=state.setdefault('activity_attempts',{});count=attempts.get(source['id'],0)+1;attempts[source['id']]=count
                    if passed:state['understanding_index']=index+1;feedback='答对了，我们继续。'
                    elif unknown or count>=2:state.update(understanding_confirmation=True,assisted=True);feedback='先看一个最短讲解，再确认一次就继续。'
                    else:feedback=summary(source['hint'],70) if source.get('hint') else ''
                if state.get('understanding_index',0)>=len(plan):
                    state.update(understanding_passed=True,understood=True,next_goal='用自己的话说一遍');feedback='已经抓住这个关键点。'
            if session['stage']=='near_transfer':ensure_variant(db,session,value,'near')
            state.update(activity_feedback=feedback,branch='activity_'+session['stage']+('_pass' if passed else '_continue'))
            db.query('UPDATE tutor_sessions SET stage=?,state=?,turn_count=turn_count+1,updated_at=UTC_TIMESTAMP() WHERE id=?',[session['stage'],json.dumps(state,ensure_ascii=False),session_id])
            user_meta={'activity_id':activity['id'],'activity_type':activity['type'],'working':short_title(working,500) if working else '', 'handwriting_image_url':handwriting['image_url'],'handwriting_recognition':handwriting['recognition'],'grading':transfer.get('grading',{})}
            if 'attempt_consumed' in transfer:user_meta['attempt_consumed']=transfer['attempt_consumed']
            if transfer.get('unknown') is True:user_meta['unknown']=True
            assistant_meta={'activity_id':activity['id'],'passed':passed,'assisted':state.get('assisted') is True}
            for role,content,metadata in [('user',answer_label(activity,answer),user_meta),('assistant',transfer.get('assistant_content') or feedback,assistant_meta)]:
                db.query('INSERT INTO tutor_turns (id,session_id,role,content,stage,metadata_json,created_at,updated_at) VALUES (?,?,?,?,?,?,UTC_TIMESTAMP(6),UTC_TIMESTAMP(6))',[new_id(),session_id,role,content,session['stage'],json.dumps(metadata,ensure_ascii=False)])
            saved=row_json('tutor_sessions',db.query('SELECT * FROM tutor_sessions WHERE id=?',[session_id]).rows[0])
            return session_payload(db,saved,value)
