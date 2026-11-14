"""Versioned, human-reviewed resource bundle imported into the existing library only."""
import copy,hashlib,json
from pathlib import Path
from sqlalchemy import select
from .models import Account,TeachingCase,CaseVersion,CaseDraftContent,KnowledgePoint,FileAsset,SourceMaterial,MaterialUnit
from .experience_policy import provenance,validate_experience
ROOT=Path(__file__).parent/'resources'
def digest(value):return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def load_bundle(root=ROOT):
    resources=json.loads((Path(root)/'teaching_experiences_v1.json').read_text())
    sources={s['id']:s for s in json.loads((Path(root)/'teaching_sources_v1.json').read_text())['sources']}
    review=json.loads((Path(root)/'teaching_review_v1.json').read_text()) if (Path(root)/'teaching_review_v1.json').is_file() else {'entries':{}}
    from .education import catalog,GRADES
    subjects={s['value'] for s in catalog()['subjects']};seen=set()
    for row in resources['entries']:
        if row['id'] in seen or row['subject'] not in subjects or row['grade'] not in GRADES:raise ValueError('资源ID重复或学科年级无效。')
        seen.add(row['id']);source=sources[row['sourceId']]
        if not source['url'].startswith('https://') or not all(row['experience'].get(k) for k in ('difficulty','diagnosis','strategy','steps','questions','responses','adjustment','effectCheck','boundary')):raise ValueError('经验来源或必要教学内容缺失。')
    return resources,sources,review

def reviewed(row,source,review):
    value=review.get('entries',{}).get(row['id'],{})
    return (value.get('resourceSha256')==digest(row) and value.get('sourceSha256')==digest(source)
            and value.get('allowedUsage')=='local_summary_only' and value.get('humanConfirmed') is True
            and review.get('reviewer') and review.get('evidence') and source.get('verification')=='web-readable')

def summary_text(row,source):
    e=row['experience']
    return '\n'.join(['师承智学中文方法摘要（AI辅助整理、用户单人复核；非来源原文或课堂实录）',row['subject']+' '+row['grade']+' '+row['topic'],e['strategy'],*e['steps'],'关键追问：'+e['questions'][0],'调整：'+e['adjustment'],'独立检查：'+e['effectCheck'],'适用边界：'+e['boundary'],'参考来源：'+source['title'],'来源作者/机构：'+source['author'],source['url'],'原作许可：'+source['license'],'本地仅含方法摘要与链接；不含第三方图片、音视频或完整教案。'])

