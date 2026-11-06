import json
from fastapi import HTTPException
from .accounts import current_user, read_json
from .algorithm import compute
from .question_detail import query_array
from .question_edit import text
from .database import Database
from .rows import row_json
from .security import new_id
from .tutor_core import knowledge,canonical_stage
from .tutor_start import record_tool
from . import retrieval


def data_snapshot(db,question_id,owner):
    rows=db.query('SELECT * FROM questions WHERE id=? AND user_id=?',[question_id,owner]).rows
    if not rows: raise HTTPException(404,'题目不存在或无权访问')
    analyses=query_array(db,'problem_analyses','SELECT * FROM problem_analyses WHERE question_id=?',question_id)
    return {'question':row_json('questions',rows[0]),'analysis':analyses[0] if analyses else None,'references':query_array(db,'reference_steps','SELECT r.* FROM reference_steps r JOIN problem_analyses a ON a.id=r.analysis_id WHERE a.question_id=? ORDER BY r.step_index,r.id',question_id)}


def variant_retrieval(db,value,transfer):
    try:
        question=value['question']; mode='reinforce' if transfer=='near' else 'variation'
        excluded=[];used=set()
        for row in db.query('SELECT * FROM variant_questions WHERE question_id=?',[question['id']]).rows:
            old=row_json('variant_questions',row);used.add(old['question_text']);excluded.extend((old['generation_metadata'] or {}).get('retrieval_ids',[]))
        prepared=retrieval.preparation(db,question,value['analysis'],'variant',mode)
        ranked=retrieval.candidates(db,question,prepared,excluded,'variant',mode)
        return {'references':[r for r in ranked.get('references',[]) if r['question_text'] not in used],'status':'ok'}
    except Exception:
        return {'references':[],'status':'unavailable'}


def ensure_variant(db,session,value,transfer):
    state=session['state']; session_id=session['id'];question=value['question'];points=knowledge(value)
    existing=db.query('SELECT * FROM variant_questions WHERE id=? AND session_id=?',[state.get(transfer+'_variant_id') or '',session_id]).rows
    if existing:
        item=row_json('variant_questions',existing[0]);candidate={k:item[k] for k in ['question_text','answer','explanation','reference_solution']}
        checked=compute({'operation':'validate_variant','text':question['question_text'],'subject':question['subject'],'knowledge_points':points,'variant_candidate':candidate})
        if checked.get('valid') is True:
            state[transfer+'_validated_variant_id']=item['id']
            db.query('UPDATE tutor_sessions SET state=? WHERE id=?',[json.dumps(state,ensure_ascii=False),session_id]);return item
        state.setdefault('invalidated_variant_ids',[]).append(item['id']);state[transfer+'_variant_id']=None;state[transfer+'_validated_variant_id']=None
    if question['status']=='archived':raise HTTPException(409,'题目已归档，不能生成新练习')
    if state.get('question_changed') is True:raise HTTPException(409,'题目已变化，请重新开始学习')
    context='；'.join([question['question_text']]+points)
    diagnoses=db.query('SELECT root_misconception FROM diagnoses WHERE question_id=? ORDER BY created_at DESC,id DESC LIMIT 1',[question['id']]).rows
    if diagnoses:context+='；'+diagnoses[0]['root_misconception']
    retrieved=variant_retrieval(db,value,transfer)
    computed=compute({'operation':'generate_variant','text':context,'subject':question['subject'],'question_type':question['question_type'],'transfer_type':transfer,'knowledge_points':points,'variant_references':retrieved['references']})
    generated=computed['variant'];generation=dict(computed['generation']);generation.update(retrieval_pipeline='bge_m3_qdrant_reranker',retrieval_status=retrieved['status']);variant_id=new_id()
    db.query('INSERT INTO variant_questions (id,question_id,session_id,transfer_type,question_text,answer,explanation,reference_solution,verified,generation_metadata,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,UTC_TIMESTAMP(),UTC_TIMESTAMP())',[variant_id,question['id'],session_id,transfer,generated['question_text'],generated['answer'],generated['explanation'],json.dumps(generated['reference_solution'],ensure_ascii=False),int(computed['verified']),json.dumps(generation,ensure_ascii=False)])
    state.update({transfer+'_variant_id':variant_id,transfer+'_validated_variant_id':variant_id if computed['verified'] else None,transfer+'_attempts':0,transfer+'_variant_generation':generation,transfer+'_variant_options':generated['options'],'activity_feedback':''})
    db.query('UPDATE tutor_sessions SET state=?,updated_at=UTC_TIMESTAMP() WHERE id=?',[json.dumps(state,ensure_ascii=False),session_id])
    output={'variant_id':variant_id,'verified':computed['verified'],**generation}
    record_tool(db,session_id,'generate_variant',{'transfer_type':transfer,'knowledge_points':points,'retrieval_pipeline':'bge_m3_qdrant_reranker'},output,{**output,'branch':transfer+'_transfer_generated'})
    return row_json('variant_questions',db.query('SELECT * FROM variant_questions WHERE id=?',[variant_id]).rows[0])


async def tutor_variant(request):
    session_id=request.path_params['session_id']
    with Database.from_environment() as db:
        user=current_user(request,db);body=await read_json(request,default_empty=True);transfer=text(body.get('transfer_type','near'),10)
        if transfer not in ['near','far']:raise HTTPException(422,'迁移类型必须是 near 或 far')
        with db.transaction():
            rows=db.query('SELECT * FROM tutor_sessions WHERE id=? AND user_id=?',[session_id,user['id']]).rows
            if not rows:raise HTTPException(404,'教学会话不存在或无权访问')
            session=row_json('tutor_sessions',rows[0]);session['stage']=canonical_stage(session['stage'])
            if session['stage']!=transfer+'_transfer':raise HTTPException(409,'当前教学阶段不能生成这类练习')
            item=ensure_variant(db,session,data_snapshot(db,session['question_id'],user['id']),transfer)
            return {k:item[k] for k in ['id','question_id','session_id','transfer_type','question_text','verified','created_at','updated_at']}
