"""Evidence-aware policy over existing CaseVersion JSON and tutoring context; no new store."""
import copy
from pydantic import BaseModel, Field
from typing import Literal

class Provenance(BaseModel):
    kind: Literal['unknown','teacher','public','team','ai_candidate']='unknown'
    author: str=Field(default='',max_length=160)
    evidence: str=Field(default='',max_length=2000)
    authorization: Literal['unknown','internal','redistribution_confirmed']='unknown'
    authorizationEvidence: str=Field(default='',max_length=2000)

def provenance(data):
    try:return Provenance.model_validate(data.get('provenance') or {}).model_dump()
    except (ValueError,TypeError):return Provenance().model_dump()

def validate_experience(data):
    p=Provenance.model_validate(data.get('provenance') or {}).model_dump()
    experience=data.get('experience') or {}
    if not isinstance(experience,dict):raise ValueError('教学经验格式无效。')
    for key in ('diagnosis','strategy','effectCheck'):
        if key in experience and (not isinstance(experience[key],str) or len(experience[key])>6000):raise ValueError('诊断、教法和效果检查须为6000字以内文本。')
    if p['kind']=='teacher' and (not p['author'].strip() or not p['evidence'].strip()):raise ValueError('真实教师经验须填写作者与教师确认依据。')
    if p['authorization']!='unknown' and not p['authorizationEvidence'].strip():raise ValueError('请填写授权或使用许可依据，公开可见不等于取得授权。')
    return p

def diagnose(subject, prompt, answer='', reason='', memory=None, evidence_id='current', dimensions=None):
    memory=copy.deepcopy(memory or [])[:6]
    observations=[]
    if str(answer).strip():observations.append({'id':evidence_id,'kind':'原始作答','text':str(answer)[:1200]})
    if str(reason).strip():observations.append({'id':evidence_id+':reason','kind':'作答说明','text':str(reason)[:1200]})
    if prompt:observations.append({'id':evidence_id+':request','kind':'学生自述','text':str(prompt)[:2000]})
    independent=[x for x in memory if not x.get('helped') and x.get('verification') in ('verified','verified_correct','verified_incorrect') and x.get('outcome') in ('independent_incorrect','independent_correct','retest_failed','retest_passed')]
    unsuccessful=sum(x.get('outcome') in ('independent_incorrect','retest_failed') for x in independent)
    strategy='foundation' if unsuccessful>=2 else 'hint'
    if any(x in str(prompt) for x in ('换个','换种','另一种','换一种')):strategy='rephrase'
    elif any(x in str(prompt) for x in ('举例','例子')):strategy='example'
    return {'schema':1,'subject':subject,'dimensions':dimensions or ['理解任务','说明依据','独立应用'],
        'observations':observations,'historyEvidence':memory,'evidenceSufficiency':'有重复独立困难记录' if unsuccessful>=2 else '需进一步确认',
        'difficulty':'学生报告当前学习遇到困难','possibleCauses':[],
        'confirmationQuestion':'请指出你从哪一步开始不确定，并说明刚才是怎么想的。',
        'recommendedStrategy':strategy,'reason':'近期至少两条未获帮助的困难记录，先检查前置知识。' if unsuccessful>=2 else '尚不能根据一次作答判断原因，先给提示并追问。'}

def match_experiences(candidates,diagnosis,subject='',grade='',knowledge_ids=None,context_text=''):
    from .retrieval import tokenize
    selected=[];rejected=[]
    terms=set(tokenize(' '.join(x['text'] for x in diagnosis['observations'])))
    for doc in candidates:
        p=provenance(doc);exp=doc.get('experience') or {};reasons=[]
        if not subject or not grade or not knowledge_ids:reasons.append('当前学科、年级或知识关联尚未明确')
        if subject and doc.get('subject')!=subject:reasons.append('学科不匹配或未标注')
        if grade and doc.get('grade')!=grade:reasons.append('年级不匹配或未标注')
        if knowledge_ids and not set(knowledge_ids).intersection(doc.get('knowledgeIds') or []):reasons.append('知识点未明确关联')
        if p['kind'] in ('unknown','ai_candidate'):reasons.append('来源尚未确认或为AI候选')
        review=doc.get('experienceReview') or {}
        if not review.get('reviewerId') or review.get('provenance')!=p:reasons.append('未经过经验来源审核或来源已变更')
        if p['authorization']=='unknown' or not p['authorizationEvidence']:reasons.append('使用许可待确认')
        if not (exp.get('strategy') or exp.get('steps')):reasons.append('没有可执行教法')
        # Only a reviewed, exact subject/grade/knowledge scope can resolve this kind of boundary.
        scope=doc.get('applicability') or {}
        scope_matches=(scope.get('kind')=='knowledge_scope' and scope.get('schema')==1
            and scope.get('subject')==subject and scope.get('grade')==grade
            and bool(set(knowledge_ids or []).intersection(scope.get('knowledgeIds') or []))
            and scope==review.get('applicability') and not scope.get('requirements'))
        matched=sorted(terms.intersection(tokenize(str(exp.get('difficulty',''))+' '+str(exp.get('diagnosis','')))))
        if not matched and not scope_matches:reasons.append('当前自述与困难及诊断字段没有明确词项匹配，需补充信息')
        if exp.get('boundary') and not exp.get('diagnosis'):reasons.append('适用边界存在但缺少诊断依据，需教师确认')
        if reasons:rejected.append({'versionId':doc.get('versionId'),'reasons':reasons});continue
        if exp.get('boundary') and not scope_matches:
            rejected.append({'versionId':doc.get('versionId'),'reasons':['适用边界需教师确认'],'conditions':[exp['boundary']]});continue
        diagnostic_only=not matched
        selected.append({'id':doc.get('id'),'versionId':doc.get('versionId'),'version':doc.get('version'),
            'strategy':diagnosis['recommendedStrategy'],'diagnosticOnly':diagnostic_only,'teachingMethod':exp.get('strategy'),'method':('先用诊断任务确认困难：'+exp.get('diagnosis','请说明当前做法')) if diagnostic_only else exp.get('strategy') or ('；'.join(exp['steps']) if isinstance(exp.get('steps'),list) else exp.get('steps')),
            'reason':'本题知识点与已复核适用范围一致，但困难尚未确认；先使用该资源的诊断任务，不直接推断错因。' if diagnostic_only else '学科、年级、知识点与已审核来源符合；教法作为候选应用，不推断学生认知原因。',
            'evidenceIds':[x['id'] for x in diagnosis['observations']]+[x.get('evidenceId') for x in diagnosis['historyEvidence'] if x.get('evidenceId')],
            'provenance':p,'conditions':[exp['boundary']] if exp.get('boundary') else [],'matchedDifficultyTerms':matched,'diagnosticBasis':exp.get('diagnosis',''),'effectCheck':exp.get('effectCheck','')})
    return {'schema':1,'selected':selected[:3],'rejected':rejected,'fallback':not selected,
        'notice':'当前没有匹配到来源与适用条件均已核对的教学经验，使用通用AI指导。' if not selected else '参考已审核教学经验，效果仍需独立练习与教师反馈验证。'}
