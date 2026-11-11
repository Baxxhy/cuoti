"""Wrong-question workflow on the existing account, FileAsset and ModelJob services."""
import copy,uuid,re
from datetime import datetime
from typing import Literal
from fastapi import APIRouter,Depends,HTTPException,Request
from pydantic import Field
from sqlalchemy import select,or_,func
from .database import get_db
from .models import WrongQuestion,RepairAttempt,StudentRecord,LearningTask,FileAsset,ModelJob,KnowledgePoint
from .ai_schemas import StrictResult,MathClaim
from .grading import assess_repair
from .math_tools import solve_text_equation,compare_equivalence
from .model_provider import ModelError

router=APIRouter(prefix='/api/wrongs')
REASONS=['概念理解错误','运算步骤错误','符号处理错误','条件遗漏','题意理解错误','计算错误','其他或待确认']
def uid(prefix):return prefix+'-'+uuid.uuid4().hex

def user(request,db):
    from .main import current_user
    return current_user(request,db)

def access(db,actor,wrong_id,write=False):
    item=db.scalar(select(WrongQuestion).where(WrongQuestion.id==wrong_id).with_for_update()) if write else db.get(WrongQuestion,wrong_id)
    rec=db.get(StudentRecord,item.record_id) if item and item.record_id else None
    owner=(item.owner_id or (rec.student_id if rec else None)) if item else None
    task=db.get(LearningTask,rec.task_id) if rec else None
    allowed=item and (owner==actor.id or actor.role=='admin' or (actor.role=='teacher' and task and task.teacher_id==actor.id))
    if not allowed:raise HTTPException(404,'没有找到有权限的错题。')
    if write:
        if actor.role!='student' or owner!=actor.id:raise HTTPException(403,'仅学生本人可修改错题。')
        if task:
            from .teaching import ensure_write
            ensure_write(db,actor,task.id)
    return item

def repair_json(row):
    return {'id':row.id,'wrongId':row.wrong_id,'answer':row.answer,'reason':row.reason,'correct':row.correct,'verification':row.verification,'details':row.details or {'version':'legacy_fixed','equation':'z + 2 = 9','scope':'历史固定示例，不能证明原题已掌握'},'createdAt':row.created_at.isoformat()}

def serialize(db,item):
    rec=db.get(StudentRecord,item.record_id) if item.record_id else None
    task=db.get(LearningTask,rec.task_id) if rec else None
    details=copy.deepcopy(item.details or {})
    attempts=db.scalars(select(RepairAttempt).where(RepairAttempt.wrong_id==item.id).order_by(RepairAttempt.created_at)).all()
    fresh=[a for a in attempts if a.details and a.details.get('version')=='dynamic_v1']
    independent=[a for a in fresh if a.details.get('phase')=='retest']
    latest=independent[-1] if independent else None
    status='pending'
    if details.get('planJobId'):status='learning'
    if any(a.correct for a in fresh if a.details.get('phase')=='practice'):status='awaiting_retest'
    if latest:status='needs_review' if (latest.verification or {}).get('status')=='unverified' else 'retest_passed' if latest.correct and not latest.details.get('helped') else 'retest_failed'
    if details.get('planJobId') and not solve_text_equation(equation_for(item))[1]:status='needs_review'
    from .models import ClassMember,Attempt
    source_attempt=db.get(Attempt,item.attempt_id) if item.attempt_id else None
    source_question=(task.questions[source_attempt.question] if task and source_attempt and 0<=source_attempt.question<len(task.questions or []) else {})
    details.setdefault('knowledgeIds',source_question.get('knowledgeIds') or (task.snapshot.get('lessonSnapshot') or {}).get('knowledgeIds',[]) if task else [])
    return {'id':item.id,'taskId':rec.task_id if rec else None,'recordId':item.record_id,'attemptId':item.attempt_id,'source':details.get('source','course' if rec else 'manual'),'prompt':item.prompt,'answer':item.answer,'reason':item.reason,'image':'/api/files/'+item.file_id if item.file_id else '', 'details':details,'status':status,'readOnly':bool(task and not db.get(ClassMember,(task.classroom_id,rec.student_id))),'taskTitle':task.title if task else None,'repairs':[repair_json(a) for a in attempts],'createdAt':item.created_at.isoformat()}

