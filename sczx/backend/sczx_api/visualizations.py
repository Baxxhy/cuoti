import json
from fastapi import HTTPException
from .accounts import current_user,read_json
from .algorithm import compute
from .database import Database
from .question_detail import query_array
from .rows import row_json
from .security import new_id
from .tutor_core import knowledge
from .tutor_start import record_tool
from .tutor_variants import data_snapshot


def visualization_config(question,points,values):
    return compute({'operation':'visualization_config','subject':question['subject'],'question_type':question['question_type'],'teach_back_points':points,'visualization_values':values})


async def session_visualization(request):
    writing=request.method=='POST';session_id=request.path_params['session_id']
    with Database.from_environment() as db:
        user=current_user(request,db);body=await read_json(request,default_empty=True) if writing else {}
        values=body.get('values',{})
        if not isinstance(values,dict):raise HTTPException(422,'演示参数格式不正确')
        observation=body.get('observation','')
        if not isinstance(observation,str):raise HTTPException(422,'observation 必须是文字')
        if len(observation)>12000:raise HTTPException(422,'observation 长度不正确')
        with db.transaction():
            sessions=db.query('SELECT * FROM tutor_sessions WHERE id=? AND user_id=?',[session_id,user['id']]).rows
            if not sessions:raise HTTPException(404,'教学会话不存在或无权访问')
            session=row_json('tutor_sessions',sessions[0]);value=data_snapshot(db,session['question_id'],user['id']);question=value['question']
            state=session['state'] if isinstance(session['state'],dict) else {}
            if writing and (state.get('question_changed') is True or question['status']=='archived'):raise HTTPException(409,'题目已变化或归档，请重新开始学习')
            config=visualization_config(question,knowledge(value),values);spec=config['spec']
            if not isinstance(spec,dict):raise HTTPException(404,'这道题暂时没有匹配的互动演示')
            if not writing:return {'question':{k:question[k] for k in ['id','title','question_text']},'spec':spec}
            visual_id=new_id()
            db.query('INSERT INTO visualization_specs (id,session_id,type,title,spec,created_at,updated_at) VALUES (?,?,?,?,?,UTC_TIMESTAMP(),UTC_TIMESTAMP())',[visual_id,session_id,spec['type'],spec['title'],json.dumps(spec,ensure_ascii=False)])
            if observation:
                interaction_id=new_id()
                db.query('INSERT INTO visualization_interactions (id,visualization_id,user_id,`values`,observation,created_at,updated_at) VALUES (?,?,?,?,?,UTC_TIMESTAMP(),UTC_TIMESTAMP())',[interaction_id,visual_id,user['id'],json.dumps(values,ensure_ascii=False),observation])
                output={'interaction_id':interaction_id,'observation':observation,'expected_observation':spec['expected_observation']}
                record_tool(db,session_id,'observe_visualization',{'type':spec['type'],'values':values},output,{**output,'branch':'visualization_evidence'})
            return row_json('visualization_specs',db.query('SELECT * FROM visualization_specs WHERE id=?',[visual_id]).rows[0])


async def visualization_types():
    return visualization_config({'subject':'数学','question_type':'综合题'},[],{})['catalog']


async def read_visualization(request):
    visual_id=request.path_params['visualization_id']
    with Database.from_environment() as db:
        user=current_user(request,db)
        rows=db.query('SELECT v.* FROM visualization_specs v JOIN tutor_sessions s ON s.id=v.session_id WHERE v.id=? AND s.user_id=?',[visual_id,user['id']]).rows
        if not rows:raise HTTPException(404,'可视化不存在或无权访问')
        result=row_json('visualization_specs',rows[0]);result['interactions']=query_array(db,'visualization_interactions','SELECT * FROM visualization_interactions WHERE visualization_id=? ORDER BY created_at,id',visual_id)
        return result
