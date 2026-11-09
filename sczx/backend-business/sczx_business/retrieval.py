"""小规模教学案例的 BM25 检索；中文二元组，无向量和模型依赖。"""
from collections import Counter
import math
import re
import unicodedata


def tokenize(text):
    text = unicodedata.normalize('NFKC', str(text)).lower()
    tokens = []
    for part in re.findall(r'[\u3400-\u9fff]+|[a-z]+|\d+(?:\.\d+)?|[=+*/^<>-]', text):
        if re.fullmatch(r'[\u3400-\u9fff]+', part):
            tokens.extend(part[i:i + 2] for i in range(len(part) - 1))
            if len(part) == 1: tokens.append(part)
        else:
            tokens.append(part)
    return tokens


def legacy_search(query, documents, limit=8):
    """返回正分匹配；空查询、空库和零匹配不返回占位案例。"""
    terms = set(tokenize(query))
    if not terms or not documents: return []
    counts = [Counter(tokenize(f"{d.get('title', '')} {d.get('title', '')} {d.get('content', '')} {d.get('retrievalText', '')}")) for d in documents]
    lengths = [sum(count.values()) for count in counts]
    average = sum(lengths) / len(lengths) or 1
    frequencies = {term: sum(term in count for count in counts) for term in terms}
    ranked = []
    for document, count, length in zip(documents, counts, lengths):
        score = 0.0
        for term in terms:
            frequency = count.get(term, 0)
            if not frequency: continue
            inverse = math.log1p((len(documents) - frequencies[term] + .5) / (frequencies[term] + .5))
            score += inverse * frequency * 2.5 / (frequency + 1.5 * (.25 + .75 * length / average))
        if score > 0:
            ranked.append({**document, 'score': round(score, 6), 'bm25Score': round(score, 6)})
    return sorted(ranked, key=lambda item: (-item['score'], str(item['id'])))[:limit]


def published_documents(db):
    from sqlalchemy import select
    from .models import TeachingCase
    from .library import current_case
    import json
    results = []
    for case in db.scalars(select(TeachingCase).where(TeachingCase.status == 'published').order_by(TeachingCase.id)).all():
        data = current_case(db, case.id)
        if data: results.append({**data, 'retrievalText': json.dumps(data.get('experience', {}), ensure_ascii=False)})
    return results


ALGORITHM_VERSION = 'teaching-context-v1'
FIELD_WEIGHTS = {'title':2.0,'knowledgePoints':2.5,'difficulty':2.0,'goal':1.6,'studentBase':1.4,'introduction':1.2,'content':1.0,'steps':.9,'questions':.9,'responses':.9,'adjustment':.8,'boundary':.7,'suggestions':.2,'references':.4}
FIELD_LABELS = {'title':'标题','knowledgePoints':'知识点','difficulty':'学生困难','goal':'教学目标','studentBase':'学生基础','introduction':'引入方法','content':'正文','steps':'讲解步骤','questions':'教师提问','responses':'学生回应','adjustment':'回应调整','boundary':'适用边界','suggestions':'模型建议','references':'原文摘录'}
SCENARIOS = {'concept_explanation':'概念讲解','misconception_correction':'认知纠正','activity_design':'活动设计','questioning':'提问设计','assessment':'理解检查','differentiated_support':'补充支持','other':'其他'}
SCENARIO_RULES = {'misconception_correction':('只改变','变号','误解','错误','机械记忆'),'activity_design':('活动','天平','演示','直观','操作'),'assessment':('检查','判断是否','掌握','测验','独立'),'questioning':('提问','追问','设问'),'differentiated_support':('补基础','基础薄弱','分层','前置'),'concept_explanation':('为什么','理解','概念','讲解','原因')}
SCENARIO_FIELDS = {'concept_explanation':('knowledgePoints','goal','introduction'),'misconception_correction':('difficulty','studentBase','responses','adjustment'),'activity_design':('introduction','steps','questions'),'assessment':('questions','responses','boundary'),'questioning':('questions','responses'),'differentiated_support':('studentBase','adjustment','boundary')}