@router.get('')
def listing(request:Request,db=Depends(get_db)):
    actor=user(request,db)
    query=select(WrongQuestion).outerjoin(StudentRecord,WrongQuestion.record_id==StudentRecord.id).outerjoin(LearningTask,StudentRecord.task_id==LearningTask.id)
    if actor.role=='student':query=query.where(or_(WrongQuestion.owner_id==actor.id,StudentRecord.student_id==actor.id))
    elif actor.role=='teacher':query=query.where(LearningTask.teacher_id==actor.id)
    return [serialize(db,x) for x in db.scalars(query.order_by(WrongQuestion.created_at.desc())).all()]

@router.get('/options')
def options(request:Request,db=Depends(get_db)):
    user(request,db)
    return {'reasons':REASONS,'knowledge':[{'id':p.id,'name':p.name} for p in db.scalars(select(KnowledgePoint)).all()]}

def checked_files(db,actor,ids):
    for fid in ids:
        asset=db.get(FileAsset,fid) if fid else None
        if fid and (not asset or asset.owner_id!=actor.id or not asset.content_type.startswith('image/')):raise HTTPException(422,'请选择本人已上传的题图。')

@router.post('',status_code=201)
def create(body:dict,request:Request,db=Depends(get_db)):
    actor=user(request,db)
    if actor.role!='student':raise HTTPException(403,'请使用学生账号录题。')
    prompt=str(body.get('prompt','')).strip();key=str(body.get('requestKey',''))
    if not 0<len(prompt)<=6000 or not 8<=len(key)<=80:raise HTTPException(422,'请填写题目并保留本次请求标识。')
    # Account-scoped stable ID gives repeat submissions one row even after a lost response.
    import hashlib
    wid='wrong-'+hashlib.sha256((actor.id+':'+key).encode()).hexdigest()[:32]
    old=db.get(WrongQuestion,wid)
    if old:return serialize(db,old)
    file_id=body.get('fileId');crop_id=body.get('cropFileId');checked_files(db,actor,[file_id,crop_id])
    ocr_id=body.get('ocrJobId')
    if file_id:
        job=db.get(ModelJob,ocr_id) if ocr_id else None
        if not job or job.owner_id!=actor.id or job.capability!='ocr' or job.status!='succeeded' or job.file_id!=(crop_id or file_id) or body.get('confirmed') is not True:raise HTTPException(422,'请先识别并人工确认本次题图。')
    ids=body.get('knowledgeIds',[])
    if not isinstance(ids,list) or len(ids)>16 or any(not db.get(KnowledgePoint,i) for i in ids):raise HTTPException(422,'知识点无效。')
    equation=str(body.get('equation','')).strip()
    if len(equation)>500:raise HTTPException(422,'请分开录入多道题。')
    item=WrongQuestion(id=wid,owner_id=actor.id,record_id=None,prompt=prompt,answer=str(body.get('answer',''))[:6000],reason=str(body.get('reason',''))[:6000],file_id=file_id,details={'version':'dynamic_v1','source':'image' if file_id else 'manual','subject':str(body.get('subject','数学'))[:80],'equation':equation,'cropFileId':crop_id,'ocrJobId':ocr_id,'confirmedText':prompt if file_id else '', 'knowledgeIds':ids,'cause':'其他或待确认','causeConfirmed':False})
    db.add(item);db.commit();return serialize(db,item)

@router.get('/{wrong_id}')
def detail(wrong_id:str,request:Request,db=Depends(get_db)):
    actor=user(request,db);item=access(db,actor,wrong_id)
    result=serialize(db,item)
    jobs=db.scalars(select(ModelJob).where(ModelJob.owner_id==(item.owner_id or db.get(StudentRecord,item.record_id).student_id),ModelJob.capability=='text').order_by(ModelJob.created_at)).all()
    from .ai_routes import serialize as job_json
    result['jobs']=[job_json(j) for j in jobs if j.input.get('wrongId')==item.id]
    return result

@router.put('/{wrong_id}')
def update(wrong_id:str,body:dict,request:Request,db=Depends(get_db)):
    actor=user(request,db);item=access(db,actor,wrong_id,True);details=copy.deepcopy(item.details or {})
    cause=body.get('cause',details.get('cause','其他或待确认'))
    if cause not in REASONS:raise HTTPException(422,'错因分类无效。')
    details.update(cause=cause,causeConfirmed=bool(body.get('causeConfirmed',False)),explanation=str(body.get('explanation',details.get('explanation','')))[:6000],draft=body.get('draft',details.get('draft',{})))
    item.details=details;db.commit();return serialize(db,item)

@router.post('/{wrong_id}/attempts',status_code=201)
def submit(wrong_id:str,body:dict,request:Request,db=Depends(get_db)):
    actor=user(request,db);item=access(db,actor,wrong_id,True)
    return save_attempt(db,actor,item,body)

