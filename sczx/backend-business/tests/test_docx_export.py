import unittest,io,copy,zipfile
from lxml import etree
from docx import Document
from docx.oxml.ns import qn
from sczx_business.docx_export import build_docx,references
from sczx_business.teaching_quality import review_plan,editorial_marks,cleaned_copy

class WordExportTests(unittest.TestCase):
    def data(self):
        quote={'unitId':'u1','materialId':'m1','materialTitle':'自编材料.pdf','label':'第1页','quote':'等式两边同时加上相同的数，相等关系保持不变。'}
        case={'id':'c1','versionId':'cv1','version':2,'title':'自编教学案例','source':'自编验收材料，非真实课堂记录','experience':{'goal':'比较两边共同变化'},'references':[quote,{**quote,'field':'goal'},{**quote,'quote':'教学目标：'+quote['quote']},{**quote,'quote':' 等式两边同时加上相同的数， 相等关系保持不变。'}]}
        return {'revision':12,'lessonSnapshot':{'title':'等式性质 Lesson 1','version':2,'grade':'七年级','subject':'数学'},'goal':'说明每一步共同运算的依据。','studentBase':'会整数运算。','blocks':[{'id':'b1','title':'观察天平','content':'教师手写保留：出示5 = 5，比较两边。','studentTask':'写出两边的值。','teacherQuestion':'两边同加3后怎样？'}],'questions':[{'id':'q1','kind':'check','prompt':'求x','equation':'x - 3 = 5','answer':'8'}],'caseSnapshot':case,'planningDetails':{'focus':'共同运算','references':[case]},'agentSources':[{'unitId':'u1','materialId':'m1','title':'自编材料.pdf','label':'第1页','content':quote['quote'],'caseVersionId':'cv1'}]}
    def test_fonts_color_a4_spacing_and_page_field_are_explicit(self):
        payload=build_docx(self.data());doc=Document(io.BytesIO(payload));s=doc.sections[0]
        self.assertAlmostEqual(s.page_width/360000,21,places=2);self.assertAlmostEqual(s.page_height/360000,29.7,places=2)
        self.assertAlmostEqual(s.left_margin/360000,2.7,places=2);self.assertAlmostEqual(s.top_margin/360000,2.5,places=2)
        self.assertEqual(doc.styles['Normal'].font.size.pt,12);self.assertEqual(doc.styles['Normal'].paragraph_format.line_spacing,1.35)
        with zipfile.ZipFile(io.BytesIO(payload)) as z:
            for file in ('word/document.xml','word/styles.xml','word/footer1.xml','word/header1.xml'):
                root=etree.fromstring(z.read(file))
                for rpr in root.iter(qn('w:rPr')):
                    fonts=rpr.find(qn('w:rFonts'));color=rpr.find(qn('w:color'))
                    self.assertIsNotNone(fonts);self.assertIsNotNone(color)
                    self.assertEqual(fonts.get(qn('w:eastAsia')),'宋体');self.assertEqual(fonts.get(qn('w:ascii')),'Times New Roman');self.assertEqual(fonts.get(qn('w:hAnsi')),'Times New Roman');self.assertEqual(fonts.get(qn('w:cs')),'Times New Roman')
                    self.assertEqual(color.get(qn('w:val')),'000000');self.assertFalse(any('Theme' in k or 'theme' in k for k in [*fonts.attrib,*color.attrib]))
            self.assertNotIn(b'pBdr',z.read('word/styles.xml'))
            self.assertIn('PAGE',z.read('word/footer1.xml').decode())
    def test_modes_deduplicate_sources_without_touching_original_text(self):
        data=self.data();before=copy.deepcopy(data);self.assertEqual(len(references(data)[1]),1)
        formal=Document(io.BytesIO(build_docx(data)));trace=Document(io.BytesIO(build_docx(data,'trace')))
        ft='\n'.join(p.text for p in formal.paragraphs);tt='\n'.join(p.text for p in trace.paragraphs)
        self.assertEqual(ft.count('自编教学案例'),1);self.assertEqual(tt.count(data['caseSnapshot']['references'][0]['quote']),1)
        self.assertNotIn('附录：',ft);self.assertIn('附录：',tt);self.assertIn('教师手写保留',ft);self.assertEqual(data,before)
        cleaned=Document(io.BytesIO(build_docx(data,clean_editorial=True)));self.assertNotIn('教师手写保留','\n'.join(p.text for p in cleaned.paragraphs));self.assertEqual(data,before)
    def test_marker_cleanup_is_bounded_explicit_and_preserves_math_and_sources(self):
        data=self.data();data['blocks'][0]['content']='保留例题：3z = 18，两边同时除以3，z = 6。\n沿用例题x - 3 = 5。'
        before=copy.deepcopy(data);self.assertTrue(editorial_marks(data));clean=cleaned_copy(data)
        self.assertEqual(clean['blocks'][0]['content'],'3z = 18，两边同时除以3，z = 6。\n例题x - 3 = 5。');self.assertEqual(clean['caseSnapshot'],data['caseSnapshot']);self.assertEqual(before,data)
    def test_quality_warnings_do_not_rewrite_or_mislabel_conditions(self):
        plan={'goal':'本次生成活动','blocks':[{'id':'a','title':'共同运算','content':'教师手写保留：通过活动引导学生深入理解，从而培养学生综合能力。'},{'id':'b','title':'共同运算','content':'等式两边同时除以c。等式两边同时除以c。'}]};before=copy.deepcopy(plan);review=review_plan(plan)
        codes={w['code'] for w in review['warnings']};self.assertTrue({'editorial','duplicate_title','division_condition'}<=codes);self.assertEqual(plan,before)
        good={'goal':'解释两边共同运算','blocks':[{'id':'a','title':'计算并核对','content':'两边同时除以非零数c，代入检验。'}]};self.assertEqual(review_plan(good)['warnings'],[])
        vague={'goal':'了解知识','blocks':[{'id':'a','title':'理解','content':'学生深入理解知识并提高认识。'}]}
        self.assertIn('vague_language',{w['code'] for w in review_plan(vague)['warnings']})
