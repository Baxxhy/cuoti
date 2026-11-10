"""AI-assisted project-authored unit drafts. Never automatically review or publish."""
import copy
from .lesson_seed import first_lesson
SOURCE='项目自编、AI辅助整理的一元一次方程单元；非教材摘录或真实教师经验，正式发布前须人工复核'
POINTS=[('kp-linear-simple','简单一元一次方程',['kp-equality']),('kp-linear-transform','方程变形与验算',['kp-linear-simple']),('kp-linear-model','实际问题中的设元与列式',['kp-linear-transform']),('kp-linear-review','一元一次方程综合检查',['kp-linear-transform','kp-linear-model'])]

def question(ident,kind,equation,answer,prompt,hint,explanation,knowledge,word=False):
    return {'id':ident,'kind':kind,'type':'expression','equation':equation,'answer':answer,'prompt':prompt,'hint':hint,'explanation':explanation,'knowledgeIds':knowledge,'teacherNote':'核对每一步是否等价，要求代回原式。'+('数值核验不替代设元、列式和情境条件核对。' if word else ''),'requiresTeacherReview':word}

def lesson(ident,title,goal,knowledge,prerequisites,explanations,examples,questions):
    prefix=ident.removeprefix('lesson-');blocks=[]
    for index,(heading,text) in enumerate(explanations):blocks.append({'id':prefix+'-explain-'+str(index),'type':'explanation','title':heading,'content':text,'required':True,'teacherNote':'先让学生说明依据，再补充规范步骤。'})
    for index,(heading,text) in enumerate(examples):blocks.append({'id':prefix+'-example-'+str(index),'type':'example','title':heading,'content':text,'required':True,'teacherQuestion':'这一步对等式两边做了什么？','studentResponse':'写出两边相同的运算并说明条件。','adjustment':'若只改变一边，回到原等式比较。'})
    blocks.extend([{'id':prefix+'-practice','type':'practice','title':'活动：比较、求解并验算','content':'先独立写出每一步，再与原式比较；把答案代回左右两边。','questionIds':[q['id'] for q in questions if q['kind']=='practice'],'required':True,'studentTask':'提交答案和运算解释，保留首次尝试。'},{'id':prefix+'-check','type':'check','title':'独立检查','content':'不看例题独立作答。若请求帮助，之后换一道未作答新题检查。','questionIds':[q['id'] for q in questions if q['kind']=='check'],'required':True}])
    return {'id':ident,'data':{'title':title,'grade':'七年级','subject':'数学','duration':40,'source':SOURCE,'authorship':{'kind':'project_authored_ai_assisted','humanReview':'pending'},'goal':goal,'knowledgeIds':knowledge,'prerequisiteIds':prerequisites,'blocks':blocks,'questions':questions}}

