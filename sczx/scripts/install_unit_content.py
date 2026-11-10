"""Install the reviewed unit using existing curriculum APIs, preserving existing edits.
Credentials are supplied by a local env/private file, never command arguments.
"""
import copy,hashlib,json
from pathlib import Path

PACKAGE='linear-unit-20261111-v1'

def call(client,method,path,body=None):
    r=client.request(method,'/api'+path,json=body)
    if not r.is_success:raise RuntimeError(path+': '+r.text)
    return r.json()

def install(client,bundle,approval,case_ids=None):
    if approval.get('answer')!='已阅读，认可五课与条件预期':raise RuntimeError('内容未获人工认可，不发布')
    approved=Path(__file__).resolve().parents[1]/approval.get('contentFile','')
    if not approved.is_file() or hashlib.sha256(approved.read_bytes()).hexdigest()!=approval.get('sha256') or json.loads(approved.read_text())!=bundle:raise RuntimeError('内容与人工复核版本不一致，不发布')
    points=call(client,'GET','/curriculum/knowledge');known={p['id'] for p in points}
    points+=[copy.deepcopy(p) for p in bundle['knowledge'] if p['id'] not in known]
    call(client,'PUT','/curriculum/knowledge',{'points':points})
    catalog=call(client,'GET','/curriculum/courses');course=next(c for c in catalog if any(u['id']==bundle['unitId'] for u in c['units']));unit=next(u for u in course['units'] if u['id']==bundle['unitId']);by_id={l['id']:l for l in unit['lessons']};mapping={};actions=[]
    for position,item in enumerate(bundle['lessons'],1):
        canonical=item['id'];existing=by_id.get(canonical) or next((l for l in by_id.values() if ((l.get('published') or l.get('draft') or {}).get('contentPackage') or {}).get('sourceId')==canonical),None)
        if existing and existing.get('published'):
            mapping[canonical]=existing['id'];actions.append({'sourceId':canonical,'lessonId':existing['id'],'action':'preserved_published','versionId':existing['published']['versionId']});continue
        if existing:
            draft=existing.get('draft') or {}
            expected=copy.deepcopy(item['data']);expected.pop('authorship',None);expected.pop('source',None)
            original=copy.deepcopy(draft);original.pop('source',None)
            unchanged_seed=canonical=='lesson-equation' and original==expected and draft.get('source')=='项目自编首课；教学示例，未经真实教师试用'
            if (draft.get('blocks') or draft.get('questions') or draft.get('goal')) and not unchanged_seed:raise RuntimeError('保留已有非空草稿，需人工整合：'+existing['id'])
        else:
            existing=call(client,'POST','/curriculum/lessons',{'unitId':bundle['unitId'],'title':item['data']['title'],'position':position})
        ident=existing['id'];mapping[canonical]=ident;data=copy.deepcopy(item['data']);data['contentPackage']={'id':PACKAGE,'sourceId':canonical,'approvedSha256':approval['sha256']};data['authorship']={**data.get('authorship',{}),'humanReview':approval['provenance'],'reviewDate':approval['date']}
        if case_ids:
            selected=case_ids.get('application' if canonical=='lesson-application' else 'equality');data['caseId']=selected['id'];data['caseVersionId']=selected['versionId']
        call(client,'PUT','/curriculum/lessons/'+ident,{'data':data,'position':position});call(client,'POST','/curriculum/lessons/'+ident+'/verify');call(client,'POST','/curriculum/lessons/'+ident+'/review');published=call(client,'POST','/curriculum/lessons/'+ident+'/publish');actions.append({'sourceId':canonical,'lessonId':ident,'action':'reviewed_and_published','versionId':published['published']['versionId']})
    metadata=copy.deepcopy(course.get('metadata') or {});metadata.setdefault('unitPlans',{})[bundle['unitId']]=[mapping[i] for i in bundle['lessonOrder']]
    call(client,'PUT','/curriculum/courses/'+course['id'],{'title':course['title'],'grade':course['grade'],'metadata':metadata})
    return {'mapping':mapping,'actions':actions,'unitId':bundle['unitId'],'approval':approval,'source':'project_authored_ai_assisted'}
