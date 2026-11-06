import base64
import hashlib
from email.message import Message

from fastapi import HTTPException
from starlette.datastructures import UploadFile

from .accounts import current_user
from .algorithm import compute, image_bytes
from .database import Database
from .manual_questions import image_suffix
from .recognition import run_recognition
from .security import new_id
from .storage import write_media, remove_media


async def read_upload(request):
    header = Message(); header['content-type'] = request.headers.get('content-type', '')
    if header.get_content_type() != 'multipart/form-data': raise HTTPException(422, '请选择上传图片')
    boundary = header.get_param('boundary') or ''
    if not boundary or len(boundary.encode()) > 70 or '\r' in boundary or '\n' in boundary:
        raise HTTPException(422, '上传分隔符无效')
    data = bytearray()
    async for chunk in request.stream():
        data.extend(chunk)
        if len(data) > 15 * 1024 * 1024 + 65536: raise HTTPException(413, '图片不能超过 15 MB')
    # Request.body() cannot consume a previously exhausted stream; retain the bounded body.
    request._body = bytes(data)
    try:
        form = await request.form(max_files=32, max_fields=32, max_part_size=15 * 1024 * 1024)
    except Exception:
        raise HTTPException(422, '上传内容格式不正确') from None
    try:
        items = form.multi_items()
        if len(items) > 32: raise HTTPException(422, '上传字段过多')
        file, deferred = None, False
        for key, value in items:
            if key == 'file':
                if file is not None or not isinstance(value, UploadFile): raise HTTPException(422, '请上传一张图片')
                file = value
            else:
                if isinstance(value, UploadFile): raise HTTPException(422, '上传字段无效')
                if len(value.encode()) > 4096: raise HTTPException(422, '上传字段过长')
                if key == 'defer_processing':
                    word = value.lower()
                    if word in ['true', '1', 'on', 'yes', 't', 'y']: deferred = True
                    elif word in ['false', '0', 'off', 'no', 'f', 'n', '']: deferred = False
                    else: raise HTTPException(422, '处理方式无效')
        if file is None: raise HTTPException(422, '缺少图片')
        image = await file.read()
        if not image: raise HTTPException(422, '图片为空，请重新选择图片')
        if len(image) > 15 * 1024 * 1024: raise HTTPException(413, '图片不能超过 15 MB')
        filename = file.filename or '上传错题'
        if len(filename) > 255: raise HTTPException(422, '文件名称过长')
        return image, filename, deferred
    finally:
        await form.close()


async def ingest_question(request, background):
    with Database.from_environment() as db:
        user = current_user(request, db)
        uploaded, filename, deferred = await read_upload(request)
        subject = request.query_params.get('subject') or '数学'
        if len(subject) > 30: raise HTTPException(422, '学科名称过长')
        normalized = compute({'operation': 'normalize', 'image_base64': base64.b64encode(uploaded).decode()})
        if normalized.get('kind') != 'original': raise HTTPException(503, '原图结果无效')
        image = image_bytes(normalized)
        question_id, job_id = new_id(), new_id()
        path = f'uploads/{question_id}/original.jpg'
        uploaded_path = f'uploads/{question_id}/uploaded.{image_suffix(uploaded)}'
        written = []
        try:
            for name, data in [(path, image), (uploaded_path, uploaded)]:
                write_media(name, data); written.append(name)
            with db.transaction():
                db.query("INSERT INTO questions (id,user_id,subject,title,question_text,status,confirmed,favorite,tags,formulas,options,question_type,knowledge_points,created_at,updated_at) VALUES (?,?,?,?,'',?,0,0,JSON_ARRAY(),JSON_ARRAY(),JSON_ARRAY(),'综合题',JSON_ARRAY(),UTC_TIMESTAMP(),UTC_TIMESTAMP())", [question_id, user['id'], subject, filename, 'awaiting_crop' if deferred else 'processing'])
                for kind, name, digest in [('original', path, normalized['sha256']), ('uploaded_original', uploaded_path, hashlib.sha256(uploaded).hexdigest())]:
                    db.query('INSERT INTO question_assets (id,question_id,kind,path,sha256,bbox,created_at,updated_at) VALUES (?,?,?,?,?,JSON_ARRAY(),UTC_TIMESTAMP(),UTC_TIMESTAMP())', [new_id(), question_id, kind, name, digest])
                if not deferred:
                    db.query("INSERT INTO processing_jobs (id,question_id,kind,status,progress,created_at,updated_at) VALUES (?,?,'ingest','pending',0,UTC_TIMESTAMP(),UTC_TIMESTAMP())", [job_id, question_id])
        except BaseException:
            for name in written: remove_media(name)
            raise
        if not deferred: background.add_task(run_recognition, job_id, question_id, path)
        return {'question_id': question_id, 'job_id': None if deferred else job_id, 'status': 'awaiting_crop' if deferred else 'pending'}
