"""Explicit sharing and version-preserving adaptation. No private draft auto-publication."""
import copy
from fastapi import APIRouter,Depends,Request
from sqlalchemy import select
from .database import get_db
from .models import Account,TeachingCase,CaseVersion,LessonDraft,LessonDraftVersion
from .classroom_models import CommunityShare,CommunityBookmark,CommunityEvent
from .exams import teacher,uid,fail
from .teaching import iso
from .library import current_case
from .curriculum import published_lesson
from .drafts import checkpoint
router=APIRouter(prefix='/api/community')
def visible(db,s,u):
 if s.owner_id==u.id:return True
 if not s.active:return False
 return s.kind!='case' or bool(db.get(TeachingCase,s.source_id) and db.get(TeachingCase,s.source_id).status=='published')
def access(db,u,ident):
 s=db.scalar(select(CommunityShare).where(CommunityShare.id==ident).with_for_update())
 if not s or not visible(db,s,u):fail('分享已撤回或没有访问权限。',404)
 return s
def view(db,u,s):
 return {'id':s.id,'ownerId':s.owner_id,'author':db.get(Account,s.owner_id).display_name,'kind':s.kind,'sourceId':s.source_id,'snapshot':s.snapshot,'active':s.active,'createdAt':iso(s.created_at),'bookmarked':bool(db.get(CommunityBookmark,(s.id,u.id))),'events':[{'id':e.id,'ownerId':e.owner_id,'author':db.get(Account,e.owner_id).display_name,'kind':e.kind,'data':e.data if not e.withdrawn else {},'withdrawn':e.withdrawn,'at':iso(e.created_at)} for e in db.scalars(select(CommunityEvent).where(CommunityEvent.share_id==s.id).order_by(CommunityEvent.created_at,CommunityEvent.id))]}
@router.get('')
def listing(request:Request,db=Depends(get_db)):
 u=teacher(request,db);return [view(db,u,s) for s in db.scalars(select(CommunityShare).order_by(CommunityShare.created_at.desc())) if visible(db,s,u)]
@router.post('',status_code=201)
def create(body:dict,request:Request,db=Depends(get_db)):
 u=teacher(request,db)
 if not body.get('confirmed'):fail('请确认将指定版本公开给其他教师；不会自动公开其他私有草稿。')
 kind=body.get('kind');source=body.get('sourceId')
 if kind=='case':
  case=db.get(TeachingCase,source);v=db.get(CaseVersion,body.get('versionId'))
  if not case or case.status!='published' or not v or v.case_id!=source:fail('只能分享已审核发布的真实案例版本。')
  snapshot=copy.deepcopy(current_case(db,source,v.id))
 elif kind=='plan':
  draft=db.get(LessonDraft,source);v=db.get(LessonDraftVersion,body.get('versionId'))
  if not draft or draft.teacher_id!=u.id or not v or v.draft_id!=draft.id:fail('请选择本人已保存的教案版本。',404)
  snapshot={k:copy.deepcopy(v.data.get(k)) for k in ['lessonId','goal','blocks','questions','caseSnapshot','lessonSnapshot']};snapshot['title']=(snapshot.get('lessonSnapshot') or {}).get('title','共享教案');snapshot['versionId']=v.id
 else:fail('分享类型无效。')
 s=CommunityShare(id=uid('share'),owner_id=u.id,kind=kind,source_id=source,snapshot=snapshot,active=True);db.add(s);db.commit();return view(db,u,s)
@router.get('/{ident}')
def detail(ident:str,request:Request,db=Depends(get_db)):
 u=teacher(request,db);return view(db,u,access(db,u,ident))
@router.post('/{ident}/withdraw')
def withdraw(ident:str,request:Request,db=Depends(get_db)):
 u=teacher(request,db);s=access(db,u,ident)
 if s.owner_id!=u.id:fail('只能撤回自己的分享。',403)
 s.active=False;db.commit();return view(db,u,s)
