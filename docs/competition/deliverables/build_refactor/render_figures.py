#!/usr/bin/env python3
"""错题帮参赛论文插图。所有可编辑文字为 #000000，900px 画布。
运行 python render_figures.py；SVG 为矢量主源，PNG 为 3 倍高分辨率插图。
"""
from pathlib import Path
import json, html
import cairosvg
from PIL import ImageFont
FONT = ImageFont.truetype("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",18)
OUT=Path(__file__).resolve().parents[1]/'figures'/'restructured'
OUT.mkdir(parents=True,exist_ok=True)
INK='#000000'; BLUE='#eaf3f8'; GREEN='#edf6ef'; GRAY='#f3f4f3'; LINE='#55616a'
TITLES={}
class Fig:
 def __init__(self,n,title,conclusion,h=640):
  self.n=n; self.h=h; self.s=[]
  TITLES[f'{n:02}']={'title':title,'conclusion':conclusion,'source':'build_refactor/render_figures.py','width':900,'height':h,'minimum_font_px':18,'text_color':'#000000'}
  self.s.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="900" height="{h}" viewBox="0 0 900 {h}"><defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0 0 L8 4 L0 8Z" fill="{LINE}"/></marker></defs><rect width="900" height="{h}" fill="#ffffff"/>')
 def rect(self,x,y,w,h,fill=BLUE,r=10,stroke='#a9b8bf',dash=False):
  self.s.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill}" stroke="{stroke}" stroke-width="1.5"'+(' stroke-dasharray="7 5"' if dash else '')+'/>')
 def text(self,x,y,lines,size=20,bold=False,anchor='start'):
  if isinstance(lines,str): lines=lines.split('\n')
  self.s.append(f'<text x="{x}" y="{y}" fill="#000000" font-family="Noto Sans CJK SC, sans-serif" font-size="{size}" font-weight="{700 if bold else 400}" text-anchor="{anchor}">')
  for i,l in enumerate(lines): self.s.append(f'<tspan x="{x}" dy="{0 if i==0 else size*1.5}">{html.escape(l)}</tspan>')
  self.s.append('</text>')
 def line(self,x1,y1,x2,y2,arrow=False,dash=False):
  self.s.append(f'<path d="M{x1},{y1} L{x2},{y2}" fill="none" stroke="{LINE}" stroke-width="2"'+(' marker-end="url(#arrow)"' if arrow else '')+(' stroke-dasharray="7 5"' if dash else '')+'/>')
 def path(self,d,arrow=True,dash=False):
  self.s.append(f'<path d="{d}" fill="none" stroke="{LINE}" stroke-width="2"'+(' marker-end="url(#arrow)"' if arrow else '')+(' stroke-dasharray="7 5"' if dash else '')+'/>')
 def circ(self,x,y,r,fill=GREEN): self.s.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{fill}" stroke="{LINE}" stroke-width="1.5"/>')
 def box(self,x,y,w,h,title,body='',fill=BLUE):
  self.rect(x,y,w,h,fill); self.text(x+16,y+32,title,20,True)
  if body:self.text(x+16,y+65,body,18)
 def label(self,x,y,t):self.text(x,y,t,18)
 def panel(self,x,y,w,h,title,fill=GRAY): self.rect(x,y,w,h,fill,12); self.text(x+16,y+32,title,21,True)
 def doc(self,x,y,w,h,title,body):
  self.s.append(f'<path d="M{x} {y} H{x+w-22} L{x+w} {y+22} V{y+h} H{x}Z" fill="#ffffff" stroke="{LINE}" stroke-width="1.5"/><path d="M{x+w-22} {y} V{y+22} H{x+w}" fill="none" stroke="{LINE}"/>')
  self.text(x+13,y+35,title,20,True);self.text(x+13,y+69,body,18)
 def save(self):
  self.s.append('</svg>'); svg=''.join(self.s); p=OUT/f'{self.n:02}.svg';p.write_text(svg)
  cairosvg.svg2png(bytestring=svg.encode(),write_to=str(OUT/f'{self.n:02}.png'),scale=3)

