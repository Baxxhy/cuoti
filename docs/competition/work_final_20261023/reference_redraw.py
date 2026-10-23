"""Reference-inspired composition only; project facts remain unchanged."""
def redraw(F):
 def rect(f,x,y,w,h,c='#FFFFFF',stroke='#6686AA',r=8):
  f.parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{c}" stroke="{stroke}" stroke-width="2"/>')
 def doc(f,x,y,label,c='#E4EDF9'):
  f.parts.append(f'<path d="M{x},{y} h58 l18,18 v82 h-76 Z M{x+58},{y} v18 h18" fill="{c}" stroke="#6686AA" stroke-width="2"/>')
  for dy in [40,55,70]:f.line(x+14,y+dy,x+60,y+dy,False)
  f.text(x+38,y+135,label,25)
 def disk(f,x,y,w,h,label,col):
  f.parts.append(f'<path d="M{x},{y+15} v{h-30} C{x},{y+h+8} {x+w},{y+h+8} {x+w},{y+h-15} V{y+15}" fill="{col}" stroke="#6686AA" stroke-width="2"/><ellipse cx="{x+w/2}" cy="{y+15}" rx="{w/2}" ry="15" fill="{col}" stroke="#6686AA" stroke-width="2"/>');f.text(x+w/2,y+h/2+12,label,25)
 # Method overview: layer labels and nested computation, rather than four equal cards.
 f=F()
 layers=[(55,165,'输入材料','#E3EFFB'),(235,230,'算法处理','#E3F2E9'),(510,150,'业务保存','#EEE7F8')]
 for y,h,title,c in layers:
  f.text(110,y+55,title,29,True);rect(f,235,y,925,h,c)
 for x,t in [(290,'题目与原图'),(580,'学生作答'),(870,'学习记录')]:
  doc(f,x,70,t); # miniature documents; label belongs to this input item
 # overwrite input miniature label placement fits layer by drawing simplified icons instead
 # Algorithm modules grouped in two complementary rows.
 for x,y,t,sub in [(265,260,'错因定位','原步骤与依据'),(700,260,'掌握评估','正误与帮助条件'),(265,370,'学习规划','阶段与可用时间'),(700,370,'习题补充','检索与生成')]:
  rect(f,x,y,395,75,'#FFFFFF',stroke='#6C9A83',r=4);f.text(x+110,y+31,t,26,True);f.text(x+250,y+60,sub,23)
 f.line(695,220,695,235)
 f.text(700,550,'仓颉业务服务',29,True)
 for x,t in [(410,'来源与版本'),(700,'任务与事件'),(990,'学习记录')]:
  rect(f,x-120,580,240,55,'#FFFFFF',stroke='#9384AD',r=3);f.text(x,616,t,25)
 f.line(695,465,695,510);f.path('M1160,592 L1182,592 L1182,120 L1160,120',dash=True)
 f.save('01')
 # Deployment: white host boundary, device/server/file/storage pictograms.
 f=F();f.text(600,48,'本地运行部署',31,True)
 rect(f,300,85,590,580,'#FFFFFF',r=14);f.text(595,125,'Linux 主机',29,True)
 rect(f,30,230,190,220,'#EDF4FC',r=14);rect(f,49,252,152,135,'#FFFFFF',r=3)
 f.text(125,310,'浏览器',26,True);f.text(125,352,'H5 页面',24);f.line(95,420,155,420,False)
 for y,title,c in [(175,'仓颉业务服务','#DCEBFA'),(370,'Python 算法服务','#DDF0E7')]:
  rect(f,350,y,490,110,c,r=6)
  for i in range(3):
   rect(f,370,y+20+i*24,55,16,'#FFFFFF',r=2)
   f.parts.append(f'<circle cx="380" cy="{y+28+i*24}" r="3" fill="#6686AA"/>')
  f.text(620,y+63,title,28,True)
 f.path('M220,310 L270,310 L270,230 L350,230');f.line(595,285,595,370)
 disk(f,350,550,205,85,'MySQL','#E4EDF9');doc(f,715,515,'原图与文件','#EEE7F8')
 f.path('M350,250 L320,250 L320,520 L450,520 L450,550');f.path('M840,250 L870,250 L870,520 L753,520 L753,515')
 rect(f,945,175,220,105,'#EEE7F8',stroke='#9384AD',r=10);f.text(1055,237,'AI 模型',26,True)
 disk(f,945,400,220,110,'Qdrant','#E2F2EF');f.text(1055,558,'BGE 表示与重排',23)
 f.path('M840,405 L915,405 L915,230 L945,230');f.path('M840,445 L915,445 L915,455 L945,455')
 f.save('17-deployment')
