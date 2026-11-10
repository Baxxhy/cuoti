"""Teacher analytics are projections of original evidence, never an AI profile."""
from datetime import datetime, timedelta
import hashlib,json
from fastapi import APIRouter,Depends,HTTPException,Request
from sqlalchemy import select
from .database import get_db
from .models import Account,Classroom,ClassMember,LearningTask,StudentRecord,Attempt,SupplementalInstruction,LearningMemoryChange
from . import learning_memory as memory
from .teaching import owned_class,user_for,cutoff,now,has_started,supplement_json
router=APIRouter(prefix='/api/insights')

def period(start=None,end=None):
    def parse(v):
        if not v:return None
        return cutoff(v,True)
    lo=parse(start);hi=parse(end)
    if end and len(end)==10:hi+=timedelta(microseconds=1)
    if lo and start and len(start)==10:lo-=timedelta(days=1)-timedelta(microseconds=1)
    if lo and hi and lo>=hi:raise HTTPException(422,'结束时间必须晚于开始时间。')
    return lo,hi

def within(e,lo,hi):
    if not lo and not hi:return True
    if not e.get('timeReliable'):return False
    at=memory.stamp(e['occurredAt']);return (not lo or at>=lo) and (not hi or at<hi)

def latest_attempts(events):
    attempts={e['eventId']:e for e in events if e['sourceType']=='attempt'}
    groups={}
    for e in attempts.values():groups.setdefault((e['studentId'],e['taskId'],e.get('questionIndex')),[]).append(e)
    latest=[]
    for group in groups.values():
        group.sort(key=lambda e:(e['occurredAt'] or '',e['eventId']));last=group[-1]
        tied=[e for e in group if e['occurredAt']==last['occurredAt']]
        if len({(e['verification'],e.get('helped')) for e in tied})>1:
            last={**last,'verification':'unverified','helped':any(e.get('helped') for e in tied)}
        latest.append(last)
    return list(attempts.values()),latest

def metrics(events):
    """Latest attempt for each student/task/published question. Unknowns never pass."""
    attempts,latest=latest_attempts(events)
    independent=[e for e in latest if not e.get('helped') and e.get('questionKind') in ('check','replacement')];correct=[e for e in independent if e['verification']=='verified_correct']
    return {'attempts':len(attempts),'answeredQuestions':len(latest),'independentQuestions':len(independent),'independentCorrectQuestions':len(correct),'independentCorrectStudents':len({e['studentId'] for e in correct}),'unverifiedQuestions':sum(e['verification']=='unverified' for e in latest),'helpedQuestions':sum(bool(e.get('helped')) for e in latest)}

