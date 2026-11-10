"""Recomputable, evidence-first learning memory. No model text scan or mastery score."""
import os,copy,json,hashlib,uuid
from datetime import datetime,timedelta,timezone
from fastapi import APIRouter,Depends,HTTPException,Request
from sqlalchemy import select,or_,text
from sqlalchemy.exc import IntegrityError
from .database import get_db
from .models import Account,ClassMember,Classroom,LearningTask,StudentRecord,Attempt,HelpRecord,WrongQuestion,RepairAttempt,KnowledgePoint,LearningMemoryChange
router=APIRouter(prefix='/api/memory')
LABELS={'none':'暂无证据','insufficient':'证据不足','strengthen':'需要补强','improving':'正在改善','independent':'已有独立正确证据','review_due':'需要再次复习'}
OUTCOMES={'independent_correct':'独立正确','independent_incorrect':'独立错误','helped_correct':'帮助后正确','helped_incorrect':'帮助后错误','unverified':'未核验作答','retest_passed':'独立复测通过','retest_failed':'独立复测未通过','legacy_repair':'历史固定示例','confirmed_cause':'已确认错因','suggested_cause':'待确认错因','teacher_confirmation':'教师人工核对','teacher_feedback':'教师反馈','help':'帮助记录'}

def now():return datetime.now(timezone.utc).replace(tzinfo=None)
def iso(value):return value.isoformat()+'Z' if value else None
def stamp(value):
    try:return datetime.fromisoformat(value.replace('Z','+00:00')).replace(tzinfo=None)
    except (ValueError,TypeError):return datetime.min

def rules():
    def number(key,default,lo,hi):
        try:return max(lo,min(hi,int(os.getenv(key,str(default)))))
        except ValueError:return default
    return {'version':'memory-rules-v1','minimumIndependent':number('SCZX_MEMORY_MIN_INDEPENDENT',2,2,20),'recentHours':number('SCZX_MEMORY_RECENT_HOURS',48,1,720),'reviewDays':number('SCZX_MEMORY_REVIEW_DAYS',7,1,365),'snoozeDays':number('SCZX_MEMORY_SNOOZE_DAYS',1,1,30)}

def actor_for(request,db):
    from .main import current_user
    return current_user(request,db)

def authorized(db,actor,student_id=None,class_id=None):
    if actor.role=='student':
        if student_id and student_id!=actor.id:raise HTTPException(404,'没有找到本人的学习记忆。')
        return actor.id,None
    if actor.role!='teacher' or not student_id:raise HTTPException(403,'请选择有权限班级的学生。')
    query=select(ClassMember.classroom_id).join(Classroom,ClassMember.classroom_id==Classroom.id).where(Classroom.teacher_id==actor.id,ClassMember.student_id==student_id)
    if class_id:query=query.where(Classroom.id==class_id)
    allowed=set(db.scalars(query).all())
    if not allowed:raise HTTPException(404,'没有当前班级学生的学习记忆权限。')
    return student_id,allowed

def verified_status(value,correct):
    status=(value or {}).get('status')
    if status in ('verified','verified_correct'):return 'verified_correct' if correct else 'verified_incorrect'
    if status in ('inconsistent','verified_incorrect'):return 'verified_incorrect'
    return 'unverified'