def save_attempt(db,actor,item,body):
    item=db.scalar(select(WrongQuestion).where(WrongQuestion.id==item.id).with_for_update())
    answer=str(body.get('answer','')).strip();key=str(body.get('requestKey',''))
    if not answer or not 8<=len(key)<=80:raise HTTPException(422,'请填写答案并保留请求标识。')
    previous=db.scalars(select(RepairAttempt).where(RepairAttempt.wrong_id==item.id).with_for_update()).all()
    replay=next((a for a in previous if (a.details or {}).get('requestKey')==key),None)
    if replay:return repair_json(replay)
    jid=body.get('variantJobId');job=db.get(ModelJob,jid) if jid else None
    if not job or job.owner_id!=actor.id or job.input.get('wrongId')!=item.id or job.input.get('mode')!='variant' or job.status!='succeeded':raise HTTPException(422,'请先生成当前错题的可核验变式题。')
    result=job.result or {};variant=result.get('variant',{})
    if result.get('variantVerification',{}).get('status')!='verified':raise HTTPException(422,'变式未通过数学核验，不能进入自动评分。')
    phase=job.input.get('phase','practice')
    if any((a.details or {}).get('variantJobId')==jid for a in previous):raise HTTPException(409,'本题已有作答，请生成独立新题再试。')
    verification=assess_repair(answer,variant.get('equation',''),variant.get('expected'))
    helped=bool(body.get('helped')) or bool(result.get('helpRequested'))
    # New help belongs to its exact variant. Unscoped historical help remains
    # conservatively helped; its missing scope cannot establish independence.
    helped=helped or bool(db.scalar(select(ModelJob.id).where(ModelJob.owner_id==actor.id,ModelJob.created_at>=job.created_at,ModelJob.id!=jid,ModelJob.input['wrongId'].as_string()==item.id,ModelJob.input['mode'].as_string()=='guidance',or_(ModelJob.input['variantJobId'].as_string()==jid,func.json_contains_path(ModelJob.input,'one','$.variantJobId')==0),ModelJob.input['strategy'].as_string()!='try')))
    row=RepairAttempt(id=uid('repair'),wrong_id=item.id,answer=answer,reason=str(body.get('reason',''))[:6000],correct=verification['correct'],verification=verification,details={'version':'dynamic_v1','planJobId':(item.details or {}).get('planJobId'),'variantJobId':jid,'variantId':jid,'equation':variant['equation'],'expected':variant['expected'],'phase':phase,'helped':helped,'requestKey':key,'verification':verification})
    db.add(row);db.commit();return repair_json(row)

@router.post('/{wrong_id}/review')
def review(wrong_id:str,body:dict,request:Request,db=Depends(get_db)):
    actor=user(request,db);item=access(db,actor,wrong_id)
    if actor.role!='teacher' or not item.record_id:raise HTTPException(403,'仅来源任务教师可确认。')
    row=db.get(RepairAttempt,str(body.get('attemptId','')))
    if not row or row.wrong_id!=item.id or (row.verification or {}).get('status')!='unverified':raise HTTPException(422,'请选择需要人工核对的作答。')
    details=copy.deepcopy(row.details or {});details['teacherReview']={'teacherId':actor.id,'correct':bool(body.get('correct')),'note':str(body.get('note',''))[:3000],'at':datetime.utcnow().isoformat()};row.details=details;db.commit();return repair_json(row)

class Analysis(StrictResult):
    cause:Literal['概念理解错误','运算步骤错误','符号处理错误','条件遗漏','题意理解错误','计算错误','其他或待确认']
    evidence:str=Field(max_length=3000)
    uncertainty:str=Field(min_length=1,max_length=1000)
    goal:str=Field(min_length=1,max_length=1000)
    steps:list[str]=Field(min_length=1,max_length=4)
    checkQuestion:str=Field(min_length=1,max_length=1000)
    strategy:Literal['hint','example','rephrase','foundation']
    mathClaims:list[MathClaim]=Field(default_factory=list,max_length=12)

class Variant(StrictResult):
    prompt:str=Field(min_length=1,max_length=2000)
    equation:str=Field(min_length=1,max_length=500)
    expected:str=Field(min_length=1,max_length=500)
    rationale:str=Field(min_length=1,max_length=1000)
class VariantResult(StrictResult):
    variant:Variant
    mathClaims:list[MathClaim]=Field(default_factory=list,max_length=12)

def equation_for(item):return str((item.details or {}).get('equation') or item.prompt).strip()

