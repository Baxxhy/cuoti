"""Teacher document template. Source snapshots are read-only in both modes."""
import io,re,copy
from collections import defaultdict
from docx import Document
from docx.shared import Cm,Pt,RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from .teaching_quality import normalized,cleaned_copy

def font_properties(rpr,size=None,bold=None):
    fonts=rpr.find(qn('w:rFonts'))
    if fonts is None:fonts=OxmlElement('w:rFonts');rpr.insert(0,fonts)
    for key in list(fonts.attrib):fonts.attrib.pop(key)
    for key,value in {'ascii':'Times New Roman','hAnsi':'Times New Roman','eastAsia':'宋体','cs':'Times New Roman'}.items():fonts.set(qn('w:'+key),value)
    color=rpr.find(qn('w:color'))
    if color is None:color=OxmlElement('w:color');rpr.append(color)
    color.attrib.clear();color.set(qn('w:val'),'000000')
    if size is not None:
        for tag in ('sz','szCs'):
            e=rpr.find(qn('w:'+tag))
            if e is None:e=OxmlElement('w:'+tag);rpr.append(e)
            e.set(qn('w:val'),str(round(size*2)))

def template():
    doc=Document()
    for style in doc.styles:
        # Also neutralize theme fonts and colors in latent character/table styles.
        font_properties(style.element.get_or_add_rPr())
    defaults=doc.styles.element.find(qn('w:docDefaults'))
    if defaults is not None:
        node=defaults.find(qn('w:rPrDefault'))
        if node is not None:
            rpr=node.find(qn('w:rPr'))
            if rpr is None:rpr=OxmlElement('w:rPr');node.append(rpr)
            font_properties(rpr,12)
    for name,size,bold,before,after in [('Normal',12,False,0,4),('Title',18,True,0,12),('Heading 1',14,True,12,6),('Heading 2',12,True,8,4),('Header',10.5,False,0,0),('Footer',10.5,False,0,0)]:
        s=doc.styles[name];font_properties(s.element.get_or_add_rPr(),size);s.font.bold=bold
        p=s.paragraph_format;p.line_spacing=1.35;p.space_before=Pt(before);p.space_after=Pt(after);p.first_line_indent=Pt(24 if name=='Normal' else 0);p.widow_control=True
        p.keep_with_next=name.startswith('Heading');p.keep_together=name!='Normal'
    for tag in ('pBdr','shd'):
        for node in list(doc.styles.element.iter(qn('w:'+tag))):node.getparent().remove(node)
    for sec in doc.sections:
        sec.page_width=Cm(21);sec.page_height=Cm(29.7);sec.top_margin=Cm(2.5);sec.bottom_margin=Cm(2.5);sec.left_margin=Cm(2.7);sec.right_margin=Cm(2.7)
        sec.header_distance=Cm(1.2);sec.footer_distance=Cm(1.2)
        p=sec.footer.paragraphs[0];p.alignment=WD_ALIGN_PARAGRAPH.CENTER;p.paragraph_format.first_line_indent=Pt(0)
        run=p.add_run();field=OxmlElement('w:fldSimple');field.set(qn('w:instr'),'PAGE');inner=OxmlElement('w:r');rp=OxmlElement('w:rPr');font_properties(rp,10.5);inner.append(rp);t=OxmlElement('w:t');t.text='1';inner.append(t);field.append(inner);p._p.append(field)
    return doc

def references(data):
    cases=[];seen=set()
    for c in [data.get('caseSnapshot'),*((data.get('planningDetails') or {}).get('references',[])),*data.get('agentCases',[])]:
        if c and c.get('versionId') not in seen:seen.add(c.get('versionId'));cases.append(c)
    snippets={}
    def collect(ref,case=None):
        quote=str(ref.get('quote') or ref.get('content') or '').strip()
        if not quote:return
        material=ref.get('unitId') or ref.get('materialId') or ref.get('materialTitle') or ref.get('title') or ref.get('unitId') or ''
        label=ref.get('label') or ref.get('page') or ''
        canonical=re.sub(r'^(教学目标|引入|引入方法|回应与调整|例题|独立检查|适用范围)[：:]\s*','',quote)
        key=(material,str(label),normalized(canonical))
        item=snippets.setdefault(key,{'material':ref.get('materialTitle') or ref.get('title') or '原始材料','label':str(label),'quote':quote,'versions':[]})
        version=case.get('versionId') if case else ref.get('caseVersionId')
        if version and version not in item['versions']:item['versions'].append(version)
    for c in cases:
        for ref in c.get('references',[]):collect(ref,c)
    for ref in data.get('agentSources',[]):collect(ref)
    return cases,list(snippets.values())