def collect(db,student_id,teacher_id=None,class_ids=None):
    """Read structured facts from permitted records. Stable source IDs survive recomputation."""
    query=select(StudentRecord,LearningTask).join(LearningTask,LearningTask.id==StudentRecord.task_id).where(StudentRecord.student_id==student_id)
    if teacher_id:query=query.where(LearningTask.teacher_id==teacher_id,LearningTask.classroom_id.in_(class_ids or []))
    pairs=db.execute(query).all();records={r.id:(r,t) for r,t in pairs};tasks={t.id:t for r,t in pairs};record_ids=list(records)
    offset_seconds=int(db.execute(text('SELECT TIMESTAMPDIFF(SECOND, UTC_TIMESTAMP(), NOW())')).scalar())
    active={m.classroom_id for m in db.scalars(select(ClassMember).where(ClassMember.student_id==student_id)).all()}
    points={p.id:p for p in db.scalars(select(KnowledgePoint)).all()};events=[]
    def add(event_id,source_type,source_id,ids,time,task=None,**data):
        ids=[k for k in dict.fromkeys(ids or []) if k in points]
        legacy=bool(task and task.source=='legacy-demo')
        local_source=source_type in ('attempt','help','wrong','repair')
        effective=time-timedelta(seconds=offset_seconds) if time and local_source and not legacy else time
        base={'rawOccurredAt':time.isoformat() if time else None,'timeBasis':'legacy_unknown' if legacy else 'database_session' if local_source else 'utc','timeReliable':not legacy and bool(effective and effective<=now()+timedelta(minutes=5)),'eventId':event_id,'sourceType':source_type,'sourceId':source_id,'studentId':student_id,'knowledgeIds':ids,'originalKnowledgeIds':list(ids),'occurredAt':iso(effective),'taskId':task.id if task else None,'classId':task.classroom_id if task else None,'lessonVersionId':((task.snapshot.get('lessonSnapshot') or {}).get('versionId') if task else None),'readOnly':bool(task and task.classroom_id not in active),'target':('/result?task='+task.id) if task else None,**data}
        events.append(base);return base
    def knowledge(task,q=None):return (q or {}).get('knowledgeIds',(task.snapshot.get('lessonSnapshot') or {}).get('knowledgeIds',task.snapshot.get('knowledgeIds',[])))
    helps=db.scalars(select(HelpRecord).where(HelpRecord.record_id.in_(record_ids or ['']))).all();help_indices={(h.record_id,h.question) for h in helps}
    attempts=db.scalars(select(Attempt).where(Attempt.record_id.in_(record_ids or ['']))).all()
    attempt_map={a.id:a for a in attempts}
    for a in attempts:
        rec,task=records[a.record_id];q=task.questions[a.question] if isinstance(a.question,int) and 0<=a.question<len(task.questions or []) else {}
        # Help fact is evaluated at attempt time: a later help must not rewrite the earlier independence.
        helped=bool(a.helped) or any(h.record_id==a.record_id and h.question==a.question and h.created_at<a.created_at for h in helps)
        verification=verified_status(a.verification,a.correct)
        outcome='unverified' if verification=='unverified' else ('helped_' if helped else 'independent_')+('correct' if verification=='verified_correct' else 'incorrect')
        add('attempt:'+a.id,'attempt',a.id,knowledge(task,q),a.created_at,task,prompt=q.get('prompt',''),equation=q.get('equation',''),answer=a.answer,reason=a.reason,helped=helped,verification=verification,outcome=outcome,questionIndex=a.question,questionKey=task.lesson_id+':'+str(q.get('id',a.question)),recordId=rec.id)
    for h in helps:
        rec,task=records[h.record_id];q=task.questions[h.question] if isinstance(h.question,int) and 0<=h.question<len(task.questions or []) else {}
        add('help:'+h.id,'help',h.id,knowledge(task,q),h.created_at,task,helped=True,verification='unverified',outcome='help',reason=h.kind,recordId=rec.id)
    wrong_query=select(WrongQuestion).where(or_(WrongQuestion.record_id.in_(record_ids or ['']),WrongQuestion.owner_id==student_id)) if not teacher_id else select(WrongQuestion).where(WrongQuestion.record_id.in_(record_ids or ['']))
    wrongs=db.scalars(wrong_query).all();wrong_map={w.id:w for w in wrongs}
    for w in wrongs:
        task=records[w.record_id][1] if w.record_id in records else None;d=w.details or {};a=attempt_map.get(w.attempt_id);q=task.questions[a.question] if task and a and 0<=a.question<len(task.questions) else None
        ids=d.get('knowledgeIds') or (knowledge(task,q) if task else [])
        add('wrong:'+w.id,'wrong',w.id,ids,w.created_at,task,prompt=w.prompt,equation=d.get('equation',w.prompt),answer=w.answer,reason=w.reason,wrongId=w.id,cause=d.get('cause'),causeConfirmed=d.get('causeConfirmed',False),outcome='confirmed_cause' if d.get('causeConfirmed') else 'suggested_cause',verification='unverified',target='/repair?wrong='+w.id)
    repairs=db.scalars(select(RepairAttempt).where(RepairAttempt.wrong_id.in_(list(wrong_map) or ['']))).all()
    for a in repairs:
        w=wrong_map[a.wrong_id];task=records[w.record_id][1] if w.record_id in records else None;wd=w.details or {};origin=next(e for e in events if e['eventId']=='wrong:'+w.id);d=a.details or {};modern=d.get('version')=='dynamic_v1';helped=bool(d.get('helped')) or d.get('phase')!='retest';verification=verified_status(a.verification,a.correct) if modern else 'unverified'
        outcome='legacy_repair' if not modern else 'unverified' if verification=='unverified' else ('retest_passed' if a.correct else 'retest_failed') if not helped else ('helped_correct' if a.correct else 'helped_incorrect')
        add('repair:'+a.id,'repair',a.id,origin['knowledgeIds'],a.created_at,task,equation=d.get('equation','z + 2 = 9' if not modern else ''),answer=a.answer,reason=a.reason,wrongId=w.id,helped=helped,verification=verification,outcome=outcome,phase=d.get('phase'),questionKey=d.get('variantId',a.id),target='/repair?wrong='+w.id)
        if d.get('teacherReview'):
            review=d['teacherReview']
            if not teacher_id or review.get('teacherId')==teacher_id:add('teacher-review:'+a.id,'teacher_confirmation',a.id,origin['knowledgeIds'],stamp(review.get('at')),task,outcome='teacher_confirmation',verification='unverified',reason=review.get('note',''),teacherCorrect=review.get('correct'),wrongId=w.id,target='/repair?wrong='+w.id)
    for rec,task in pairs:
        if rec.feedback and rec.feedback_at:add('feedback:'+rec.id+':'+iso(rec.feedback_at),'teacher_feedback',rec.id,knowledge(task),rec.feedback_at,task,outcome='teacher_feedback',verification='unverified',reason=rec.feedback,teacherId=task.teacher_id)
    changes=db.scalars(select(LearningMemoryChange).where(LearningMemoryChange.student_id==student_id).order_by(LearningMemoryChange.created_at,LearningMemoryChange.id)).all()
    visible_ids={e['eventId'] for e in events}
    # A teacher sees only corrections to their authorized facts; personal observations never leak.
    changes=[c for c in changes if not teacher_id or c.source_event_id in visible_ids]
    for c in changes:
        if c.kind=='knowledge_correction' and c.source_event_id in visible_ids:
            event=next(e for e in events if e['eventId']==c.source_event_id);event['knowledgeIds']=c.details['knowledgeIds'];event['correctionId']=c.id
    flattened=[]
    for event in sorted(events,key=lambda x:(x['occurredAt'] or '',x['eventId'])):
        for kp in event['knowledgeIds'] or [None]:flattened.append({**copy.deepcopy(event),'knowledgeId':kp,'evidenceId':event['eventId']+':'+str(kp or 'unlinked'),'label':OUTCOMES[event['outcome']]})
    for e in flattened:
        # Resolved wrongs are tied to their actual independent retest, not any later correct answer.
        if e['sourceType']=='wrong':
            passes=[a for a in flattened if a.get('wrongId')==e['wrongId'] and a['sourceType']=='repair' and a['outcome'] in ('retest_passed','retest_failed')]
            e['retestOutcome']=passes[-1]['outcome'] if passes else None
            e['hasPractice']=any(a.get('wrongId')==e['wrongId'] and a['sourceType']=='repair' and a.get('phase')=='practice' for a in flattened)
    return flattened,tasks,points,changes