def import_resources(db,actor_id,*,apply=False,root=ROOT,storage=None):
    """Caller owns transaction. Never revise/update any existing library row."""
    bundle,sources,review=load_bundle(root)
    actor=db.get(Account,actor_id)
    if not actor or actor.role!='admin':raise ValueError('资源导入需使用现有管理员账号。')
    if storage is None:
        from .model_jobs import storage_dir
        storage=storage_dir()
    storage=Path(storage);result={'batch':bundle['batch'],'apply':apply,'created':[],'pending':[],'skipped':[],'conflicts':[]}
    # Preflight identifiers and file contents before any changes; do not take ownership of colliding content.
    for row in bundle['entries']:
        existing=db.get(TeachingCase,row['id'])
        if existing:
            versions=db.scalars(select(CaseVersion).where(CaseVersion.case_id==row['id']).order_by(CaseVersion.number.desc())).all()
            result['skipped'].append({'id':row['id'],'reason':'已有资源/教师修改/历史版本均不覆盖','currentVersion':versions[0].id if versions else None});continue
        suffix=row['id'][4:]
        for model,ident in [(FileAsset,'resfile-'+suffix),(SourceMaterial,'resmat-'+suffix),(MaterialUnit,'resunit-'+suffix)]:
            if db.get(model,ident):result['conflicts'].append(ident)
        path=storage/'curated'/(row['id']+'.txt')
        if path.exists() and path.read_text()!=summary_text(row,sources[row['sourceId']]):result['conflicts'].append(str(path))
    if result['conflicts']:raise ValueError('资源标识或生成摘要文件存在冲突；未写入数据库。')
    skipped={x['id'] for x in result['skipped']}
    for row in bundle['entries']:
        if row['id'] in skipped:continue
        source=sources[row['sourceId']];accepted=bool(reviewed(row,source,review));entry={'id':row['id'],'subject':row['subject'],'grade':row['grade'],'sourceId':source['id'],'humanReviewed':accepted}
        result['created' if accepted else 'pending'].append(entry)
        if not apply:continue
        suffix=row['id'][4:];text=summary_text(row,source);key='curated/'+row['id']+'.txt';path=storage/key
        path.parent.mkdir(parents=True,exist_ok=True)
        if not path.exists():
            with path.open('x') as file:file.write(text)
        fileid='resfile-'+suffix;material='resmat-'+suffix;unit='resunit-'+suffix
        db.add(FileAsset(id=fileid,owner_id=actor_id,original_name=row['topic']+'-中文方法摘要.txt',content_type='text/plain; charset=utf-8',size=len(text.encode()),storage_key=key));db.flush()
        rights={'sourceLicense':source['license'],'reuseMode':source['reuseMode'],'localUsage':'仅本地教学方法摘要；用户单人复核','originalRedistributionApproved':False,'thirdPartyMediaIncluded':False,'sourceAuthor':source['author'],'sourceTitle':source['title'],'sourceUrl':source['url']}
        db.add(SourceMaterial(id=material,owner_id=actor_id,file_id=fileid,title=row['topic']+'（中文整理摘要，非原文）',metadata_json={'author':source['author'],'sourceUrl':source['url'],'sourceNote':'项目中文方法摘要，非来源原文；不含原课件、视频或图像。','subject':row['subject'],'grade':row['grade'],'curatedSummary':True,'rights':rights}));db.flush()
        db.add(MaterialUnit(id=unit,material_id=material,position=1,label='中文方法摘要（非来源原文）',kind='text',text=text,original_text=text,details={'curatedSummary':True,'sourceUrl':source['url'],'rights':rights}));db.flush()
        kp=db.get(KnowledgePoint,row['knowledgeId'])
        if kp and kp.name!=row['topic']:raise ValueError('知识点ID冲突，未覆盖旧知识点。')
        if not kp:db.add(KnowledgePoint(id=row['knowledgeId'],name=row['topic'],aliases=[row['topic']],prerequisites=[]));db.flush()
        links=[row['knowledgeId']]
        # Link exact existing topic names, without rewriting any old course or knowledge point.
        links+=list(db.scalars(select(KnowledgePoint.id).where(KnowledgePoint.name==row['topic'],KnowledgePoint.id!=row['knowledgeId'])).all())
        scope={**copy.deepcopy(row['applicability']),'knowledgeIds':links}
        p=provenance({'provenance':{'kind':'public' if accepted else 'ai_candidate','author':source['author'],'evidence':source['url']+'；'+row['sourceClaims'],'authorization':'internal' if accepted else 'unknown','authorizationEvidence':review.get('evidence','')+'；只确认项目中文方法摘要的本地使用，不代表取得原材料再分发许可。' if accepted else ''}})
        data={'title':row['title'],'content':text,'grade':row['grade'],'subject':row['subject'],'source':source['institution'],'author':source['author'],'knowledgeIds':links,'knowledgeLinks':[{'id':k,'name':row['topic']} for k in links],'experience':copy.deepcopy(row['experience']),'provenance':p,'applicability':scope,'resourceRights':rights,'curatedImport':{'batch':bundle['batch'],'resourceSha256':digest(row),'sourceSha256':digest(source),'sourceId':source['id']},'references':[{'unitId':unit,'materialId':material,'materialTitle':row['topic']+'（中文整理摘要）','label':'中文方法摘要（非来源原文）','field':'content','quote':text[:1000],'quoteKind':'adapted_summary','author':source['author'],'sourceUrl':source['url']}]}
        if accepted:data['experienceReview']={'reviewerId':actor_id,'reviewedAt':review['reviewedAt'],'provenance':p,'applicability':copy.deepcopy(scope),'humanReview':{'reviewer':review['reviewer'],'method':'AI辅助整理、用户单人复核','evidence':review['evidence'],'allowedUsage':'local_summary_only'}}
        validate_experience(data)
        db.add(TeachingCase(id=row['id'],title=row['title'],content=text,source=source['institution'],status='published' if accepted else 'draft'));db.flush()
        if accepted:db.add(CaseVersion(id='resver-'+suffix,case_id=row['id'],number=1,data=data))
        else:db.add(CaseDraftContent(case_id=row['id'],data=data,reviewed=False))
    db.flush();return result

