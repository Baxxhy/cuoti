import json
from fastapi import HTTPException
from .accounts import text_field,secret
from .database import Database
from .memory_sources import task_snapshot
from .rows import row_json
from .security import new_id,media_url
from .task_core import owner,task_row,validate_version
from .task_images import image
from .task_policy import object_value
from .task_sources import public_source
from .tasks import strict


def self_check_row(db,task):
    rows=db.query('SELECT * FROM learning_self_checks WHERE user_id=? AND task_id=?',[task['user_id'],task['id']]).rows
    return row_json('learning_self_checks',rows[0]) if rows else {}


def self_check_public(note,current,can_save):
    item={k:note[k] for k in ['id','task_id','question_id','text','version','updated_at']} if note and note['deleted'] is not True else None
    if item is not None:item['kind']='student_self_report'
    return {'version':note['version'] if note else 0,'source_current':current,'can_save':can_save,'note':item}


def audit(db,task,note,operation):
    run_id=new_id();evidence={k:note[k] for k in ['task_id','question_id','version','input_fingerprint']}
    evidence.update(note_id=note['id'],operation=operation,scope='student_self_report',student_confirmed=True)
    encoded=json.dumps(evidence,ensure_ascii=False)
    db.query("INSERT INTO agent_runs (id,session_id,agent_name,status,result,created_at,updated_at) VALUES (?,?,'student_self_check','completed',?,UTC_TIMESTAMP(6),UTC_TIMESTAMP(6))",[run_id,task['session_id'],encoded])
    db.query("INSERT INTO agent_tool_calls (id,agent_run_id,tool_name,input_json,output_json,created_at,updated_at) VALUES (?,?,'save_self_check',?,?,UTC_TIMESTAMP(6),UTC_TIMESTAMP(6))",[new_id(),run_id,encoded,encoded])


def self_check(request,task_id,body):
    method=request.method
    with Database.from_environment() as db:
        user_id=owner(request,db);initial=task_row(db,task_id,user_id)
        if method!='GET':strict(body,['version'] if method=='DELETE' else ['text','version','confirmed','input_fingerprint'])
        with db.transaction():
            snapshot=task_snapshot(db,initial['question_id'],user_id,lock=True);task=task_row(db,task_id,user_id,True)
            current=validate_version(db,task,snapshot);can_save=current and task['status']=='completed'
            note=self_check_row(db,task);version=note['version'] if note else 0
            if method=='GET':return self_check_public(note,current,can_save)
            supplied=body.get('version')
            if type(supplied) is not int or supplied<0:raise HTTPException(422,'请提供要点版本')
            if method=='DELETE' and (not note or note['deleted'] is True):return self_check_public(note,current,can_save)
            text=''
            if method=='PATCH':
                if not can_save:raise HTTPException(409,'请完成当前题目版本的学习，再保存自检要点')
                if body.get('confirmed') is not True:raise HTTPException(422,'请先确认这是你要保存的自检要点')
                if text_field(body,'input_fingerprint',64)!=task['input_fingerprint']:raise HTTPException(409,'原题版本已变化，请重新核对')
                text=text_field(body,'text',300)
                if not text.strip():raise HTTPException(422,'请写一句自检要点')
                if note and note['deleted'] is not True and note['text']==text:return self_check_public(note,current,can_save)
            if supplied!=version:raise HTTPException(409,'自检要点已在别处更新，请重新读取后再保存')
            if not note:
                db.query('INSERT INTO learning_self_checks (id,user_id,question_id,task_id,input_fingerprint,text,version,deleted,created_at,updated_at) VALUES (?,?,?,?,?,?,1,0,UTC_TIMESTAMP(6),UTC_TIMESTAMP(6))',[new_id(),user_id,task['question_id'],task_id,task['input_fingerprint'],text])
            else:db.query('UPDATE learning_self_checks SET text=?,deleted=?,version=version+1,updated_at=UTC_TIMESTAMP(6) WHERE id=?',[text,1 if method=='DELETE' else 0,note['id']])
            saved=self_check_row(db,task);audit(db,task,saved,'delete' if method=='DELETE' else 'create' if version==0 else 'edit')
            return self_check_public(saved,current,can_save)


def history(request,task_id):
    with Database.from_environment() as db:
        user_id=owner(request,db);task_row(db,task_id,user_id);items=[]
        rows=db.query('SELECT * FROM learning_task_actions WHERE task_id=? ORDER BY created_at DESC,id DESC LIMIT 51',[task_id]).rows
        for row in rows[:50]:
            action=row_json('learning_task_actions',row);result=object_value(action,'result');attempt=object_value(result,'attempt')
            item={k:action[k] for k in ['id','kind','status','created_at']}
            item.update(text=object_value(action,'body').get('text',''),feedback=object_value(result,'student_view').get('feedback',''),phase=attempt.get('phase',''),verdict=attempt.get('verdict',''),assisted=attempt.get('assisted') is True,source=attempt.get('source'),visualization=None)
            visual=object_value(object_value(result,'checkpoint'),'visualization')
            if action['kind'] in ['visualize','observe_visualization','close_visualization'] and visual:
                spec=object_value(visual,'spec');values=object_value(visual,'values')
                controls=''.join(v.get('label','')+'：'+json.dumps(values[v.get('name','')],ensure_ascii=False,separators=(',',':'))+'；' for v in spec.get('interactive_variables') or [])
                item.update(visualization={'title':spec['title'],'relation_tex':visual['current_equation_tex'],'controls':controls},phase=visual['source_phase'],assisted=True)
            image_id=object_value(action,'body').get('handwriting_id','')
            item['handwriting_image_url']=media_url('/'+image(db,task_row(db,task_id,user_id),image_id)['original_path'],secret()) if image_id else ''
            items.append(item)
        return {'items':items,'has_more':len(rows)>50,'source_question':public_source(db,task_id)}