# 01 问题—机制—可观察闭环，非流程框链
f=Fig(1,'引言总览：从保存错题到证据驱动的学习闭环','以原始作答和有效学习证据连接诊断、辅导与复习。',650)
f.panel(20,20,270,565,'(a) 学习中的断点',GRAY)
f.doc(40,82,225,150,'保存题目','原题照片／作答过程\n材料分散，难回看')
f.line(151,244,151,294,False,True);f.text(162,277,'断点',18)
f.doc(40,310,225,150,'查看解析','看懂 ≠ 独立做对\n训练与复习缺少关联')
f.text(40,510,'关键问题',20,True);f.text(40,545,'缺少可追溯证据\n缺少明确的下一步',18)
f.panel(315,20,270,565,'(b) 错题帮的机制',BLUE)
f.circ(450,229,78,'#ffffff');f.text(450,216,'原始作答',22,True,'middle');f.text(450,251,'来源与版本',18,False,'middle')
for x,y,t in [(336,90,'证据驱动诊断'),(336,352,'任务驱动辅导'),(336,459,'验证驱动更新')]:
 f.rect(x,y,228,69,'#ffffff');f.text(x+114,y+41,t,20,True,'middle')
f.line(450,160,450,150,True);f.line(450,309,450,351,True);f.line(450,422,450,458,True)
f.panel(610,20,270,565,'(c) 可观察的能力',GREEN)
f.text(633,112,'回放真实错误步骤',20,True);f.text(633,149,'依据可查，支持核对',18)
f.line(632,177,857,177)
f.text(633,221,'形成有序修复任务',20,True);f.text(633,258,'订正后进入独立练习',18)
f.line(632,286,857,286)
f.text(633,330,'合格证据更新估计',20,True);f.text(633,367,'辅助轨迹单独保留',18)
f.line(632,395,857,395)
f.text(633,439,'关联后续复习',20,True);f.text(633,476,'新作答进入下一轮\n不把点击视为掌握',18)
f.text(450,625,'学习成效需后续真实学生研究；图中呈现当前产品机制。',18,False,'middle');f.save()

# 02 方法框架；计算、业务、证据分区
f=Fig(2,'总体方法框架：证据、计算与业务提交分离','计算建议经业务资格校验后进入学习记录，新作答形成反馈。',760)
f.panel(20,20,860,122,'输入与学习证据',GRAY)
for x,t,b in [(40,'原始材料','题目／图片／实际步骤'),(322,'用户上下文','偏好／有效学习记忆'),(604,'来源快照','版本／指纹／记录引用')]:f.text(x,88,t,20,True);f.text(x,119,b,18)
f.line(450,143,450,175,True)
f.panel(20,177,860,206,'Python 智能计算服务：返回结构化建议',BLUE)
f.box(40,230,242,124,'诊断与规划','实际步骤关联\n任务阶段与工具选择','#ffffff');f.box(328,230,242,124,'受控工具执行','检索／判题／图形\nPydantic 结构校验','#ffffff');f.box(616,230,242,124,'验证与反馈','支持范围内符号核验\n证据不足返回待核对','#ffffff')
f.line(282,291,326,291,True);f.line(570,291,614,291,True)
f.line(450,384,450,423,True);f.label(471,411,'结构化计算结果')
f.panel(20,425,860,132,'仓颉业务控制：提交前重新校验',GREEN)
f.text(43,493,'身份／来源版本／租约／预算／当前步骤／证据资格',20,True)
f.text(43,530,'有效：事务提交结果与审计；失效：拒绝、回滚或标记 stale',18)
f.line(450,558,450,601,True)
f.rect(20,603,860,88,'#ffffff');f.text(43,639,'业务输出',20,True);f.text(170,639,'错因回放 · 订正建议 · 针对性训练 · 后续复习',20)
f.text(43,674,'MySQL 保留权威状态与历史；原始作答不会被模型解释覆盖。',18)
f.path('M860 688 L890 688 L890 159 L865 159 L865 144',True,True);f.text(450,738,'虚线反馈：学生的新作答 → 新证据 → 下一轮任务与记录',18,False,'middle');f.save()

