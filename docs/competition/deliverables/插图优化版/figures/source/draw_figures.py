from pathlib import Path
from xml.sax.saxutils import escape
from lxml import etree as E
from PIL import ImageFont
import cairosvg,json,shutil
B=Path(__file__).resolve().parent;O=B.parent;O.mkdir(parents=True,exist_ok=True)
C={'blue':'#EAF3FB','green':'#EBF5EE','orange':'#FFF1DE','purple':'#F1ECFA','ink':'#344054','white':'#FFFFFF','red':'#F9E8E5','line':'#8390A1'}
FONT='/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'
class F:
 def __init__(self,n,title):
  self.n=n;self.title=title;self.a=[];self.labels=[];self.edges=[]
  self.a.append('<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="800" viewBox="0 0 1200 800"><title>'+escape(title)+'</title><desc>错题帮科研技术插图。文字、形状、图标和连线为可编辑矢量；算例为机制演示。</desc><defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 Z" fill="#344054"/></marker></defs>')
  self.rect(0,0,1200,800,'white',stroke='none',r=0)
 def add(self,s):self.a.append(s)
 def rect(self,x,y,w,h,fill='white',stroke='ink',r=8,sw=2,dash=False):
  self.add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{C.get(fill,fill)}" stroke="{C.get(stroke,stroke)}" stroke-width="{sw}"'+(' stroke-dasharray="8 6"' if dash else '')+'/>')
 def text(self,x,y,t,size=28,anchor='start',bold=False,color='ink'):
  font=ImageFont.truetype(FONT,size);w=font.getlength(t);left=x-w/2 if anchor=='middle' else x-w if anchor=='end' else x
  self.labels.append({'text':t,'bbox':[round(left,2),y,round(left+w,2),y+size+3],'size':size})
  self.add(f'<text x="{x}" y="{y+size*.9}" fill="{C.get(color,color)}" font-family="Noto Sans CJK SC, DejaVu Sans, sans-serif" font-size="{size}" font-weight="{600 if bold else 400}" text-anchor="{anchor}">{escape(t)}</text>')
 def lines(self,x,y,lines,size=28,gap=42,anchor='start',bold=False):
  for i,t in enumerate(lines):self.text(x,y+i*gap,t,size,anchor,bold)
 def line(self,pts,arrow=False,dash=False,width=2,color='ink'):
  self.edges.append({'points':pts,'arrow':arrow,'dash':dash})
  self.add('<polyline points="'+' '.join(f'{x},{y}' for x,y in pts)+f'" fill="none" stroke="{C.get(color,color)}" stroke-width="{width}" stroke-linejoin="round" stroke-linecap="round"'+(' stroke-dasharray="8 7"' if dash else '')+(' marker-end="url(#arrow)"' if arrow else '')+'/>')
 def circle(self,x,y,r,fill='white',stroke='ink',sw=2):self.add(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{C.get(fill,fill)}" stroke="{C.get(stroke,stroke)}" stroke-width="{sw}"/>')
 def icon(self,name,x,y,size=38):
  root=E.fromstring((B/'icons'/f'{name}.svg').read_bytes());inner=''.join(E.tostring(c,encoding='unicode') for c in root)
  self.add(f'<g transform="translate({x} {y}) scale({size/24})" fill="none" stroke="{C["ink"]}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">{inner}</g>')
 def panel(self,x,y,w,h,title,fill='blue',icon=None):
  self.rect(x,y,w,h,fill,stroke='none',r=12)
  if icon:self.icon(icon,x+20,y+20);self.text(x+70,y+20,title,32,bold=True)
  else:self.text(x+22,y+20,title,32,bold=True)
 def node(self,x,y,w,h,label,fill='white',size=28,icon=None):
  self.rect(x,y,w,h,fill)
  if icon:self.icon(icon,x+14,y+(h-32)/2,32);self.text(x+54,y+h/2-size*.55,label,size)
  else:self.text(x+w/2,y+h/2-size*.55,label,size,'middle')
 def diamond(self,cx,cy,w,h,label,fill='orange',size=28):
  self.add(f'<path d="M {cx-w/2} {cy} L {cx} {cy-h/2} L {cx+w/2} {cy} L {cx} {cy+h/2} Z" fill="{C[fill]}" stroke="{C["ink"]}" stroke-width="2"/>');self.text(cx,cy-size*.55,label,size,'middle')
 def paper(self,x,y,w,h,title,lines,fill='blue',size=28):
  self.add(f'<path d="M{x} {y} H{x+w-28} L{x+w} {y+28} V{y+h} H{x} Z M{x+w-28} {y} V{y+28} H{x+w}" fill="{C[fill]}" stroke="{C["ink"]}" stroke-width="2"/>')
  self.text(x+20,y+18,title,28,bold=True);self.line([(x+16,y+62),(x+w-16,y+62)],color='line')
  self.lines(x+20,y+82,lines,size,46)
 def db(self,x,y,w,h,title,fill='blue'):
  self.add(f'<path d="M{x} {y+20} V{y+h-20} C{x} {y+h+7} {x+w} {y+h+7} {x+w} {y+h-20} V{y+20}" fill="{C[fill]}" stroke="{C["ink"]}" stroke-width="2"/><ellipse cx="{x+w/2}" cy="{y+20}" rx="{w/2}" ry="20" fill="{C[fill]}" stroke="{C["ink"]}" stroke-width="2"/>');self.text(x+w/2,y+h/2-4,title,28,'middle',True)
 def save(self):
  self.add('</svg>');p=O/f'{self.n:02d}.svg';p.write_text('\n'.join(self.a))
  cairosvg.svg2png(url=str(p),write_to=str(O/f'{self.n:02d}.png'),output_width=3000,output_height=2000)
  (B/f'{self.n:02d}_layout.json').write_text(json.dumps({'title':self.title,'labels':self.labels,'edges':self.edges},ensure_ascii=False,indent=2))

# 01: three research questions, with evidence-bearing examples rather than a system pipeline.
f=F(1,'研究问题与方案')
f.text(38,24,'研究问题',32,bold=True);f.text(365,24,'关键方法',32,bold=True);f.text(850,24,'可观察证据',32,bold=True)
for y,fill in [(90,'blue'),(325,'green'),(560,'purple')]:f.rect(26,y,1148,208,fill,stroke='none',r=12)
f.icon('search',48,116,40);f.text(105,119,'过程缺依据',30,bold=True)
f.lines(52,174,['2x + 3 = 11','2x = 11 + 3'],30,44)
f.line([(300,194),(364,194)],True)
f.circle(466,194,70,'white');f.text(466,151,'{4} ≠ {7}',29,'middle',True);f.text(466,198,'解集比较',26,'middle')
f.line([(536,194),(620,194)],True);f.lines(638,148,['定位实际步骤','引用原作答'],28,46)
f.line([(812,194),(864,194)],True);f.node(886,130,240,122,'首步不等价','white',30)
f.icon('pencil-line',48,352,40);f.text(105,355,'答对缺情境',30,bold=True)
f.lines(52,412,['提示后完成','独立重新作答'],28,44);f.line([(300,428),(364,428)],True)
f.paper(380,356,360,150,'条件对照',['2x − 3 = 11'],'white',32)
f.line([(740,428),(865,428)],True);f.icon('check',890,382,36);f.text(941,384,'x = 7',34,bold=True);f.text(890,446,'记录独立回答',28)
f.icon('calendar-days',48,588,40);f.text(105,591,'训练缺接续',30,bold=True);f.lines(52,647,['到期错题','可用时间'],28,44)
f.line([(300,663),(365,663)],True)
for x,lab in [(405,'复习'),(550,'作答'),(695,'反馈')]:
 f.circle(x,660,34,'white');f.text(x,646,lab,26,'middle');
f.line([(435,660),(520,660)],True);f.line([(580,660),(665,660)],True);f.line([(728,660),(862,660)],True)
f.db(885,596,240,130,'学习记录','white');f.save()

# 02: concrete input, algorithm representations, guarded business commit and real student feedback.
f=F(2,'总体方法')
f.panel(30,30,300,566,'学习证据','blue','file-text');f.paper(54,112,252,160,'原题',['2x + 3 = 11'],'white',30)
f.icon('pencil-line',58,310,35);f.text(108,310,'原始作答',28,bold=True);f.rect(53,359,253,58,'red',stroke='none');f.text(66,370,'2x = 11 + 3',29)
f.text(58,467,'辅助记录',28,bold=True);f.lines(58,516,['提示 / 答案曝光'],25,36)
f.panel(390,30,365,566,'Python 计算','green','cpu')
f.text(418,115,'错因定位',29,bold=True);f.text(418,162,'{4} ≠ {7}',32);f.text(610,167,'→ 首步',27)
f.line([(415,224),(730,224)],color='line')
f.text(418,252,'掌握评估',29,bold=True);f.text(418,297,'p → p′',32);f.rect(600,304,115,22,'white');f.rect(600,304,40,22,'purple',stroke='none');f.text(418,353,'按实际作答更新',26)
f.line([(415,409),(730,409)],color='line')
f.text(418,437,'学习规划',29,bold=True);f.icon('calendar-days',420,489,42);f.lines(480,484,['当前阶段','下一任务'],27,40)
f.line([(330,278),(390,278)],True)
f.panel(820,30,350,566,'仓颉业务','orange','shield-check')
f.node(844,119,302,62,'来源校验','white',29);f.text(995,202,'v1 = v1',32,'middle')
f.line([(995,244),(995,280)],True);f.node(844,283,302,64,'事务提交','white',29);f.line([(995,347),(995,402)],True);f.db(860,407,270,139,'学习记录','blue')
f.line([(755,278),(792,278),(792,150),(844,150)],True);f.text(762,307,'提案',24)
f.rect(390,648,780,118,'purple',stroke='none',r=12);f.icon('list-checks',1082,673,40);f.text(1090,720,'学习任务',27,'middle');f.icon('user-round',758,673,42);f.text(780,720,'学生真实动作',27,'middle');f.icon('pencil-line',440,675,40);f.text(492,677,'新作答',29,bold=True)
f.line([(995,546),(995,627),(1100,627),(1100,648)],True);f.line([(1045,694),(815,694)],True);f.line([(735,694),(595,694)],True)
f.line([(390,707),(180,707),(180,596)],True);f.text(72,739,'进入下一轮',26);f.save()

# 03: layered architecture, database/file connections originate exclusively from Cangjie.
f=F(3,'系统架构')
f.panel(30,28,1140,107,'客户端','blue','smartphone');f.text(650,65,'uni-app / Vue 3',34,'middle',True)
f.line([(590,135),(590,180)],True);f.line([(680,180),(680,135)],True)
f.panel(30,185,1140,155,'仓颉业务服务','orange','server')
f.text(85,278,'身份与归属',28);f.text(380,278,'任务与状态',28);f.text(700,278,'校验与事务',28);f.text(1000,278,'公开接口',28)
f.panel(480,403,690,181,'Python / FastAPI','green','cpu')
f.text(512,473,'诊断 · 掌握 · 规划',28);f.text(512,524,'LangGraph 单协调器',28)
f.line([(760,340),(760,403)],True);f.text(538,354,'内部计算请求',26);f.line([(1010,403),(1010,340)],True);f.text(1033,355,'提案',26)
f.line([(145,340),(145,657)],True);f.line([(365,340),(365,657)],True)
f.text(30,460,'业务读写',24);f.text(250,460,'资源管理',24)
f.db(42,663,205,104,'MySQL','blue');f.rect(278,665,210,101,'blue');f.icon('folder',294,694,36);f.text(340,695,'文件资源',27)
f.line([(650,584),(650,665)],True);f.line([(1040,584),(1040,665)],True)
f.node(530,665,290,101,'Qdrant / BGE','blue',28);f.node(900,665,270,101,'Qwen','purple',30)
f.text(540,603,'检索',26);f.text(1064,603,'模型调用',24);f.save()

# 04: a verified prefix is shown separately from an uncertain prefix.
f=F(4,'错因证据')
f.text(28,24,'(a) 已核验前缀',30,bold=True)
f.panel(26,86,354,399,'原题与步骤','blue','pencil-line')
f.text(55,170,'2x + 3 = 11',32,bold=True);f.text(55,264,'①  2x = 8',32);f.rect(49,352,307,65,'red',stroke='none');f.text(60,366,'②  x = 5',32)
f.panel(421,86,335,399,'解集对照','green','search')
f.text(584,170,'原题：{4}',30,'middle');f.text(584,264,'{4} = {4}',32,'middle');f.text(584,366,'{4} ≠ {5}',32,'middle')
f.line([(380,281),(421,281)],True);f.line([(380,385),(421,385)],True)
f.panel(796,86,378,399,'诊断资格','orange','shield-check')
f.icon('check',821,230,35);f.text(870,232,'前序有效',29);f.icon('check',821,286,35);f.text(870,288,'本步不等价',29)
f.line([(985,330),(985,366)],True);f.node(819,375,331,73,'首错：第 2 步','green',30)
f.line([(756,385),(796,385)],True)
f.text(28,536,'(b) 前序证据不足',30,bold=True)
f.rect(26,590,1148,173,'orange',stroke='none',r=12)
f.lines(54,620,['前一步待核对','后一步已判错'],29,49);f.line([(302,675),(415,675)],True)
f.diamond(576,675,300,116,'首错资格不足',fill='white',size=27);f.line([(726,675),(820,675)],True);f.node(850,638,275,74,'保留错误候选','white',29);f.save()

# 05: weighted evidence, bypassed assistance and an explicit gate.
f=F(5,'辅助感知更新')
f.text(30,25,'实际行为',32,bold=True);f.text(467,25,'事件准入',32,bold=True);f.text(866,25,'状态输出',32,bold=True)
f.node(30,105,290,80,'独立作答','blue',30);f.node(30,245,290,80,'提示后作答','blue',30)
f.line([(320,145),(452,145)],True,width=4);f.text(340,103,'w = 1',26)
f.line([(320,285),(452,285)],True,width=2);f.text(333,242,'w = 0.35',24)
f.panel(455,96,275,261,'有效事件','orange','shield-check');f.lines(480,170,['来源有效','学生确认','判题可靠'],28,46)
f.line([(730,220),(805,220)],True);f.panel(810,95,360,262,'贝叶斯更新','green','chart-no-axes-combined');f.text(990,169,'p → p′ → p″',32,'middle')
f.text(836,237,'w = 1 → 0.914',26)
f.text(836,291,'w = 0.35 → 0.608',26)
f.text(780,384,'先验 0.35，非选择题正确作答',24)
f.line([(590,357),(590,425)],True,dash=True);f.text(480,437,'未通过：待核对',27)
f.line([(28,499),(1171,499)],color='line')
f.node(30,546,290,80,'完整答案曝光','purple',30);f.line([(320,586),(810,586)],True,dash=True);f.text(452,540,'不增加掌握证据',27);f.node(810,546,360,80,'辅助学习记录','purple',29)
f.node(30,684,290,80,'局部订正','purple',30);f.line([(320,724),(810,724)],True,dash=True);f.text(452,677,'记录当前修复',27);f.node(810,684,360,80,'过程记录','purple',29);f.save()
# 06: a priority decision ladder, then a separate admissibility funnel and queue.
f=F(6,'学习规划')
f.text(28,24,'(a) 当前行动',32,bold=True);f.text(638,24,'(b) 后续候选',32,bold=True)
f.rect(25,86,542,592,'blue',stroke='none',r=12)
for y,condition,action in [(152,'目标完成','结束'),(279,'证据不足','核对'),(406,'基础缺失','知识回顾'),(533,'重复错误','局部订正')]:
 f.diamond(198,y,284,96,condition,size=28);f.line([(340,y),(390,y)],True);f.text(350,y-37,'是',24);f.node(397,y-35,149,70,action,'white',26)
 if y<533:f.line([(198,y+48),(198,y+79)],True);f.text(214,y+51,'否',24)
f.line([(198,581),(198,620)],True);f.text(46,632,'其余按当前学习阶段执行',27)
f.line([(440,678),(602,678),(602,153),(640,153)],True);f.text(370,707,'阶段完成后',27)
f.panel(640,86,535,251,'硬约束筛选','orange','shield-check')
f.add('<path d="M668 169 H1146 L1066 288 H748 Z" fill="white" stroke="#344054" stroke-width="2"/>')
f.text(906,184,'学科一致 · 时间可容纳',27,'middle');f.text(906,238,'排除刚完成题',27,'middle')
f.line([(907,337),(907,378)],True)
f.panel(640,383,535,245,'优先组与排序','green','list-checks')
f.circle(683,483,20,'orange');f.text(683,469,'1',25,'middle');f.text(727,468,'合格到期题',28);f.text(1094,468,'Q',28,'middle',True)
f.circle(683,563,20,'purple');f.text(683,549,'2',25,'middle');f.text(727,548,'其他候选',28);f.text(1094,548,'Q',28,'middle',True)
f.line([(1020,479),(1060,479)],True);f.line([(1020,559),(1060,559)],True)
f.line([(907,628),(907,684)],True);f.node(749,689,316,82,'下一任务','purple',32,icon='calendar-days');f.save()

# 07: retrieval precedes conditional generation, then a shared validation surface.
f=F(7,'同源核验补题')
f.paper(28,44,310,192,'原题与技能',['13x + 7 = 98','一元一次方程'],'blue',28)
f.circle(465,140,62,'blue');f.icon('search',442,116,46);f.text(465,218,'题库检索',29,'middle',True)
f.line([(338,140),(402,140)],True);f.line([(527,140),(600,140)],True)
f.diamond(760,140,300,132,'候选可用',size=29);f.line([(910,140),(1064,140),(1064,360)],True);f.text(951,96,'是',26)
f.line([(760,206),(760,305),(465,305),(465,360)],True);f.text(780,248,'否',26)
f.paper(293,368,348,206,'受约束生成',['5x + 3 = −32','x = −7'],'green',30);f.icon('file-plus',581,386,35)
f.line([(641,472),(794,472)],True)
f.panel(802,368,370,222,'统一核验','orange','shield-check')
f.icon('check',827,452,29);f.text(870,450,'技能与年级',27);f.icon('check',827,518,29);f.text(870,515,'答案与材料',27)
f.line([(982,590),(982,642)],True);f.text(1002,603,'通过',25);f.paper(825,650,346,119,'保存后作答',[],'purple')
f.line([(802,555),(724,555),(724,708),(634,708)],True,dash=True);f.text(610,589,'未通过',25);f.node(289,669,345,78,'重试或结束','white',30)
f.save()

# 08: three ownership lanes; Python invocation ends on return, human actions start the next one.
f=F(8,'任务协同')
for x,w,title,fill,icon in [(25,275,'学生','blue','user-round'),(330,355,'仓颉业务','orange','server'),(715,460,'Python 计算','green','cpu')]:
 f.panel(x,24,w,748,title,fill,icon)
f.node(45,127,235,75,'提交真实动作','white',27)
f.node(350,127,315,75,'受理与读取检查点','white',27);f.line([(280,165),(350,165)],True)
f.node(778,127,335,73,'证据诊断','white',28);f.line([(665,165),(778,165)],True)
f.node(778,255,335,73,'动作处理','white',28);f.line([(945,200),(945,255)],True)
f.node(778,382,335,73,'掌握更新','white',28);f.line([(945,328),(945,382)],True)
f.node(778,508,335,73,'学习规划','white',28);f.line([(945,455),(945,508)],True)
f.line([(778,291),(745,291),(745,354),(818,354)],True);f.text(829,337,'工具反馈',25);f.line([(1000,355),(1090,355),(1090,328)],True)
f.line([(1113,163),(1150,163),(1150,623),(540,623),(540,571)],True,dash=True);f.text(954,645,'证据不足',25)
f.node(350,490,315,81,'校验与事务提交','white',27);f.line([(778,547),(665,547)],True)
f.node(350,665,315,75,'保存检查点','white',28);f.line([(507,571),(507,665)],True)
f.node(45,665,235,75,'等待新动作','purple',28);f.line([(350,702),(280,702)],True)
f.line([(65,665),(65,252),(162,252),(162,202)],True,dash=True);f.text(89,339,'恢复后继续',26)
f.text(754,706,'返回后结束本次调用',26);f.save()

# 09: object relationships on the left, immutable history/current version on the right.
f=F(9,'来源关联')
f.text(28,24,'(a) 学习对象关联',32,bold=True);f.text(653,24,'(b) 来源版本演化',32,bold=True)
f.rect(25,85,553,681,'blue',stroke='none',r=12);f.rect(621,85,553,681,'purple',stroke='none',r=12)
f.icon('user-round',81,109,45);f.text(146,115,'学生',30,bold=True);f.line([(220,142),(359,142)],True)
f.paper(363,103,184,144,'当前题目',['来源标识'],'white',26)
f.line([(455,247),(455,292),(114,292),(114,345)],True);f.line([(455,292),(295,292),(295,345)],True);f.line([(455,292),(455,345)],True)
f.paper(44,352,145,147,'原图',[],'white');f.icon('file-text',95,429,44)
f.paper(218,352,175,147,'实际作答',[],'white');f.icon('pencil-line',269,429,44)
f.node(405,352,145,147,'学习任务','green',27)
f.line([(477,499),(477,540),(168,540),(168,595)],True);f.line([(477,540),(477,595)],True)
f.paper(61,602,215,135,'来源快照',[],'white');f.db(350,603,200,128,'学习事件','green')
f.paper(649,120,222,187,'v1',['2x + 3 = 11'],'blue',25);f.paper(925,120,222,187,'v2',['2x − 3 = 11'],'green',25)
f.line([(871,209),(925,209)],True);f.text(874,160,'编辑',24)
f.line([(760,307),(760,386)],True);f.line([(1036,307),(1036,386)],True)
f.paper(650,393,221,145,'冻结快照',[],'blue');f.node(925,393,222,145,'重新核验','orange',28,icon=None)
f.line([(760,538),(760,623)],True);f.line([(1036,538),(1036,623)],True)
f.node(649,630,223,91,'历史保留','white',28);f.node(925,630,222,91,'当前有效结果','green',27)
f.save()

# 10: time axis separates the long compute interval from the guarded commit phase.
f=F(10,'异步提交')
f.text(28,26,'异步执行时间线',32,bold=True)
f.line([(62,123),(1139,123)],True)
for x,t,label in [(94,'t0','请求受理'),(334,'t1','任务领取'),(624,'t2','异步计算'),(1042,'t3','结果返回')]:
 f.circle(x,123,10,'white');f.text(x,65,t,27,'middle');f.text(x,156,label,28,'middle',True)
f.paper(31,226,236,154,'冻结来源',['v1'],'blue',31);f.node(291,226,233,154,'绑定执行租约','orange',27)
f.rect(560,226,610,154,'green',stroke='none',r=12);f.icon('cpu',584,254,42);f.text(647,252,'Python 计算结果',30,bold=True);f.text(584,315,'计算期间：可编辑 · 可取消',27)
f.line([(1042,380),(1042,410),(620,410),(620,455)],True)
f.panel(28,461,795,283,'提交前复核','orange','shield-check')
for x,y,label in [(57,547,'版本有效'),(444,547,'租约有效'),(57,636,'未被取消'),(444,636,'来源一致')]:
 f.icon('check',x,y,32);f.text(x+48,y,label,29)
f.line([(823,603),(859,603)],True);f.diamond(922,603,124,117,'全部',size=25)
f.line([(984,603),(1085,603),(1085,557)],True);f.text(1008,626,'满足',24);f.db(966,445,207,109,'事务提交','green')
f.line([(922,662),(922,716),(996,716)],True,dash=True);f.text(850,752,'否则',24);f.node(1000,676,173,79,'拒绝结果','white',27)
f.save()
print('Created 10 editable SVG files and 3000 × 2000 PNGs')
