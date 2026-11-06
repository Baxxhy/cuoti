import os
import re
from pathlib import Path
from fastapi import HTTPException
from .accounts import secret
from .database import Database
from .media import serve_media
from .rows import row_json
from .security import valid_media


async def serve_practice_image(request):
    if not valid_media(request.url.path,request.query_params.get('expires'),request.query_params.get('signature'),secret()):raise HTTPException(403,'资源链接已失效，请返回页面刷新')
    raw=request.path_params['image_index']
    if not re.fullmatch(r'[+-]?[0-9]+',raw):raise HTTPException(422,'图片序号无效')
    index=int(raw)
    if not -(2**63)<=index<2**63:raise HTTPException(422,'图片序号无效')
    with Database.from_environment() as db:
        rows=db.query('SELECT * FROM dataset_questions WHERE id=?',[request.path_params['question_id']]).rows
        if not rows:raise HTTPException(404,'图片不存在')
        paths=row_json('dataset_questions',rows[0]).get('image_paths') or []
        if index<0 or index>=len(paths):raise HTTPException(404,'图片不存在')
        stored=paths[index]
    project=Path(__file__).resolve().parents[2]
    configured=Path(os.environ.get('SCZX_QUESTION_BANK_ROOT','data/question_bank_assets'))
    bank=configured if configured.is_absolute() else project/configured
    absolute=Path(stored) if Path(stored).is_absolute() else project/stored
    # Lexical containment plus no-follow traversal in serve_media, matching the original file API.
    try:relative=absolute.relative_to(bank)
    except ValueError:raise HTTPException(404,'图片不存在') from None
    return await serve_media(request,storage_root=bank,storage_path=str(relative))