# 03 层次架构
f=Fig(3,'系统分层架构与职责边界','仓颉负责业务事实与提交，Python负责内部智能计算。',665)
f.panel(30,20,840,110,'交互层 · uni-app / Vue 3 / TypeScript',BLUE)
f.text(52,94,'录题与校对   错因回放   修复任务   练习复习   角色页面',20)
f.line(450,131,450,177,True);f.label(470,161,'业务 HTTP API')
f.panel(30,179,840,150,'业务层 · 仓颉服务',GREEN)
f.text(52,252,'身份与权限    来源版本    持久任务    资格校验    事务提交',20)
f.text(52,296,'任务工作线程与业务路由同属当前服务进程',18)
f.line(450,330,450,374,True);f.label(470,360,'内部鉴权／结构化合同')
f.panel(30,377,840,110,'计算层 · Python / FastAPI',BLUE)
f.text(52,449,'诊断与判题    学习任务计算    认知规则    检索与工具执行',20)
f.path('M31 295 L12 295 L12 520 L158 520 L158 536');f.label(33,511,'业务读写')
f.box(30,538,257,102,'MySQL','唯一业务事实库',GREEN)
f.line(450,488,450,535,True);f.box(321,538,257,102,'Qdrant / BGE','题库索引与排序',GRAY)
f.line(740,488,740,535,True);f.box(612,538,257,102,'ApiPoolProvider','轮询访问外部 Qwen',GRAY)
f.save()

# 04 容器依赖，明确文件服务
f=Fig(4,'容器视图：信任边界与持久化依赖','学生只访问业务入口；内部计算不直接写业务数据库。',720)
f.panel(20,20,860,103,'客户端信任域',GRAY);f.text(45,91,'学生／教师／授权家长  →  uni-app 客户端',22,True)
f.line(450,124,450,172,True);f.label(470,155,'业务请求与媒体授权')
f.panel(20,174,860,330,'本地服务域（当前运行组合）',BLUE)
f.box(42,238,365,115,'仓颉业务服务','路由／任务执行器／权限／事务',GREEN)
f.box(493,238,365,115,'Python 计算服务','内部计算端点／工具／模型池','#ffffff')
f.line(408,284,491,284,True);f.label(418,260,'计算');f.line(492,322,409,322,True);f.label(420,348,'结果')
f.box(42,394,365,82,'原始文件与派生媒体','独立保留；业务鉴权访问','#ffffff')
f.line(224,354,224,391,True)
f.box(20,557,267,118,'MySQL','仓颉读写权威记录\n参数化查询／事务',GREEN)
f.box(317,557,267,118,'Qdrant 索引','计算服务检索\n命中后回查业务题库',GRAY)
f.box(614,557,267,118,'外部模型接口','ApiPoolProvider 轮询\n逻辑模型 Qwen',GRAY)
f.path('M43 309 L30 309 L30 534 L150 534 L150 555');f.path('M550 354 L550 516 L450 516 L450 555');f.path('M800 354 L800 516 L747 516 L747 555')
f.text(450,709,'实线表示调用／读写依赖；当前无独立消息队列或云对象存储。',18,False,'middle');f.save()

# 05 concrete multi-panel diagnosis with evidence zoom
f=Fig(5,'错因回放：单位换算中的实际步骤定位','学生路径与参考顺序不同；诊断引用实际步骤并保留核对等级。',700)
f.rect(20,20,860,78,GRAY);f.text(42,53,'题目示例：以 72 km/h 匀速行驶 10 s，求路程。',22,True);f.text(42,83,'以下是机制示意，不是运行截图或新增测试结果。',18)
f.panel(20,120,270,435,'(a) 学生原始作答',BLUE)
f.text(39,193,'步骤 s1',20,True);f.text(39,232,'s = vt',25)
f.rect(37,270,235,130,'#ffffff');f.text(50,307,'步骤 s2（原文）',19,True);f.text(50,350,'72 × 10 = 720 m',21)
f.text(39,451,'实际步骤 ID 与内容',18);f.text(39,485,'构成定位对象',18)
f.panel(315,120,270,435,'(b) 参考资源',GRAY)
f.text(334,193,'先换算速度',20,True);f.text(334,235,'72 km/h = 20 m/s',20)
f.text(334,307,'再计算路程',20,True);f.text(334,351,'20 × 10 = 200 m',20)
f.text(334,451,'参考第 2 步',18);f.text(334,485,'不等于学生第 2 步',18)
f.panel(610,120,270,435,'(c) 定位与证据放大',GREEN)
f.text(628,193,'首次偏差候选：s2',20,True);f.text(628,239,'km/h 与 s 未统一',19)
f.line(628,270,861,270);f.text(628,307,'引用：s2 原文 + 版本',18);f.text(628,351,'原因：换算条件遗漏',18)
f.text(628,414,'模型语义建议：待核对',18,True);f.text(628,458,'学生补充／确认／修正',18);f.text(628,500,'不伪装为符号证明',18)
f.path('M272 380 L300 380 L300 580 L745 580 L745 557',True,True)
f.rect(20,615,860,65,GRAY);f.text(42,655,'虚线关联学生 s2 与诊断引用；当前派生诊断随输入变更清除并重建。',18);f.save()