def normalize(value):
    return re.sub(r'\s+',' ',unicodedata.normalize('NFKC',str(value or '')).lower()).translate(str.maketrans({'−':'-','×':'*','÷':'/'})).strip()


def normalize_grade(value):
    value=normalize(value)
    aliases={'初一':'7','初二':'8','初三':'9','高一':'10','高二':'11','高三':'12'}
    if value in aliases:return aliases[value]
    match=re.fullmatch(r'(?:小学|初中)?([一二三四五六七八九十]+|\d+)年级(?:数学|语文|英语)?',value)
    if match:
        numeral=match[1]
        grade={'一':'1','二':'2','三':'3','四':'4','五':'5','六':'6','七':'7','八':'8','九':'9','十':'10','十一':'11','十二':'12'}.get(numeral,numeral)
        return grade if grade.isdigit() and 1<=int(grade)<=12 else ''
    return value if value.isdigit() and 1<=int(value)<=12 else ''


def knowledge_documents(db):
    from sqlalchemy import select
    from .models import KnowledgePoint
    return [{'id':p.id,'name':p.name,'aliases':p.aliases or [],'prerequisites':p.prerequisites or []} for p in db.scalars(select(KnowledgePoint).order_by(KnowledgePoint.id)).all()]


def validate_request(request, points):
    from .ai_schemas import RetrievalRequest
    request=RetrievalRequest.model_validate(request).model_dump()
    existing={p['id'] for p in points}
    for group,key in [(request['filters'],'knowledgeIds'),(request['context'],'knowledgeIds'),(request['context'],'prerequisiteIds')]:
        values=group[key]
        if len(values)!=len(set(values)) or any(v not in existing for v in values):raise ValueError('知识点ID不存在或重复，请重新选择。')
    if request['filters']['grade'] and not normalize_grade(request['filters']['grade']):raise ValueError('请选择有效的年级。')
    request['query']=request['query'].strip()
    return request


def identify_knowledge(text, points, aliases=True):
    text=normalize(text);matches=[]
    for point in points:
        terms=[point['name'],*(point.get('aliases',[]) if aliases else [])]
        hits=[term for term in terms if normalize(term) and normalize(term) in text]
        if hits:matches.append({'id':point['id'],'name':point['name'],'matchedNames':hits,'source':'name' if point['name'] in hits else 'alias'})
    return matches


def fields_for(document, points):
    experience=document.get('experience') or {};confirmed=set(document.get('knowledgeIds') or [])
    def as_text(value):
        if isinstance(value,list):return '\n'.join(str(v) for v in value if isinstance(v,(str,int,float)))
        return str(value or '') if not isinstance(value,dict) else ''
    fields={key:as_text(experience.get(key,''))[:12000] for key in FIELD_WEIGHTS}
    fields['title']=str(document.get('title',''))[:1000];fields['content']=str(document.get('content',''))[:20000]
    names=[p['name']+' '+ ' '.join(p.get('aliases',[])) for p in points if p['id'] in confirmed]
    fields['knowledgePoints']+='\n'+'\n'.join(names)
    # One excerpt per distinct quote, never multiply identical evidence by field references.
    quotes=dict.fromkeys(str(r.get('quote',''))[:1200] for r in document.get('references',[]) if r.get('quote'))
    fields['references']='\n'.join(quotes)[:4800]
    return fields


def _field_bm25(terms, counters):
    if not counters:return []
    lengths=[sum(c.values()) for c in counters];average=sum(lengths)/len(counters) or 1
    idf={t:math.log1p((len(counters)-sum(t in c for c in counters)+.5)/(sum(t in c for c in counters)+.5)) for t in terms}
    return [sum(idf[t]*c.get(t,0)*2.5/(c.get(t,0)+1.5*(.25+.75*length/average)) for t in terms if c.get(t,0)) for c,length in zip(counters,lengths)]


