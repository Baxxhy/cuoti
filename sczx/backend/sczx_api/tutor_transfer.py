from fastapi import HTTPException
from .algorithm import compute
from .manual_questions import answer_text
from .rows import row_json
from .security import new_id
from .tutor_core import activity
from .tutor_completion import complete_learning
from .tutor_variants import ensure_variant


def answer_transfer(db,session,value,answer,unknown,elapsed):
    state=session['state'];stage=session['stage'];near=stage=='near_transfer';kind='near' if near else 'far'
    result={};passed=False;feedback='';skip_far=state.get('teaching_policy',{}).get('skip_far_transfer') is True
    if near and isinstance(state.get('near_confirmation'),dict):
        state.update(near_confirmation=None,near_transfer=False,assisted=True);passed=True
        if skip_far:complete_learning(db,session,value,True);feedback='本轮练习完成。'
        else:
            session['stage']='far_transfer';state['next_goal']='换个场景再试一次';ensure_variant(db,session,value,'far');feedback='继续换个场景练习。'
    else:
        rows=db.query('SELECT * FROM variant_questions WHERE id=? AND session_id=?',[state.get(kind+'_variant_id') or '',session['id']]).rows
        if not rows:raise HTTPException(409,'练习已变化，请刷新后继续')
        variant=row_json('variant_questions',rows[0])
        help_needed=unknown or any(phrase in answer_text(answer) for phrase in ['不会写','不知道怎么写','没有思路','没思路','教我写','请教我','不会做'])
        if help_needed:
            lines=[]
            for step in variant.get('reference_solution') or []:
                if len(lines)>=6:break
                text=answer_text(step).strip()
                if text:lines.append(text)
            if not lines:lines=[variant.get('explanation') or '先找出已知条件，再列出关系式。']
            guidance='可以按这个顺序写：'+''.join(f'\n{i+1}. {text}' for i,text in enumerate(lines))
            expected=answer_text(variant['answer'])
            if expected and expected not in guidance:guidance+=f'\n{len(lines)+1}. 得到结论：{expected}'
            state.update(transfer_guidance=guidance,assisted=True)
            result.update(assistant_content=guidance,attempt_consumed=False,unknown=True)
            feedback='不会写没关系，先按提示一步步写，这次不计作答次数。'
        else:
            state['transfer_guidance']=None;question=value['question']
            grade=compute({'operation':'grade_answer','text':variant['question_text'],'answer':answer,'expected':variant['answer'],'reference_solution':variant.get('reference_solution') or [],'subject':question['subject'],'question_type':question['question_type'],'options':state.get(kind+'_variant_options',[])})
            result['grading']=grade;feedback=grade.get('feedback','')
            if grade.get('can_update_learning') is not True:state['last_grading']=grade;result['attempt_consumed']=False
            else:
                passed=grade.get('correct') is True;count=state.get(kind+'_attempts',0)+1;state[kind+'_attempts']=count;result['attempt_consumed']=True
                db.query('INSERT INTO variant_attempts (id,variant_id,user_id,answer,correct,elapsed_seconds,hint_level,created_at,updated_at) VALUES (?,?,?,?,?,?,?,UTC_TIMESTAMP(),UTC_TIMESTAMP())',[new_id(),variant['id'],session['user_id'],answer_text(answer),int(passed),elapsed,session.get('hint_level',0)])
                if passed:
                    state[stage]=True
                    if near and not skip_far:
                        session['stage']='far_transfer';state['next_goal']='换个场景再试一次';ensure_variant(db,session,value,'far');feedback='相似题做对了，换个场景再试一次。'
                    else:complete_learning(db,session,value,False);feedback='练习完成，本轮学习结束。'
                elif count>=2:
                    state[stage]=False;state['assisted']=True
                    if near and not skip_far:
                        state['near_confirmation']=activity('near-remediation-'+variant['id'],'看懂这一步就继续','根据刚才的讲解，这道题的参考结论是什么？',[('expected',answer_text(variant['answer'])),('unsure','我还不能确定')],['expected'],'',variant.get('explanation') or '')
                        feedback='先看简短讲解，确认后继续。'
                    else:state['transfer_insufficient']=True;complete_learning(db,session,value,True);feedback='本轮学习结束，已安排近期复习。'
    result.update(passed=passed,feedback=feedback)
    return result