# 06 task agent nested loop
f=Fig(6,'任务驱动智能体：有界规划、工具执行与反馈','持久协调器控制任务状态，算法在预算内执行工具并返回建议。',730)
f.panel(20,20,860,125,'仓颉持久任务协调器',GREEN)
f.text(43,87,'租约领取 · 来源快照 · 版本／幂等 · 取消 · 预算 · 提交前复核',20)
f.text(43,122,'持久检查点与事件保留于 MySQL；不是多个自治 Agent 的协商网络。',18)
f.line(160,146,160,195,True);f.label(178,178,'受控上下文')
f.panel(20,197,860,365,'Python 任务计算：一次有界执行',BLUE)
f.box(43,254,250,115,'观察与规划','读取学生动作与来源\n选择阶段和下一工具','#ffffff')
f.box(335,254,250,115,'执行受控工具','判题／检索／图形\n手写识别需确认','#ffffff')
f.box(627,254,230,115,'验证与判定','结构／符号／资格\n不确定则待核对','#ffffff')
f.line(294,307,333,307,True);f.line(586,307,625,307,True)
f.rect(150,418,600,94,GREEN);f.text(450,453,'检查点：repair → independent → contrast → done',20,True,'middle');f.text(450,488,'阶段不等于任务业务状态；支持范围决定可获得的证据。',18,False,'middle')
f.path('M741 370 L741 402 L450 402 L450 417');f.path('M149 464 L85 464 L85 383 L168 383 L168 370',True,True)
f.line(750,197,750,147,True);f.label(470,179,'候选结果回交业务层')
f.rect(20,611,860,85,GRAY);f.text(43,647,'学生反馈',20,True);f.text(175,647,'补充过程／作答／确认／继续 → 新版本动作',20)
f.text(43,679,'虚线回路为预算内调整；等待学生时交还控制，不无限自主运行。',18);f.path('M21 648 L9 648 L9 103 L18 103',True,True);f.save()

# 07 sequence
f=Fig(7,'关键时序：受理回执、后台计算与读取结果','受理与结果读取分别发生，耗时计算在持久任务提交事务外。',725)
xs=[105,325,555,790]
for x,t in zip(xs,['学生端','仓颉业务服务','Python 计算','MySQL']):
 f.rect(x-90,20,180,65,BLUE);f.text(x,60,t,20,True,'middle');f.line(x,86,x,690,False,True)
def msg(a,b,y,t):
 f.line(xs[a],y,xs[b],y,True)
 mid=(xs[a]+xs[b])/2; tw=FONT.getlength(t)+12
 f.rect(mid-tw/2,y-34,tw,27,'#ffffff',0,stroke='none')
 f.text(mid,y-11,t,18,False,'middle')
msg(0,1,140,'创建／提交动作')
msg(1,3,207,'校验来源与幂等，事务建任务')
msg(1,0,251,'返回任务受理回执')
msg(1,3,300,'工作器领取租约与快照')
msg(1,2,359,'内部计算请求')
msg(2,1,416,'结构化候选结果')
f.rect(235,454,645,145,GREEN);f.text(250,487,'提交事务：重新检查租约、任务版本与来源',18,True);f.text(250,524,'有效：更新结果、事件与合格证据；失效：回滚',18)
msg(1,3,578,'提交／拒绝过期结果')
msg(0,1,627,'后续请求：读取任务状态')
msg(1,0,674,'当前状态与下一步入口')
f.save()

