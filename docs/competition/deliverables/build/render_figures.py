"""Render evidence-grounded HLD figures at a fixed A4-readable logical width.

Source of truth: explicit node positions, routes and labels below. SVG text stays
editable; companion DOT retains node/relationship semantics, MMD is the original
reviewed design. At 16.2 cm output width, 13 px labels are 9.33 pt. The manifest
records the minimum recommended placed height; do not shrink tall figures into
10.6 cm frames. No business code or external model calls are involved.
"""
from pathlib import Path
from xml.sax.saxutils import escape
import json
import subprocess
import cairosvg

F = Path(__file__).resolve().parents[1] / 'figures'
T = {'01':'产品学习闭环','02':'系统上下文','03':'整体分层架构','04':'C4容器架构','05':'核心模块职责','06':'采集结构化流程','07':'诊断证据传递','08':'智能体执行时序','09':'任务生命周期','10':'验证驱动学习阶段','11':'学习记录掌握复习','12':'概念数据关系','13':'角色权限边界','14':'当前运行拓扑','15':'异常恢复提交保护','16':'手机交付路线'}
NAVY='#173B63'; TEAL='#168C89'; TEXT='#203C53'; LINE='#658092'; GRAY='#F2F6FA'
manifest=[]
class Figure:
 def __init__(self,k,h):
  self.k=k;self.h=h;self.nodes={};self.edges=[];self.smallest=15
  self.parts=[f'<svg xmlns="http://www.w3.org/2000/svg" width="640" height="{h}" viewBox="0 0 640 {h}" role="img"><title>{escape(T[k])}</title><defs><marker id="a" markerWidth="7" markerHeight="7" refX="6.3" refY="3.5" orient="auto"><path d="M0 0L7 3.5L0 7Z" fill="{LINE}"/></marker><marker id="t" markerWidth="7" markerHeight="7" refX="6.3" refY="3.5" orient="auto"><path d="M0 0L7 3.5L0 7Z" fill="{TEAL}"/></marker></defs><rect width="640" height="{h}" fill="white"/>']
 def text(self,x,y,s,size=15,color=TEXT,anchor='middle',bold=False):
  self.smallest=min(self.smallest,size)
  for i,line in enumerate(s.split('\n')):
   self.parts.append(f'<text x="{x}" y="{y+i*(size+6)}" text-anchor="{anchor}" font-family="Noto Sans CJK SC, sans-serif" font-size="{size}" font-weight="{600 if bold else 400}" fill="{color}">{escape(line)}</text>')
 def panel(self,x,y,w,h,label,planned=False):
  self.parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="{GRAY}" stroke="#D8E3EC"'+(' stroke-dasharray="6 4"' if planned else '')+'/>')
  self.text(x+14,y+25,label,14,NAVY,'start',True)
 def box(self,id,x,y,w,h,label,tone='light',shape='box'):
  self.nodes[id]=(x,y,w,h,label)
  fill= NAVY if tone=='main' else '#E8F5F1' if tone=='teal' else '#FFFFFF'
  stroke= NAVY if tone=='main' else '#70B9AE' if tone=='teal' else '#B9CBD8'
  if shape=='ellipse':self.parts.append(f'<ellipse cx="{x+w/2}" cy="{y+h/2}" rx="{w/2}" ry="{h/2}" fill="{fill}" stroke="{stroke}" stroke-width="1.2"/>')
  else:self.parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="7" fill="{fill}" stroke="{stroke}" stroke-width="1.2"/>')
  lines=label.split('\n'); self.text(x+w/2,y+h/2-(len(lines)-1)*10.5+5,label,15,'white' if tone=='main' else TEXT,bold=tone=='main')
 def pos(self,id,side):
  x,y,w,h,_=self.nodes[id]
  return {'n':(x+w/2,y),'s':(x+w/2,y+h),'e':(x+w,y+h/2),'w':(x,y+h/2)}[side]
 def arrow(self,a,b,sidea='s',sideb='n',via=(),label='',at=None,dash=False):
  self.edges.append((a,b,label,dash)); pts=[self.pos(a,sidea),*via,self.pos(b,sideb)];self.route(pts,label,at,dash)
 def route(self,pts,label='',at=None,dash=False):
  d='M'+' L'.join(f'{x},{y}' for x,y in pts)
  self.parts.append(f'<path d="{d}" fill="none" stroke="{TEAL if dash else LINE}" stroke-width="1.5" marker-end="url(#{"t" if dash else "a"})"'+(' stroke-dasharray="5 4"' if dash else '')+'/>')
  if label:
   if at is None:at=((pts[0][0]+pts[-1][0])/2,(pts[0][1]+pts[-1][1])/2-6)
   x,y=at;w=max(len(line) for line in label.split('\n'))*13+10
   self.parts.append(f'<rect x="{x-w/2}" y="{y-14}" width="{w}" height="{len(label.split(chr(10)))*19}" rx="3" fill="white"/>');self.text(x,y,label,13)
 def rule(self,y,label):
  self.parts.append(f'<path d="M24 {y}H616" stroke="#D8E3EC"/>');self.text(30,y+23,label,13,LINE,'start')
 def save(self):
  p=F/f'{self.k}_{T[self.k]}';svg=''.join(self.parts)+'</svg>';p.with_suffix('.svg').write_text(svg)
  cairosvg.svg2png(bytestring=svg.encode(),write_to=str(p.with_suffix('.png')),scale=2.5)
  dot=['digraph G {','graph [layout=neato,overlap=false,splines=polyline];','node [shape=box,fontname="Noto Sans CJK SC"];']
  for id,(x,y,w,h,label) in self.nodes.items():
   dot.append(f'{id} [label={json.dumps(label,ensure_ascii=False)},pos="{(x+w/2)/72},{(self.h-y-h/2)/72}!",width="{w/72}",height="{h/72}"];')
  for a,b,label,dash in self.edges:dot.append(f'{a} -> {b} [label={json.dumps(label,ensure_ascii=False)}'+(',style=dashed' if dash else '')+'];')
  dot.append('}')
  if self.k=='13':
   matrix=[('身份','可访问范围','服务端准入依据'),('学生','本人题目、作答、任务','当前身份与本人归属'),('家长','已关联学生学习摘要','有效关联关系'),('教师','本人班级、作业与复核','角色与班级归属'),('管理员','受控工作台与审计字段','专用权限与字段白名单')]
   cells=''.join('<TR>'+''.join('<TD>'+escape(cell)+'</TD>' for cell in row)+'</TR>' for row in matrix)
   dot=['digraph G {','node [shape=plain,fontname="Noto Sans CJK SC"];','matrix [label=<<TABLE BORDER="0" CELLBORDER="1" CELLSPACING="0" CELLPADDING="14">'+cells+'</TABLE>>];','}']
  p.with_suffix('.dot').write_text('\n'.join(dot))
  # 16.2 cm = 459.213 pt; fixed 640 logical width gives an exact scale.
  manifest.append({'id':self.k,'name':T[self.k],'logical_width':640,'logical_height':self.h,'width_cm':16.2,'natural_height_cm':round(self.h/640*16.2,2),'min_font_px':self.smallest,'min_font_pt_at_16_2_cm':round(self.smallest*459.213/640,2),'min_placed_height_cm_for_9pt':round(self.h*9/(self.smallest*72/2.54),2)})