def prepare(db,actor,item,data):
    mode=data.get('mode','analysis')
    if mode not in ('analysis','guidance','variant'):raise HTTPException(422,'补救操作无效。')
    variant_id=data.get('variantJobId') or None
    if variant_id and mode!='guidance':raise HTTPException(422,'只有当前变式题的指导可关联变式。')
    original_question={'prompt':item.prompt,'equation':equation_for(item)}
    question=copy.deepcopy(original_question)
    if variant_id:
        variant_job=db.get(ModelJob,variant_id) if isinstance(variant_id,str) else None
        if not variant_job or variant_job.owner_id!=actor.id or variant_job.capability!='text' or variant_job.input.get('wrongId')!=item.id or variant_job.input.get('mode')!='variant' or variant_job.status!='succeeded':raise HTTPException(422,'请选择本题本人已完成的变式题。')
        result=variant_job.result or {};variant=result.get('variant') or {}
        equation=variant.get('equation','')
        if result.get('variantVerification',{}).get('status')!='verified' or assess_repair(variant.get('expected',''),equation,variant.get('expected'))['status']!='verified_correct':raise HTTPException(422,'变式题尚未通过数学核验，不能进入指导。')
        # Generated titles and client-provided context are not trusted as the current exercise.
        question={'prompt':'解方程，说明每一步两边进行的共同运算。','equation':equation}
    if mode=='variant' and data.get('phase','practice') not in ('practice','retest'):raise HTTPException(422,'练习阶段无效。')
    if mode=='variant' and data.get('phase')=='retest':
        practice=db.scalars(select(RepairAttempt).where(RepairAttempt.wrong_id==item.id)).all()
        if not (item.details or {}).get('planJobId') or not any((a.details or {}).get('version')=='dynamic_v1' and a.details.get('phase')=='practice' for a in practice):raise HTTPException(422,'先完成本题补救与变式练习，再生成独立新题。')
    history=[];parent_id=data.get('parentJobId')
    cursor=parent_id;seen=set()
    for _ in range(4):
        if not cursor:break
        if not isinstance(cursor,str) or cursor in seen:raise HTTPException(422,'补救历史关联无效。')
        seen.add(cursor);parent=db.get(ModelJob,cursor)
        if not parent or parent.owner_id!=actor.id or parent.input.get('wrongId')!=item.id or parent.status!='succeeded' or parent.input.get('mode') not in ('analysis','guidance'):raise HTTPException(422,'只能关联本题已完成的补救历史。')
        if (parent.input.get('variantJobId') or None)!=variant_id or (variant_id and parent.input.get('mode')!='guidance'):raise HTTPException(422,'原题与不同变式题的指导不能混用，请开始新一轮。')
        history.insert(0,{'student':parent.input.get('prompt',''),'strategy':parent.input.get('strategy','hint'),'representation':(parent.result or {}).get('representation','question'),'hint':str((parent.result or {}).get('hint') or (parent.result or {}).get('goal',''))[:1000],'question':(parent.result or {}).get('question') or (parent.result or {}).get('checkQuestion','')})
        cursor=parent.input.get('parentJobId')
    details=serialize(db,item)['details'];points=[db.get(KnowledgePoint,k) for k in details.get('knowledgeIds',[])];points=[p for p in points if p]
    strategy=data.get('strategy','hint');prompt=str(data.get('prompt','')).strip()[:3000]
    if strategy=='continue':strategy='foundation' if re.search('不懂|不会|不知道|不明白',prompt) else 'try' if re.search('懂了|明白了|自己试',prompt) else 'hint'
    from .tutoring import STRATEGIES
    if strategy not in STRATEGIES:raise HTTPException(422,'指导方式无效。')
    context={'question':question,'knowledge':[{'id':p.id,'name':p.name} for p in points],'prerequisites':[{'id':p.id,'name':p.name} for p in db.scalars(select(KnowledgePoint).where(KnowledgePoint.id.in_(list({i for p in points for i in p.prerequisites}) or ['']))).all()],'teachingCases':[],'originalAnswer':'' if variant_id else item.answer,'originalReason':'' if variant_id else item.reason,'confirmedCause':details.get('cause') if details.get('causeConfirmed') else None}
    if variant_id:context['originalQuestion']=original_question
    past=db.scalars(select(ModelJob).where(ModelJob.owner_id==actor.id,ModelJob.input['wrongId'].as_string()==item.id,ModelJob.input['mode'].as_string()=='variant',ModelJob.status=='succeeded')).all()
    default_prompt='请依据当前变式题给我提示，不直接给出答案。' if variant_id else '请依据本题和我的原作答提供针对性补救。'
    return {'remediation':True,'wrongId':item.id,'mode':mode,'variantJobId':variant_id,'phase':data.get('phase','practice'),'strategy':strategy,'prompt':prompt or default_prompt,'context':context,'history':history,'parentJobId':parent_id,'previousEquations':[(j.result or {}).get('variant',{}).get('equation','') for j in past][-30:],'_validation':{'equation':question['equation']},'guidance':mode=='guidance'}