# 08 lifecycle custom topology avoiding false transitions
f=Fig(8,'任务生命周期：八类业务状态','完成、待核对与失效具有不同语义；完成不等于掌握。',740)
# x positions running central at440,280
nodes={'queued':(80,80),'running':(355,80),'waiting_student':(640,80),'needs_review':(640,290),'completed':(355,480),'failed':(80,290),'cancelled':(80,480),'stale':(640,480)}
for name,(x,y) in nodes.items():
 f.rect(x,y,180,80,GREEN if name in ('running','completed') else BLUE)
 f.text(x+90,y+47,name,18,True,'middle')
f.line(261,120,353,120,True);f.label(282,103,'领取')
f.path('M535 120 L638 120',True);f.label(552,103,'等待')
f.path('M730 80 L730 40 L170 40 L170 78',True);f.text(450,31,'学生新动作：waiting_student → queued',18,False,'middle')
f.path('M535 140 L600 140 L600 330 L638 330');f.label(610,264,'需核对')
f.path('M355 140 L300 140 L300 330 L262 330');f.label(224,249,'失败')
f.line(445,161,445,478,True);f.rect(357,300,176,67,'#ffffff');f.text(445,327,'执行成功',18,True,'middle');f.text(445,353,'且提交有效',18,False,'middle')
f.path('M355 150 L285 150 L285 520 L262 520');f.label(224,441,'取消')
f.line(536,520,638,520,True);f.text(587,568,'来源变化',18,False,'middle')
f.path('M535 154 L570 154 L570 493 L638 493',True,True);f.text(615,410,'来源失效',18,False,'middle')
f.rect(20,620,860,96,GRAY);f.text(41,654,'状态图为核心受控迁移；queued 亦可被取消或标记 stale。',18);f.text(41,687,'仅 running 可完成；failed／needs_review 重试须校验后回 queued。',18)
f.save()

# 09 qualification panel
f=Fig(9,'学习任务条件对照：从辅助轨迹到限定近迁移','独立、正确且适配的首次有效证据，才可进入对应认知更新。',650)
f.panel(20,20,414,465,'(a) 辅助学习轨迹',BLUE)
f.text(45,100,'查看提示／参考解析',22,True);f.text(45,142,'学生接受帮助后完成订正',20)
f.doc(45,192,362,142,'保留：学习过程','原始错误 + 提示记录\n订正内容 + 来源版本')
f.text(45,391,'不自动等同于独立作答',21,True);f.text(45,433,'不单凭任务完成更新掌握',20)
f.panel(463,20,417,465,'(b) 合格作答证据',GREEN)
f.text(489,97,'真实作答 + 判定正确',21,True)
f.text(489,148,'独立完成，未获得辅助',20)
f.text(489,197,'题目未见且内容适配',20)
f.text(489,246,'来源有效，资格满足',20)
f.text(489,295,'首次应用，避免重复计数',20)
f.line(487,329,855,329)
f.text(489,376,'满足条件 → 认知规则更新',20,True)
f.text(489,425,'条件不足 → 留存并待核对',20)
f.rect(20,532,860,94,GRAY);f.text(42,568,'近迁移证据',20,True);f.text(186,568,'限定在支持范围和当前资格内，不是远迁移能力认证。',20);f.text(42,603,'认知数值为规则估计；真实学习收益需要后续研究验证。',18);f.save()

# 10 conceptual version data
f=Fig(10,'概念数据与版本：派生结果清除与任务快照保留','编辑清除当前派生诊断；冻结任务快照按原始来源解释。',700)
f.panel(20,20,415,560,'(a) 业务实体与关联',BLUE)
f.doc(43,84,367,102,'题目与学生实际作答','题目来源／原图／实际步骤')
f.doc(43,232,367,102,'诊断与持久学习任务','引用题目、作答及来源快照')
f.doc(43,380,367,131,'学习事件与证据记录','订正／独立作答／条件对照\n认知估计／复习计划')
f.line(225,188,225,230,True);f.line(225,336,225,378,True)
f.panel(465,20,415,560,'(b) 版本关系与当前有效性',GREEN)
f.rect(490,84,365,120,'#ffffff');f.text(508,119,'来源 v1 → 诊断 d1 → 任务 t1',19,True);f.text(508,159,'任务 t1 冻结来源与事件',18)
f.rect(490,261,365,120,'#ffffff');f.text(508,296,'编辑 v2：清除诊断 d1',20,True);f.text(508,335,'重建当前分析与诊断',18)
f.line(673,206,673,259,True);f.label(689,240,'编辑')
f.text(490,438,'旧来源失效 → 旧任务 stale',20,True);f.text(490,479,'任务快照 ≠ 永久诊断表',20)
f.path('M437 285 L463 285',True,True)
f.rect(20,611,860,66,GRAY);f.text(42,652,'图为概念关系，省略低层字段；虚线表示来源引用，实线表示组织关系。',18);f.save()

