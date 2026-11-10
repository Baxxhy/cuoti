"""Bounded student guidance on existing ModelJob history and published task snapshots."""
import copy,re,time,hashlib,json
from typing import TypedDict,Literal
from fastapi import HTTPException
from pydantic import Field
from sqlalchemy import select
from langgraph.graph import StateGraph,START,END
from .ai_schemas import GuidanceResult
from .models import ModelJob,LearningTask,KnowledgePoint
from .model_provider import ModelError
from .math_tools import solve_text_equation

STRATEGIES={'hint':'给我提示','example':'举个例子','rephrase':'换一种讲法','foundation':'补基础','try':'自己试试'}
class TutoringResult(GuidanceResult):
    strategy:Literal['hint','example','rephrase','foundation','try']
    representation:Literal['question','numeric','balance','symbolic','comparison']
    nextStrategy:Literal['hint','example','rephrase','foundation','try']='hint'
    prerequisiteId:str=''
    usedCaseVersionIds:list[str]=Field(default_factory=list,max_length=5)

PUBLIC_BLOCK=('id','type','title','content','activity','questionIds')
PUBLIC_QUESTION=('id','kind','prompt','equation','knowledgeIds')
def public_fields(value,fields):return {key:copy.deepcopy(value[key]) for key in fields if key in value}
def request_fingerprint(payload):
    keys=('guidance','strategy','prompt','question','blockId','parentJobId','ocrJobId','confirmed','recognizedText','confirmedEquation')
    request={key:payload.data.get(key) for key in keys}
    return hashlib.sha256(json.dumps({'data':request,'record':payload.recordId,'file':payload.fileId,'capability':payload.capability},sort_keys=True,ensure_ascii=False).encode()).hexdigest()