def coverage(db):
    """Actual published-library counts and existing ModelJob fallback records; no new store."""
    from .education import catalog
    from .library import current_case
    from .models import ModelJob
    documents=[current_case(db,c.id) for c in db.scalars(select(TeachingCase).where(TeachingCase.status=='published')).all()]
    docs=[d for d in documents if d and d.get('curatedImport',{}).get('batch')=='resources-20261114-v1']
    rows=[]
    for subject in catalog()['subjects']:
        values=[d for d in docs if d['subject']==subject['value']]
        rows.append({'subject':subject['value'],'publishedSummaries':len(values),'sourceVerified':sum(d['provenance']['kind']=='public' for d in values),'explicitSourceLicense':sum(d['resourceRights']['sourceLicense'] in ('CC-BY-SA-4.0','CC-BY-NC-SA-4.0') for d in values),'humanReviewed':sum(bool(d.get('experienceReview',{}).get('humanReview')) for d in values),'studentEligible':len(values),'teacherEligible':len(values)})
    gaps=[]
    # Sort narrow identifiers first: MySQL filesort must not carry large model JSON blobs.
    recent_ids=db.scalars(select(ModelJob.id).where(ModelJob.capability.in_(['text','lesson_agent'])).order_by(ModelJob.created_at.desc(),ModelJob.id.desc()).limit(200)).all()
    for job_id in recent_ids:
        job=db.get(ModelJob,job_id)
        ctx=job.input.get('context') or {};decision=(job.result or {}).get('experienceDecision') or ctx.get('experienceDecision') or {}
        if decision.get('fallback'):
            lesson=ctx.get('lesson') or ctx or job.input.get('lesson') or {}
            gaps.append({'jobId':job.id,'subject':lesson.get('subject',''),'grade':lesson.get('grade',''),'query':str(job.input.get('prompt') or job.input.get('task') or '')[:180],'reason':decision.get('notice',''),'createdAt':job.created_at.isoformat()})
    drafts=db.scalars(select(CaseDraftContent)).all()
    return {'batch':'resources-20261114-v1','subjects':rows,'summary':{'catalogSubjects':len(rows),'coveredSubjects':sum(r['publishedSummaries']>=3 for r in rows),'publishedSummaries':len(docs),'uniqueSources':len({d['curatedImport']['sourceId'] for d in docs}),'teamAuthored':sum(d['provenance']['kind']=='team' for d in docs),'aiCandidates':sum((d.data.get('curatedImport',{}).get('batch')=='resources-20261114-v1' and d.data.get('provenance',{}).get('kind')=='ai_candidate') for d in drafts),'unverified':sum(not d.get('experienceReview') for d in docs),'scope':'仅统计本批导入资源；可用表示通过来源/适用条件规则，不代表教学效果已验证。'},'recentGaps':gaps,'gapScope':'最近200条指导与备课任务内的无匹配记录；不是全部历史统计。'}