def calculate(evidence,config=None,clock=None):
    config=config or rules();clock=clock or now();facts=[e for e in evidence if e['sourceType'] in ('attempt','repair') and e['outcome']!='legacy_repair'];known=[e for e in facts if e['verification'] in ('verified_correct','verified_incorrect')];independent=[e for e in known if not e.get('helped')];correct=[e for e in independent if e['verification']=='verified_correct'];errors=[e for e in independent if e['verification']=='verified_incorrect'];last=independent[-1] if independent else None
    status='none' if not evidence else 'insufficient';reason='暂无作答记录。' if not evidence else '目前还缺少足够的独立练习证据。'
    if len(independent)>=2 and len(errors)>=2 and all(e['verification']=='verified_incorrect' for e in independent[-2:]):status,reason='strengthen','最近两次独立作答未通过，建议先订正再检查。'
    elif last and last['verification']=='verified_correct' and errors and stamp(last['occurredAt'])>=stamp(errors[-1]['occurredAt']):status,reason='improving','错误之后新增了独立正确证据，可继续检查。'
    distinct={e.get('questionKey',e['sourceId']) for e in correct}
    if last and last['verification']=='verified_correct' and len(distinct)>=config['minimumIndependent'] and (not errors or stamp(errors[-1]['occurredAt'])<stamp(correct[-2]['occurredAt'])):status,reason='independent','已有不同题目的独立正确证据，仍可按间隔复习。'
    if status in ('independent','improving') and last and last.get('timeReliable',True) and clock-stamp(last['occurredAt'])>=timedelta(days=config['reviewDays']):status,reason='review_due','距最近独立作答已达到配置的复习间隔，建议再检查一次。'
    if last:
        tied=[e for e in independent if e['occurredAt']==last['occurredAt']]
        if len({e['verification'] for e in tied})>1:status,reason='insufficient','同一时间的正确与错误证据顺序不确定，请补充一次独立检查。'
    return {'status':status,'statusLabel':LABELS[status],'reason':reason,'evidenceCount':len(evidence),'verifiedCount':len(known),'independentCorrect':len(correct),'independentIncorrect':len(errors),'helpedCorrect':sum(e['outcome']=='helped_correct' for e in known),'unverifiedCount':sum(e['verification']=='unverified' for e in facts),'legacyCount':sum(e['outcome']=='legacy_repair' for e in evidence),'lastPracticedAt':facts[-1]['occurredAt'] if facts else None,'lastIndependentAt':last['occurredAt'] if last else None,'basisIds':[e['evidenceId'] for e in known[-6:]],'recentVerifiedCount':sum(e.get('timeReliable',True) and timedelta(0)<=clock-stamp(e['occurredAt'])<=timedelta(hours=config['recentHours']) for e in known),'dayCount':len({e['occurredAt'][:10] for e in independent})}

