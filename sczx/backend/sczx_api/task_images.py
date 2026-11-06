import base64
import copy
import hashlib
import json
import re
from fastapi import HTTPException
from .accounts import text_field
from .database import Database
from .learning_evidence import digest
from .memory_sources import task_snapshot
from .practice import request_text
from .rows import row_json
from .security import new_id
from .storage import read_media,write_media,remove_media
from .task_core import owner,task_row,public,validate_version
from .task_policy import object_value,at_limit


def image(db,task,image_id):
    rows=db.query('SELECT * FROM learning_task_images WHERE id=? AND task_id=? AND input_fingerprint=?',[image_id,task['id'],task['input_fingerprint']]).rows
    if not rows:raise HTTPException(422,'这张作答照片不属于当前任务版本')
    return row_json('learning_task_images',rows[0])


def attach_image(db,task,body,event):
    image_id=request_text(body,'handwriting_id',36)
    if not image_id:
        if 'handwriting_confirmed' in body:raise HTTPException(422,'核对标记缺少对应照片')
        return
    if event.get('kind')!='answer':raise HTTPException(422,'照片只能关联本人确认后的作答')
    if body.get('handwriting_confirmed') is not True:raise HTTPException(422,'请先核对照片识别文字，再确认提交')
    photo=image(db,task,image_id)
    if photo.get('confirmation_step_id')!=task['step_id'] or not isinstance(photo.get('recognition'),dict):raise HTTPException(409,'照片对应的步骤已更新，请重新核对当前作答')
    event.update(handwriting_id=image_id,handwriting_confirmed=True,handwriting_recognition=photo['recognition'])


def compute_action(task):
    event=copy.deepcopy(task['pending_action'])
    if event.get('kind')!='recognize_handwriting':return event
    with Database.from_environment() as db:
        photo=image(db,task,event['handwriting_id']);raw=read_media(photo['original_path'])
        if hashlib.sha256(raw).hexdigest()!=photo['sha256']:raise HTTPException(503,'作答原图校验失败，请重新上传')
        event['image_base64']=base64.b64encode(raw).decode();return event


def save_result(db,task,view,next_step):
    event=object_value(task,'pending_action')
    if event.get('kind')!='recognize_handwriting':return
    draft=object_value(view,'handwriting');photo=image(db,task,event['handwriting_id'])
    if draft.get('id')!=photo['id'] or not isinstance(draft.get('recognition'),dict):raise HTTPException(503,'手写转写结果格式不正确')
    db.query('UPDATE learning_task_images SET recognition=?,confirmation_step_id=?,updated_at=UTC_TIMESTAMP(6) WHERE id=?',[json.dumps(draft['recognition'],ensure_ascii=False),next_step,photo['id']])
    draft['image_url']='/'+photo['original_path'];view['handwriting']=draft


def retain_for_support(db,task,result,view,next_step):
    if object_value(task,'pending_action').get('kind') not in ['visualize','observe_visualization','close_visualization','hint','reveal','resume'] or object_value(task,'checkpoint').get('phase','')!=object_value(result,'checkpoint').get('phase','') or view.get('input_kind')!='text':return
    draft=object_value(object_value(task,'student_view'),'handwriting')
    if not draft or object_value(view,'handwriting'):return
    photo=image(db,task,draft['id'])
    if photo.get('confirmation_step_id')!=task['step_id']:return
    db.query('UPDATE learning_task_images SET confirmation_step_id=?,updated_at=UTC_TIMESTAMP(6) WHERE id=?',[next_step,photo['id']]);view['handwriting']=copy.deepcopy(draft)


def upload(request,task_id,body,raw):
    written=None
    try:
        with Database.from_environment() as db:
            user_id=owner(request,db);initial=task_row(db,task_id,user_id)
            if any(k not in ['request_id','version','step_id','input_fingerprint'] for k in body):raise HTTPException(422,'上传包含不支持的字段')
            request_id=text_field(body,'request_id',80);step=text_field(body,'step_id',36);fingerprint=text_field(body,'input_fingerprint',64)
            if request_id=='__initial__':raise HTTPException(422,'请求编号不可用')
            try:
                version_text=text_field(body,'version',12)
                if not re.fullmatch(r'[+-]?[0-9]+',version_text):raise ValueError
                version=int(version_text)
                if not -(2**63)<=version<2**63:raise ValueError
            except (HTTPException,ValueError):raise HTTPException(422,'步骤版本无效') from None
            extension='png' if raw.startswith(b'\x89PNG\r\n\x1a\n') else 'jpg' if raw.startswith(b'\xff\xd8\xff') else 'webp' if raw.startswith(b'RIFF') and raw[8:12]==b'WEBP' else ''
            if not extension:raise HTTPException(422,'请上传JPEG、PNG或WEBP作答照片')
            checksum=hashlib.sha256(raw).hexdigest();body_hash=digest([str(version),step,fingerprint,checksum])
            with db.transaction():
                snapshot=task_snapshot(db,initial['question_id'],user_id,lock=True);task=task_row(db,task_id,user_id,True)
                prior=db.query('SELECT body_hash FROM learning_task_actions WHERE task_id=? AND request_id=?',[task_id,request_id]).rows
                if prior:
                    if prior[0]['body_hash']!=body_hash:raise HTTPException(409,'同一上传编号不能更换照片或步骤')
                    validate_version(db,task,snapshot);return public(task)
                if not validate_version(db,task,snapshot):return public(task)
                if task['status'] not in ['waiting_student','needs_review'] or object_value(task,'student_view').get('input_kind')!='text':raise HTTPException(409,'请先回到当前可作答步骤再上传')
                if version!=task['version'] or step!=task['step_id'] or fingerprint!=task['input_fingerprint']:raise HTTPException(409,'学习步骤已更新，请刷新后重新上传')
                if at_limit(task):raise HTTPException(409,'这次学习已到上限，请结束后回原题重开')
                image_id=new_id();path=f'uploads/answers/{user_id}/learning_task/{task_id}/{image_id}.{extension}';written=path;write_media(path,raw)
                db.query('INSERT INTO learning_task_images (id,task_id,request_id,input_fingerprint,upload_step_id,original_path,sha256,created_at,updated_at) VALUES (?,?,?,?,?,?,?,UTC_TIMESTAMP(6),UTC_TIMESTAMP(6))',[image_id,task_id,request_id,fingerprint,step,path,checksum])
                event={'kind':'recognize_handwriting','text':'','handwriting_id':image_id}
                db.query("INSERT INTO learning_task_actions (id,task_id,request_id,body_hash,kind,input_version,input_step_id,body,status,created_at,updated_at) VALUES (?,?,?,?,'recognize_handwriting',?,?,?,'pending',UTC_TIMESTAMP(6),UTC_TIMESTAMP(6))",[new_id(),task_id,request_id,body_hash,version,step,json.dumps(event,ensure_ascii=False)])
                db.query("UPDATE learning_tasks SET status='queued',version=version+1,pending_action=?,active_request=?,lease_token=NULL,lease_until=NULL,exit_reason='',updated_at=UTC_TIMESTAMP(6) WHERE id=?",[json.dumps(event,ensure_ascii=False),request_id,task_id])
                result=public(task_row(db,task_id,user_id))
            return result
    except BaseException:
        if written:remove_media(written)
        raise