def build_docx(data,mode='formal',clean_editorial=False):
    if mode not in ('formal','trace'):raise ValueError('未知导出范围')
    data=cleaned_copy(data) if clean_editorial else copy.deepcopy(data)
    doc=template();lesson=data.get('lessonSnapshot') or {};details=data.get('planningDetails') or {};section_no=0
    title=doc.add_heading(lesson.get('title') or '教案',0);title.alignment=WD_ALIGN_PARAGRAPH.CENTER
    def section(label):
        nonlocal section_no
        section_no+=1;doc.add_heading('一二三四五六七八九十'[section_no-1]+'、'+label,1)
    def paragraph(text,label=None,reference=False):
        if not text:return
        for line in str(text).splitlines():
            if not line.strip():continue
            p=doc.add_paragraph()
            if label:p.add_run(label+'：').bold=True
            p.add_run(line.strip())
            if reference:p.paragraph_format.first_line_indent=Pt(0);p.paragraph_format.space_after=Pt(3)
            if reference:
                for run in p.runs:font_properties(run._r.get_or_add_rPr(),10.5)
            elif re.match(r'^\d+[.、．）)]',line):p.paragraph_format.first_line_indent=Pt(0)
    section('课时基本信息');paragraph(' · '.join(x for x in (lesson.get('grade',''),lesson.get('subject','')) if x));paragraph(f"教案版本 {data.get('revision',0)}；来源课时 v{lesson.get('version','未记录')}")
    if data.get('goal'):section('教学目标');paragraph(data['goal'])
    if data.get('studentBase'):section('学情分析');paragraph(data['studentBase'])
    if details.get('focus') or details.get('difficulty'):
        section('教学重点与难点');paragraph(details.get('focus'), '重点');paragraph(details.get('difficulty'),'难点')
    section('教学过程')
    for i,b in enumerate(data.get('blocks',[]),1):
        doc.add_heading(f"{i}. {b.get('title','教学环节')}",2)
        paragraph(b.get('content',''))
        for key,label in [('studentTask','学生任务'),('teacherQuestion','关键提问'),('studentResponse','预设回应'),('adjustment','困难处理')]:paragraph(b.get(key),label)
    for key,label in [('teacherQuestions','关键提问'),('studentResponses','预设回应'),('adjustments','困难处理')]:paragraph(details.get(key),label)
    questions=data.get('questions',[])
    for checking,label in [(False,'例题与课堂练习'),(True,'课堂检测与评价')]:
        selected=[q for q in questions if (q.get('kind')=='check')==checking]
        if not selected:continue
        section(label)
        for i,q in enumerate(selected,1):
            doc.add_heading(f"{i}. {q.get('prompt','题目')}",2)
            p=doc.add_paragraph();p.paragraph_format.first_line_indent=Pt(24);p.paragraph_format.keep_together=True
            for key,lab in [('equation','题目'),('answer','参考答案'),('hint','提示'),('explanation','讲解')]:
                if not q.get(key):continue
                if p.text:p.add_run().add_break()
                p.add_run(lab+'：').bold=True;p.add_run(str(q[key]))
    cases,snippets=references(data)
    if cases or snippets:
        section('参考案例及材料出处')
        for i,c in enumerate(cases,1):
            paragraph(f"{i}. {c.get('title','参考案例')}（v{c.get('version','')}）",reference=True)
            paragraph(c.get('source') or c.get('author'),'来源',True)
            exp=c.get('experience') or {};summary=exp.get('goal') or exp.get('difficulty')
            if summary:paragraph(summary,'经验摘要',True)
            locations=[]
            for ref in snippets:
                if c.get('versionId') in ref['versions']:
                    value=ref['material']+(' · '+ref['label'] if ref['label'] else '')
                    if value not in locations:locations.append(value)
            if locations:paragraph('；'.join(locations),'原文位置',True)
        if mode=='trace':
            doc.add_heading('附录：原文依据',1)
            for i,ref in enumerate(snippets,1):
                p=doc.add_paragraph(f"{i}. {ref['material']} · {ref['label']}");p.paragraph_format.first_line_indent=Pt(0);p.paragraph_format.keep_with_next=True
                linked=[f"{c['title']} v{c.get('version','')}" for c in cases if c.get('versionId') in ref['versions']]
                paragraph('；'.join(linked),'对应案例',True);paragraph(ref['quote'],reference=True)
        elif snippets:
            # At most one concise excerpt per case; normalize and deduplicate globally.
            used=set()
            for c in cases:
                ref=next((x for x in snippets if c.get('versionId') in x['versions'] and normalized(x['quote']) not in used and len(x['quote'])<=220),None)
                if ref:used.add(normalized(ref['quote']));paragraph(ref['quote'],'依据摘录',True)
    for part in [doc.element,*(s.header._element for s in doc.sections),*(s.footer._element for s in doc.sections)]:
        for run in part.iter(qn('w:r')):
            rp=run.find(qn('w:rPr'))
            if rp is None:rp=OxmlElement('w:rPr');run.insert(0,rp)
            font_properties(rp)
    for rp in doc.styles.element.iter(qn('w:rPr')):font_properties(rp)
    output=io.BytesIO();doc.save(output);return output.getvalue()