def class_report(db,actor,class_id,task_id=None,start=None,end=None):
    room=owned_class(db,actor,class_id);lo,hi=period(start,end)
    tasks=list(db.scalars(select(LearningTask).where(LearningTask.classroom_id==class_id,LearningTask.teacher_id==actor.id)).all())
    if task_id and task_id not in {t.id for t in tasks}:raise HTTPException(404,'没有找到本班任务。')
    selected={t.id:t for t in tasks if not task_id or t.id==task_id}
    students=list(db.scalars(select(Account).join(ClassMember,ClassMember.student_id==Account.id).where(ClassMember.classroom_id==class_id)).all());active={s.id for s in students}
    records=list(db.scalars(select(StudentRecord).where(StudentRecord.task_id.in_(list(selected) or ['']))).all());current=[r for r in records if r.student_id in active]
    all_events=[];student_rows=[];knowledge={};review=[];unknown_times=set()
    for student in students:
        facts,_,points,changes=memory.collect(db,student.id,actor.id,{class_id});unknown_times.update(e['eventId'] for e in facts if e['taskId'] in selected and not e.get('timeReliable'));facts=[e for e in facts if e['taskId'] in selected and within(e,lo,hi)]
        all_events+=facts;mine=[r for r in current if r.student_id==student.id];events={e['eventId']:e for e in facts};stats=metrics(facts)
        rows=[]
        ids=set(k for t in selected.values() for k in memory.task_knowledge(t))|{e['knowledgeId'] for e in facts if e['knowledgeId']}
        for kp in ids:
            if kp not in points:continue
            ev=[e for e in facts if e['knowledgeId']==kp];state=memory.calculate(ev);rows.append({'id':kp,'name':points[kp].name,'state':state})
            row=knowledge.setdefault(kp,{'id':kp,'name':points[kp].name,'prerequisites':points[kp].prerequisites or [],'students':[],'evidence':[]})
            fact=[e for e in ev if e['sourceType'] in ('attempt','repair') and e['outcome']!='legacy_repair'];verified=[e for e in fact if e['verification'] in ('verified_correct','verified_incorrect')]
            row['students'].append({'id':student.id,'name':student.display_name,'state':state,'hasEvidence':bool(fact),'verified':bool(verified),'correct':any(not e.get('helped') and e['verification']=='verified_correct' for e in verified),'error':any(not e.get('helped') and e['verification']=='verified_incorrect' for e in verified),'retestPassed':any(e['outcome']=='retest_passed' for e in ev),'pendingRetest':any(e['sourceType']=='wrong' and e.get('retestOutcome')!='retest_passed' for e in ev),'assigned':any(kp in memory.task_knowledge(selected[r.task_id]) for r in mine)})
            row['evidence']+=ev
        for e in events.values():
            if (e['sourceType'] in ('attempt','repair') and e['verification']=='unverified') or (e['sourceType']=='attempt' and e.get('reason')):
                review.append({**e,'manualReviews':[{'id':c.id,'note':c.details.get('note'),'at':memory.iso(c.created_at)} for c in changes if c.kind=='observation' and c.source_event_id==e['eventId']],'studentName':student.display_name,'reviewKind':'需核对' if e['verification']=='unverified' else '学生解释'})
        for c in changes:
            original=c.details.get('original') or {}
            if c.kind=='correction_request' and original.get('taskId') in selected and not any(x.details.get('requestId')==c.id for x in changes):review.append({'eventId':c.source_event_id,'studentId':student.id,'studentName':student.display_name,'taskId':original.get('taskId'),'reviewKind':'关联纠正请求','reason':c.details.get('reason'),'requestId':c.id,'evidenceId':original.get('evidenceId')})
        student_rows.append({'id':student.id,'name':student.display_name,'assigned':len(mine),'submitted':sum(r.completed for r in mine),'started':sum(has_started(r) or any(e['taskId']==r.task_id for e in facts) for r in mine),'unsubmitted':sum(not r.completed for r in mine),'overdue':sum(not r.completed and bool(cutoff(selected[r.task_id].due_date) and now()>cutoff(selected[r.task_id].due_date)) for r in mine),'metrics':stats,'knowledge':rows,'evidence':list(events.values()),'records':[{'taskId':r.task_id,'feedback':r.feedback,'observation':r.observation,'submitted':r.completed} for r in mine]})
    for row in knowledge.values():
        ss=row['students'];row['counts']={'classStudents':len(students),'assignedStudents':sum(s['assigned'] for s in ss),'answeredStudents':sum(s['hasEvidence'] for s in ss),'verifiedStudents':sum(s['verified'] for s in ss),'independentCorrectStudents':sum(s['correct'] for s in ss),'independentErrorStudents':sum(s['error'] for s in ss),'strengthenStudents':sum(s['state']['status']=='strengthen' for s in ss),'insufficientStudents':sum(s['state']['status'] in ('none','insufficient') for s in ss),'retestedStudents':sum(s['retestPassed'] for s in ss),'pendingRetestStudents':sum(s['pendingRetest'] for s in ss)}
    questions=[]
    for task in selected.values():
        for index,q in enumerate(task.questions or []):
            ev=[e for e in {e['eventId']:e for e in all_events}.values() if e['sourceType']=='attempt' and e['taskId']==task.id and e.get('questionIndex')==index];by={}
            for e in sorted(ev,key=lambda e:(e['occurredAt'] or '',e['eventId'])):by[e['studentId']]=e
            _,latest=latest_attempts(ev);questions.append({'id':task.id+':'+str(index),'taskId':task.id,'taskTitle':task.title,'versionId':(task.snapshot.get('lessonSnapshot') or {}).get('versionId'),'index':index,'prompt':q.get('prompt'),'equation':q.get('equation'),'knowledgeIds':q.get('knowledgeIds',memory.task_knowledge(task)),'students':len(by),'correctStudents':sum(e['verification']=='verified_correct' for e in latest),'incorrectStudents':sum(e['verification']=='verified_incorrect' for e in latest),'unverifiedStudents':sum(e['verification']=='unverified' for e in latest),'helpedStudents':len({e['studentId'] for e in ev if e.get('helped')}),'attempts':len(ev),'evidence':ev})
    supplements=list(db.scalars(select(SupplementalInstruction).where(SupplementalInstruction.task_id.in_(list(selected) or ['']))).all())
    stats=metrics(all_events);stats.update(members=len(students),tasks=len(selected),assignedStudents=len({r.student_id for r in current}),startedStudents=sum(s['started']>0 for s in student_rows),submittedStudents=sum(s['submitted']>0 for s in student_rows),unsubmittedStudents=sum(s['unsubmitted']>0 for s in student_rows),overdueStudents=sum(s['overdue']>0 for s in student_rows),inactiveRecords=len(records)-len(current))
    return {'class':{'id':room.id,'name':room.name,'grade':room.grade,'subject':room.subject},'tasks':[{'id':t.id,'title':t.title} for t in tasks],'stats':stats,'students':student_rows,'knowledge':sorted(knowledge.values(),key=lambda k:(-k['counts']['independentErrorStudents'],k['name'])),'questions':questions,'reviewQueue':review,'interventions':[supplement_json(db,actor,s) for s in supplements],'range':{'start':memory.iso(lo),'endExclusive':memory.iso(hi),'participation':'当前成员已分配记录的当前状态；作答/知识证据按区间过滤','unknownTimeExcluded':len(unknown_times) if lo or hi else 0,'unknownTimeTotal':len(unknown_times)}}

@router.get('')
def overview(request:Request,classId:str,taskId:str|None=None,start:str|None=None,end:str|None=None,db=Depends(get_db)):
    return class_report(db,user_for(request,db),classId,taskId,start,end)

@router.post('/reviews',status_code=201)
def review(body:dict,request:Request,db=Depends(get_db)):
    """Append manual observations via the existing memory audit; no regrading."""
    from .learning_memory import change
    decision=body.get('decision')
    if decision not in ('confirmed','returned'):raise HTTPException(422,'请选择确认或退回。')
    body={**body,'kind':'observation','note':('人工确认：' if decision=='confirmed' else '退回补充：')+str(body.get('reason',''))}
    return change(body,request,db)


def record_metrics(db,record,task,attempts,helps):
    facts=[]
    for a in attempts:
        q=task.questions[a.question] if 0<=a.question<len(task.questions) else {}
        facts.append({'eventId':'attempt:'+a.id,'studentId':record.student_id,'taskId':task.id,'sourceType':'attempt','questionIndex':a.question,'questionKind':q.get('kind'),'occurredAt':memory.iso(a.created_at),'verification':memory.verified_status(a.verification,a.correct),'helped':a.helped or any(h.question==a.question and h.created_at<a.created_at for h in helps)})
    return metrics(facts)