def task_knowledge(task):return list(dict.fromkeys([*(task.snapshot.get('lessonSnapshot') or {}).get('knowledgeIds',task.snapshot.get('knowledgeIds',[])),*[k for q in task.questions or [] for k in q.get('knowledgeIds',[])]]))

def recommendations(kp,evidence,state,tasks,points,changes,student_id,clock=None,config=None):
    clock=clock or now();config=config or rules();candidates=[]
    def task_target(point,kind='learn'):
        valid=[t for t in tasks.values() if point in task_knowledge(t)]
        # Never recommend writing an old task after membership ends.
        valid=[t for t in valid if not any(e['taskId']==t.id and e['readOnly'] for e in evidence)]
        if not valid:return None
        if kind=='check':
            seen={(e['taskId'],e.get('questionIndex')) for e in evidence if e['sourceType']=='attempt'}
            for t in sorted(valid,key=lambda t:(t.published_at,t.id),reverse=True):
                for index,q in enumerate(t.questions or []):
                    if q.get('kind')=='check' and (t.id,index) not in seen and point in q.get('knowledgeIds',task_knowledge(t)):return '/check?task='+t.id+'&question='+str(index)
            return None
        t=sorted(valid,key=lambda t:(t.published_at,t.id),reverse=True)[0];return '/'+kind+'?task='+t.id
    wrongs=[e for e in evidence if e['sourceType']=='wrong' and not e['readOnly']]
    for e in reversed(wrongs):
        if e.get('retestOutcome')=='retest_passed':continue
        action='independent_retest' if e.get('hasPractice') else 'continue_repair'
        candidates.append({'action':action,'label':'独立新题' if action=='independent_retest' else '继续补救','target':e['target'],'reason':'补救后尚无这道错题的独立新题通过记录。' if action=='independent_retest' else '已有原始错题，先继续针对性订正。','priority':1 if action=='continue_repair' else 2,'evidenceIds':[e['evidenceId']]})
    if not candidates:
        helped=[e for e in evidence if e['outcome']=='helped_correct']
        errors=[e for e in evidence if e['outcome'] in ('independent_incorrect','retest_failed')]
        independent=[e for e in evidence if e['outcome'] in ('independent_correct','retest_passed')]
        if helped and (not independent or stamp(independent[-1]['occurredAt'])<stamp(helped[-1]['occurredAt'])):
            target=task_target(kp,'check')
            if target:candidates.append({'action':'independent_retest','label':'独立检查','target':target,'reason':'已有帮助后正确记录，仍需补充独立新题证据。','priority':2,'evidenceIds':[helped[-1]['evidenceId']]})
        elif errors and (not independent or stamp(independent[-1]['occurredAt'])<stamp(errors[-1]['occurredAt'])):
            target=task_target(kp)
            if target:candidates.append({'action':'review_explanation','label':'回看讲解','target':target,'reason':'相关独立作答有错误，先回看原课时。','priority':1,'evidenceIds':[errors[-1]['evidenceId']]})
        elif state['status']=='review_due':
            target=task_target(kp,'check')
            if target:candidates.append({'action':'new_practice','label':'再次检查','target':target,'reason':'已达到复习间隔，建议用一次新的实际作答检查。','priority':4,'evidenceIds':state['basisIds'][-2:]})
        elif state['status'] in ('none','insufficient'):
            target=task_target(kp,'learn' if state['status']=='none' else 'check')
            if target:candidates.append({'action':'review_example' if state['status']=='none' else 'new_practice','label':'查看例题' if state['status']=='none' else '补充练习','target':target,'reason':'先查看课时例题，再补充实际作答证据。' if state['status']=='none' else '目前独立证据不足，可补充一道实际练习。','priority':5,'evidenceIds':state['basisIds'][-2:]})
    if not candidates:return None
    item=sorted(candidates,key=lambda e:e['priority'])[0];item.update(id='review:'+student_id+':'+kp,knowledgeId=kp)
    return item

