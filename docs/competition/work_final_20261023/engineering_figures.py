"""Engineering views: distinct notation, topology and restrained color families."""
def draw(F):
 def rect(f,x,y,w,h,col='#FFFFFF',radius=0):
  f.parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="{col}" stroke="#596575" stroke-width="2"/>')
 def oval(f,x,y,w,h,t,col):
  f.parts.append(f'<ellipse cx="{x}" cy="{y}" rx="{w/2}" ry="{h/2}" fill="{col}" stroke="#826C52" stroke-width="2"/>');f.text(x,y+9,t,27)
 def dot(f,x,y,r=7):f.parts.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="#596575"/>')
 # Use cases: actor, subject boundary, ovals; warm ochre.
 f=F();f.text(610,58,'学生使用范围',32,True);rect(f,280,90,855,565,'#FFFCF5')
 f.parts.append('<circle cx="115" cy="285" r="24" fill="#F2DBA9" stroke="#826C52" stroke-width="3"/>')
 for a in [(115,309,115,400),(65,345,165,345),(115,400,75,460),(115,400,155,460)]:f.line(*a,False)
 f.text(115,515,'学生',29,True)
 for x,y,t in [(510,190,'录入与整理'),(900,190,'查看与订正'),(510,370,'类似题练习'),(900,370,'模拟考试'),(510,550,'到期复习'),(900,550,'学习记录')]:
  oval(f,x,y,285,100,t,'#F3E5C6')
 for y in [190,370,550]:f.path(f'M165,345 L235,345 L235,{y} L367,{y}',False)
 for y in [190,370,550]:f.path(f'M235,{y+70} L900,{y+70} L900,{y+50}',False)
 f.line(235,190,235,620,False)
 f.save('11-usecases')
 # Dependency as packages and interface connectors, jade.
 f=F();f.text(600,52,'业务模块与算法入口',32,True)
 def package(x,y,w,h,title,body):
  rect(f,x,y,w,h,'#F0F7F3');rect(f,x,y-22,145,22,'#BFD8C8');f.text(x+w/2,y+45,title,28,True)
  for i,t in enumerate(body):f.text(x+w/2,y+92+i*36,t,24)
 package(55,110,310,195,'题目业务',['录入 · 编辑 · 分析','原图与题目保存'])
 package(445,110,310,195,'学习业务',['任务 · 练习 · 复习','进度与作答保存'])
 package(835,110,310,195,'账户与资源',['身份 · 归属 · 文件','公共访问检查'])
 rect(f,55,390,1090,65,'#D0E4D8');f.text(600,432,'仓颉算法客户端',29,True)
 for x in [210,600]:f.line(x,305,x,390)
 f.line(835,208,755,208,False);f.text(795,183,'检查',22)
 for x,t in [(210,'分析与诊断'),(600,'任务计算'),(990,'判题与补题')]:
  f.line(x,455,x,535);dot(f,x,495,8);f.box(x-155,535,310,100,t,'#F7F8F5',round=0)
 f.save('12-components')
 # State view: core cycle and peripheral stops, restrained plum.
 f=F();f.text(600,50,'任务执行状态',32,True);dot(f,55,160,11)
 for x,t in [(110,'排队'),(465,'执行'),(820,'等待学生')]:f.box(x,110,270,100,t,'#E6DDEB',round=34)
 f.line(66,160,110,160);f.line(380,160,465,160);f.text(422,135,'领取',22)
 f.line(735,160,820,160);f.text(777,135,'返回',22)
 f.path('M955,110 L955,82 L245,82 L245,110');f.text(600,106,'提交合法新动作',22)
 for x,t in [(110,'待核对'),(465,'失败'),(820,'完成')]:f.box(x,405,270,95,t,'#F4EFF6',round=24)
 f.path('M520,210 L520,345 L245,345 L245,405');f.line(600,210,600,405);f.path('M680,210 L680,345 L955,345 L955,405')
 f.text(315,385,'需核对',22);f.text(660,385,'失败',22);f.text(1020,385,'结束',22)
 rect(f,110,575,980,82,'#F6F2ED');f.text(600,625,'取消 / 来源失效：终止当前计算结果的采用',27)
 f.save('13-states')
 # Physical data subset with multiplicities, slate and cream.
 f=F();f.text(600,50,'任务记录的数据关系',32,True)
 def entity(x,y,w,title,rows):
  rect(f,x,y,w,150,'#FFFFFF');rect(f,x,y,w,44,'#D6E4ED');f.text(x+w/2,y+30,title,26,True)
  for i,t in enumerate(rows):f.text(x+18,y+84+i*35,t,22,anchor='start')
 entity(55,100,300,'users',['PK  id','学生身份'])
 entity(845,100,300,'questions',['PK  id','题目材料'])
 entity(435,315,330,'learning_tasks',['PK  id','FK  user_id / question_id'])
 f.path('M205,250 L205,390 L435,390',False);f.text(225,285,'1',23);f.text(405,368,'多',23)
 f.path('M995,250 L995,390 L765,390',False);f.text(975,285,'1',23);f.text(795,368,'多',23)
 for x,title,row in [(55,'task_actions','请求 · 动作 · 结果'),(435,'task_steps','工具 · 核验 · 轨迹'),(815,'task_requests','请求编号 · 内容摘要')]:
  entity(x,550,330,title,['FK  task_id',row])
  f.path(f'M600,465 L600,510 L{x+165},510 L{x+165},550',False)
 f.text(660,495,'1 → 多',22)
 f.text(600,84,'下方三个表名省略 learning_ 前缀',22);f.save('14-relations')
 # Navigation as tab strip and branches with mobile icons, coral + sand.
 f=F();f.text(600,50,'页面组织与返回位置',32,True)
 for i,(t,items) in enumerate([('今日',['当前任务','到期复习']),('错题',['错题列表','题目详情']),('学习',['专项练习','模拟考试']),('我的',['个人资料','学习记录'])]):
  x=45+i*290;rect(f,x,110,240,70,'#EFD7CC',12);f.text(x+120,155,t,29,True)
  f.line(x+120,180,x+120,240,False)
  for j,a in enumerate(items):
   y=260+j*140;rect(f,x+24,y,192,82,'#FCF5E9',4);f.text(x+120,y+50,a,26)
   if j==0:f.line(x+120,y+82,x+120,y+140,False)
 rect(f,240,570,720,75,'#F4F2EF');f.text(600,617,'题目详情承接分析、订正与类似题入口',27)
 f.save('15-navigation')
 # Trust boundaries with open lanes and gates, icy blue.
 f=F();f.text(600,50,'请求进入系统的检查位置',32,True)
 for x,w,title,col in [(40,290,'学生设备','#EDF4FA'),(400,355,'业务服务','#DCEAF4'),(835,325,'内部计算','#F1F4F6')]:
  rect(f,x,100,w,485,col);f.text(x+w/2,145,title,28,True)
 for y,a,b,t in [(240,115,575,'访问自己的题目'),(360,575,1000,'发送必要计算材料'),(480,1000,575,'返回计算结果')]:
  f.line(a,y,b,y);f.text((a+b)/2,y-22,t,24)
 f.text(575,305,'认证与归属',26,True);f.text(575,540,'版本检查与保存',26,True)
 f.text(185,540,'不持有模型凭据',24)
 f.text(1000,540,'不写业务数据库',24)
 f.text(600,655,'显示内容 → 受控规格；业务写入 → 仓颉接口',27)
 f.save('16-boundaries')
 # Deployment with device, host, disks and external service, olive/sand.
 f=F();f.text(600,50,'本地运行部署',32,True)
 rect(f,40,210,195,250,'#F8F4E7',15);rect(f,60,240,155,160,'#FFFFFF',3);f.text(137,300,'浏览器',27,True);f.text(137,350,'H5 页面',25);f.line(105,430,170,430,False)
 rect(f,330,95,535,525,'#F3F5E9',8);f.text(597,140,'Linux 主机',30,True)
 f.box(365,190,465,90,'仓颉业务进程','#DDE4C4',round=2)
 f.box(365,355,465,90,'Python 算法进程','#E9E8D7',round=2)
 f.line(235,300,330,300);f.path('M330,300 L345,300 L345,235 L365,235');f.line(597,280,597,355)
 for x,t in [(440,'MySQL'),(710,'原图与文件')]:
  f.box(x-105,510,210,70,t,'#FFFFFF',round=3,size=25)
 f.path('M365,235 L350,235 L350,495 L440,495 L440,510');f.path('M830,235 L848,235 L848,495 L710,495 L710,510')
 f.box(935,180,225,100,'Qwen 服务','#F0DFC0',round=20);f.box(935,395,225,100,['检索资源','Qdrant / BGE'],'#ECEFE3',round=2,size=24)
 f.path('M830,400 L900,400 L900,230 L935,230');f.path('M830,420 L895,420 L895,445 L935,445')
 f.save('17-deployment')
 # Validation matrix: evidence mapping, no numeric outcome invented.
 f=F();f.text(600,50,'不同测试回答不同问题',32,True)
 cols=[90,365,665,965];labels=['验证层次','主要对象','发现的问题','不能替代']
 for x,t in zip(cols,labels):f.text(x,125,t,25,True,anchor='start')
 rows=[('规则测试','公式与分支','计算及条件错误','学生学习实验'),('接口测试','请求与保存','归属及提交冲突','模型准确率评估'),('浏览器测试','页面与操作','跳转及反馈错误','原生安装验收'),('部署检查','进程与依赖','启动及连接失败','完整业务回归')]
 for i,row in enumerate(rows):
  y=170+i*115;rect(f,55,y,1090,95,['#E7EEF0','#F4EBDA','#E9EEE0','#F1E6E7'][i])
  for x,t in zip(cols,row):f.text(x,y+55,t,24,anchor='start')
 f.save('18-validation')