# 11 permissions matrix
f=Fig(11,'角色权限矩阵：归属与授权共同决定访问','角色名称不是访问许可，班级范围与可撤回授权必须同时校验。',590)
cols=[20,240,397,554,711,880]
headers=['访问对象','学生本人','教师','家长','管理操作']
rows=[('自己的题目','本人范围','班级授权','报告范围','受限字段'),('布置与复核','参与作业','所属班级','不代替复核','受限管理'),('学习报告','本人查看','班级范围','学生授权','受限字段'),('授权撤回','可撤回','不扩大范围','可撤回','不可绕过'),('原始材料','归属校验','任务范围','不默认开放','媒体校验')]
f.rect(20,25,860,70,BLUE,0)
for j,h in enumerate(headers):f.text((cols[j]+cols[j+1])/2,68,h,19,True,'middle')
for i,row in enumerate(rows):
 y=95+i*75;f.rect(20,y,860,75,'#ffffff' if i%2==0 else GRAY,0)
 for j,t in enumerate(row):f.text((cols[j]+cols[j+1])/2,y+45,t,18,j==0,'middle')
for x in cols:f.line(x,25,x,470)
f.text(450,524,'检查：身份 → 对象归属／班级范围 → 授权有效性 → 字段与媒体访问',18,True,'middle')
f.text(450,566,'家长报告须学生明确授权；双方撤回后不能继续沿用旧授权。',18,False,'middle');f.save()

#12 deployment
f=Fig(12,'部署与故障恢复：当前本机组合及演进边界','当前验收覆盖服务组合与受测重启场景，公网交付仍需独立验收。',700)
f.panel(20,20,860,413,'(a) 当前已验证的本地运行组合',BLUE)
f.box(44,87,238,112,'浏览器 / H5','移动宽度与桌面布局\nApp 本地资源构建','#ffffff')
f.box(329,87,238,112,'仓颉业务服务','回环业务入口\n任务与识别工作线程',GREEN)
f.box(614,87,238,112,'Python 计算服务','回环内部入口\n受控算法合同','#ffffff')
f.line(283,141,327,141,True);f.line(568,141,612,141,True)
f.box(44,271,238,112,'原始与派生文件','独立保存／恢复关联','#ffffff');f.box(329,271,238,112,'MySQL','任务／快照／事件／回执',GREEN);f.box(614,271,238,112,'外部计算依赖','Qdrant 与模型接口','#ffffff')
f.line(448,200,448,269,True);f.path('M330 176 L308 176 L308 325 L284 325');f.line(733,200,733,269,True)
f.panel(20,466,860,115,'(b) 受测恢复机制',GREEN);f.text(42,530,'重启后读取持久任务 → 重新领取有效租约 → 检查点续行／幂等防重复',19)
f.rect(20,611,860,67,GRAY);f.text(42,652,'后续：HTTPS 可达业务入口、签名安装包与真机矩阵；不是当前云部署实绩。',18);f.save()

#13 mobile phases
f=Fig(13,'手机 App 路线：用交付证据区分资源构建与正式发行','复用跨端工程，按可达性、原生行为和发行验证逐步交付。',615)
for x,title,body,fill in [
 (20,'① 已有工程证据','uni-app / Vue 3\nH5 实际运行\nApp 本地资源构建',GREEN),
 (314,'② 下一交付关口','可达 HTTPS 业务入口\n应用身份与签名\n相机／相册／文件真机验证',BLUE),
 (608,'③ 后续产品验证','Android / iOS 安装验证\n设备与网络适配矩阵\n真实学生可用性与长期效果',GRAY)]:
 f.panel(x,35,272,375,title,fill);f.text(x+19,129,body,19)
 f.line(x+20,244,x+251,244);f.text(x+19,289,'验收依据',20,True)
 if x==20:f.text(x+19,330,'构建与浏览器记录\n不等于已发布安装包',18)
 elif x==314:f.text(x+19,330,'签名包与真实设备记录\n逐项检查权限和失败反馈',18)
 else:f.text(x+19,330,'可复核设备测试\n知情参与的使用研究',18)
