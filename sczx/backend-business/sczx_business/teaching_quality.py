"""Explainable warnings; never mutate teacher text or mathematical content."""
import re,unicodedata
from collections import Counter
META_PHRASES=('教师手写保留','沿用原来的内容','保留例题','沿用例题','根据用户要求生成','本次生成','模型建议如下','根据当前任务上下文','原始活动保持不变','不增加新题ID','请在平台继续操作','本模块通过核验','Agent已完成','以下内容可供参考')
FILLER=('引导学生','进一步帮助学生','从而培养学生','使学生深入理解','让学生充分认识到','在此基础上','学生可能回答','教师进一步追问','提高学生的综合能力')
# Explicit prefixes only, shown to the teacher before a one-off export cleanup.
PREFIX_RE=re.compile(r'(?m)^(\s*)(教师手写保留|保留例题|模型建议如下|以下内容可供参考)[：:]\s*')
def normalized(text):return re.sub(r'\s+','',unicodedata.normalize('NFKC',str(text or '')))
def editorial_marks(data):
    items=[]
    for path,text in [('goal',data.get('goal','')),('studentBase',data.get('studentBase','')),*[(f'blocks.{i}.{key}',b.get(key,'')) for i,b in enumerate(data.get('blocks',[])) for key in ('title','content','teacherQuestion','studentTask','studentResponse','adjustment')]]:
        found=[p for p in META_PHRASES if p in text]
        if found:items.append({'field':path,'phrases':found,'text':text})
    return items

def cleaned_copy(data):
    import copy
    result=copy.deepcopy(data)
    def clean(text):return re.sub(r'(?m)^(\s*)沿用例题',r'\1例题',PREFIX_RE.sub(r'\1',str(text)))
    for key in ('goal','studentBase'):result[key]=clean(result.get(key,''))
    for block in result.get('blocks',[]):
        for key in ('title','content','teacherQuestion','studentTask','studentResponse','adjustment'):
            if key in block:block[key]=clean(block[key])
    return result

def review_plan(plan,target=None):
    warnings=[];seen_titles={};seen_paragraphs={};seen_sentences={}
    def add(code,field,text,message,origin='generated'):
        warnings.append({'code':code,'field':field,'excerpt':text[:180],'message':message,'origin':origin})
    if not target:
        for phrase in META_PHRASES:
            if phrase in plan.get('goal',''):add('editorial','goal',phrase,'目标中含生成或编辑过程用语')
    for b in plan.get('blocks',[]):
        origin='generated' if not target or b['id']==target else 'existing'
        title=normalized(b['title'])
        if title in seen_titles:add('duplicate_title',b['id'],b['title'],'活动标题重复',origin)
        seen_titles[title]=b['id']
        text='\n'.join(str(b.get(k,'')) for k in ('content','teacherQuestion','studentTask','studentResponse','adjustment'))
        for phrase in META_PHRASES:
            if phrase in text:add('editorial',b['id'],phrase,'含编辑或系统过程用语，请核对后再采用',origin)
        para=normalized(b['content'])
        if len(para)>24 and para in seen_paragraphs:add('duplicate_paragraph',b['id'],b['content'],'与另一活动内容重复',origin)
        seen_paragraphs[para]=b['id']
        sentences=[normalized(s) for s in re.split('[。！？\n]',b['content']) if len(normalized(s))>=12]
        for i,sentence in enumerate(sentences):
            if (i and sentence==sentences[i-1]) or sentence in seen_sentences:add('repeated_sentence',b['id'],sentence,'教学句子重复，请检查是否有必要',origin)
            seen_sentences[sentence]=b['id']
        repeated=sum(text.count(p) for p in FILLER)
        concrete=bool(re.search(r'出示|计算|写出|圈出|比较|解释|列出|观察|操作|提问|说出|独立|代入|验算|\d|[=？?]',text))
        if repeated>=4 or (not concrete and (repeated or re.search(r'理解|认识|思考|掌握|感受|体会',text))):add('vague_language',b['id'],b['content'],'套话偏多或缺少可执行活动',origin)
        if re.search(r'同除|同时除以|两边.{0,8}除以',text) and not re.search(r'非零|不为.?0|不等于.?0|≠\s*0|不能为零|不得为零|不能是零',text) and not re.search(r'除以\s*[-−]?[1-9]',text):add('division_condition',b['id'],b['content'],'出现同除表述，核对除数非零条件',origin)
    return {'status':'review' if warnings else 'passed','warnings':warnings,'scope':'文本规则仅提示元话语、重复与条件风险，不代替数学及课堂适用性审查'}