def evidence_digest(item):
    return hashlib.sha256(json.dumps({'evidence':item['evidence'],'basis':(item.get('recommendation') or {}).get('evidenceIds',[])},ensure_ascii=False,sort_keys=True,default=str).encode()).hexdigest()

def build(db,actor,student_id=None,class_id=None,clock=None):
    student_id,classes=authorized(db,actor,student_id,class_id);evidence,tasks,points,changes=collect(db,student_id,actor.id if actor.role=='teacher' else None,classes);config=rules();active={m.classroom_id for m in db.scalars(select(ClassMember).where(ClassMember.student_id==student_id)).all()}
    # Course targets must be writable even when there are no evidence rows yet.
    writable={k:t for k,t in tasks.items() if t.classroom_id in active}
    relevant=set(k for t in tasks.values() for k in task_knowledge(t))|{e['knowledgeId'] for e in evidence if e['knowledgeId']}
    relevant|={k for p in list(relevant) if p in points for k in (points[p].prerequisites or []) if k in points}
    items=[]
    for kp in sorted(relevant):
        if kp not in points:continue
        facts=[e for e in evidence if e['knowledgeId']==kp];state=calculate(facts,config,clock);rec=recommendations(kp,facts,state,writable,points,changes,student_id,clock,config)
        transitions=[]
        for index,fact in enumerate(facts):
            if fact['sourceType'] not in ('attempt','repair'):continue
            historical=calculate(facts[:index+1],config,stamp(fact['occurredAt']))
            if not transitions or transitions[-1]['status']!=historical['status']:transitions.append({'at':fact['occurredAt'],'status':historical['status'],'label':historical['statusLabel'],'evidenceId':fact['evidenceId']})
        items.append({'stateHistory':transitions[-20:],'id':kp,'name':points[kp].name,'prerequisites':[{'id':i,'name':points[i].name} for i in points[kp].prerequisites or [] if i in points],'state':state,'evidence':facts,'recommendation':rec,'lessons':[{'taskId':t.id,'title':t.title,'lessonId':t.lesson_id,'versionId':(t.snapshot.get('lessonSnapshot') or {}).get('versionId'),'readOnly':t.classroom_id not in active,'target':'/learn?task='+t.id} for t in tasks.values() if kp in task_knowledge(t)]})
    by_id={i['id']:i for i in items}
    for item in items:
        difficult=[by_id[p['id']] for p in item['prerequisites'] if p['id'] in by_id and by_id[p['id']]['state']['independentIncorrect']>=2 and by_id[p['id']]['state']['status'] in ('strengthen','insufficient')]
        if difficult and (not item['recommendation'] or item['recommendation']['priority']>3):
            pre=difficult[0];target=next((l['target'] for l in pre['lessons'] if not l['readOnly']),None) or (pre['recommendation'] or {}).get('target')
            if target:item['recommendation']={'id':'review:'+student_id+':'+item['id'],'knowledgeId':item['id'],'action':'foundation','label':'补前置知识','target':target,'reason':pre['name']+'有两条独立错误证据，可先检查这一层前置知识。','priority':3,'evidenceIds':pre['state']['basisIds'],'prerequisiteId':pre['id']}
    audit=[{'id':c.id,'kind':c.kind,'eventId':c.source_event_id,'knowledgeId':c.knowledge_id,'actorId':c.actor_id,'details':c.details,'createdAt':iso(c.created_at)} for c in changes]
    for item in items:
        decisions=[c for c in changes if c.knowledge_id==item['id'] and c.kind in ('review_required','observation','review_content')]
        item['teacherDecisions']=[{'id':c.id,'kind':c.kind,'reason':c.details.get('reason'),'note':c.details.get('note'),'at':iso(c.created_at)} for c in decisions]
        item['state']['reviewRequested']=any(c.kind=='review_required' for c in decisions)
        specified=[c for c in decisions if c.kind=='review_content']
        targets={l['target'] for i in items for l in i['lessons'] if not l['readOnly']}|{e['target'] for i in items for e in i['evidence'] if e['sourceType']=='wrong' and not e['readOnly']}
        if specified and specified[-1].details.get('target') in targets:
            from urllib.parse import urlparse,parse_qs
            c=specified[-1];params=parse_qs(urlparse(c.details['target']).query);baseline=c.details.get('baselineEventIds',[])
            completed=any(e['eventId'] not in baseline and e['sourceType'] in ('attempt','repair') and e['verification'] in ('verified_correct','verified_incorrect') and ((params.get('task') and e['taskId']==params['task'][0]) or (params.get('wrong') and e.get('wrongId')==params['wrong'][0])) for e in evidence)
            if not completed:item['recommendation']={'id':'review:'+student_id+':'+item['id'],'knowledgeId':item['id'],'action':'teacher_review','label':'查看教师建议','target':c.details['target'],'reason':c.details['reason'],'priority':0,'evidenceIds':[c.details['original']['evidenceId']],'teacherConfirmed':True}
        snoozes=[c for c in changes if c.kind=='snooze' and c.knowledge_id==item['id']]
        if item['recommendation'] and snoozes:
            c=snoozes[-1];latest=max((stamp(e['occurredAt']) for e in item['evidence']),default=datetime.min)
            if (clock or now())-c.created_at<timedelta(days=config['snoozeDays']) and c.details.get('evidenceDigest')==evidence_digest(item):item['recommendation'].update(snoozed=True,snoozedUntil=iso(c.created_at+timedelta(days=config['snoozeDays'])))
    visible=[i['recommendation'] for i in items if i['recommendation'] and not i['recommendation'].get('snoozed')]
    revisions=[(c.id,iso(c.created_at)) for c in changes]
    revision=hashlib.sha256(json.dumps({'evidence':evidence,'changes':revisions,'derived':[{'id':i['id'],'state':i['state'],'recommendation':i['recommendation']} for i in items],'rules':config,'day':(clock or now()).isoformat()[:10]},ensure_ascii=False,sort_keys=True,default=str).encode()).hexdigest()
    return {'studentId':student_id,'studentName':db.get(Account,student_id).display_name,'scope':'当前有权限班级与本教师任务' if actor.role=='teacher' else '本人全部学习记录','rules':config,'revision':revision,'items':items,'unlinkedEvidence':[e for e in evidence if not e['knowledgeId']],'recommendations':sorted(visible,key=lambda x:(x['priority'],x['knowledgeId'])),'audit':audit,'knowledgeOptions':[{'id':p.id,'name':p.name} for p in points.values()]}