def prepare(db,user,record,data):
    """Rebuild all trusted context; ignore client context/history/answer fields."""
    task=db.get(LearningTask,record.task_id);question=data.get('question');block_id=data.get('blockId')
    if question is not None and (isinstance(question,bool) or not isinstance(question,int) or not 0<=question<len(task.questions)):raise HTTPException(422,'当前题目不存在。')
    blocks=task.snapshot.get('blocks',[]);block=next((b for b in blocks if b.get('id')==block_id),None)
    q=task.questions[question] if question is not None else None
    if not block and q:block=next((b for b in blocks if q.get('id') in b.get('questionIds',[])),None)
    if block_id and not block:raise HTTPException(422,'当前内容块不存在。')
    strategy=data.get('strategy','hint')
    if strategy not in STRATEGIES and strategy!='continue':raise HTTPException(422,'请选择有效的指导方式。')
    prompt=data.get('prompt','');prompt=prompt.strip() if isinstance(prompt,str) else ''
    if len(prompt)>3000:raise HTTPException(422,'问题最多3000字，请分段提问。')
    if not prompt and strategy!='try':raise HTTPException(422,'请写下问题或对追问的回应。')
    parent=None;history=[];cursor=data.get('parentJobId');seen=set()
    for _ in range(4):
        if not cursor:break
        if not isinstance(cursor,str) or cursor in seen:raise HTTPException(422,'指导历史关联无效。')
        seen.add(cursor);item=db.get(ModelJob,cursor)
        if not item or item.owner_id!=user.id or item.record_id!=record.id or not item.input.get('guidance') or item.input.get('question')!=question or item.input.get('blockId')!=(block or {}).get('id'):
            raise HTTPException(422,'请选择当前题目与内容块的指导历史。')
        if item.input.get('ocrJobId')!=data.get('ocrJobId'):raise HTTPException(422,'原题与不同题图的指导不能混用，请开始新一轮。')
        if item.status!='succeeded':raise HTTPException(409,'上一轮尚未完成，请先重试或结束该轮。')
        parent=parent or item
        history.append({'student':str(item.input.get('prompt',''))[:1000],'strategy':item.input['strategy'],'representation':(item.result or {}).get('representation'),'hint':str((item.result or {}).get('hint',''))[:1000],'question':str((item.result or {}).get('question',''))[:300]})
        cursor=item.input.get('parentJobId')
    if strategy=='continue':strategy=(parent.result or {}).get('nextStrategy','hint') if parent else 'hint'
    if data.get('strategy')=='continue':
        if re.search('不懂|不理解|不明白|不会|不知道',prompt):strategy='foundation'
        elif re.search('懂了|明白了|自己试|我来试',prompt):strategy='try'
        elif strategy=='try':strategy='hint'
    history.reverse()
    lesson=task.snapshot.get('lessonSnapshot') or {}
    ids=list((q or {}).get('knowledgeIds') or lesson.get('knowledgeIds') or task.snapshot.get('knowledgeIds') or [])
    points=[db.get(KnowledgePoint,i) for i in ids];points=[p for p in points if p]
    prereq_ids=list(dict.fromkeys(i for p in points for i in p.prerequisites))[:12]
    prerequisites=[db.get(KnowledgePoint,i) for i in prereq_ids];prerequisites=[{'id':p.id,'name':p.name} for p in prerequisites if p]
    from .retrieval import student_request,retrieve,published_documents,knowledge_documents
    spec=student_request(task.snapshot,q,record.observation,prompt,str(data.get('recognizedText',''))[:6000]);knowledge=knowledge_documents(db);known={p['id'] for p in knowledge}
    for key in ('knowledgeIds','prerequisiteIds'):spec['context'][key]=[i for i in spec['context'][key] if i in known]
    retrieved=retrieve(spec,published_documents(db),knowledge)
    sources=[]
    for value in retrieved['items'][:4]:sources.append({k:copy.deepcopy(value[k]) for k in ('id','versionId','version','title','source','content','references') if k in value})
    ocr_id=data.get('ocrJobId');file_id=None;recognized=''
    if ocr_id:
        original=db.get(ModelJob,ocr_id)
        if not original or original.owner_id!=user.id or original.record_id!=record.id or original.capability!='ocr' or original.status!='succeeded' or original.input.get('question')!=question or ('blockId' in original.input and original.input.get('blockId')!=(block or {}).get('id')) or data.get('confirmed') is not True:raise HTTPException(422,'请先核对当前内容与题目的识别结果。')
        recognized=str(data.get('recognizedText','')).strip()
        if len(recognized)>6000:raise HTTPException(422,'本轮核对文字最多6000字，请分段处理。')
        if not recognized:raise HTTPException(422,'请填写确认后的题目。')
        file_id=original.file_id
    confirmed_equation=str(data.get('confirmedEquation','')) if ocr_id else ''
    if len(confirmed_equation)>500:raise HTTPException(422,'数学表达式最多500字。')
    context={'lesson':{'id':task.lesson_id,'versionId':lesson.get('versionId'),'title':task.title,'grade':lesson.get('grade',''),'goal':str(task.snapshot.get('goal',''))[:1200]},'block':public_fields(block,PUBLIC_BLOCK) if block else None,'question':public_fields(q,PUBLIC_QUESTION) if q else None,'knowledge':[{'id':p.id,'name':p.name} for p in points],'prerequisites':prerequisites,'teachingCases':sources,'observation':str(record.observation or '')[:1200]}
    from .learning_memory import related_memory
    context['learningMemory']=related_memory(db,user,record,ids)
    if ocr_id:
        if not confirmed_equation:
            match=re.search(r'(?<![A-Za-z])([A-Za-z0-9(][A-Za-z0-9()+*/ .−-]{0,80}=[A-Za-z0-9()+*/ .−-]{1,80})',recognized)
            confirmed_equation=match.group(1).strip() if match else ''
        context['question']={'id':(q or {}).get('id'),'kind':'confirmed_image','prompt':recognized,'equation':confirmed_equation,'knowledgeIds':ids}
        context['focus']='confirmed_image'
    return {'guidance':True,'strategy':strategy,'selectedStrategy':data.get('strategy','hint'),'prompt':prompt[:3000] or '我想自己试试','question':question,'blockId':(block or {}).get('id'),'parentJobId':parent.id if parent else None,'context':context,'history':history,'ocrJobId':ocr_id,'recognizedText':recognized,'confirmedEquation':confirmed_equation,'confirmed':bool(ocr_id),'fileId':file_id,'_validation':{'answer':str((q or {}).get('answer','')),'equation':str((q or {}).get('equation',''))},'scope':{'studentId':user.id,'taskId':task.id,'classId':task.classroom_id,'lessonId':task.lesson_id,'lessonVersionId':lesson.get('versionId'),'questionId':(q or {}).get('id'),'knowledgeIds':[p.id for p in points]}}

