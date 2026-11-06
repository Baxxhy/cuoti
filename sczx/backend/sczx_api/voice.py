import base64
import hashlib
from fastapi import HTTPException
from starlette.concurrency import run_in_threadpool
from .accounts import current_user,read_json,secret
from .algorithm import compute
from .database import Database
from .ingest import read_upload
from .question_edit import number
from .review_search import optional_text
from .rows import row_json
from .security import new_id,media_url
from .storage import write_media,remove_media


def validate_context(db,owner,question_id,work_id):
    if question_id and not db.query('SELECT id FROM questions WHERE id=? AND user_id=?',[question_id,owner]).rows:raise HTTPException(404,'题目不存在或无权访问')
    if work_id:
        rows=db.query('SELECT * FROM student_works WHERE id=? AND user_id=?',[work_id,owner]).rows
        if not rows:raise HTTPException(404,'作答记录不存在或无权访问')
        if question_id and rows[0]['question_id']!=question_id:raise HTTPException(422,'作答记录与题目不匹配')


def insert_voice(db,owner,question_id,work_id,kind,path,text,metadata,failed=False):
    record_id=new_id();duration=number(metadata.get('duration_ms',0))
    if not 0<=duration<=2147483647 or int(duration)!=duration:raise HTTPException(422,'整数超出允许范围')
    model=metadata.get('model') if isinstance(metadata.get('model'),str) else ''
    db.query('INSERT INTO voice_records (id,user_id,question_id,work_id,kind,audio_path,transcript,model_name,status,duration_ms,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,UTC_TIMESTAMP(),UTC_TIMESTAMP())',[record_id,owner,question_id or None,work_id or None,kind,path,text,model,'failed' if failed else 'completed',int(duration)])
    return row_json('voice_records',db.query('SELECT * FROM voice_records WHERE id=?',[record_id]).rows[0])


async def transcribe(request):
    with Database.from_environment() as db:
        user=current_user(request,db);owner=user['id'];question_id=request.query_params.get('question_id','');work_id=request.query_params.get('work_id','');validate_context(db,owner,question_id,work_id)
        data,filename,deferred=await read_upload(request,audio=True);parts=filename.split('.');suffix='.'+parts[-1].lower() if len(parts)>1 else '.webm'
        if suffix not in ['.webm','.wav','.mp3','.m4a','.ogg','.mp4']:suffix='.webm'
        path=f'uploads/voice/{owner}/{new_id()}{suffix}';write_media(path,data)
        try:computed=await run_in_threadpool(compute,{'operation':'voice_transcribe','audio_base64':base64.b64encode(data).decode(),'audio_suffix':suffix})
        except Exception:
            insert_voice(db,owner,question_id,work_id,'stt',path,'',{'model':'faster-whisper-small'},failed=True)
            raise HTTPException(502,'语音转写失败，请稍后重试或使用文字输入') from None
        metadata=computed.get('metadata') or {};text=computed['text']
        with db.transaction():
            record=insert_voice(db,owner,question_id,work_id,'stt',path,text,metadata)
            if work_id:db.query('UPDATE student_works SET explanation=?,updated_at=UTC_TIMESTAMP(6) WHERE id=? AND user_id=?',[text,work_id,owner])
        record.update(text=text,bytes=len(data),editable=True,metadata=metadata,audio_url=media_url('/'+path,secret()));return record


async def synthesize(request):
    with Database.from_environment() as db:
        user=current_user(request,db);owner=user['id'];body=await read_json(request);text=optional_text(body,'text',12000).strip()
        if not text:raise HTTPException(400,'朗读文本不能为空')
        question_id='' if body.get('question_id') is None else optional_text(body,'question_id',36);validate_context(db,owner,question_id,'')
        computed=await run_in_threadpool(compute,{'operation':'voice_synthesize','text':text,'voice':optional_text(body,'voice',100,'zh-CN-XiaoxiaoNeural')})
        data=base64.b64decode(computed['audio_base64'],validate=True)
        if not data or len(data)>64*1024*1024 or hashlib.sha256(data).hexdigest()!=computed['sha256']:raise HTTPException(502,'语音合成结果无效')
        metadata=computed.get('metadata') or {};path=f'uploads/voice/{owner}/tts-{new_id()}.mp3';write_media(path,data)
        try:
            record=insert_voice(db,owner,question_id,'','tts',path,text,metadata)
            record.update(text=text,browser_fallback=False,metadata=metadata,audio_url=media_url('/'+path,secret()));return record
        except Exception:
            try:remove_media(path)
            except OSError:pass
            raise