# 01: a compact two-column journey, with an outside evidence feedback loop.
f=Figure('01',450)
for id,x,y,label,tone in [('a',36,24,'采集与校对\n原题与原始作答','main'),('b',354,24,'证据驱动诊断\n首错位置与依据','light'),('c',354,156,'回放与易错地图\n关联具体原题','light'),('d',36,156,'修复任务\n订正与独立作答','teal'),('e',36,288,'支持时条件对照\n验证单一条件变化','teal'),('g',354,288,'学习记录与复习\n产生新的学习表现','light')]:f.box(id,x,y,250,72,label,tone)
f.arrow('a','b','e','w');f.arrow('b','c');f.arrow('c','d','w','e');f.arrow('d','e');f.arrow('e','g','e','w');f.arrow('g','c','e','e',[(624,324),(624,192)],dash=True)
f.rule(390,'真实学习记录影响下一步；未支持的题型不强行生成对照。');f.save()
# 02: context, not container internals.
f=Figure('02',455)
for id,x,y,label,tone in [('s',28,25,'学生\n录题、学习、复习','light'),('t',350,25,'教师 / 家长 / 管理员\n各自授权范围内协作','light'),('sys',160,175,'错题帮学习系统','main'),('q',28,325,'外部 Qwen 模型\n提供结构化候选','teal'),('b',350,325,'题库与知识资料\n导入、映射与索引','light')]:f.box(id,x,y,262 if id!='sys' else 320,76,label,tone)
f.arrow('s','sys',via=[(159,135),(320,135)]);f.arrow('t','sys',via=[(481,135),(320,135)]);f.arrow('sys','q',via=[(320,285),(159,285)]);f.arrow('b','sys',sidea='n',sideb='e',via=[(481,290),(560,290),(560,213)])
f.rule(420,'角色边界由服务端校验，外部能力不直接维护学生业务状态。');f.save()
# 03: horizontal layers, storage and algorithm dependencies separated.
f=Figure('03',570)
f.box('u',44,20,552,58,'移动交互｜uni-app · Vue 3 · TypeScript','main');f.box('j',44,125,552,66,'仓颉业务｜身份、题目、任务、学习状态','main')
f.arrow('u','j',label='业务 API',at=(320,106))
f.box('m',30,245,270,66,'MySQL 与受控文件\n业务事实、原图与派生资源','teal');f.box('p',340,245,270,66,'Python 智能计算\n识别、诊断、策略、核验')
f.arrow('j','m',via=[(320,220),(165,220)]);f.arrow('j','p',via=[(320,220),(475,220)])
f.box('r',30,385,270,70,'BGE / Qdrant\n嵌入、召回与重排');f.box('q',340,385,270,70,'ApiPoolProvider → Qwen\n模型请求与轮询')
f.arrow('p','r',via=[(475,350),(165,350)]);f.arrow('p','q')
f.rule(500,'算法返回结构化结果；仓颉核对依据并决定业务事务提交。');f.save()
# 04: C4 container distinctions, no artificial microservices.
f=Figure('04',625)
f.panel(16,92,608,457,'系统边界：当前主线运行单元')
f.box('u',180,12,280,54,'用户浏览器 / 未来手机 App');f.box('c',160,138,320,62,'uni-app 客户端\nH5 / App 前端资源','main');f.arrow('u','c',label='交互',at=(320,118))
f.box('j',160,245,320,70,'仓颉业务服务\nAPI 与进程内 worker','main');f.arrow('c','j',label='JSON / 上传',at=(320,230))
f.box('m',34,370,174,68,'MySQL\n业务事实','teal');f.box('p',233,370,174,68,'Python / FastAPI\n内部算法');f.box('a',432,370,174,68,'受控本地文件\n媒体与导出','teal')
f.arrow('j','m',via=[(320,343),(121,343)]);f.arrow('j','p');f.arrow('j','a',via=[(320,343),(519,343)])
f.box('b',50,477,228,50,'BGE / Qdrant 检索组件');f.box('q',350,565,256,48,'Qwen 外部模型服务')
f.arrow('p','b',via=[(320,459),(164,459)]);f.arrow('p','q',sidea='s',sideb='n',via=[(320,459),(630,459),(630,554),(478,554)],label='经模型池',at=(478,547))
f.save()
# 05: module responsibility matrix plus dependency spine.
f=Figure('05',545)
f.panel(20,20,600,430,'仓颉业务服务：按学习事实组织内部模块')
f.box('a',48,72,240,60,'身份与数据权限','main');f.box('c',352,72,240,60,'题目与原始作答')
f.box('d',352,184,240,60,'分析诊断与来源证据');f.box('t',48,184,240,60,'学习任务与检查点','main')
f.box('p',48,300,240,60,'练习、作业与教师复核');f.box('e',352,300,240,60,'有效学习事件','teal')
f.box('r',48,386,240,46,'复习与记录');f.box('v',352,386,240,46,'易错地图与学习报告')
f.arrow('a','c','e','w');f.arrow('c','d');f.arrow('d','t','w','e');f.arrow('t','p');f.arrow('p','e','e','w');f.arrow('d','e');f.arrow('e','v');f.arrow('p','r')
f.box('x',100,485,440,48,'Python 内部计算：规划、工具与核验');f.arrow('t','x','w','w',via=[(10,214),(10,509)],dash=True)
f.save()
# 06: branching capture pipeline and explicit original/derived separation.
f=Figure('06',555)
f.box('a',28,20,264,58,'拍照 / 相册选择');f.box('m',356,20,256,58,'手动录入')
f.box('b',28,126,264,64,'保存原始图片','main');f.box('o',356,126,256,64,'原图资产保留\n不被清洁图覆盖','teal')
f.arrow('a','b');f.arrow('b','o','e','w',dash=True)
f.box('c',28,236,264,64,'裁剪与预处理\n保存派生图片');f.box('d',356,236,256,64,'识别结构化候选\n题干、选项、作答');f.arrow('b','c');f.arrow('c','d','e','w')
f.box('e',180,356,280,64,'学生校对与确认','teal');f.arrow('d','e',via=[(484,328),(320,328)]);f.arrow('m','e','e','e',via=[(630,49),(630,388)])
f.box('f',180,468,280,64,'仓颉保存题目与作答\n再启动分析与诊断','main');f.arrow('e','f',label='确认版本',at=(320,450));f.save()
# 07: evidence lineage, parallel inputs then guarded persistence.
f=Figure('07',570)
for id,x,label in [('q',22,'原题与条件'),('s',232,'学生步骤 ID'),('r',442,'参考步骤 ID')]:f.box(id,x,20,176,55,label)
f.box('snap',130,125,380,58,'仓颉：冻结输入快照','main')
for id in ('q','s','r'):f.arrow(id,'snap',via=[(f.pos(id,'s')[0],101),(320,101)])
f.box('py',30,240,270,74,'Python 语义诊断\n结构化候选与定位');f.box('v',340,240,270,74,'规则 / SymPy\n支持范围内核验','teal');f.arrow('snap','py',via=[(320,211),(165,211)]);f.arrow('py','v','e','w')
f.box('res',130,369,380,58,'首错位置、作用域、验证状态');f.arrow('v','res',via=[(475,341),(320,341)])
f.box('save',30,480,270,64,'仓颉：复核来源与版本\n保存诊断和证据','main');f.box('ui',340,480,270,64,'回放与地图\n核验结果 / 待核对');f.arrow('res','save',via=[(320,453),(165,453)]);f.arrow('save','ui','e','w');f.save()
# 08: deliberately drawn sequence with short labels above every message.
f=Figure('08',650);xs=[70,242,414,576]
for i,(x,label) in enumerate(zip(xs,['学生前端','仓颉协调器','MySQL','Python工具'])):
 f.box('lane'+str(i),x-60,14,120,46,label,'main');f.parts.append(f'<path d="M{x} 62 V620" stroke="#BBCBD7" stroke-dasharray="5 5"/>')
