import re
from fastapi import HTTPException
from .database import Database
from .manual_questions import answer_text
from .rows import row_json


async def knowledge_cards(request):
    params=[];subject=request.query_params.get('subject','');grade=request.query_params.get('grade','');misconception=request.query_params.get('misconception','')
    words=[w for w in re.split(r'[\s，、]+',request.query_params.get('q','')) if len(w)>=2][:5]
    sql='SELECT * FROM knowledge_points WHERE 1=1'
    if subject:sql+=' AND subject=?';params.append(subject)
    if words:
        sql+=' AND ('+' OR '.join('(name LIKE ? OR code LIKE ? OR CAST(content AS CHAR) LIKE ?)' for _ in words)+')'
        for word in words:params.extend(['%'+word+'%']*3)
    if grade:sql+=" AND LOCATE(?,JSON_UNQUOTE(JSON_EXTRACT(content,'$.grade'))) > 0";params.append(grade)
    if misconception:sql+=" AND LOCATE(?,JSON_UNQUOTE(JSON_EXTRACT(content,'$.common_misconceptions'))) > 0";params.append(misconception)
    sql+=' ORDER BY subject,code LIMIT 50'
    with Database.from_environment() as db:
        result=[]
        for row in db.query(sql,params).rows:
            item=row_json('knowledge_points',row);content=item['content'] if isinstance(item['content'],dict) else {}
            if grade and grade not in answer_text(content.get('grade','')):continue
            labels=content.get('common_misconceptions',[]);labels=labels if isinstance(labels,list) else []
            if misconception and misconception not in ' '.join(map(answer_text,labels)):continue
            result.append(item)
        return result


async def read_knowledge_card(request):
    code=request.path_params['code']
    with Database.from_environment() as db,db.transaction():
        rows=db.query('SELECT * FROM knowledge_points WHERE code=? OR id=? LIMIT 1',[code,code]).rows
        if not rows:raise HTTPException(404,'知识卡不存在')
        result=row_json('knowledge_points',rows[0]);card_id=rows[0]['id']
        for key,sql in [('prerequisites','SELECT k.* FROM knowledge_relations r JOIN knowledge_points k ON k.id=r.target_id WHERE r.source_id=?'),('next_knowledge','SELECT k.* FROM knowledge_relations r JOIN knowledge_points k ON k.id=r.source_id WHERE r.target_id=?')]:
            result[key]=[row_json('knowledge_points',row) for row in db.query(sql,[card_id]).rows]
        return result
