"""项目自编的等式性质首课；不冒充教材摘录或教师审定。"""
from sqlalchemy import select
from .models import Course, Lesson, CourseUnit, KnowledgePoint, LessonContent


def first_lesson():
    questions = [
        {'id':'eq-practice-add','kind':'practice','equation':'x - 3 = 5','prompt':'两边同时加3，x等于多少？','answer':'8','hint':'把两边都写成加3后的算式。','explanation':'x - 3 + 3 = 5 + 3，所以x = 8。'},
        {'id':'eq-practice-sub','kind':'practice','equation':'y + 4 = 11','prompt':'两边同时减4，y等于多少？','answer':'7','hint':'只减左边会破坏相等关系。','explanation':'y + 4 - 4 = 11 - 4，所以y = 7。'},
        {'id':'eq-check-divide','kind':'check','equation':'3z = 18','prompt':'求z，并解释两边为什么可以同时除以3。','answer':'6','hint':'3不等于0，两边同除以3。','explanation':'3z ÷ 3 = 18 ÷ 3，所以z = 6。'},
        {'id':'eq-check-multiply','kind':'check','equation':'w / 4 = 3','prompt':'求w，并写出两边共同进行的运算。','answer':'12','hint':'两边同时乘4。','explanation':'(w / 4) × 4 = 3 × 4，所以w = 12。'},
        {'id':'eq-new-combine','kind':'replacement','equation':'2(a - 1) = 10','prompt':'先使a - 1单独在一边，再求a。','answer':'6','hint':'先两边除以2，再两边加1。','explanation':'a - 1 = 5，所以a = 6。'},
        {'id':'eq-new-negative','kind':'replacement','equation':'b / (-3) = 2','prompt':'求b，说明两边共同进行的运算。','answer':'-6','hint':'两边同时乘-3，负数关系用公式表示。','explanation':'b = 2 × (-3) = -6。'},
    ]
    for q in questions:
        q.update(type='expression',knowledgeIds=['kp-equality'],feedback=[{'answer':'5','message':'检查是否只改变了等式一边；左右两边应进行同一种运算。'}])
    return {'title':'等式性质','grade':'七年级','subject':'数学','duration':35,'source':'项目自编首课；教学示例，未经真实教师试用','goal':'理解等式两边共同变化的条件，能用同加、同减、同乘和同除以非零数求未知数，并解释每一步。','knowledgeIds':['kp-equality'],'prerequisiteIds':['kp-equal','kp-operations','kp-expression'],'caseId':'case-balance','caseVersionId':None,
    'blocks':[
        {'id':'eq-intro','type':'explanation','title':'相等的两边','content':'等式表示两边的值相等，例如5 = 5。只改变一边通常不能保持相等。先预测两边同时增加相同数量后会怎样。','required':True},
        {'id':'eq-balance','type':'activity','title':'让天平两边一起变化','content':'天平两边各有5单位。两边同时增加相同的正量，观察结果，再用自己的话解释。此实物类比只展示非负数量。','required':True,'activity':{'type':'balance','base':5,'step':1,'max':10}},
        {'id':'eq-add-sub','type':'explanation','title':'同加、同减','content':'若a = b，那么a + c = b + c，a - c = b - c。c可以为正数、负数或零。关键是两边同时进行相同运算。','required':True},
        {'id':'eq-example-add','type':'example','title':'例题：消去减去的数','content':'x - 3 = 5\n两边同时加3：x - 3 + 3 = 5 + 3\n得到x = 8。把8代回，8 - 3 = 5，成立。','required':True},
        {'id':'eq-practice','type':'practice','title':'随堂练习','content':'每一步都说明两边进行了什么运算。','questionIds':['eq-practice-add','eq-practice-sub'],'required':True},
        {'id':'eq-mul-div','type':'explanation','title':'同乘、同除的条件','content':'若a = b，则ac = bc。若c ≠ 0，则a / c = b / c。除数不能为零。\n等式两边同乘0虽仍相等，却可能丢失原方程的信息：x = 2乘0得到0 = 0，不能从0 = 0恢复x = 2。解方程时可逆变形必须保留条件。','required':True},
        {'id':'eq-example-div','type':'example','title':'例题：共同除以非零数','content':'3z = 18，两边同时除以3：z = 6。\nw / 4 = 3，两边同时乘4：w = 12。\n负数也可参与运算：若b / (-3) = 2，则b = -6；用公式表达，不把负重量放到天平上。','required':True},
        {'id':'eq-check','type':'check','title':'独立检查','content':'独立作答并解释。需要帮助可以先学习当前题，再换新题重新检查。','questionIds':['eq-check-divide','eq-check-multiply'],'required':True},
    ],'questions':questions}


def ensure_curriculum(db):
    names=[('kp-equal','相等关系',[]),('kp-operations','基本运算',[]),('kp-expression','算式含义',['kp-operations']),('kp-equality','等式性质',['kp-equal','kp-expression'])]
    for ident,name,prerequisites in names:
        if not db.get(KnowledgePoint,ident): db.add(KnowledgePoint(id=ident,name=name,prerequisites=prerequisites))
    db.flush()
    lesson=db.get(Lesson,'lesson-equation')
    if not lesson:return
    if not db.get(CourseUnit,'unit-equation'):
        db.add(CourseUnit(id='unit-equation',course_id=lesson.course_id,title='一元一次方程',position=1));db.flush()
    if not lesson.unit_id:lesson.unit_id='unit-equation'
    if not db.get(LessonContent,lesson.id):db.add(LessonContent(lesson_id=lesson.id,draft=first_lesson(),reviewed=False,status='draft'))
    for ident,title,position in [('lesson-simple','解简单的一元一次方程',2),('lesson-application','用方程解决生活问题',3)]:
        if not db.get(Lesson,ident):
            db.add(Lesson(id=ident,course_id=lesson.course_id,unit_id='unit-equation',title=title,position=position));db.flush()
            db.add(LessonContent(lesson_id=ident,draft={'title':title,'grade':'七年级','subject':'数学','goal':'','duration':30,'blocks':[],'questions':[],'knowledgeIds':[],'prerequisiteIds':['kp-equality'],'source':'项目自编目录草稿'},status='draft',reviewed=False))
