"""Native editable SVG diagrams; no generated image is traced or overpainted."""
from pathlib import Path
from html import escape
import cairosvg,json,re
from PIL import ImageFont
O=Path(__file__).resolve().parent.parent/'deliverables/参赛终稿/figures';O.mkdir(exist_ok=True)
BLUE='#E8EFF6';GREEN='#E9F2EC';ORANGE='#F7EDDF';PURPLE='#EEEAF5';LINE='#596575'
class F:
 def __init__(self):
  self.parts=['<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="720" viewBox="0 0 1200 720"><defs><marker id="arr" markerWidth="9" markerHeight="7" refX="8" refY="3.5" orient="auto"><path d="M0,0 L9,3.5 L0,7" fill="#596575"/></marker></defs><rect width="1200" height="720" fill="white"/>']
 def text(self,x,y,t,size=27,bold=False,anchor='middle'):
  chunks=[]
  for part in re.split(r'([\u2e80-\u9fff\uff00-\uffef]+)',t):
   if not part:continue
   chinese=bool(re.search(r'[\u2e80-\u9fff\uff00-\uffef]',part))
   family='SimSun' if chinese else 'DejaVu Serif'
   path='/root/.local/share/fonts/sjzb5/simsun.ttc' if chinese else '/usr/share/fonts/truetype/dejavu/DejaVuSerif'+('-Bold' if bold else '')+'.ttf'
   width=ImageFont.truetype(path,size*4).getlength(part)/4
   chunks.append((part,family,width))
  cursor=x-(sum(c[2] for c in chunks)/2 if anchor=='middle' else 0)
  for part,family,width in chunks:
   self.parts.append(f'<text x="{cursor:.2f}" y="{y}" fill="#000000" font-family="{family}" font-size="{size}" font-weight="{700 if bold else 400}" text-anchor="start">{escape(part)}</text>')
   cursor+=width

 def box(self,x,y,w,h,lines,fill=BLUE,round=10,size=27):
  self.parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{round}" fill="{fill}" stroke="{LINE}" stroke-width="1.8"/>')
  if isinstance(lines,str):lines=lines.split('\n')
  for i,t in enumerate(lines):self.text(x+w/2,y+h/2+(i-(len(lines)-1)/2)*36+9,t,size)
 def line(self,x1,y1,x2,y2,arrow=True,dash=False):
  self.parts.append(f'<path d="M{x1},{y1} L{x2},{y2}" fill="none" stroke="{LINE}" stroke-width="2.4"'+(' marker-end="url(#arr)"' if arrow else '')+(' stroke-dasharray="7 6"' if dash else '')+'/>')
 def path(self,d,arrow=True,dash=False):
  self.parts.append(f'<path d="{d}" fill="none" stroke="{LINE}" stroke-width="2.4"'+(' marker-end="url(#arr)"' if arrow else '')+(' stroke-dasharray="7 6"' if dash else '')+'/>')
 def circle(self,x,y,r,label,fill=GREEN):
  self.parts.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{fill}" stroke="{LINE}" stroke-width="2"/>');self.text(x,y+9,label)
 def save(self,id):
  svg=''.join(self.parts)+'</svg>';(O/(id+'.svg')).write_text(svg);cairosvg.svg2png(bytestring=svg.encode(),write_to=str(O/(id+'.png')),output_width=3000,output_height=1800)
# Student problem motivation: three parallel needs, shared evidence base.
f=F();f.text(600,62,'中学生错题学习中的三个连续问题',34,True)
for x,n,title,lines,fill in [(45,'01','错误定位',['答案错在哪里？','原步骤缺少对应解释'],BLUE),(435,'02','针对性帮助',['当前需要什么帮助？','不同困难需要不同支持'],GREEN),(825,'03','后续验证',['离开提示后能否再做？','订正结果需要新作答观察'],ORANGE)]:
 f.text(x+165,138,n,25,True);f.box(x,170,330,205,[title]+lines,fill,size=25)
f.line(375,272,435,272);f.line(765,272,825,272)
f.box(125,475,950,110,['真实错题材料：原题、本人作答、后续回答和帮助记录'],'#F4F5F6',size=28)
for x in [210,600,990]:f.line(x,475,x,375,dash=True)
f.text(600,655,'学习问题由同一道题及其前后作答联系起来',27);f.save('00-background')
# Overall method, evidence/control separation.
f=F();f.text(70,58,'输入材料',29,True,anchor='start');f.box(45,90,1110,75,'原题与原图    ·    学生原作答    ·    已有学习记录','#F4F5F6')
labels=[('错因定位','原步骤与规则','错误位置及依据',BLUE),('掌握评估','正误与帮助条件','估计值及更新理由',GREEN),('学习规划','阶段、时间与候选','当前主行动',PURPLE),('习题补充','原题与训练目标','可作答候选',ORANGE)]
for i,(title,a,b,col) in enumerate(labels):
 x=45+i*285;f.box(x,245,255,195,[title,a,b],col,size=25);f.line(x+128,165,x+128,245)
 if i<3:f.line(x+255,343,x+285,343)