msgs=[(0,1,'① 动作与版本'),(1,2,'② 幂等保存'),(1,0,'③ 已受理'),(1,2,'④ 领取 / 读来源'),(1,3,'⑤ 上下文与预算'),(3,3,'规划 → 工具 → 核验'),(3,1,'⑥ 结果与证据'),(1,2,'⑦ 重验并事务提交'),(0,1,'⑧ 查询任务'),(1,0,'⑨ 当前一步与反馈')]
for i,(a,b,label) in enumerate(msgs):
 y=103+i*52
 if a==b:f.route([(xs[a],y),(620,y),(620,y+20),(xs[a],y+20)]);f.text(554,y-10,label,13,anchor='end')
 else:f.route([(xs[a],y),(xs[b],y)]);f.text((xs[a]+xs[b])/2,y-10,label,13)
 f.edges.append(('lane'+str(a),'lane'+str(b),label,False))
f.rule(616,'等待与查询分离：计算在服务端推进，业务状态保存在 MySQL。');f.save()
# 09: normal transitions plus explicit grouped exceptional-state rules.
f=Figure('09',650)
f.box('q',36,30,244,62,'排队 queued','teal',shape='ellipse');f.box('r',360,30,244,62,'执行 running','main');f.arrow('q','r','e','w',label='领取',at=(320,54))
f.box('w',36,180,244,70,'等待学生\nwaiting_student','teal',shape='ellipse');f.box('n',360,180,244,70,'待核对\nneeds_review','teal',shape='ellipse')
f.arrow('r','w',via=[(482,130),(158,130)]);f.arrow('r','n');f.arrow('w','q','w','w',via=[(18,215),(18,61)],dash=True);f.text(100,116,'有效动作后重新排队',13,anchor='start')
f.arrow('n','q','e','n',via=[(625,215),(625,12),(158,12)],dash=True)
f.box('c',36,335,244,64,'完成 completed','teal',shape='ellipse');f.box('e',360,335,244,64,'失败 failed',shape='ellipse')
f.arrow('r','c','s','n',via=[(320,113),(320,300),(158,300)]);f.arrow('r','e','e','e',via=[(615,61),(615,367)])
f.panel(22,444,596,176,'异常与终止规则：保持历史，不允许迟到结果写入')
f.text(40,490,'• failed：仅在允许恢复且预算未耗尽时回到 queued。',14,anchor='start')
f.text(40,521,'• 活跃 / 可重试任务：主动结束 → cancelled。',14,anchor='start')
f.text(40,552,'• 除 cancelled / stale 外，来源变更 → stale。',14,anchor='start')
f.text(40,583,'• running 租约过期可重新领取；完成不等于掌握。',14,anchor='start')
f.save()
# 10: learning stages are distinct from execution states.
f=Figure('10',610)
f.box('s',180,20,280,56,'当前原题与诊断','main');f.box('r',28,130,264,70,'支持时局部订正\nrepair');f.box('i',356,130,256,70,'原题独立作答\nindependent','main')
f.arrow('s','r',via=[(320,100),(160,100)]);f.arrow('s','i',via=[(320,100),(484,100)]);f.arrow('r','i','e','w')
f.box('t',356,267,256,70,'适用时条件对照\ncontrast','teal');f.box('d',28,267,264,70,'当前任务完成\ndone')
f.arrow('i','t',label='有已验证对照',at=(484,242));f.arrow('i','d',via=[(484,228),(160,228)],label='无适用对照',at=(185,219));f.arrow('t','d','w','e')
f.panel(28,390,584,172,'学习更新的独立门槛')
f.text(48,436,'条件对照确认正确，且独立、未重复曝光、来源有效。',14,anchor='start');f.text(48,471,'满足业务准入 → 一次近迁移证据与后续复习安排。',14,anchor='start');f.text(48,510,'证据不足时补充作答或核对；不直接记作确定成功。',14,anchor='start');f.save()
# 11: review attempts do NOT automatically call cognition updates.
f=Figure('11',610)
f.panel(18,18,604,268,'路径 A：满足准入的任务 / 练习证据 → 认知更新')
f.box('a',36,72,260,60,'任务 / 专项练习结果');f.box('v',354,72,250,60,'核验与资格准入','main');f.arrow('a','v','e','w')
f.box('c',354,189,250,64,'认知规则计算');f.box('m',36,189,260,64,'掌握 / 误区状态\n及认知更新记录','teal');f.arrow('v','c');f.arrow('c','m','w','e')
f.panel(18,312,604,165,'路径 B：复习作答 → 记录与下次计划')
f.box('r',36,366,260,72,'复习作答与核对');f.box('p',354,366,250,72,'复习记录\n更新下次计划','teal');f.arrow('r','p','e','w')
f.box('mem',36,527,260,60,'有效记忆与学习建议');f.box('self',354,527,250,60,'自检要点：学生自述')
f.arrow('p','mem',via=[(479,501),(166,501)]);f.arrow('m','mem','w','w',via=[(8,221),(8,557)],dash=True);f.arrow('self','mem','w','e',dash=True);f.save()
# 12: a conceptual model, not a dense physical ERD.
f=Figure('12',620)
f.box('u',180,16,280,50,'用户：学习数据归属','main');f.box('q',180,108,280,50,'错题：关联学习材料');f.arrow('u','q',label='1 : N',at=(320,92))
f.box('a',22,222,180,66,'原始作答\n与学生步骤');f.box('d',230,222,180,66,'分析、诊断\n与证据');f.box('t',438,222,180,66,'学习任务','main')
for id in ('a','d','t'):f.arrow('q',id,via=[(320,193),(f.pos(id,'n')[0],193)])
f.box('s',22,380,180,66,'冻结来源\n每任务至多一份');f.box('act',230,380,180,66,'动作与工具轨迹\n每任务可有多条');f.box('self',438,380,180,66,'自检要点\n每任务至多一份')
for id in ('s','act','self'):f.arrow('t',id,via=[(528,335),(f.pos(id,'n')[0],335)])
f.box('m',22,532,280,60,'掌握估计与认知更新');f.box('r',338,532,280,60,'复习计划与复习记录')
f.arrow('u','m','w','w',via=[(10,41),(10,562)],dash=True);f.arrow('q','r','e','e',via=[(630,133),(630,562)],dash=True);f.save()
# 13: role/scope/enforcement matrix; avoids eight parallel arrows.
f=Figure('13',490)
cols=[28,130,365,612];rowtops=[82,160,238,316]
f.parts.append(f'<rect x="28" y="20" width="584" height="50" rx="6" fill="{NAVY}"/>')
f.text(78,51,'身份',15,'white',bold=True);f.text(245,51,'可访问范围',15,'white',bold=True);f.text(486,51,'服务端准入依据',15,'white',bold=True)
rows=[('学生','本人题目、作答、任务','当前身份与本人归属'),('家长','已关联学生学习摘要','有效关联关系'),('教师','本人班级、作业与复核','角色与班级归属'),('管理员','受控工作台与审计字段','专用权限与字段白名单')]
for y,(role,scope,gate) in zip(rowtops,rows):
 f.parts.append(f'<rect x="28" y="{y}" width="584" height="66" fill="{GRAY}"/>');f.text(78,y+39,role,15,bold=True);f.text(245,y+39,scope,14);f.text(486,y+39,gate,14)
 for x in cols[1:-1]:f.parts.append(f'<path d="M{x} {y+8}V{y+58}" stroke="#D1DEE8"/>')
