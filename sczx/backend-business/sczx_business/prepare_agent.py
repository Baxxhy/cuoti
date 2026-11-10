"""Six bounded teaching nodes. ModelJob.result is the durable per-node checkpoint."""
import asyncio,copy,hashlib,json,time
from datetime import datetime,timezone
from typing import TypedDict
from fastapi import HTTPException
from sqlalchemy import select
from langgraph.graph import StateGraph,START,END
from langgraph.errors import NodeCancelledError
from .database import SessionLocal
from .models import Lesson,LessonDraft,ModelJob,MaterialUnit
from .curriculum import published_lesson,apply_template
from .retrieval import retrieve,published_documents,knowledge_documents,legacy_search,tokenize
from .planning_schemas import PlanningInput,GeneratedPlan
from .model_provider import ModelError

STEPS=[('context','理解任务与课时','curriculum.read'),('cases','检索教学案例','retrieval.bm25'),('materials','定位原文材料','materials.read'),('generate','生成备课建议','codex.lesson_plan'),('validate','核验结构与依据','plan.validate'),('ready','等待教师确认','teacher.review')]
TOOLS={tool for _,_,tool in STEPS}
TASK_TYPES={'activity':'活动设计','misconception':'误解纠正','foundation':'补基础'}

def now():return datetime.now(timezone.utc).isoformat()
def fingerprint(draft):
    fields=draft_fields(draft) if isinstance(draft,LessonDraft) else draft
    return hashlib.sha256(json.dumps(fields,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def draft_fields(row):
    return {key:copy.deepcopy(getattr(row,key)) for key in ('goal','student_base','due_date','blocks','questions','case_id','case_snapshot','lesson_snapshot','planning_details','revision')}
def current_draft(db,owner,lesson):
    return db.scalar(select(LessonDraft).where(LessonDraft.teacher_id==owner,LessonDraft.lesson_id==lesson))
def infer_task(text,selected='auto'):
    if selected!='auto':return selected
    if any(w in text for w in ('补基础','基础薄弱','前置','基础不牢')):return 'foundation'
    if any(w in text for w in ('机械','误解','错误','只改','变号','纠正')):return 'misconception'
    return 'activity'

def build_input(db,user,raw):
    try:request=PlanningInput.model_validate(raw).model_dump()
    except ValueError:raise HTTPException(422,'请选择课时并填写有效教学任务。') from None
    lesson=db.get(Lesson,request['lessonId'])
    version=published_lesson(db,request['lessonId']) if lesson else None
    if not version:raise HTTPException(422,'该课时尚未发布，请先选择可用课时。')
    draft=current_draft(db,user.id,lesson.id)
    if draft and draft.lesson_snapshot and draft.lesson_snapshot.get('versionId')!=version['versionId']:
        raise HTTPException(409,'教案仍使用旧课时来源，请先在备课页核对并使用当前发布课时，再开始新任务。历史Agent结果仍可查看。')
    baseline=draft_fields(draft) if draft else None
    # Use the saved personalized draft, including its order and block IDs.
    if draft:
        version={**(draft.lesson_snapshot or version),'goal':draft.goal,'blocks':copy.deepcopy(draft.blocks),'questions':copy.deepcopy(draft.questions),'studentBase':draft.student_base,'planningDetails':copy.deepcopy(draft.planning_details or {}),'caseSnapshot':copy.deepcopy(draft.case_snapshot),'caseId':draft.case_id}
    data={**request,'taskType':infer_task(request['task'],request['taskType']),'lesson':version,
          'documents':published_documents(db),'knowledge':knowledge_documents(db),'draftHash':fingerprint(baseline),
          'draftId':draft.id if draft else None,'ownerId':user.id,'workflowVersion':'teaching-plan-v1','label':request['task'][:64]}
    if request.get('qualityRevisionOf'):
        parent=db.scalar(select(ModelJob).where(ModelJob.id==request['qualityRevisionOf']).with_for_update())
        if not parent or parent.owner_id!=user.id or parent.capability!='lesson_agent':raise HTTPException(404,'原备课任务不存在。')
        if parent.input.get('qualityRevisionOf') or db.scalar(select(ModelJob.id).where(ModelJob.owner_id==user.id,ModelJob.input['qualityRevisionOf'].as_string()==parent.id).limit(1).with_for_update()):raise HTTPException(409,'这项建议已使用一次语言修订，请手动编辑。')
        base=(parent.result or {}).get('editable') or (parent.result or {}).get('plan')
        if not base or parent.input['lessonId']!=lesson.id:raise HTTPException(422,'请先选择已完成的同课时建议。')
        data.update(basePlan=copy.deepcopy(base),qualityRevision='按文本质量警告改进表述，保留数学条件与题目；只修订一次',lesson=copy.deepcopy(parent.input['lesson']))
        by_id={b['id']:b for b in base['blocks']}
        data['lesson']['blocks']=[{**b,**{k:v for k,v in by_id[b['id']].items() if k!='evidenceIds'}} for b in data['lesson']['blocks']]
    if request['parentJobId']:
        parent=db.get(ModelJob,request['parentJobId'])
        if not parent or parent.owner_id!=user.id or parent.capability!='lesson_agent':raise HTTPException(404,'原备课任务不存在。')
        result=parent.result or {};base=result.get('editable') or result.get('plan')
        if not base or parent.input.get('lessonId')!=lesson.id or not request['regenerateBlockId']:raise HTTPException(422,'请选择原任务中的一个活动重新生成。')
        if request['regenerateBlockId'] not in {b['id'] for b in base['blocks']}:raise HTTPException(422,'活动不存在。')
        data.update(basePlan=copy.deepcopy(base),resumeFrom=copy.deepcopy(result),lesson=copy.deepcopy(parent.input['lesson']),documents=copy.deepcopy(parent.input['documents']),knowledge=copy.deepcopy(parent.input['knowledge']))
    elif request.get('rewriteBlockId'):
        target=request['rewriteBlockId']
        if target not in {b['id'] for b in version['blocks']}:raise HTTPException(422,'活动不存在。')
        data['regenerateBlockId']=target
        data['basePlan']={'title':version['title'],'goal':version['goal'],'rationale':['保留教师当前教案，仅改写选定活动'],'blocks':[{'id':b['id'],'title':b['title'],'content':b['content'],'evidenceIds':['lesson:'+version['versionId']]} for b in version['blocks']],'mathClaims':[]}
    elif request['regenerateBlockId']:raise HTTPException(422,'单独生成需要对应原任务。')
    details=(draft.planning_details or {}) if draft else {}
    selected=[draft.case_snapshot if draft else None,*details.get('references',[])]
    data['selectedReferences']=[copy.deepcopy(c) for c in selected if c and c.get('versionId')]
    return data

def validate_plan(value,lesson,evidence,only=None):
    plan=GeneratedPlan.model_validate(value).model_dump(exclude_unset=True)
    plan.setdefault('mathClaims',[])
    ids=[b['id'] for b in plan['blocks']];expected={only} if only else {b['id'] for b in lesson['blocks']}
    if len(ids)!=len(set(ids)) or set(ids)!=expected:raise ValueError('活动ID与当前课时不一致。')
    available={r['id'] for r in evidence}
    for block in plan['blocks']:
        if len(set(block['evidenceIds']))!=len(block['evidenceIds']) or any(i not in available for i in block['evidenceIds']):raise ValueError('存在未知或重复引用。')
    return plan

def collect_materials(db,cases,query):
    # Only positioned excerpts from the published case versions can be teacher evidence.
    refs={}
    for case in cases:
        for ref in case.get('references') or []:
            unit=db.get(MaterialUnit,ref.get('unitId'))
            if not unit or not (unit.text or unit.original_text or '').strip():continue
            quote=str(ref.get('quote') or '')[:3000]
            if not quote.strip():continue
            key=ref['unitId']+':'+hashlib.sha256(quote.encode()).hexdigest()[:10]
            refs.setdefault(key,{'id':key,'unitId':unit.id,'materialId':unit.material_id,'title':ref.get('materialTitle') or '原文材料','label':ref.get('label') or unit.label,'content':quote,'caseId':case['id'],'caseVersionId':case['versionId'],'kind':'material','url':'/#/source?unit='+unit.id})
    return legacy_search(query,list(refs.values()),6)

class AgentState(TypedDict):
    checkpoint:dict

async def run_agent(job_id,run_id,provider):
    from .model_jobs import event,math_check
    with SessionLocal() as db:
        job=db.get(ModelJob,job_id);data=copy.deepcopy(job.input);checkpoint=copy.deepcopy(job.result or {})
    if not checkpoint:
        checkpoint={'workflowVersion':'teaching-plan-v1','startedAt':now(),'budgetStartedAt':now(),'steps':[],'warnings':[],'decision':'pending','modelCalls':0}
        if data.get('resumeFrom'):
            checkpoint=copy.deepcopy(data['resumeFrom']);checkpoint.update(decision='pending',startedAt=now(),budgetStartedAt=now(),modelCalls=0)
            checkpoint.pop('accepted',None);checkpoint['steps']=[{**x,'reusedFrom':data['parentJobId']} for x in checkpoint['steps'] if x['key'] in ('context','cases','materials')]
            checkpoint.pop('editable',None);checkpoint.pop('plan',None);checkpoint.pop('generated',None);checkpoint.pop('verification',None)
    checkpoint.setdefault('budgetStartedAt',now())
    def remaining():
        return 270-(datetime.now(timezone.utc)-datetime.fromisoformat(checkpoint['budgetStartedAt'])).total_seconds()
    def persist(state):
        with SessionLocal.begin() as db:
            job=db.scalar(select(ModelJob).where(ModelJob.id==job_id).with_for_update())
            if job.status=='cancelled':raise asyncio.CancelledError()
            job.result=copy.deepcopy(state)
    async def node(key,title,tool,state):
        value=copy.deepcopy(state['checkpoint'])
        if any(s['key']==key and s['status']=='succeeded' for s in value['steps']):return {'checkpoint':value}
        if remaining()<=0:raise ModelError('备课任务达到总时限，已完成步骤保留。')
        step={'key':key,'title':title,'tool':tool,'status':'running','startedAt':now()}
        value['steps']=[s for s in value['steps'] if s['key']!=key]+[step]
        persist(value)
        with SessionLocal.begin() as db:
            job=db.get(ModelJob,job_id);event(db,job,title)
        try:
            if key=='context':
                value['context']={'task':data['task'],'taskType':data['taskType'],'taskLabel':TASK_TYPES[data['taskType']],'constraints':data['constraints'],'lessonId':data['lessonId'],'lessonTitle':data['lesson']['title'],'lessonVersionId':data['lesson']['versionId'],'goal':data['lesson']['goal'],'grade':data['lesson']['grade'],'subject':data['lesson']['subject'],'knowledgeIds':data['lesson'].get('knowledgeIds',[]),'prerequisiteIds':data['lesson'].get('prerequisiteIds',[])}
                step['output']={'recognizedType':TASK_TYPES[data['taskType']],'lessonVersionId':data['lesson']['versionId'],'method':'显式选择或有限关键词规则；课时由服务端读取'}
            elif key=='cases':
                lesson=data['lesson'];query=(data['task']+' '+lesson['title'])[:2000]
                context={'grade':lesson['grade'],'subject':lesson['subject'],'goal':lesson['goal'][:2000],'knowledgeIds':lesson.get('knowledgeIds',[]),'prerequisiteIds':lesson.get('prerequisiteIds',[])}
                result=retrieve({'query':query,'context':context,'limit':4},data['documents'],data['knowledge'])
                selected=data.get('selectedReferences',[]); seen={c['versionId'] for c in selected}; value['cases']=[*selected,*[c for c in result['items'] if c['versionId'] not in seen]][:8];value['retrieval']={k:v for k,v in result.items() if k not in ('items','candidateItems')}
                if not value['cases']:value['warnings'].append('未找到案例，仅依据当前课时生成；不编造案例出处。')
                step['output']={'caseCount':len(value['cases']),'rerank':False,'versions':[{'id':c['id'],'versionId':c['versionId']} for c in value['cases']]}
            elif key=='materials':
                with SessionLocal() as db:value['materials']=collect_materials(db,value['cases'],data['task']+' '+data['lesson']['title'])
                lesson_id='lesson:'+data['lesson']['versionId']
                value['evidence']=[{'id':lesson_id,'kind':'lesson','title':data['lesson']['title'],'content':'\n'.join(b['title']+'：'+b['content'] for b in data['lesson']['blocks'])[:14000],'versionId':data['lesson']['versionId'],'url':'/#/courses'},*value['materials']]
                if not value['materials']:value['warnings'].append('没有可定位的已解析原文；保留课时依据，待补充材料。')
                step['output']={'materialCount':len(value['materials']),'evidenceIds':[e['id'] for e in value['evidence']]}
            elif key=='generate':
                target=data.get('regenerateBlockId');blocks=[b for b in data['lesson']['blocks'] if not target or b['id']==target]
                request={'task':data['task'],'taskType':TASK_TYPES[data['taskType']],'constraints':data['constraints'],'goal':data['lesson']['goal'],'grade':data['lesson']['grade'],'knowledge':[p for p in data['knowledge'] if p['id'] in set(data['lesson'].get('knowledgeIds',[]))],
                         'rewriteBlockId':target,'qualityRevision':data.get('qualityRevision'),'studentBase':data['lesson'].get('studentBase',''),'planningDetails':data['lesson'].get('planningDetails',{}),'blocks':blocks,'questions':data['lesson']['questions'],'cases':[{'id':c['id'],'title':c['title'],'experience':c.get('experience',{})} for c in value['cases']],'evidence':value['evidence'],'currentPlan':data.get('basePlan')}
                value['modelCalls']+=1;persist(value)
                generated,model,source=await asyncio.wait_for(provider.call('lesson_plan',request,request_id=run_id),timeout=min(120,max(.01,remaining())))
                value['generated']=generated
                try:plan=validate_plan(generated,data['lesson'],value['evidence'],target)
                except ValueError as error:raise ModelError('备课结构或引用校验失败：'+str(error),retryable=True) from None
                if target:
                    base=copy.deepcopy(data['basePlan']);by_id={b['id']:b for b in plan['blocks']};base['blocks']=[by_id.get(b['id'],b) for b in base['blocks']];base['mathClaims']=(base.get('mathClaims',[])+plan.get('mathClaims',[]))[:12];plan=base
                value['plan']=plan;value['editable']=copy.deepcopy(plan);value['model']=model
                step['output']={'model':model,'provider':source,'blockCount':len(plan['blocks']),'onlyBlock':target,'origin':'模型生成，待教师核对'}
            elif key=='validate':
                plan=validate_plan(value['plan'],data['lesson'],value['evidence'])
                from .math_conditions import require_conditions
                value['conditionCheck']=require_conditions(plan)
                verification=await asyncio.wait_for(asyncio.to_thread(math_check,plan['mathClaims']),timeout=min(12,max(.01,remaining())))
                if verification['status']=='inconsistent':raise ModelError('列出的数学表达式不一致，请先修改建议再确认。')
                overlap=set(tokenize(plan['goal']))&set(tokenize(data['lesson']['goal']+' '+data['lesson']['title']))
                from .teaching_quality import review_plan
                value['textQuality']=review_plan(plan,data.get('regenerateBlockId'))
                value['verification']={**verification,'structure':'passed','references':'passed','goalTermsOverlap':bool(overlap),'humanReviewRequired':True}
                if not overlap:value['warnings'].append('目标措辞与当前课时缺少共同词，请教师重点核对目标一致性。')
                step['output']=value['verification']
            elif key=='ready':
                value['decision']='pending';step['output']={'next':'教师编辑、确认后保存备课草稿；不自动发布'}
            step.update(status='succeeded',finishedAt=now());persist(value);return {'checkpoint':value}
        except BaseException as error:
            step.update(status='cancelled' if isinstance(error,asyncio.CancelledError) else 'failed',finishedAt=now(),error=str(error) if isinstance(error,(ModelError,ValueError)) else '步骤中断，已完成结果保留')
            try:persist(value)
            except asyncio.CancelledError:pass
            raise
    graph=StateGraph(AgentState);previous=START
    for key,title,tool in STEPS:
        async def bound(state,key=key,title=title,tool=tool):return await node(key,title,tool,state)
        graph.add_node(key,bound);graph.add_edge(previous,key);previous=key
    graph.add_edge(previous,END)
    try:
        result=await graph.compile().ainvoke({'checkpoint':checkpoint},{'recursion_limit':10})
    except NodeCancelledError:
        with SessionLocal() as db:cancelled=db.get(ModelJob,job_id).status=='cancelled'
        if cancelled:raise asyncio.CancelledError() from None
        raise ModelError('工作流节点被中断，已完成结果保留，可手动继续。') from None
    return result['checkpoint']