def retrieve(spec, documents, points=None, variant='B3'):
    """Pure ranking over an immutable input corpus; no network or database writes."""
    import time
    start=time.perf_counter();points=points or [];spec=validate_request(spec,points)
    query=spec['query'];filters=spec['filters'];context=spec['context'];expanded=variant in ('B3','B4');knowledge_enabled=variant in ('B2','B3','B4')
    identified=identify_knowledge(query,points,aliases=expanded) if knowledge_enabled else []
    explicit=set(filters['knowledgeIds']);targets=explicit or {p['id'] for p in identified} or (set(context['knowledgeIds']) if expanded else set())
    by_id={p['id']:p for p in points};previous=set()
    if spec['includePrerequisites'] and knowledge_enabled:
        previous={v for ident in targets for v in by_id.get(ident,{}).get('prerequisites',[])}
        if expanded:previous.update(context['prerequisiteIds'])
    previous-=targets
    scenario=filters['scenario']
    if scenario=='other' and expanded:
        scenario=next((key for key,words in SCENARIO_RULES.items() if any(w in query for w in words)),'other')
    eligible=[]
    for doc in documents:
        if filters['grade'] and normalize_grade(doc.get('grade'))!=normalize_grade(filters['grade']):continue
        if filters['subject'] and normalize(doc.get('subject'))!=normalize(filters['subject']):continue
        if explicit and not (set(doc.get('knowledgeIds') or []) & (explicit|previous)):continue
        eligible.append(doc)
    browse=not query and not any(filters[k] for k in ('grade','subject','knowledgeIds')) and filters['scenario']=='other' and not any(context.values())
    understanding={'normalizedQuery':normalize(query),'knowledge':identified,'scenario':scenario,'expansions':[]}
    warnings=[]
    # A shared alias is ambiguous: retain candidates, but do not silently choose one target.
    alias_to_ids={}
    for hit in identified:
        for name in hit['matchedNames']:alias_to_ids.setdefault(normalize(name),[]).append(hit['id'])
    if any(len(ids)>1 for ids in alias_to_ids.values()):warnings.append('知识点名称或别名存在歧义，请选择明确知识点。')
    if browse:
        ranked=sorted(eligible,key=lambda d:(str(d.get('title','')),d['id']))
        items=[{**d,'score':0,'bm25Score':0,'matchedFields':[],'knowledgeMatches':[],'matchReasons':[]} for d in ranked]
    elif variant=='B0':items=legacy_search(query,eligible,20)
    else:
        terms=set(tokenize(normalize(query)))
        if expanded:
            for hit in identified:
                terms.update(tokenize(hit['name']));understanding['expansions'].append({'text':hit['name'],'source':hit['source'],'knowledgeId':hit['id']})
        assist={}
        if expanded:
            for key,weight in [('recognizedText',.55),('questionText',.4),('equation',.15),('studentObservation',.45),('goal',.25)]:
                assist[key]=(set(tokenize(context[key])),weight)
        fields=[fields_for(d,points if knowledge_enabled else []) for d in eligible]
        contributions=[[] for _ in eligible]
        raw_query_fields=[set() for _ in eligible]
        generic=set(tokenize('如何 怎么 怎样 讲解 学生 理解 教学 案例 方法 为什么 这题 怎么做 帮我 不懂 不会 请问'))
        anchors=terms-generic
        generic_query=not re.sub(r'(为什么要这样做|这是什么意思|能帮我看看吗|请再讲一遍|要怎么解|怎么解|怎么求|哪里错了|哪一步错了|这道题|这题|这一题|怎么做|怎么办|为什么|怎么理解|什么意思|不明白|不懂|不会|帮我|请问|我|呢|呀|啊|[\s?？。！!])','',normalize(query))
        for field,weight in FIELD_WEIGHTS.items():
            counters=[Counter(tokenize(values[field])) for values in fields]
            scores=_field_bm25(terms,counters)
            if expanded and field in SCENARIO_FIELDS.get(scenario,()):weight*=1.35
            for index,(score,counter) in enumerate(zip(scores,counters)):
                matching=terms&counter.keys();raw_query_fields[index].update(anchors&counter.keys())
                auxiliary=0
                for assist_terms,boost in assist.values():
                    if assist_terms:
                        overlap=len(assist_terms&counter.keys())/len(assist_terms)
                        auxiliary+=boost*overlap
                value=weight*(score/(1+score)+.25*auxiliary)
                if value:contributions[index].append({'field':field,'label':FIELD_LABELS[field],'score':round(value,6),'bm25':round(score,6),'matchedTerms':sorted(matching)[:16],'contextMatched':auxiliary>0})
        items=[]
        for index,document in enumerate(eligible):
            confirmed=set(document.get('knowledgeIds') or []);direct=confirmed&targets if knowledge_enabled else set();prerequisite=confirmed&previous if knowledge_enabled else set()
            literal=bool(raw_query_fields[index]) or (not anchors and bool(terms) and any(v['bm25']>0 for v in contributions[index]))
            if query and not literal and not ((direct or prerequisite) and identified) and not (generic_query and (direct or any(v['contextMatched'] for v in contributions[index]))):continue
            if not query and not explicit and not any(context.values()) and scenario=='other' and not any(filters.values()):continue
            text_score=sum(v['score'] for v in contributions[index]);knowledge_score=.45*bool(direct)+.16*bool(prerequisite)
            if not query and not targets and not any(context.values()):
                # Filter-only browsing is honest browsing; the scenario only selects field emphasis.
                text_score=0
            contextual=.08*bool(context['grade'] and normalize_grade(context['grade']) and normalize_grade(context['grade'])==normalize_grade(document.get('grade')))+.04*bool(context['subject'] and normalize(context['subject'])==normalize(document.get('subject'))) if expanded else 0
            if query and text_score<=0 and knowledge_score<=0:continue
            knowledge_matches=[{'id':ident,'name':by_id[ident]['name'],'relation':'direct' if ident in direct else 'prerequisite'} for ident in sorted(direct|prerequisite) if ident in by_id]
            reasons=[]
            if direct:reasons.append('直接关联目标知识点')
            if prerequisite:reasons.append('关联一层前置知识')
            evidence=[v for v in contributions[index] if v['bm25']>0]
            if evidence:reasons.append('匹配'+ '、'.join(v['label'] for v in sorted(evidence,key=lambda v:-v['score'])[:3]))
            if contextual:reasons.append('与课时适用信息一致')
            score=text_score+knowledge_score+contextual
            items.append({**document,'score':round(score,6),'bm25Score':round(sum(v['bm25'] for v in contributions[index]),6),'textScore':round(text_score,6),'knowledgeScore':round(knowledge_score,6),'contextScore':round(contextual,6),'matchedFields':contributions[index],'knowledgeMatches':knowledge_matches,'matchReasons':reasons})
        items.sort(key=lambda d:(-d['score'],str(d['id'])))
    return {'query':query,'mode':'browse' if browse or not query else 'search','method':'field-bm25+knowledge+context','algorithmVersion':ALGORITHM_VERSION,'variant':variant,'queryUnderstanding':understanding,'warnings':warnings,'items':items[:spec['limit']],'candidateItems':items[:20],'totalDocuments':len(documents),'eligibleDocuments':len(eligible),'matchedCount':len(items),'rerankApplied':False,'elapsedMs':round((time.perf_counter()-start)*1000,3)}


def search(query,documents,limit=8):
    """Compatibility adapter; structured callers pass the knowledge catalog to retrieve."""
    return retrieve({'query':query,'limit':limit},documents)['items']


def student_request(snapshot, question, observation, prompt, recognized=''):
    version=snapshot.get('lessonSnapshot') or {};question=question or {}
    text=lambda value,limit:str(value or '')[:limit]
    return {'query':text(prompt,2000),'context':{
        'grade':text(version.get('grade'),40), 'subject':text(version.get('subject'),80),
        'knowledgeIds':(question.get('knowledgeIds') or version.get('knowledgeIds') or [])[:16],
        'prerequisiteIds':(version.get('prerequisiteIds') or [])[:32],
        'goal':text(snapshot.get('goal') or version.get('goal'),2000),
        'questionText':text(question.get('prompt'),3000), 'equation':text(question.get('equation'),1000),
        'studentObservation':text(observation,4000), 'recognizedText':text(recognized,12000)},'limit':3}