def model_input(data):
    # Private validation never crosses the provider boundary; long source texts stay in storage.
    value={key:copy.deepcopy(data[key]) for key in ('guidance','strategy','prompt','question','blockId','context','history','recognizedText','confirmedEquation') if key in data}
    size=lambda:len(json.dumps(value,ensure_ascii=False))
    if size()<=24000:return value
    context=value.get('context',{})
    if context.get('block'):context['block']['content']=str(context['block'].get('content',''))[:2000]
    for source in context.get('teachingCases',[]):
        source['content']=str(source.get('content',''))[:1000]
        source['references']=[{key:str(ref.get(key,''))[:300] for key in ('unitId','quote','materialTitle','label')} for ref in source.get('references',[])[:2]]
    for turn in value.get('history',[]):
        for key in ('student','hint'):turn[key]=str(turn.get(key,''))[:500]
        turn['question']=str(turn.get('question',''))[:200]
    while size()>24000 and value.get('history'):value['history'].pop(0)
    while size()>24000 and context.get('teachingCases'):context['teachingCases'].pop()
    if size()>24000:raise ModelError('本轮内容超过上下文上限，请缩短问题或分段提问。')
    return value

def validate_result(result,data):
    from .model_jobs import math_check
    value=TutoringResult.model_validate(result).model_dump();verification=math_check(value['mathClaims'])
    if verification['status']=='inconsistent':raise ModelError('指导包含已核验的数学错误，未展示，可重试。')
    if value['strategy']!=data['strategy']:raise ModelError('指导没有执行所选策略，未展示。')
    if len(value['steps'])>4:raise ModelError('本轮指导过长，未展示。')
    if data['strategy']=='rephrase' and data.get('history') and value['representation']==data['history'][-1]['representation']:raise ModelError('换讲法没有改变解释方式，未展示。')
    versions={c.get('versionId') for c in model_input(data)['context']['teachingCases']}
    if not set(value['usedCaseVersionIds'])<=versions:raise ModelError('指导来源不在本次公开材料中。')
    if value['prerequisiteId'] and value['prerequisiteId'] not in {p['id'] for p in data['context']['prerequisites']}:raise ModelError('基础知识不属于当前一层前置关系。')
    text='\n'.join([value['title'],value['hint'],*value['steps'],value['question']])
    leak_text=text+'\n'+'\n'.join(c['left']+'\n'+c['right'] for c in value['mathClaims'])
    equation=data.get('confirmedEquation') or data['_validation'].get('equation') or data.get('recognizedText','')
    solved,known=solve_text_equation(equation)
    if known:
        for solution in solved.split(', '):
            var,answer=solution.split('=');n=re.escape(answer)
            # Match explicit original-question solutions; other numerical examples remain possible.
            if re.search(r'(?<![A-Za-z])'+re.escape(var)+r'\s*(?:=|等于|为)\s*'+n+r'(?![\d.])',leak_text) or re.search(r'(?:答案|结果)(?:是|为|等于|[:：=])?\s*'+n+r'(?![\d.])',leak_text):raise ModelError('本轮直接给出了当前题目答案，已拦截。')
    normalized=lambda s:re.sub(r'\s+','',s).replace('−','-').replace('×','*').replace('÷','/')
    if data['strategy']=='example' and equation and normalized(equation) in normalized(text):raise ModelError('举例复用了当前题目，已拦截。')
    if any(word in text for word in ('系统已经检测到你不掌握','根据你的学习画像','本Agent正在','经过多维分析','显著提升你的理解能力')):raise ModelError('指导含有无依据的学习判断，未展示。')
    validate_arithmetic_text(text)
    coverage=need_coverage(data.get('prompt',''),text)
    if coverage['missing']:raise ModelError('当前明确需求未覆盖：'+'、'.join(coverage['missing'])+'；请先回答该问题再回到原题。')
    value['needCoverage']=coverage
    value['verification']=verification;value['verification']['scope']='仅核对声明关系和可解析数值等式；未验证自然语言及完整教学适切性。'
    value['sources']=[c for c in data['context']['teachingCases'] if c.get('versionId') in value['usedCaseVersionIds']]
    value['prerequisites']=data['context']['prerequisites'] if data['strategy']=='foundation' else []
    return value

class State(TypedDict,total=False):
    data:dict
    request:dict
    result:dict
    model:str
    provider:str
    calls:int
    started:float
    nodes:list

