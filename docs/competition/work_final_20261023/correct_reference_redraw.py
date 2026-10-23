"""Corrected user reference: blue/teal semantic icons and hub/layer compositions."""
def redraw(F):
 def finish(f,name):
  f.parts=[p.replace('#596575','#337EC4') for p in f.parts]
  f.parts=[p.replace('stroke="#337EC4"','stroke="#20A58E"') if 'stroke-dasharray' in p else p for p in f.parts]
  f.save(name)
 def rect(f,x,y,w,h,c='#FFFFFF',r=8):
  f.parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{c}" stroke="#83A8CF" stroke-width="2"/>')
 def ring(f,x,y,r):
  for rr,c in [(r+20,'#F1F6FC'),(r+10,'#E2EEFB'),(r,'#CDE3FA')]:
   f.parts.append(f'<circle cx="{x}" cy="{y}" r="{rr}" fill="{c}"/>')
 def icon(f,x,y,kind):
  if kind=='device':
   rect(f,x,y,43,66,'white',6);rect(f,x+6,y+9,31,42,'#E3EFFB',1);f.line(x+13,y+59,x+30,y+59,False)
  elif kind=='paper':
   f.parts.append(f'<path d="M{x},{y} h42 l14,14 v52 h-56 Z M{x+42},{y} v14 h14" fill="white" stroke="#2877CD" stroke-width="2.5"/>')
   for dy in [27,39,51]:f.line(x+11,y+dy,x+44,y+dy,False)
  elif kind=='book':
   f.parts.append(f'<path d="M{x},{y+8} Q{x+15},{y-2} {x+30},{y+8} Q{x+45},{y-2} {x+60},{y+8} v47 Q{x+45},{y+37} {x+30},{y+48} Q{x+15},{y+37} {x},{y+47} Z M{x+30},{y+8} v40" fill="white" stroke="#2877CD" stroke-width="2.5"/>')
  else:
   for i in range(3):
    rect(f,x,y+i*22,60,17,'white',3)
    f.parts.append(f'<circle cx="{x+10}" cy="{y+i*22+8}" r="3" fill="#2681DA"/>')
 def card(f,x,y,w,h,title,sub,c='#EAF3FE',kind='paper'):
  rect(f,x,y,w,h,c);f.parts.append(f'<rect x="{x}" y="{y+12}" width="5" height="{h-24}" fill="#267CDD"/>')
  icon(f,x+20,y+25,kind);f.text(x+w/2+25,y+48 if sub else y+h/2+10,title,28,True)
  if sub:f.text(x+w/2+25,y+90,sub,24)
 def db(f,x,y,w,h,title):
  f.parts.append(f'<path d="M{x},{y+15} v{h-30} C{x},{y+h+8} {x+w},{y+h+8} {x+w},{y+h-15} V{y+15}" fill="#E2F4EF" stroke="#51A895" stroke-width="2"/><ellipse cx="{x+w/2}" cy="{y+15}" rx="{w/2}" ry="15" fill="#D6EEE7" stroke="#51A895" stroke-width="2"/>');f.text(x+w/2,y+h/2+12,title,26,True)
 # Background: three needs orbit the same student problem, not a proposed algorithm.
 f=F();f.text(600,55,'中学生错题学习问题链',34,True)
 ring(f,600,335,100);f.text(600,325,'错题学习',32,True);f.text(600,370,'原题与本人作答',23)
 card(f,50,170,380,135,'错误理解','原作答哪里出现偏差',kind='book')
 card(f,770,170,380,135,'针对性帮助','当前困难需要什么支持','#E3F4EF',kind='book')
 card(f,410,530,380,135,'独立作答','新问题能否自行完成','#E9F0FC')
 f.line(430,250,500,302);f.line(700,302,770,250);f.line(600,435,600,530)
 f.path('M230,170 C300,82 900,82 960,170');f.path('M960,305 C1010,450 940,560 790,585');f.path('M410,585 C260,560 185,430 230,305')
 finish(f,'00-background')
 # Technical route: input evidence, four explicit computations, business output.
 f=F();f.text(600,48,'错题帮总体技术路线',32,True)
 rect(f,30,100,230,530,'#F7FAFE');f.text(145,143,'输入材料',29,True)
 for y,t in [(190,'题目与原图'),(335,'学生作答'),(480,'学习记录')]:
  icon(f,70,y,'paper');f.text(145,y+100,t,25)
 ring(f,600,345,98);f.text(600,330,'Python',30,True);f.text(600,376,'算法计算',28,True)
 for x,y,t,c in [(410,170,'错因定位','#E0EEFD'),(790,170,'掌握评估','#DDF3EC'),(410,520,'学习规划','#E2F2F7'),(790,520,'习题补充','#E5ECFA')]:
  f.circle(x,y,68,t,c)
 f.line(260,345,482,345);f.line(465,217,525,275,False);f.line(735,217,675,275,False);f.line(525,415,465,473,False);f.line(675,415,735,473,False)
 rect(f,940,100,235,530,'#F7FCFA');f.text(1057,143,'仓颉业务',28,True)
 for y,t in [(210,'来源与版本'),(350,'任务与事件'),(490,'学习记录')]:
  rect(f,960,y,195,80,'#E2F3ED');f.text(1057,y+50,t,26)
 f.line(718,345,940,345)
 f.path('M1057,630 L1057,680 L145,680 L145,630',dash=True)
 finish(f,'01')
 # Architecture: nested runtime tiers with actual service boundaries and storage icons.
 f=F();f.text(600,47,'系统组成与调用关系',32,True)
 card(f,45,95,760,125,'uni-app 学生端','','#E4F0FD',kind='device')
 card(f,45,285,760,140,'仓颉业务服务','','#E7F3FC',kind='server')
 card(f,45,505,760,150,'Python 算法服务','','#E2F3ED',kind='server')
 f.line(425,220,425,285);f.text(550,266,'业务请求',24)
 f.line(425,425,425,505);f.text(550,478,'内部计算',24)
 db(f,940,270,220,95,'MySQL');icon(f,950,392,'paper');f.text(1090,440,'原图与文件',25)
 f.path('M805,345 L900,345 L900,318 L940,318');f.path('M900,345 L900,425 L950,425')
 rect(f,910,515,270,145,'#EDF4FC');f.text(1045,558,'AI 模型',28,True);f.text(1045,604,'Qdrant / BGE',25);f.text(1045,640,'检索资源',24)
 f.line(805,580,910,580)
 finish(f,'03')
