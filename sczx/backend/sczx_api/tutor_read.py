import json
from fastapi import HTTPException
from .accounts import current_user,secret
from .database import Database
from .question_detail import query_array
from .rows import row_json
from .security import media_url
from .tutor_core import canonical_stage,knowledge,understanding_plan,public_progress,public_activity,activity,visualization
from .tutor_start import opening_activity
from .tutor_variants import data_snapshot,ensure_variant


def session_activity(db,session,value):
    state=session['state'];stage=session['stage'];feedback=state.get('activity_feedback','')
    if stage=='understanding' and state.get('understanding_passed') is not True:
        if state.get('teaching_policy',{}).get('mode')!='compressed' and state.get('understanding_confirmation') is True:
            plan=state.get('understanding_plan',[])
            if not plan:return None
            index=max(0,min(state.get('understanding_index',0),len(plan)-1));source=plan[index]
            item=activity(source['id']+'-confirmation','确认一下就继续','解题时，需要依据题目条件一步一步检查，对吗？',[('yes','对，需要检查条件'),('unsure','我还不确定')],['yes'],'',source.get('teaching',''))
            return public_activity(item,1,feedback)
        return opening_activity(state)
    if stage=='teach_back':
        item=activity('teach-back','用一句话讲清楚','如果再遇到这种题，你会先看什么、再怎么判断？')
        points=knowledge(value);cube=any('正方体' in t or '相对面' in t for t in points+[r['text'] for r in value['references']])
        item.update(type='teach_back',sentence_starter='我会先看……',keywords=['相间','Z字两端','折叠'] if cube else points[:3])
        return public_activity(item,state.get('teach_back_attempts',0)+1,feedback)
    if stage in ['near_transfer','far_transfer']:
        if stage=='near_transfer' and state.get('near_confirmation'):
            return public_activity(state['near_confirmation'],1,feedback)
        transfer='near' if stage=='near_transfer' else 'far';variant=ensure_variant(db,session,value,transfer)
        options=state.get(transfer+'_variant_options',[]);kind=state.get('teaching_policy',{}).get('question_type') or value['question']['question_type']
        activity_type=('multiple_choice' if kind=='multiple_choice' else 'single_choice') if options else 'short_answer' if kind=='fill_blank' else 'variant'
        public_options=[]
        for option in options:
            if not isinstance(option,dict):continue
            label,text=option.get('label',''),option.get('text','')
            public_options.append({'value':label,'label':text if not label else label if not text else label+'  '+text})
        item=activity(transfer+'-variant-'+variant['id'],'相似题练习' if transfer=='near' else '换个场景试一试',variant['question_text'],teaching=state.get('transfer_guidance',''))
        item.update(type=activity_type,variant_id=variant['id'],options=public_options,input_mode='multiple_choice' if activity_type=='multiple_choice' else 'choice' if activity_type=='single_choice' else kind)
        if state.get('transfer_guidance'):item['teaching_title']='我们一步一步写'
        return public_activity(item,state.get(transfer+'_attempts',0)+1,feedback)
    return None


def session_payload(db,session,value):
    state,question=session['state'],value['question'];points=knowledge(value);stage=session['stage']
    result=dict(session)
    # Keep projection order: generating an activity can update internal variant state.
    result['state']=public_progress(state)
    result['stage_status']='completed' if stage=='finished' else 'passed' if stage=='understanding' and state.get('understanding_passed') is True else 'active'
    result.update(activity=session_activity(db,session,value),assisted=state.get('assisted') is True,teaching_policy=state.get('teaching_policy',{'mode':'full'}),answer_reveal=state.get('answer_reveal'),completion_summary=state.get('completion_summary',''),knowledge_title=' · '.join(points[:2]) or question['title'],visualization_available=visualization(question['subject'],question['question_type'],points) is not None)
    figures=db.query("SELECT path FROM question_assets WHERE question_id=? AND kind IN ('question_figure','crop') ORDER BY (kind='question_figure') DESC,created_at DESC,id DESC LIMIT 1",[question['id']]).rows
    result['question']={'id':question['id'],'text':question['question_text'],'figure_url':media_url('/'+figures[0]['path'],secret()) if figures else None}
    turns=query_array(db,'tutor_turns','SELECT * FROM tutor_turns WHERE session_id=? ORDER BY created_at,id',session['id'])
    for turn in turns:
        metadata=turn['metadata_json'] if isinstance(turn['metadata_json'],dict) else {}
        if metadata.get('handwriting_image_url'):metadata['handwriting_image_url']=media_url(metadata['handwriting_image_url'],secret())
    result['turns']=turns
    return result


async def read_tutor(request):
    session_id=request.path_params['session_id']
    with Database.from_environment() as db:
        user=current_user(request,db)
        with db.transaction():
            rows=db.query('SELECT * FROM tutor_sessions WHERE id=? AND user_id=?',[session_id,user['id']]).rows
            if not rows:raise HTTPException(404,'教学会话不存在或无权访问')
            session=row_json('tutor_sessions',rows[0]);session['stage']=canonical_stage(session['stage'])
            value=data_snapshot(db,session['question_id'],user['id']);state=session['state'] if isinstance(session['state'],dict) else {};session['state']=state
            state.setdefault('understanding_passed',False);state.setdefault('assisted',False)
            if state.get('teaching_policy',{}).get('mode')=='compressed' and state.get('teaching_brief'):
                state.setdefault('answer_reveal_acknowledged',False);state.setdefault('targeted_check_pending',False)
            elif not state.get('understanding_plan'):
                question=value['question'];state['understanding_plan']=understanding_plan(question['question_text'],question['subject'],question['question_type'],knowledge(value),[r['text'] for r in value['references']]);state['understanding_index']=0;state['activity_attempts']={}
            db.query('UPDATE tutor_sessions SET stage=?,state=? WHERE id=?',[session['stage'],json.dumps(state,ensure_ascii=False),session_id])
            return session_payload(db,session,value)