def unit_bundle():
    simple=['kp-linear-simple'];transform=['kp-linear-transform'];model=['kp-linear-model'];review=['kp-linear-review']
    q=lambda *a,**kw:question(*a,**kw)
    first=first_lesson();first['source']=SOURCE;first['authorship']={'kind':'project_authored_ai_assisted','humanReview':'pending'}
    rows=[{'id':'lesson-equation','data':first}]
    rows.append(lesson('lesson-simple','解简单的一元一次方程','用等式性质解加减、乘除及两步方程，并代回原式验算。',simple,['kp-equality'],[
      ('确定未知量与运算顺序','一元一次方程含一个未知数，未知数最高次数为1。先看未知项外面做了什么运算，再逆向逐步消去；每一步两边必须同时进行相同运算。'),
      ('系数与非零条件','解4x=20时，两边同除以4，4不为0。解x/(-3)=4时，两边同乘-3。除数不能为0；为保持方程等价，解题时同乘的数也取非零数。'),
      ('代回原式','把候选值代入原方程，分别计算左右两边。两边相等才与原式相符；计算相符不替代对推理过程的解释。')],[
      ('例题：先加减后乘除','解2x+3=11：两边减3得2x=8；两边除以非零数2得x=4。验算2×4+3=11。'),
      ('例题：负数系数','解-2x+5=13：两边减5得-2x=8；两边除以-2得x=-4。验算-2×(-4)+5=13。')],[
      q('simple-p1','practice','x+7=12','5','求x，并说明消去7的方法。','两边同时减7。','x=5；5+7=12。',simple),q('simple-p2','practice','4x=20','5','求x，说明同除条件。','4不为0，两边同时除以4。','x=5；4×5=20。',simple),q('simple-c1','check','x/(-3)=4','-12','求x并验算。','两边同时乘-3。','x=-12；(-12)/(-3)=4。',simple),q('simple-c2','check','-2x+5=13','-4','求x，写出两步共同运算。','先两边减5。','-2x=8，x=-4。',simple),q('simple-r1','replacement','x/5+2=1','-5','求x并代回。','先减2，再乘5。','x/5=-1，x=-5。',simple),q('simple-r2','replacement','3x-4=11','5','求x并解释。','先加4，再除以非零数3。','3x=15，x=5。',simple)]))
    rows.append(lesson('lesson-transform','含括号与分母的方程','用分配律、合并同类项及同乘非零公倍数解方程，解释移项并验算。',transform,simple,[
      ('移项来自共同运算','从2x+3=11到2x=11-3，实际是两边同时减3。移项后的符号变化来自共同运算，不能只移动一个符号而不检查等式。'),
      ('去括号与合并同类项','用分配律展开每一项：-2(x+3)=-2x-6。括号前是负数时，两项都要乘这个负数；合并时只合并同类项。'),
      ('去分母的范围','本课分母均为已知非零常数。两边同乘这些分母的非零公倍数时，左右两边的每一项都要乘。含未知数分母的题还需定义域和增根核对，本课不作自动评分。')],[
      ('例题：括号与两边运算','解2(x-3)+4=10：展开得2x-6+4=10，即2x-2=10；两边加2再除以2，x=6。验算2(6-3)+4=10。'),
      ('例题：常数分母','解x/2+x/3=5：两边同乘非零数6，得3x+2x=30；5x=30，x=6。原式6/2+6/3=5。')],[
      q('transform-p1','practice','2(x-3)+4=10','6','展开括号并求x。','乘2时括号内两项都要乘。','2x-2=10，x=6。',transform),q('transform-p2','practice','(x-1)/3=2','7','去分母并求x。','两边同乘非零数3。','x-1=6，x=7。',transform),q('transform-c1','check','3(2x-1)-2(x+4)=9','5','求x并解释负号的作用。','-2要乘括号内每一项。','6x-3-2x-8=9，4x=20，x=5。',transform),q('transform-c2','check','(x+2)/4-(x-1)/6=1','4','求x，写出两边同乘的数。','两边同乘非零数12。','3(x+2)-2(x-1)=12，x=4。',transform),q('transform-r1','replacement','-3(x-2)=12','-2','求x并验算。','先除以非零数-3。','x-2=-4，x=-2。',transform),q('transform-r2','replacement','x/2+x/3=5','6','求x。','公倍数6不为0。','3x+2x=30，x=6。',transform)]))
    rows.append(lesson('lesson-application','用方程解决生活问题','说明未知量、单位和数量关系，列出一元一次方程，求解后核对情境条件。',model,transform,[
      ('先说明未知量','先写“设每支笔x元”，明确数量和单位。找到同一个量的两种表达，或总量与各部分的关系，再用等号连接。数值答案正确不能证明列式过程正确。'),
      ('检验包含两层','先代回方程核对等式，再检查实际条件。例如长度和单价应为正，人数通常为整数。若结果不符合条件，回查设元、列式与计算。'),
      ('条件不足时先补充','“几支笔共21元”若没有支数，就不能唯一确定单价。不能为得到一个答案自行补造条件。本课给出参考方程用于核对数值，学生的设元、列式与文字解释仍需教师核对。')],[
      ('例题：单价与固定费用','3支同价笔加6元包装费共21元。设每支笔x元，列3x+6=21。两边减6再除以3，得x=5。验算3×5+6=21，且5元为正，符合条件。'),
      ('例题：周长关系','长方形长比宽多3厘米，周长30厘米。设宽x厘米，长x+3厘米；2[x+(x+3)]=30。解得x=6，长9。验算2(6+9)=30，长宽均为正。')],[
      q('application-p1','practice','3x+6=21','5','3支同价笔加6元包装费共21元，每支笔几元？在解释中写设元和列式。','总价=3支笔的钱+包装费。','设每支x元；3x+6=21；x=5元，代回总价21元。',model,True),q('application-p2','practice','2(x+x+3)=30','6','长方形长比宽多3厘米，周长30厘米，宽几厘米？写出数量关系。','周长是长与宽之和的2倍。','设宽x，长x+3；x=6厘米，长9厘米。',model,True),q('application-c1','check','5x+8=43','7','5本同价练习本加8元运费共43元，每本几元？写设元、列式与验算。','先区分总价中的固定运费。','设单价x元；5x+8=43，x=7元；5×7+8=43。',model,True),q('application-c2','check','3x=180','60','匀速车3小时行180千米，每小时几千米？写速度关系和单位。','路程=速度×时间。','设速度x千米/时；3x=180；x=60千米/时。',model,True),q('application-r1','replacement','4x+5=33','7','4盒同价材料加5元配送费共33元，每盒几元？','先减固定配送费。','4x=28，x=7元；4×7+5=33。',model,True),q('application-r2','replacement','2x+3x=45','9','上午完成2组、下午完成3组，每组人数相同，共45人，每组几人？','先数一共有几组。','(2+3)x=45；x=9人，为正整数。',model,True)]))
    rows.append(lesson('lesson-unit-review','一元一次方程单元复习','联系等式性质、方程变形和实际数量关系，独立求解并用原式与情境验算。',review,['kp-linear-transform','kp-linear-model'],[
      ('选择解题路径','先辨认结构：加减、乘除、括号或常数分母。每一步写明依据。需要前置知识时回看对应课时，不把记住“移项变号”替代等式运算。'),
      ('核对条件与结论','同除的数必须非零。两边同乘0仍相等，但会丢失方程信息，不能用来求原方程的唯一解。0x=0有无穷多解，0x=1无解；本单元自动评分只覆盖可验证的单变量唯一实数解。'),
      ('从方程回到实际问题','得到数值后代回原式，并检查单位、正数或整数条件。文字列式和解释交给教师核对；系统只按已声明范围保存核验结果。')],[
      ('例题：解释完整链条','解5(x-2)=2x+8：5x-10=2x+8；两边减2x并加10，3x=18；两边除以3得x=6。代回5(6-2)=20，2×6+8=20。'),
      ('例题：核查一份错误解法','把x/2+x/4=9同乘4后写成2x+x=9不成立：右边也要乘4，正确为2x+x=36，x=12。原式12/2+12/4=9。')],[
      q('review-p1','practice','2(x+3)=18','6','求x，说明展开与共同运算的区别。','可先两边同除以2。','x+3=9，x=6。',['kp-equality','kp-linear-transform']),q('review-p2','practice','x/3-2=1','9','求x并验算。','先加2再乘3。','x/3=3，x=9。',simple),q('review-c1','check','x/2+x/4=9','12','独立求解，写出去分母的完整等式。','两边每一项同乘4。','2x+x=36，x=12。',transform),q('review-c2','check','5(x-2)=2x+8','6','独立求解并代回原方程。','展开后比较两边的未知项。','5x-10=2x+8，x=6。',transform),q('review-r1','replacement','4x+12=40','7','4件同价物品加12元固定费用共40元，每件几元？写列式与验算。','总价包含固定费用。','4x=28，x=7元。',model,True),q('review-r2','replacement','-x/2=3','-6','求x并说明乘数条件。','两边同时乘非零数-2。','x=-6；-(-6)/2=3。',['kp-equality','kp-linear-simple'])]))
    return {'unitId':'unit-equation','title':'一元一次方程','source':SOURCE,'knowledge':[{'id':i,'name':n,'prerequisites':p,'aliases':[]} for i,n,p in POINTS],'lessonOrder':[r['id'] for r in rows],'lessons':rows}