f.rule(409,'内部算法另用服务认证；手机与浏览器不直连 MySQL / 算法服务。')
f.text(30,465,'受控资源仍需校验访问资格；仅知道记录 ID 不能绕过权限。',13,LINE,'start');f.save()
# 14: actual local topology, clearly separate external model provider.
f=Figure('14',590)
f.box('u',180,10,280,50,'开发浏览器');f.panel(20,95,600,390,'当前本地主机运行示例')
f.box('v',160,145,320,56,'Vite H5 前端 :5174','main');f.box('c',160,245,320,62,'仓颉业务服务 :8002\nAPI 与进程内 worker','main');f.arrow('u','v');f.arrow('v','c',label='开发代理',at=(320,229))
f.box('m',34,370,174,64,'MySQL\n环境配置端口','teal');f.box('p',233,370,174,64,'Python :8012\n内部算法');f.box('a',432,370,174,64,'本地媒体\n与导出','teal')
for id in ('m','p','a'):f.arrow('c',id,via=[(320,339),(f.pos(id,'n')[0],339)])
f.box('b',34,526,270,50,'BGE / Qdrant 检索');f.box('q',350,526,256,50,'外部 Qwen 模型池')
f.arrow('p','b',via=[(320,508),(169,508)]);f.arrow('p','q',via=[(320,508),(478,508)]);f.save()
# 15: failure and late-result branches are outside guarded happy path.
f=Figure('15',630)
f.box('a',28,20,270,62,'已受理动作与检查点','main');f.box('b',354,20,258,62,'worker 领取租约');f.arrow('a','b','e','w')
f.box('c',354,151,258,62,'有界算法计算');f.box('r',28,151,270,62,'重启 / 租约过期\n重新领取后计算');f.arrow('b','c');f.arrow('r','c','e','w',dash=True)
f.box('d',180,292,280,64,'提交前复核\n来源、版本、租约','main');f.arrow('c','d',via=[(483,254),(320,254)])
f.box('e',28,443,270,72,'同一事务保存\n轨迹、检查点、合法证据','teal');f.box('x',354,443,258,72,'取消 / 失效 / 版本变化\n丢弃迟到结果')
f.arrow('d','e',via=[(320,404),(163,404)],label='核对通过',at=(163,393));f.arrow('d','x',via=[(320,404),(483,404)])
f.rule(557,'计算失败给出恢复入口；request_id 与唯一约束防止重复写入。');f.text(30,611,'超过预算或不具备恢复条件时明确暂停，保留已有记录。',13,LINE,'start');f.save()
# 16: compact vertical delivery roadmap; completed base vs planned stages.
f=Figure('16',625)
f.box('a',40,18,560,68,'当前已验证基础\nuni-app 工程、H5 运行、App 本地资源构建','main')
f.panel(20,126,600,405,'后续手机交付路线（规划）',planned=True)
f.box('d',44,179,250,86,'01 发行准备\nAppID、包标识\n可达 HTTPS 业务地址');f.box('e',348,179,250,86,'02 设备联调\n相机、权限、公式\n文件与任务恢复');f.arrow('a','d',via=[(320,108),(169,108)]);f.arrow('d','e','e','w')
f.box('f',348,360,250,86,'03 分平台签名安装\nAndroid / iOS\n分别产出与验证','teal');f.box('g',44,360,250,86,'04 独立验收与维护\n设备记录、升级保留\n数据与版本回归','teal');f.arrow('e','f');f.arrow('f','g','w','e')
f.text(40,500,'前置条件：签名材料、开发者账户、测试设备。',14,anchor='start');f.rule(565,'资源构建不等于 APK / IPA；服务端继续承担模型计算与业务数据。');f.save()
(F/'readability_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
print('已生成16张可读SVG/PNG及DOT；最小边注13px，16.2cm宽时≥9.3pt。')
for x in manifest: print(f"{x['id']}  建议高度{x['natural_height_cm']}cm  最小字{x['min_font_pt_at_16_2_cm']}pt")