@router.get('')
def overview(request:Request,studentId:str|None=None,classId:str|None=None,db=Depends(get_db)):
    return build(db,actor_for(request,db),studentId,classId)

@router.post('/changes',status_code=201)
def change(body:dict,request:Request,db=Depends(get_db)):
    actor=actor_for(request,db);student_id,classes=authorized(db,actor,body.get('studentId'),body.get('classId'));kind=body.get('kind');key=str(body.get('requestKey',''));reason=str(body.get('reason','')).strip()
    allowed=('snooze','correction_request') if actor.role=='student' else ('knowledge_correction','observation','review_required','review_content')
    if kind not in allowed or not 8<=len(key)<=80:raise HTTPException(422,'请选择有效操作并保留请求标识。')
    old=db.scalar(select(LearningMemoryChange).where(LearningMemoryChange.actor_id==actor.id,LearningMemoryChange.request_key==key))
    fingerprint=hashlib.sha256(json.dumps(body,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
    if old:
        if old.details.get('requestHash')!=fingerprint:raise HTTPException(409,'请求标识已用于其他修订。')
        return {'id':old.id,'created':False}
    current=build(db,actor,student_id,body.get('classId'))
    if body.get('expectedRevision')!=current['revision']:raise HTTPException(409,'证据或规则已更新，请重新读取后确认；输入未提交。')
    kp=body.get('knowledgeId');item=next((i for i in current['items'] if i['id']==kp),None)
    event=next((e for i in current['items'] for e in i['evidence'] if e['evidenceId']==body.get('evidenceId')),None)
    event=event or next((e for e in current['unlinkedEvidence'] if e['evidenceId']==body.get('evidenceId')),None)
    if kind=='snooze':
        if not item or not item['recommendation']:raise HTTPException(422,'没有可稍后处理的建议。')
    elif not event or not reason or len(reason)>3000:raise HTTPException(422,'请选择原始证据并说明修订理由。')
    ids=body.get('knowledgeIds',[])
    if kind=='knowledge_correction' and (not isinstance(ids,list) or not 1<=len(ids)<=8 or any(not db.get(KnowledgePoint,i) for i in ids)):raise HTTPException(422,'请选择真实知识点。')
    # Serialize competing corrections without touching original facts.
    db.commit()
    db.scalar(select(Account).where(Account.id==student_id).with_for_update())
    replay=db.scalar(select(LearningMemoryChange).where(LearningMemoryChange.actor_id==actor.id,LearningMemoryChange.request_key==key))
    if replay:
        if replay.details.get("requestHash")!=fingerprint:raise HTTPException(409,"请求标识已用于其他修订。")
        return {"id":replay.id,"created":False}
    db.expire_all();latest=build(db,actor,student_id,body.get('classId'))
    if latest['revision']!=current['revision']:raise HTTPException(409,'已有新的修订，请重新读取后确认。')
    if body.get('correctionRequestId'):
        proposed=db.get(LearningMemoryChange,str(body['correctionRequestId']))
        if not proposed or proposed.student_id!=student_id or proposed.kind!='correction_request' or proposed.source_event_id!=event['eventId']:raise HTTPException(422,'纠正请求与当前证据不一致。')
    detail={'reason':reason,'requestHash':fingerprint,'originalState':copy.deepcopy(item['state']) if item else None,'baselineEventIds':list({e['eventId'] for i in current['items'] for e in i['evidence']}),'original':copy.deepcopy(event or item['state']),'knowledgeIds':ids if kind=='knowledge_correction' else [],'note':str(body.get('note',''))[:3000],'proposedKnowledgeIds':body.get('knowledgeIds',[]) if kind=='correction_request' else [],'requestId':body.get('correctionRequestId'),'evidenceDigest':evidence_digest(item) if kind=='snooze' else None}
    if kind=='review_content':
        target=body.get('target','');valid={l['target'] for i in current['items'] for l in i['lessons'] if not l['readOnly']}|{e['target'] for i in current['items'] for e in i['evidence'] if e['sourceType']=='wrong' and not e['readOnly']}
        if target not in valid:raise HTTPException(422,'请选择有权限的实际课时或错题。')
        detail['target']=target
    row=LearningMemoryChange(id='memory-'+uuid.uuid4().hex,student_id=student_id,actor_id=actor.id,source_event_id=event['eventId'] if event else '',knowledge_id=kp,kind=kind,request_key=key,details=detail)
    db.add(row)
    try:db.commit()
    except IntegrityError:
        db.rollback();old=db.scalar(select(LearningMemoryChange).where(LearningMemoryChange.actor_id==actor.id,LearningMemoryChange.request_key==key))
        if old and old.details.get('requestHash')==fingerprint:return {'id':old.id,'created':False}
        raise HTTPException(409,'记录已变化，请重新读取。') from None
    return {'id':row.id,'created':True}

def related_memory(db,actor,record,current_ids,limit=6):
    """Only bounded, structured history from current IDs plus one prerequisite layer."""
    points={p.id:p for p in db.scalars(select(KnowledgePoint)).all()};direct=[k for k in current_ids if k in points];prerequisites={k for ident in direct for k in points[ident].prerequisites or [] if k in points};related=set(direct)|prerequisites
    evidence,_,_,changes=collect(db,actor.id)
    values=[e for e in evidence if e['knowledgeId'] in related and e['taskId']!=record.task_id and e['outcome'] not in ('help','legacy_repair','suggested_cause')]
    values=sorted(values,key=lambda e:(0 if e['outcome'] in ('independent_incorrect','retest_failed','retest_passed','confirmed_cause','teacher_confirmation','teacher_feedback') else 1,-stamp(e['occurredAt']).timestamp() if stamp(e['occurredAt'])!=datetime.min else 0))[:limit]
    return [{'evidenceId':e['evidenceId'],'sourceType':e['sourceType'],'sourceId':e['sourceId'],'knowledgeId':e['knowledgeId'],'occurredAt':e['occurredAt'],'verification':e['verification'],'helped':e.get('helped',False),'outcome':e['outcome'],'teacherConfirmed':e['sourceType'] in ('teacher_confirmation','teacher_feedback'),'knowledgeCorrectionId':e.get('correctionId'),'relation':'当前知识点' if e['knowledgeId'] in direct else '一层前置知识','summary':str(e.get('reason') or e.get('equation') or e.get('prompt') or e['label'])[:180]} for e in values]