f.rect(20,461,860,118,'#ffffff');f.text(42,502,'跨端边界',20,True);f.text(42,542,'客户端保持交互与受控渲染；数据、业务校验与智能计算继续由服务端承担。',18);f.save()

#14 student journey noncards swimlane
f=Fig(14,'学生使用旅程：冷启动到持续修复的分层导航','无历史时给出学习入口，有历史后以真实任务与复习组织下一步。',670)
f.rect(20,20,860,98,BLUE);f.text(43,58,'首页：今日',23,True);f.text(43,95,'新用户：年级／学科方向与知识入口     有记录：修复任务与到期复习',19)
xs=[130,450,770]
for x,label in zip(xs,['收录与校对','理解与订正','练习与复习']):
 f.circ(x,208,44,GREEN);f.text(x,215,label[:2],22,True,'middle');f.text(x,284,label,22,True,'middle')
f.line(176,208,404,208,True);f.line(496,208,724,208,True)
f.text(130,335,'保留原图与实际作答\n识别结果支持校正',18,False,'middle')
f.text(450,335,'错因回放与依据核对\n修复路线给出下一步',18,False,'middle')
f.text(770,335,'先独立作答再判定\n复习保留真实反馈',18,False,'middle')
f.rect(20,423,860,133,GRAY);f.text(42,461,'跨页面可追溯入口',21,True);f.text(42,504,'易错地图 → 对应原题 → 当前诊断／任务／历史记录',20);f.text(42,539,'主操作保持清晰；详细依据进入二级页面，避免首页一次堆叠全部信息。',18)
f.path('M770 575 L770 609 L130 609 L130 575',True,True);f.text(450,645,'新证据改变后续任务与复习优先级，不凭空生成能力画像。',18,False,'middle');f.save()

#15 three evidence paths, different admission and signed updates
f=Fig(15,'复习、任务与练习：不同写入目标和证据门槛','任务正向对照与练习正负证据分开准入；复习不直接更新认知。',720)
f.rect(20,20,860,89,GRAY);f.text(42,56,'共同约束：本人实际作答、有效来源与业务资格',22,True);f.text(42,92,'各路径按自身合同核对；不能把任务的正确对照门槛套给全部练习。',18)
for x in [20,315,610]:f.line(x+135,111,x+135,150,True)
f.panel(20,152,270,424,'(a) 复习',BLUE)
f.text(39,234,'作答 → 判题与反馈',19,True);f.text(39,280,'待核对时阻止确定更新',18)
f.line(39,313,270,313);f.text(39,356,'复习回执与记录',20,True);f.text(39,400,'规则间隔／下次计划',18)
f.text(39,464,'可进入有效学习记忆',18);f.text(39,513,'不直接更新掌握估计',18,True)
f.panel(315,152,270,424,'(b) 持久学习任务',GREEN)
f.text(334,234,'可验证的条件对照',20,True);f.text(334,280,'独立、正确、未曝光',18)
f.line(334,313,565,313);f.text(334,356,'answer + contrast',19,True);f.text(334,400,'来源有效且尚未应用',18)
f.text(334,464,'限定近迁移正向证据',18);f.text(334,513,'任务完成本身不足',18,True)
f.panel(610,152,270,424,'(c) 独立题库练习',GREEN)
f.text(629,234,'曾提供、内容适配',20,True);f.text(629,280,'同题同模式不重复',18)
f.line(629,313,860,313);f.text(629,356,'判题确认正确或错误',19,True);f.text(629,400,'允许 can_update_learning',18)
f.text(629,464,'正向／负向规则证据',18);f.text(629,513,'不保证远迁移能力',18,True)
f.path('M450 578 L450 612 L745 612 L745 578',False)
f.rect(315,630,565,65,'#ffffff');f.text(336,671,'任务／练习 → 仓颉事务保存认知规则估计',19,True);f.save()
(OUT/'titles.json').write_text(json.dumps(TITLES,ensure_ascii=False,indent=2))
print(f'Generated {len(TITLES)} SVG/PNG pairs in {OUT}')
