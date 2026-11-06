import re
from fastapi import HTTPException
from .algorithm import compute
from .question_edit import text
from .storage import read_media


def validate_handwriting(body,owner,session_id,kind='tutor'):
    raw=text(body.get('handwriting_image_url',''),2048,trim=True)
    recognition=body.get('handwriting_recognition')
    if not raw:
        if recognition is not None:raise HTTPException(422,'手写识别结果缺少对应原图')
        return {'image_url':'','recognition':None}
    path=raw.split('?',1)[0];prefix=f'/uploads/answers/{owner}/{kind}/{session_id}/handwriting-'
    if not path.startswith(prefix) or not re.fullmatch(r'[0-9a-f]{32}\.jpg',path[len(prefix):]):raise HTTPException(422,'手写作答图片无效')
    try:read_media(path[1:])
    except Exception:raise HTTPException(422,'手写作答图片无效') from None
    if recognition is not None and not isinstance(recognition,dict):raise HTTPException(422,'手写作答识别结果无效')
    return {'image_url':path,'recognition':compute({'operation':'validate_handwriting','recognition':recognition or {}})}
