"""Distinct visual grammars for scenes, infrastructure, evidence and state data."""
from html import escape

def redraw(F):
 def raw(f,s): f.parts.append(s)
 def rect(f,x,y,w,h,fill='#FFFFFF',stroke='#536570',rx=3):
  raw(f,f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" stroke="{stroke}" stroke-width="2"/>')
 def ellipse(f,x,y,rx,ry,fill):
  raw(f,f'<ellipse cx="{x}" cy="{y}" rx="{rx}" ry="{ry}" fill="{fill}" stroke="#536570" stroke-width="2"/>')
 def paper(f,x,y,w,h,fill='#F6F1E7'):
  rect(f,x+9,y+9,w,h,'#F0F1F2');rect(f,x,y,w,h,fill)
  f.line(x+22,y+38,x+w-22,y+38,False)
 def db(f,x,y,w,h,fill='#E0ECE9'):
  raw(f,f'<path d="M{x},{y+16} L{x},{y+h-16} C{x},{y+h+7} {x+w},{y+h+7} {x+w},{y+h-16} L{x+w},{y+16}" fill="{fill}" stroke="#536570" stroke-width="2"/>');ellipse(f,x+w/2,y+16,w/2,16,fill)
 def server(f,x,y):
  for i in range(3):
   rect(f,x,y+i*21,58,16,'#FFFFFF',rx=3)
   raw(f,f'<circle cx="{x+10}" cy="{y+i*21+8}" r="3" fill="#779593"/>')
 def node(f,x,y,w,title,rows,fill):
  rect(f,x,y,w,145,'white');rect(f,x,y,w,42,fill)
  f.text(x+18,y+29,title,24,True,'start')
  for i,t in enumerate(rows):f.text(x+18,y+76+i*32,t,23,anchor='start')
 # Motivation as three pieces of student work rather than a software pipeline.
 f=F();f.text(600,52,'从学生的一份错题出发',32,True)
 for x,n,title in [(55,'01','定位错误'),(445,'02','获得帮助'),(835,'03','再次独立作答')]:
  f.text(x,119,n,25,True,'start');f.text(x+165,119,title,28,True);paper(f,x,150,310,350)
 f.text(210,220,'3x + 2 = 17',28);f.text(210,283,'3x = 17 + 2',28)
 raw(f,'<ellipse cx="262" cy="275" rx="49" ry="26" fill="none" stroke="#AA7464" stroke-width="3"/>')
 f.text(210,361,'移项后的符号',25);f.text(210,405,'需要回到原步骤核对',23)
 f.text(600,220,'为什么要变号？',26)
 f.line(490,260,710,260,False);f.text(600,312,'先理解等式性质',25);f.text(600,359,'再完成自己的订正',25)
 f.text(990,220,'2x − 3 = 11',28)
 for y in [280,333,386]:f.line(875,y,1105,y,False)
 f.text(990,450,'不用提示，重新尝试',23)
 f.line(375,320,435,320);f.line(765,320,825,320)
 f.text(600,580,'错误理解、所需帮助与后续表现，是三个不同的学习问题',27)
 f.text(600,637,'题目与作答过程为示意材料',22);f.save('00-background')
 # Infrastructure: device silhouettes, server racks, database cylinders and file stacks.
 f=F();f.text(55,50,'学生端',28,True,'start');f.text(465,50,'应用服务',28,True,'start');f.text(960,50,'数据与资源',28,True,'start')
 rect(f,30,85,290,560,'#F1F5F8',stroke='#C3D1DB',rx=18)
 rect(f,72,135,86,150,'white',rx=12);rect(f,81,152,68,103,'#DFEAF2',rx=2);f.line(105,272,127,272,False)
 rect(f,175,175,104,78,'white');f.line(227,253,227,280,False);f.line(200,280,254,280,False)
 f.text(175,348,'uni-app',30,True);f.text(175,394,'Vue 页面 · 多端复用',24);f.text(175,454,'录题与作答',26);f.text(175,495,'反馈与历史',26)
 rect(f,400,105,415,210,'#E5EFEC',stroke='#A1B9AD',rx=6);server(f,425,132)
 f.text(640,162,'仓颉业务服务',29,True);f.text(608,226,'身份权限 · 任务状态',25);f.text(608,267,'数据交互 · 事务保存',25)
 rect(f,400,425,415,210,'#EFEDF4',stroke='#B5ADC7',rx=6);server(f,425,450)
 f.text(640,480,'Python 算法服务',28,True);f.text(608,544,'FastAPI 内部接口',25);f.text(608,587,'诊断 · 评估 · 规划 · 补题',24)
 f.line(320,210,400,210);f.line(607,315,607,425);f.text(690,373,'算法调用',23)
 db(f,930,105,200,105);f.text(1030,168,'MySQL',27,True)
 paper(f,952,246,156,70,'#F5EFE4');f.text(1030,304,'原图与文件',23)
 f.path('M815,195 L875,195 L875,160 L930,160');f.path('M875,195 L875,280 L952,280')
 rect(f,900,419,260,215,'#FCFAF5',stroke='#CEBDA1',rx=6)
 f.text(1030,465,'Qwen 模型',27,True);f.line(920,485,1140,485,False)
 db(f,920,510,48,75,'#F1E5CF');f.text(1050,540,'Qdrant 索引',24);f.text(1030,602,'BGE 表示与重排',23)
 f.line(815,530,900,530)
 f.text(600,693,'箭头：调用方向    圆柱：数据存储    叠页：文件资源',23);f.save('03')
 # Diagnosis as annotated evidence comparison with a shared qualification rail.
 f=F();f.text(55,52,'(a) 原作答中的首次偏差',29,True,'start');f.text(670,52,'(b) 前序材料尚不充分',29,True,'start')
 paper(f,55,85,510,385,'#F0F5F2');paper(f,635,85,510,385,'#F8F2EA')
 for x in [310,890]:f.text(x,157,'原题：2x + 3 = 11',29)
 f.text(110,230,'2x = 8',30,anchor='start');f.text(425,230,'前序成立',24)
 f.text(110,305,'x = 5',30,anchor='start');f.text(425,305,'解发生变化',24)
 raw(f,'<path d="M99,321 L255,321" stroke="#AC796B" stroke-width="4"/>')
 f.text(310,408,'第二步可确认为首错',27,True)
 f.text(890,230,'此前步骤尚未核验',26);f.text(890,305,'后续一步发现不等价',26);f.text(890,408,'保留错误候选，继续核对',25,True)
 f.text(600,535,'来源匹配 → 证据排序 → 前缀核对',29,True)
 f.text(600,590,'S = I_s + 2I_r + I_f + 0.5I_k − 4I_c',28)
 f.text(600,659,'排序分比较依据；首错判断还需要此前各步成立',25);f.save('04')
 # Mastery as analytic evidence/estimate strips; values are rule demonstrations.
 f=F();f.text(55,52,'(a) 有效作答与权重',29,True,'start')
 f.text(55,108,'来源当前、判定明确、完整作答、未重复',26,anchor='start')
 f.text(55,153,'局部或失效记录保留原状态；完整答案曝光不作独立证据',24,anchor='start')
 f.line(55,189,1145,189,False)
 f.text(55,239,'(b) 同一起点，不同帮助条件',29,True,'start')
 colors=['#9EBBAE','#B7AEC9','#C9CDD1'];labels=['独立答对  w=1','提示后答对  w=0.35','答案曝光'];values=[.913957,.608193,.35]
 for i,(lab,v,col) in enumerate(zip(labels,values,colors)):
  y=300+i*78;f.text(55,y+8,lab,25,anchor='start');f.line(455,y,1040,y,False)
  rect(f,455,y-10,585*v,20,col,stroke=col,rx=0)
  raw(f,f'<circle cx="{455+585*v}" cy="{y}" r="7" fill="#536570"/>')
  f.text(1120,y+8,f'{v:.3f}',26)
 f.text(455,506,'0',22);f.text(1040,506,'1',22);f.text(730,506,'掌握估计',23)
 f.text(600,565,'p′ = pL₁ʷ / [pL₁ʷ + (1−p)L₀ʷ]',28)
 f.text(600,613,'答对后：p″ = p′ + (1−p′)λ min(w,1)',27)
 f.text(600,680,'先验 p=0.35；默认规则演算，不代表学生实验结果',24);f.save('05')
 # Data diagram: entity tables and a distinct historical-version strip.
 f=F();f.text(55,45,'(a) 核心记录关联',29,True,'start')
 node(f,45,95,300,'题目与来源',['原题 · 原图 · 原作答','当前来源版本'],'#E5EEF4')
 node(f,450,95,300,'实际步骤',['步骤ID与原文','作答顺序'],'#E3EEE7')
 node(f,855,95,300,'诊断结果',['错误候选与引用','核对状态'],'#EDE9F2')
 node(f,45,325,300,'学习任务',['冻结来源快照','任务版本'],'#F4EBDD')
 node(f,450,325,300,'学习事件',['学生回答与帮助','判定结果'],'#E5EEF4')
 node(f,855,325,300,'检查点',['当前阶段与进度','已保存结果'],'#E3EEE7')
 for y in [167,397]:f.line(345,y,450,y);f.line(750,y,855,y)
 f.line(195,240,195,325)
 f.text(55,535,'(b) 原题编辑后',29,True,'start');f.line(95,595,1105,595,False)
 for x,head,sub in [(180,'原题 v1 → v2','内容来源改变'),(600,'旧任务快照','保留当时材料'),(1020,'后续提交','重新核对来源')]:
  raw(f,f'<circle cx="{x}" cy="595" r="7" fill="#849CA9"/>');f.text(x,574,head,25,True);f.text(x,648,sub,24)
 f.save('09')
