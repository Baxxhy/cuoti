"""Original motion graphics for the competition demo; actual UI remains unaltered."""
from pathlib import Path
import subprocess,math,json
from PIL import Image,ImageDraw,ImageFont
import numpy as np
import imageio_ffmpeg
B=Path(__file__).resolve().parent;ROOT=B.parents[2];O=ROOT/'.runtime/competition-video/edit';O.mkdir(parents=True,exist_ok=True)
FF=imageio_ffmpeg.get_ffmpeg_exe();F='/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc';FB='/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc'
INK='#15243B';BLUE='#2454CE';MUTED='#52647B';BG='#F6F8FC'
def font(s,b=False):return ImageFont.truetype(FB if b and Path(FB).exists() else F,s)
def text(d,xy,t,s=42,c=INK,b=False):d.text(xy,t,font=font(s,b),fill=c)
def ease(x):return 1-(1-max(0,min(1,x)))**3
def duration(p):
 r=subprocess.run([FF,'-i',str(p)],capture_output=True,text=True)
 import re
 m=re.search(r'Duration: (\d+):(\d+):([\d.]+)',r.stderr);return int(m[1])*3600+int(m[2])*60+float(m[3])
def draw(t,total,ending=False):
 im=Image.new('RGB',(1920,1080),BG);d=ImageDraw.Draw(im)
 # restrained editorial grid; no external image assets or template footage
 d.rectangle((0,0,16,1080),fill=BLUE);d.line((110,100,1810,100),fill='#DDE5EF',width=2)
 text(d,(110,46),'错题帮  /  2026 仓颉杯',25,BLUE,True)
 text(d,(110,1015),'学生使用情境 · 手机浏览器实录 · 中文合成旁白',23,MUTED)
 if ending:
  text(d,(110,165),'把学习接起来',88,INK,True)
  text(d,(114,300),'从一道错题，到下一次独立作答。',43,MUTED)
  nodes=[('诊断','找到具体偏差'),('订正','修复关键一步'),('验证','改变条件再做'),('复习','留下后续安排')]
  for i,(a,b) in enumerate(nodes):
   a0=ease((t-i*.7)/1.3);x=140+i*440;y=int(505+40*(1-a0));
   if a0>0:
    d.ellipse((x,y,x+94,y+94),fill=['#E6EDFF','#E5F1EB','#FFF0DC','#EDE9F7'][i],outline='#C7D4E6',width=2)
    text(d,(x+25,y+20),str(i+1),37,BLUE,True);text(d,(x,y+130),a,48,INK,True);text(d,(x,y+205),b,30,MUTED)
    if i<3:d.line((x+134,y+47,x+385,y+47),fill='#BBC9DB',width=3)
  text(d,(114,895),'仓颉业务服务  ·  Python智能计算  ·  uni-app跨端界面',29,MUTED)
 elif t<7:
  p=ease(t/1.7);x=int(110-60*(1-p));text(d,(x,205),'错题帮',156,INK,True)
  d.rectangle((114,405,114+int(580*ease((t-.6)/1.7)),413),fill=BLUE)
  text(d,(114,475),'让每一道错题，成为下一步。',53,INK)
  text(d,(118,605),'初二学生小林的一次完整学习',34,MUTED)
  d.rounded_rectangle((1320,225,1765,795),radius=20,fill='white',outline='#D7E1EE',width=2)
  text(d,(1360,275),'我的错题',30,MUTED);text(d,(1360,390),'3x + 2 = 17',43,INK,True)
  text(d,(1360,495),'3x = 17 + 2',42,BLUE)
  d.line((1360,565,1710,565),fill='#E0E7F1',width=2);text(d,(1360,625),'从这一步开始检查',29,MUTED)
 elif t<17:
  text(d,(110,165),'整理之后，怎样学会？',78,INK,True)
  questions=[('01','哪里开始偏差','保留原作答，回到具体步骤'),('02','换个条件还会吗','重新作答，区分帮助与表现'),('03','今天先复习什么','关联记录，形成可执行安排')]
  for i,(n,a,b) in enumerate(questions):
   k=ease((t-7-i*.9)/1.2);x=int(114+70*(1-k));y=335+i*190
   if k>0:
    text(d,(x,y),n,42,BLUE,True);text(d,(x+110,y-6),a,49,INK,True);text(d,(x+110,y+70),b,32,MUTED)
  d.line((112,938,1808,938),fill='#DDE5EF',width=2)
 else:
  text(d,(110,165),'一条可以继续的学习路线',76,INK,True)
  stages=['录入','诊断','订正','验证','复习'];p=(t-17)/max(1,total-17)
  for i,label in enumerate(stages):
   x=155+i*345;y=430;active=p>(i*.14)
   fill=['#E7EFFF','#E7F2ED','#FFF0DC','#EBE9F8','#E7EFFF'][i]
   d.ellipse((x,y,x+130,y+130),fill=fill if active else '#EDF1F6',outline=BLUE if active else '#C6D2E1',width=3)
   text(d,(x+48,y+29),str(i+1),46,BLUE if active else MUTED,True);text(d,(x+12,y+170),label,51,INK,True)
   if i<4:
    end=x+292;d.line((x+153,y+65,end,y+65),fill=BLUE if active else '#C6D2E1',width=3);d.polygon([(end,y+65),(end-13,y+58),(end-13,y+72)],fill=BLUE if active else '#C6D2E1')
  text(d,(114,790),'原始材料  →  实际作答  →  学习记录  →  后续任务',36,MUTED)
  text(d,(114,880),'接下来，进入真实系统。',40,BLUE,True)
 # Narration caption is outside the animation's content area.
 data=json.loads((B/'narration.json').read_text())['outro' if ending else 'intro']['text']
 chunks=[]
 for sentence in __import__('re').split(r'(?<=[。！？；])',data):
  while len(sentence)>43:chunks.append(sentence[:43]);sentence=sentence[43:]
  if sentence:chunks.append(sentence)
 weights=[len(c) for c in chunks];at=max(0,(t-.7)/max(1,total-2.5))*sum(weights);acc=0
 if .7<=t<=total-1.8:
  for sentence,weight in zip(chunks,weights):
   acc+=weight
   if at<=acc:
    d.rectangle((105,926,1815,980),fill=BG)
    f=font(31);tx=(1920-f.getlength(sentence))/2;d.text((tx,934),sentence,font=f,fill=INK);break
 d.rectangle((110,987,110+int(1700*min(1,t/total)),992),fill=BLUE)
 return im
if __name__=='__main__':
 import sys
 kind=sys.argv[1] if len(sys.argv)>1 else 'intro';voice=ROOT/f'.runtime/competition-video/voices/{kind}.mp3';total=duration(voice)+2.5
 dest=O/(kind+'.mp4');log=(O/(kind+'-ffmpeg.log')).open('w')
 cmd=[FF,'-y','-f','rawvideo','-pixel_format','rgb24','-video_size','1920x1080','-framerate','25','-i','pipe:0','-i',str(voice),'-filter_complex','[1:a]adelay=700|700,apad[a]','-map','0:v','-map','[a]','-t',str(total),'-c:v','libx264','-preset','fast','-crf','20','-pix_fmt','yuv420p','-c:a','aac','-b:a','160k','-movflags','+faststart',str(dest)]
 proc=subprocess.Popen(cmd,stdin=subprocess.PIPE,stderr=log)
 for i in range(math.ceil(total*25)):proc.stdin.write(draw(i/25,total,kind=='outro').tobytes())
 proc.stdin.close();assert proc.wait()==0;log.close();draw(total/2,total,kind=='outro').save(O/(kind+'-preview.png'));print(kind,total,dest,flush=True)