f.box(45,500,1110,75,'仓颉业务服务：核对当前题目和任务，保存结果与学习记录',GREEN,size=27)
for i in range(4):f.line(173+i*285,440,173+i*285,500)
f.box(330,620,540,65,'学生订正、独立练习与后续复习',BLUE);f.line(600,575,600,620);f.path('M870,652 L1178,652 L1178,125 L1155,125',dash=True);f.save('01')
# Architecture with exclusive DB business edge and separate inference resources.
f=F();f.box(50,50,760,105,['uni-app / Vue 3 客户端','录题、作答、反馈与历史'],BLUE)
f.box(50,240,760,135,['仓颉业务服务','身份与权限 · 任务状态 · 事务与保存'],GREEN)
f.box(50,460,760,135,['Python / FastAPI 算法服务','诊断 · 判题 · 掌握更新 · 规划与补题'],PURPLE)
f.line(430,155,430,240);f.text(550,205,'业务接口',23);f.line(430,375,430,460);f.text(560,425,'内部算法接口',23)
f.box(905,225,245,150,['MySQL','原图与文件资源'],GREEN,size=25);f.line(810,305,905,305)
f.box(905,440,245,195,['Qwen 模型','Qdrant 索引','BGE 表示与重排'],ORANGE,size=25);f.line(810,530,905,530)
f.text(600,680,'箭头表示调用方向；算法结果返回仓颉后保存',24);f.save('03')
# Evidence diagnosis mechanism and two cases.
f=F();f.text(55,53,'(a) 诊断资格与首错判断',29,True,anchor='start')
for x,lab,col in [(45,'实际步骤\nID与原文',BLUE),(335,'候选依据\n来源与规则',GREEN),(625,'证据排序\nS及依据组成',PURPLE),(915,'前缀核对\n确认首错资格',ORANGE)]:f.box(x,90,240,120,lab,col,size=25)
for x in [285,575,865]:f.line(x,150,x+50,150)
f.text(600,267,'S = I_s + 2I_r + I_f + 0.5I_k − 4I_c',29)
f.box(45,325,535,280,[],BLUE);f.box(620,325,535,280,[],ORANGE)
f.text(313,370,'(b) 前序成立',28,True);f.text(888,370,'(c) 证据不足',28,True)
for x in [313,888]:f.text(x,425,'原题：2x + 3 = 11',28)
f.text(313,475,'2x = 8：保持原题解');f.text(313,520,'x = 5：解发生变化');f.text(313,570,'结果：第二步为已核验首错',25,True)
f.text(888,475,'此前步骤尚未核验');f.text(888,520,'后续一步发现不等价');f.text(888,570,'结果：保留错误候选，需核对',25,True)
f.text(600,670,'排序分用于比较依据，首错资格另由规则与前序决定',26);f.save('04')
# Mastery mechanism, no data chart but explicit equation and scenario values.
f=F();f.text(45,55,'(a) 有效事件',29,True,anchor='start');f.box(45,90,330,140,['来源当前 · 判定明确','整题作答 · 未重复'],BLUE)
f.box(45,320,330,100,['局部、失效或重复','保留原状态'],ORANGE);f.line(210,230,210,320);f.text(260,280,'不满足',22)
f.box(460,90,695,140,['独立：w = 1      提示：w = 0.35','符合间隔条件的独立正确：w = 1.25'],GREEN,size=26);f.line(375,160,460,160);f.text(417,137,'有效',22)
f.text(600,280,'(b) 权重与更新',29,True);f.box(460,320,695,120,['p′ = pL₁ʷ / [pL₁ʷ + (1−p)L₀ʷ]','答对后：p″ = p′ + (1−p′)λ min(w,1)'],PURPLE,size=26);f.line(810,230,810,320)
f.box(45,485,330,100,['看过完整答案','保存辅助记录'],ORANGE);f.path('M375,185 L410,185 L410,535 L375,535')
f.box(460,485,695,100,['输出：掌握估计、熵、遗忘风险和理由'],BLUE,size=25);f.line(810,440,810,485)
f.text(600,650,'同一起点0.35：独立答对0.914；提示答对0.608；答案曝光0.350',25);f.save('05')
# Planner two stages with distinct lists / grouped candidate lanes.
f=F();f.text(45,55,'(a) 当前行动决策',30,True,anchor='start')
items=['时间或目标结束 → 停止','材料不足 → 核对','缺少前置知识 → 回顾','本题未完成 → 订正、提示或重做']
f.box(45,90,1110,190,[],BLUE)
for i,t in enumerate(items):f.text(90,130+i*42,t,27,anchor='start')
f.line(600,280,600,345);f.text(790,320,'当前阶段完成且有预算',24)
f.text(45,350,'(b) 后续候选选择',30,True,anchor='start')
f.box(45,395,275,140,['硬约束过滤','学科、时间、近期完成','候选按ID去重'],GREEN,size=23)
f.box(415,395,280,140,['到期题优先分组','组内评分与稳定排序'],PURPLE,size=25)
f.box(790,395,365,140,['一项主行动','至多两项备选','无候选：回顾或结束'],ORANGE,size=25)
f.line(320,465,415,465);f.line(695,465,790,465)
f.text(600,625,'Q = 0.20E + 0.20W + 0.15G + 0.20D + 0.15F + 0.10T − 0.30P',24)
f.text(600,675,'硬约束与到期组优先于分数',26,True);f.save('06')
# Retrieval / generated branches, separate gates.
f=F();f.box(30,65,250,125,['原题与训练目标','学科、年级与模式'],BLUE,size=24)
f.box(360,50,340,145,['题库检索与重排','候选资格、技能匹配','参考答案与可判分条件'],GREEN,size=24);f.line(280,125,360,125)
f.box(360,320,340,145,['受约束生成','方程构造或模型生成','技能、答案与材料复核'],ORANGE,size=24)
f.line(530,195,530,320);f.text(645,268,'无合格候选',24)
f.path('M155,190 L155,392 L360,392');f.text(175,290,'检索不可用',23)
f.box(825,70,345,120,['仓颉核对来源','保存具体练习会话'],PURPLE,size=25);f.line(700,125,825,125);f.text(762,98,'通过',23)
f.path('M700,390 L770,390 L770,155 L825,155');f.text(757,295,'通过',23)
f.box(825,320,345,110,['学生作答','保存答案与判题结果'],BLUE,size=25);f.line(995,190,995,320)
f.box(360,555,340,90,['未通过：重试或返回原题'],ORANGE,size=24);f.line(530,465,530,555)
f.text(600,690,'题库来源与生成来源分别保留；检索相似度不等于技能一致',25);f.save('07')
# Workflow swimlane, no fake multi agent.
f=F();f.text(45,48,'单协调器工作流',31,True,anchor='start')
f.box(30,85,1140,105,[],BLUE);f.text(135,125,'学生交互',27,True);f.text(640,125,'当前题目、真实新回答、已保存进度',27);f.text(640,165,'需要输入时返回页面等待',25)
f.box(30,245,1140,230,[],GREEN);f.text(1020,285,'Python算法',27,True)
for x,t in [(65,'错因诊断'),(350,'回答处理'),(635,'掌握更新'),(920,'下一步规划')]:f.box(x,330,215,75,t,'white',size=25)
for x in [280,565,850]:f.line(x,367,x+70,367)
f.line(172,190,172,330);f.box(360,420,480,40,'按需工具调用与结果反馈',PURPLE,size=23);f.line(457,405,457,420)
f.box(30,540,1140,110,[],ORANGE);f.text(150,580,'仓颉业务',27,True);f.text(680,585,'核对来源与执行资格 → 保存事件和检查点',27);f.line(1025,405,1025,540)
f.path('M30,590 L12,590 L12,138 L30,138',dash=True);f.text(600,700,'新回答触发下一次调用；等待期间没有后台代答',25);f.save('08')
# Data relationships with versions, actual steps and checkpoint.
f=F();f.text(55,55,'(a) 内容与事件关联',29,True,anchor='start')
f.box(45,105,300,110,['当前题目与来源版本','原图、题干、原作答'],BLUE,size=24)
f.box(450,105,300,110,['实际步骤','ID、原文及顺序'],GREEN,size=25);f.line(345,160,450,160)
f.box(855,105,300,110,['诊断结果','候选、引用与状态'],PURPLE,size=25);f.line(750,160,855,160)
f.box(45,330,300,110,['学习任务','冻结来源、任务版本'],ORANGE,size=24);f.line(195,215,195,330)
f.box(450,330,300,110,['学生动作与事件','回答、帮助及判定'],BLUE,size=24);f.line(345,385,450,385)
f.box(855,330,300,110,['检查点','阶段、进度及结果'],GREEN,size=25);f.line(750,385,855,385)
f.text(55,510,'(b) 原题编辑后的关系',29,True,anchor='start')
f.box(45,545,300,85,'原题 v1 → 当前 v2',BLUE,size=26);f.box(450,545,300,85,'旧任务保留来源快照',ORANGE,size=25);f.box(855,545,300,85,'后续提交核对来源',PURPLE,size=25)
f.line(345,588,450,588,dash=True);f.line(750,588,855,588,dash=True);f.text(600,690,'来源版本识别材料，任务版本识别进度；旧快照用于历史解释',24);f.save('09')
# Sequence showing race with source edit.
f=F();xs=[150,480,810,1080]
for x,t in zip(xs,['学生与前端','仓颉工作器','Python算法','MySQL']):f.text(x,60,t,26,True);f.line(x,85,x,660,arrow=False,dash=True)
for y,a,b,t in [(135,150,480,'提交动作'),(205,480,1080,'受理并保存请求'),(280,480,810,'读取快照后调用'),(365,810,480,'返回算法结果'),(490,480,1080,'核对来源、版本与租约'),(565,480,1080,'通过后事务提交'),(640,480,150,'返回已保存状态')]:f.line(a,y,b,y);f.text((a+b)/2,y-14,t,23)
f.box(580,395,540,40,'原题编辑或取消 → 旧结果拒绝提交',ORANGE,size=22)
f.save('10')
print('10 editable SVG figures exported')