@router.put('/{ident}/bookmark')
def bookmark(ident:str,body:dict,request:Request,db=Depends(get_db)):
 u=teacher(request,db);s=access(db,u,ident);old=db.get(CommunityBookmark,(s.id,u.id))
 if body.get('selected') and not old:db.add(CommunityBookmark(share_id=s.id,owner_id=u.id))
 elif not body.get('selected') and old:db.delete(old)
 db.commit();return view(db,u,s)
@router.post('/{ident}/events',status_code=201)
def event(ident:str,body:dict,request:Request,db=Depends(get_db)):
 u=teacher(request,db);s=access(db,u,ident);kind=body.get('kind');text=body.get('text','')
 if kind not in ('discussion','feedback') or not isinstance(text,str) or not text.strip() or len(text)>6000:fail('请选择讨论或使用反馈并填写内容。')
 task_id=body.get('taskId')
 if task_id:
  from .models import LearningTask
  t=db.get(LearningTask,task_id)
  if not t or t.teacher_id!=u.id:fail('请选择本人有权限的实际任务。')
 e=CommunityEvent(id=uid('ce'),share_id=s.id,owner_id=u.id,kind=kind,data={'text':text,'taskId':task_id,'basis':'关联实际任务，仅为作者自述' if task_id else '个人讨论或自述，未验证课堂效果'});db.add(e);db.commit();return view(db,u,s)
@router.post('/{ident}/events/{eid}/withdraw')
def withdraw_event(ident:str,eid:str,request:Request,db=Depends(get_db)):
 u=teacher(request,db);s=access(db,u,ident);e=db.get(CommunityEvent,eid)
 if not e or e.share_id!=s.id or e.owner_id!=u.id:fail('只能撤回自己的讨论或反馈。',403)
 e.withdrawn=True;db.commit();return view(db,u,s)
@router.post('/{ident}/adapt',status_code=201)
def adapt(ident:str,body:dict,request:Request,db=Depends(get_db)):
 u=teacher(request,db);s=access(db,u,ident);lesson=published_lesson(db,body.get('lessonId'))
 if not s.active or not lesson:fail('请选择当前课时及仍公开的分享。')
 db.scalar(select(Account).where(Account.id==u.id).with_for_update())
 if db.scalar(select(LessonDraft.id).where(LessonDraft.teacher_id==u.id,LessonDraft.lesson_id==lesson['lessonId'])):fail('该课时已有本人教案，保留原稿；请选择另一课时。',409)
 src=s.snapshot;blocks=copy.deepcopy(lesson['blocks']);goal=src.get('goal') or lesson['goal']
 if s.kind=='case':
  if blocks:blocks[0]['content']=src['content']
  case_id=s.source_id;case_snapshot=src
 else:blocks=copy.deepcopy(src.get('blocks') or blocks);case_id=(src.get('caseSnapshot') or {}).get('id');case_snapshot=src.get('caseSnapshot')
 draft=LessonDraft(id=uid('draft'),teacher_id=u.id,lesson_id=lesson['lessonId'],case_id=case_id,case_snapshot=copy.deepcopy(case_snapshot),lesson_snapshot=copy.deepcopy(lesson),goal=goal,student_base='',due_date='',blocks=blocks,questions=copy.deepcopy(lesson['questions']),planning_details={});db.add(draft);db.flush();checkpoint(db,draft,'从共享版本创建独立改编草稿');provenance={'draftId':draft.id,'lessonId':lesson['lessonId'],'sourceShareId':s.id,'sourceVersionId':src['versionId'],'sourceAuthor':src.get('author') or ('原案例未署名' if s.kind=='case' else db.get(Account,s.owner_id).display_name),'status':'私有草稿，需经原有核对/预览/发布流程'};db.add(CommunityEvent(id=uid('ce'),share_id=s.id,owner_id=u.id,kind='adaptation',data=provenance));db.commit();return provenance
