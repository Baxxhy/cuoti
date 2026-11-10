"""Additional fields and outcome projection for existing teaching supplements."""
import copy
from fastapi import HTTPException
from sqlalchemy import select
from .models import StudentRecord,LearningTask,WrongQuestion,KnowledgePoint
from . import learning_memory as memory

def prepare(db,user,task,targets,body):
    if not body.knowledgeId:return None
    if not db.get(KnowledgePoint,body.knowledgeId):raise HTTPException(422,'请选择真实知识点。')
    details={'knowledgeId':body.knowledgeId,'targets':{},'baseline':{},'baselineQuestions':{},'case':None}
    for sid in targets:
        facts,tasks,_,_=memory.collect(db,sid,user.id,{task.classroom_id})
        facts=[e for e in facts if e['taskId']==task.id]
        if body.difficultyOnly and not any(e['knowledgeId']==body.knowledgeId and not e.get('helped') and e['verification']=='verified_incorrect' and e['sourceType'] in ('attempt','repair') for e in facts):raise HTTPException(422,'候选名单已变化，请重新查看原始错误并确认。')
        target=body.targets.get(sid) or body.target or {'taskId':task.id,'kind':'check' if body.kind=='retest' else 'learn'}
        if target.get('wrongId'):
            wrong=db.get(WrongQuestion,target['wrongId']);rec=db.get(StudentRecord,wrong.record_id) if wrong and wrong.record_id else None
            if not rec or rec.student_id!=sid or rec.task_id!=task.id:raise HTTPException(422,'错题必须来自该学生的当前任务，个人错题不共享。')
            target={'wrongId':wrong.id,'kind':'repair'}
        else:
            tid=target.get('taskId');rec=db.scalar(select(StudentRecord).where(StudentRecord.task_id==tid,StudentRecord.student_id==sid));t=db.get(LearningTask,tid)
            if not rec or not t or t.teacher_id!=user.id or t.classroom_id!=task.classroom_id:raise HTTPException(422,'目标必须是本班已分配的真实课时。')
            if target.get('kind') not in ('learn','check'):raise HTTPException(422,'目标入口无效。')
            if target.get('kind')=='check' and not any(q.get('kind')=='check' for q in t.questions):raise HTTPException(422,'该课时没有独立检查题。')
            target={'taskId':tid,'kind':target['kind']}
        details['targets'][sid]=target
        # Include target-task history even when it differs from source task.
        target_facts=memory.collect(db,sid,user.id,{task.classroom_id})[0]
        details['baseline'][sid]=list({e['eventId'] for e in target_facts})
        details['baselineQuestions'][sid]=list({e.get('questionKey') for e in target_facts if e['sourceType'] in ('attempt','repair')})
    if body.caseId:
        from .library import current_case as published_case_json
        case=published_case_json(db,body.caseId)
        if not case:raise HTTPException(422,'案例已撤回，请重新选择。')
        details['case']=copy.deepcopy(case)
    return details

def outcomes(db,item,student_id):
    d=item.details or {};target=d.get('targets',{}).get(student_id)
    if not target:return None
    task=db.get(LearningTask,item.task_id);facts=memory.collect(db,student_id,item.teacher_id,{task.classroom_id})[0]
    baseline=set(d.get('baseline',{}).get(student_id,[]));old_questions=set(d.get('baselineQuestions',{}).get(student_id,[]))
    fresh={e['eventId']:e for e in facts if e['eventId'] not in baseline and e['sourceType'] in ('attempt','repair') and ((target.get('wrongId') and e.get('wrongId')==target['wrongId']) or (target.get('taskId') and e['taskId']==target['taskId']))}
    rows=list(fresh.values());new=[e for e in rows if e.get('questionKey') not in old_questions];passed=[e for e in new if not e.get('helped') and e['verification']=='verified_correct']
    return {'newAttempts':len(rows),'newQuestions':len({e.get('questionKey') for e in new}),'independentPassed':bool(passed),'needsHelp':any(e.get('helped') or e['verification']!='verified_correct' for e in rows),'evidence':rows,'target':target,'label':'新增独立正确证据' if passed else '有新作答，尚无独立新题通过' if rows else '尚无新作答'}