async def run(data,provider,request_id):
    audit={'modelCalls':0,'started':time.perf_counter()}
    async def context(state):return {'request':model_input(state['data']),'nodes':['固定学习上下文']}
    async def evidence(state):return {'nodes':state['nodes']+['读取公开案例与一层前置知识']}
    async def generate(state):
        if state['data']['strategy']=='try':return {'result':{'title':'自己试试','hint':'请写下你的答案和两边共同进行的运算。','steps':['回到原题作答；之前的帮助记录仍保留。'],'question':'你准备先对等式两边做什么？','mathClaims':[],'strategy':'try','representation':'question','nextStrategy':'hint','usedCaseVersionIds':[],'prerequisiteId':''},'model':'','provider':'程序检查点','calls':0,'nodes':state['nodes']+['等待自主作答']}
        last=None
        for index in range(2):
            request=copy.deepcopy(state['request'])
            if index:request['repairStructure']=True;request['qualityRevision']=str(last)
            try:
                audit['modelCalls']+=1
                value,model,source=await provider.call('text',request,request_id=request_id)
                audit['model']=model;audit['provider']=source
                value=validate_result(value,state['data'])
                return {'result':value,'model':model,'provider':source,'calls':index+1,'nodes':state['nodes']+['生成本轮指导']}
            except ModelError as error:
                last=error
                if error.retryable and "结构" not in str(error):raise
            except ValueError as error:last=ModelError('指导不符合结果结构。')
        raise last
    async def verify(state):
        result=state['result'] if state['result'].get('verification') else validate_result(state['result'],state['data'])
        return {'result':{**result,'workflow':{'nodes':state['nodes']+['核验并等待学生回应'],'modelCalls':state['calls'],'elapsedMs':round((time.perf_counter()-state['started'])*1000),'historyTurns':len(state['request'].get('history',[])),'contextChars':len(json.dumps(state['request'],ensure_ascii=False))}},'nodes':state['nodes']+['核验并等待学生回应']}
    graph=StateGraph(State)
    for name,node in [('context',context),('evidence',evidence),('generate',generate),('verify',verify)]:graph.add_node(name,node)
    graph.add_edge(START,'context');graph.add_edge('context','evidence');graph.add_edge('evidence','generate');graph.add_edge('generate','verify');graph.add_edge('verify',END)
    try:state=await graph.compile().ainvoke({'data':data,'started':time.perf_counter(),'nodes':[]})
    except ModelError as error:
        error.metrics={'modelCalls':audit['modelCalls'],'elapsedMs':round((time.perf_counter()-audit['started'])*1000),'historyTurns':len(data.get('history',[]))}
        error.model=getattr(error,'model',audit.get('model',''));error.provider=getattr(error,'provider',audit.get('provider',''));raise
    return state['result'],state['model'],state['provider']


def need_coverage(prompt,text):
    """Narrow topical guards, not a substitute for human teaching review."""
    required=[];missing=[]
    if re.search('天平',prompt):
        required.append('天平两侧与具体变化')
        if not ('天平' in text and re.search('左|一侧|一边|两盘',text) and re.search('右|另一侧|另一边|两盘',text) and re.search('加|减|放|拿|取|增|移',text)):missing.append(required[-1])
    if re.search('乘[以]?零|乘[以]?0|乘0',prompt) and re.search('信息|丢失|逆|还原',prompt):
        required.append('不同输入乘零同结果、不能逆推')
        if not (re.search('不同|两个数|任意|任何',text) and re.search(r'乘|×|\*',text) and re.search('0|零',text) and re.search('无法|不能|区分|还原|逆推|不知道',text)):missing.append(required[-1])
    if re.search('除[以]?零|除[以]?0|除数.*零',prompt):
        required.append('除零与乘法逆运算或唯一结果')
        if not (re.search('除|÷|/',text) and re.search('0|零',text) and re.search(r'乘|×|\*',text) and re.search('不存在|没有|不可能|不唯一|任意|无法|不能|确定',text)):missing.append(required[-1])
    return {'required':required,'missing':missing,'scope':'仅检查明确教学主题的必要表征，适切性仍需人工评阅'}


def validate_arithmetic_text(text):
    # Audit arithmetic equalities written in prose too, not only declared claims.
    from .math_tools import compare_equivalence
    for left,right in re.findall(r'(?<![A-Za-z0-9])([A-Za-z\d()+*/×÷.− \t-]+)\s*=\s*([-A-Za-z\d.]+)',text):
        # Do not mistake the numeric suffix of a variable equation for arithmetic.
        if re.search('[A-Za-z]',left+right):continue
        equal,verified=compare_equivalence(left.strip(),right.strip())
        if verified and not equal:raise ModelError('指导正文中的数值运算错误，已拦截。')