def validate(result,data):
    from .model_jobs import math_check
    if data['mode']=='analysis':
        value=Analysis.model_validate(result).model_dump();evidence=value['evidence']
        originals='\n'.join([data['context']['originalAnswer'],data['context']['originalReason']])
        if evidence and evidence not in originals:raise ModelError('错因证据必须逐字来自原作答或解释。')
        value.update(confirmed=False)
    else:
        value=VariantResult.model_validate(result).model_dump();v=value['variant'];original=data['context']['question']['equation']
        norm=lambda s:re.sub(r'\s','',s).replace('−','-')
        if norm(v['equation']) in [norm(original),*[norm(s) for s in data.get('previousEquations',[])]]:raise ModelError('变式必须是本题相关的新题，不能重复原题或已做题。')
        solved,ok=solve_text_equation(v['equation']);orig_solved,orig_ok=solve_text_equation(original)
        checked=assess_repair(v['expected'],v['equation'],v['expected'])
        if not ok or checked['status']!='verified_correct':raise ModelError('变式参考答案未通过程序核验，未进入可评分练习。')
        # Bounded generator: accept only same structural difficulty family. Unknown conceptual conditions need clarification.
        if not orig_ok:raise ModelError('原题条件或答案未确定，请先确认单道可核验方程；不能据此自动生成评分题。')
        from .math_tools import parse_math_expression
        import sympy as sp
        def family(eq):
            l,r=eq.split('=');left,right=parse_math_expression(l),parse_math_expression(r)
            expr=left-right;x=next(iter(expr.free_symbols));side=left if left.free_symbols else right
            polynomial=sp.Poly(side,x);coefficient=polynomial.coeff_monomial(x);constant=polynomial.coeff_monomial(1)
            operation='additive' if coefficient==1 and constant!=0 else 'multiplicative' if coefficient!=1 and constant==0 else 'mixed'
            return sp.Poly(expr,x).degree(),bool(re.search(r'\d\s*\(',eq)),bool('/' in eq or '÷' in eq),operation,bool(left.free_symbols and right.free_symbols)
        if family(original)!=family(v['equation']):raise ModelError('变式未保留原题运算结构，请生成同类不同数值的新题。')
        if orig_solved.split('=',1)[1]==solved.split('=',1)[1]:raise ModelError('变式只换字母或沿用同一答案，请改变数值。')
        var,expected_value=solved.split('=',1)
        if re.search(re.escape(var)+r'\s*=\s*'+re.escape(expected_value)+r'(?![\d.])',v['prompt']) or re.search(r'(?:答案|结果)(?:为|是|[:：=])?\s*'+re.escape(expected_value)+r'(?![\d.])',v['prompt']):raise ModelError('变式题干泄露参考答案，未进入独立练习。')
        value['variantVerification']={'status':'verified','scope':'同类结构、不同题目与答案；单变量单解实数方程','equation':v['equation']}
    from .tutoring import validate_arithmetic_text
    validate_arithmetic_text('\n'.join([value.get('goal',''),*value.get('steps',[]),value.get('checkQuestion','')]))
    from .math_conditions import require_conditions
    value['conditionCheck']=require_conditions(value)
    verification=math_check(value.get('mathClaims',[]))
    if verification['status']=='inconsistent':raise ModelError('补救内容含已确认数学错误，已拦截。')
    value['verification']=verification
    return value

async def run(data,provider,request_id):
    if data['mode']=='guidance':
        from .tutoring import run as guidance
        return await guidance(data,provider,request_id)
    last=None
    for index in range(2):
        value={k:copy.deepcopy(v) for k,v in data.items() if k!='_validation'}
        if last:value['qualityRevision']=str(last)
        try:
            result,model,source=await provider.call('text',value,request_id=request_id)
            result=validate(result,data);result['workflow']={'modelCalls':index+1,'scope':'wrong:'+data['wrongId']}
            return result,model,source
        except (ModelError,ValueError) as error:last=error if isinstance(error,ModelError) else ModelError('补救结果不符合结构。')
    last.metrics={'modelCalls':2,'scope':'wrong:'+data['wrongId']}
    last.model=locals().get('model','');last.provider=locals().get('source','')
    raise last
