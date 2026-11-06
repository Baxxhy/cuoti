from fastapi import HTTPException
from .question_edit import text,number,flag


def integer(value,minimum,maximum):
    value=number(value)
    if not minimum<=value<=maximum or int(value)!=value:raise HTTPException(422,'整数超出允许范围')
    return int(value)


def filters(value):
    if not isinstance(value,dict):raise HTTPException(422,'筛选条件格式不正确')
    result={key:text(value[key],limit) for key,limit in [('subject',30),('knowledge_point',100),('error_type',100)] if key in value}
    low,high=number(value.get('mastery_min',0)),number(value.get('mastery_max',1))
    if low<0 or high>1 or low>high:raise HTTPException(422,'掌握度范围无效')
    for key,number_value in [('mastery_min',low),('mastery_max',high)]:
        if key in value:result[key]=number_value
    if 'due_review' in value:result['due_review']=flag(value['due_review'])
    return result


def items(value):
    if not isinstance(value,list):raise HTTPException(422,'试卷题目格式不正确')
    if len(value)>200:raise HTTPException(422,'试卷不能超过 200 题')
    result=[]
    for item in value:
        if not isinstance(item,dict):raise HTTPException(422,'试卷题目格式不正确')
        result.append({'question_id':text(item.get('question_id'),36,1,True),'score':integer(item.get('score',10),1,100)})
    return result


def payload(body,creating):
    result={}
    if 'title' in body:result['title']=text(body['title'],255,1,True)
    if 'filters' in body:result['filters']=filters(body['filters'])
    if 'items' in body:result['items']=items(body['items'])
    if creating:
        result.update(limit=integer(body.get('limit',10),1,200),default_score=integer(body.get('default_score',10),1,100))
        ids=body.get('question_ids',[])
        if not isinstance(ids,list):raise HTTPException(422,'题目编号格式不正确')
        if len(ids)>200:raise HTTPException(422,'试卷不能超过 200 题')
        result['question_ids']=[text(value,36,1,True) for value in ids]
    return result
