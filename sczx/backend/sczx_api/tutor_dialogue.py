import base64
import json
from fastapi import HTTPException
from .accounts import current_user,read_json
from .algorithm import compute
from .database import Database
from .diagnosis import knowledge_cards
from .learning_memory import learning_memory,audit_manifest
from .question_detail import query_array
from .rows import row_json
from .security import new_id
from .storage import read_media
from .tutor_core import canonical_stage
from .tutor_start import record_tool
from .tutor_variants import data_snapshot


def snapshot(db,session_id,owner):
    rows=db.query('SELECT * FROM tutor_sessions WHERE id=? AND user_id=? FOR UPDATE',[session_id,owner]).rows
    if not rows:raise HTTPException(404,'教学会话不存在或无权访问')
    session=row_json('tutor_sessions',rows[0]);session['stage']=canonical_stage(session['stage'])
    if session['stage']=='finished':raise HTTPException(409,'本次学习已经完成')
    question_id=session['question_id'];value=data_snapshot(db,question_id,owner);question=value['question'];state=session['state'] if isinstance(session['state'],dict) else {}
    if question['status']=='archived' or state.get('question_changed') is True:raise HTTPException(409,'题目已变化或归档，请重新开始学习')
    value['session']=session
    value['steps']=query_array(db,'student_steps','SELECT * FROM student_steps WHERE work_id=(SELECT id FROM student_works WHERE question_id=? ORDER BY created_at DESC,id DESC LIMIT 1) ORDER BY step_index,id',question_id)
    works=query_array(db,'student_works','SELECT * FROM student_works WHERE question_id=? ORDER BY created_at DESC,id DESC LIMIT 1',question_id);value['work']=works[0] if works else None
    value['assets']=query_array(db,'question_assets',"SELECT * FROM question_assets WHERE question_id=? AND kind IN ('crop','question_figure') ORDER BY created_at,id",question_id)
    value['turns']=query_array(db,'tutor_turns','SELECT * FROM tutor_turns WHERE session_id=? ORDER BY created_at DESC,id DESC LIMIT 7',session_id)
    memory=learning_memory(db,owner,question);value.update(memory=memory['legacy_rows'],memory_snapshot=memory['snapshot'])
    return value


def context(value,message):
    question=value['question'];analysis=value.get('analysis') or {};session=value['session'];state=session['state'] if isinstance(session['state'],dict) else {}
    result={'memory_snapshot':value['memory_snapshot'],**{k:question[k] for k in ['subject','question_type','question_text','student_answer','knowledge_points']}}
    points=[]
    for source in [question,analysis]:
        for point in source.get('knowledge_points',[]):
            if point not in points and len(points)<10:points.append(point)
    recent=[{k:turn[k] for k in ['role','content']} for turn in reversed(value['turns'])]+[{'role':'user','content':message}]
    result.update(knowledge_points=points,grade=question['grade'] or '',final_answer=analysis.get('final_answer',''),reference_steps=[r['text'] for r in value['references']],student_steps=[r['text'] for r in value['steps']],student_message=message,turn_count=session['turn_count']+1,hint_level=session['hint_level'],repeated_count=state.get('repeated_count',0)+1 if message==state.get('last_message','') else 0,recent_turns=recent)
    return result


async def tutor_dialogue(request):
    session_id=request.path_params['session_id']
    with Database.from_environment() as db:
        user=current_user(request,db);body=await read_json(request);message=body.get('message','')
        if not isinstance(message,str):raise HTTPException(422,'message 必须是文字')
        if len(message)>12000:raise HTTPException(422,'message 长度不正确')
        message=message.strip()
        if not message:raise HTTPException(422,'请输入你的想法')
        with db.transaction():initial=snapshot(db,session_id,user['id'])
        domain=context(initial,message);payload={'operation':'tutor_dialogue_prepare','dialogue_context':domain,'dialogue_memory_rows':initial['memory']}
        preparation=compute(payload);plan=preparation.get('plan') or {};uses_knowledge=plan.get('tool_name')=='knowledge_search'
        cards=knowledge_cards(db,preparation['knowledge_query'],domain['subject'],domain['grade']) if uses_knowledge else []
        payload.update(operation='tutor_dialogue_finish',dialogue_preparation=preparation,dialogue_cards=cards)
        images=[];seen=set()
        for asset in initial['assets']:
            path=asset['path']
            if path in seen:continue
            seen.add(path)
            try:images.append(base64.b64encode(read_media(path)).decode())
            except HTTPException as error:
                if error.status_code!=404:raise
        payload['images_base64']=images;computed=compute(payload)
        with db.transaction():
            current=snapshot(db,session_id,user['id'])
            if initial!=current:raise HTTPException(409,'题目、会话或学习记录已变化，请刷新后重试')
            if uses_knowledge and cards!=knowledge_cards(db,preparation['knowledge_query'],domain['subject'],domain['grade']):raise HTTPException(409,'知识卡已更新，请重试')
            session=current['session'];state=session['state'] if isinstance(session['state'],dict) else {};stage=session['stage'];graph=computed.get('graph') or {};agent=computed.get('agent') or {};tool=agent.get('tool') or {};verification=agent.get('verification') or {}
            state.update(last_message=message,repeated_count=domain['repeated_count'])
            for key in ['branch','strategy','next_goal','mastery_proven']:state[key]=graph[key]
            state.setdefault('understanding_passed',False)
            state.update(dialogue_stage=graph['stage'],agent_verification=verification['status'],agent_memory_refs=plan['memory_source_ids'])
            if plan.get('tool_name')=='visualization':state['visualization_type']=(tool.get('evidence') or {}).get('visualization_type')
            db.query('UPDATE tutor_sessions SET stage=?,turn_count=?,hint_level=?,state=?,updated_at=UTC_TIMESTAMP() WHERE id=?',[stage,domain['turn_count'],graph['hint_level'],json.dumps(state,ensure_ascii=False),session_id])
            metadata={k:graph[k] for k in ['branch','strategy','next_goal','mastery_proven']}
            metadata.update(knowledge_sources=computed.get('knowledge_sources',[]),tool_name=plan['tool_name'],decision_verified=verification['status'],planner_status=agent['planner_status'])
            for role,text,meta in [('user',message,{'input_stage':stage}),('assistant',computed['reply'],metadata)]:
                db.query('INSERT INTO tutor_turns (id,session_id,role,content,stage,metadata_json,created_at,updated_at) VALUES (?,?,?,?,?,?,UTC_TIMESTAMP(6),UTC_TIMESTAMP(6))',[new_id(),session_id,role,text,stage,json.dumps(meta,ensure_ascii=False)])
            output=dict(tool.get('evidence') or {});output.update(stage=stage,next_goal=graph['next_goal'],executed=tool['executed'])
            details={'memory_manifest':audit_manifest(initial['memory_snapshot'])}
            details.update({k:agent[k] for k in ['observation','plan','verification','planner_status']})
            record_tool(db,session_id,plan['tool_name'],tool.get('consumed_input') or {},output,{**output,'branch':graph['branch'],**details})
            return {'message':computed['reply'],'stage':stage,'hint_level':graph['hint_level'],**metadata}
