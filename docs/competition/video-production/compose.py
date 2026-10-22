"""Compose real mobile recordings with editorial framing, narration and captions."""
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
import json,subprocess,re,math,hashlib
import imageio_ffmpeg
B=Path(__file__).resolve().parent;R=B.parents[2];WORK=R/'.runtime/competition-video';O=WORK/'edit';O.mkdir(parents=True,exist_ok=True)
FF=imageio_ffmpeg.get_ffmpeg_exe();REG='/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc';BOLD='/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc'
def font(size,b=False):return ImageFont.truetype(BOLD if b and Path(BOLD).exists() else REG,size)
def dur(p):
 q=subprocess.run([FF,'-i',str(p)],capture_output=True,text=True);m=re.search(r'Duration: (\d+):(\d+):([\d.]+)',q.stderr)
 return int(m[1])*3600+int(m[2])*60+float(m[3])
def wrap(t,width,size):
 f=font(size);lines=[];s=''
 for c in t:
  if f.getlength(s+c)>width:lines.append(s);s=c
  else:s+=c
 if s:lines.append(s)
 return lines

def background(n,total,scene,portrait=False):
 W,H=(1080,2400) if portrait else (1920,1080);im=Image.new('RGB',(W,H),'#F6F8FC');d=ImageDraw.Draw(im)
 blue='#2454CE';ink='#15243B';gray='#52647B'
 if portrait:
  d.text((55,28),'错题帮  /  手机浏览器实录',font=font(27,True),fill=blue)
  d.text((55,79),scene['title'],font=font(35,True),fill=ink)
  d.rounded_rectangle((96,150,984,2078),radius=22,fill='white',outline='#CAD6E6',width=3)
  if scene.get('note'):
   for j,line in enumerate(wrap(scene['note'],970,26)):
    d.text((55,2112+j*38),line,font=font(26),fill=blue)
  d.rectangle((55,2335,55+int(970*(n+1)/total),2340),fill=blue)
 else:
  d.rectangle((0,0,14,H),fill=blue);d.text((110,60),'错题帮',font=font(38,True),fill=blue)
  d.text((110,119),'2026 仓颉杯 · 学生完整使用演示',font=font(25),fill=gray)
  d.text((110,216),f'{n+1:02d}',font=font(106,True),fill='#CFDBEF')
  y=367
  for line in wrap(scene['title'],900,65):d.text((110,y),line,font=font(65,True),fill=ink);y+=90
  y+=36
  for point in scene.get('points',[])[:3]:
   d.ellipse((115,y+15,125,y+25),fill=blue);d.text((149,y),point,font=font(30),fill=gray);y+=65
  d.rounded_rectangle((1138,47,1586,1033),radius=28,fill='white',outline='#CAD6E6',width=3)
  d.text((1638,70),'手机端',font=font(25,True),fill=blue)
  d.text((1638,116),'真实操作',font=font(23),fill=gray)
  d.text((1638,155),'真实反馈',font=font(23),fill=gray)
  d.line((110,929,1008,929),fill='#DAE2EF',width=2)
  d.rectangle((110,988,110+int(898*(n+1)/total),993),fill=blue)
  d.text((110,1018),f'功能实录  {n+1:02d} / {total:02d}',font=font(23),fill=gray)
  if scene.get('note'):d.text((110,866),scene['note'],font=font(24),fill=blue)
 return im

def ass(scene,length,path,portrait=False):
 W,H=(1080,2400) if portrait else (1920,1080)
 # Captions sit outside the phone viewport, keeping controls and results legible.
 fs=36 if portrait else 32;cx,cy=(540,2220) if portrait else (558,820)
 chunks=[]
 for sentence in re.split(r'(?<=[。！？；])',scene['text']):
  sentence=sentence.strip()
  if not sentence:continue
  chunks.extend(wrap(sentence,930 if portrait else 900,fs))
 voice=dur(path.with_suffix('.mp3')) if path.with_suffix('.mp3').exists() else length-2
 weights=[max(2,len(c)) for c in chunks];total=sum(weights);clock=.7
 def tm(x):return f'{int(x//3600)}:{int(x//60)%60:02d}:{int(x)%60:02d}.{int(x*100)%100:02d}'
 header=f'''[Script Info]\nScriptType: v4.00+\nPlayResX: {W}\nPlayResY: {H}\nWrapStyle: 2\n[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\nStyle: Narration,Noto Sans CJK SC,{fs},&H003B2415,&H003B2415,&H00FCF8F6,&H00FCF8F6,0,0,0,0,100,100,0,0,1,2,0,5,30,30,40,1\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n'''
 events=[]
 for c,w in zip(chunks,weights):
  dt=voice*w/total;events.append(f'Dialogue: 0,{tm(clock)},{tm(clock+dt)},Narration,,0,0,0,,{{\\pos({cx},{cy})\\fad(80,80)}}{c}');clock+=dt
 path.write_text(header+'\n'.join(events))
 return [(round(.7+sum(weights[:i])/total*voice,3),round(.7+sum(weights[:i+1])/total*voice,3),c) for i,c in enumerate(chunks)]

if __name__=='__main__':
 import sys,shutil
 mode=sys.argv[1] if len(sys.argv)>1 else 'landscape';portrait=mode=='portrait'
 only=next((set(x.split('=',1)[1].split(',')) for x in sys.argv if x.startswith('--only=')),None)
 clips=json.loads((WORK/'take2/clips.json').read_text());narr=json.loads((B/'narration.json').read_text())
 # These captures finished their visible operation before a recording-selector
 # timeout. Retain only the independently checked successful portions, never
 # the timeout, failed login attempt, or an unconfirmed result.
 partial={'24-variation-answer','39-review-answer','41-review-schedule','51-password-login'}
 selected=[c for c in clips if (c['status']=='ok' or c['id'] in partial) and c['id'] in narr]
 raw=Path((WORK/'take2/raw-path.txt').read_text().strip());manifest=[]
 for i,c in enumerate(selected):
  key=c['id'];scene=narr[key];stem=key+('-portrait' if portrait else '');dest=O/(stem+'.mp4');voice=WORK/'voices'/f'{key}.mp3'
  assert voice.exists(),key
  audio=dur(voice);rawlen=c['end']-c['start'];length=max(rawlen,audio+2)
  # Avoid prolonged dead waiting; trim only explicitly reviewed ranges in edit_ranges.json.
  edits=json.loads((B/'edit_ranges.json').read_text()) if (B/'edit_ranges.json').exists() else {}
  ranges=edits.get(key,[[0,rawlen]])
  playable=sum(b-a for a,b in ranges);length=max(playable,audio+2)
  bg=O/(stem+'-bg.png');background(i,len(selected),scene,portrait).save(bg)
  sub=O/(stem+'.ass');shutil.copyfile(voice,sub.with_suffix('.mp3'));captions=ass(scene,length,sub,portrait)
  targetW,targetH=(864,1872) if portrait else (432,936);x,y=(108,177) if portrait else (1146,72)
  # Native recording content occupies top-left 432×936; padded encoder canvas is discarded.
  filterParts=[]
  for j,(a,b) in enumerate(ranges):filterParts.append(f'[1:v]trim=start={a}:end={b},setpts=PTS-STARTPTS[v{j}]')
  if len(ranges)>1:filterParts.append(''.join(f'[v{j}]' for j in range(len(ranges)))+f'concat=n={len(ranges)}:v=1:a=0[real]')
  else:filterParts.append('[v0]null[real]')
  # Extend only the final real frame when narration needs more time; no accelerated student action.
  filterParts.append(f'[real]crop=432:936:0:0,scale={targetW}:{targetH}:flags=lanczos,fps=25[phone]')
  # Keep the background clock running until -t, repeating only the last genuine
  # phone frame. Subtitles must continue updating after the source action ends.
  filterParts.append(f'[0:v][phone]overlay={x}:{y}:eof_action=repeat:repeatlast=1:shortest=0,ass={sub.as_posix()}[v]')
  filterParts.append('[2:a]adelay=700|700,highpass=f=75,acompressor=threshold=0.18:ratio=2:attack=15:release=180,loudnorm=I=-16:TP=-1.5:LRA=9,apad[a]')
  assert all(0<=a<b<=rawlen+.03 for a,b in ranges),key
  cmd=[FF,'-y','-filter_complex_threads','2','-loop','1','-framerate','25','-i',str(bg),'-ss',str(c['start']),'-i',str(raw),'-i',str(voice),'-filter_complex',';'.join(filterParts),'-map','[v]','-map','[a]','-t',str(length),'-r','25','-c:v','libx264','-threads','4','-preset','fast','-crf','20','-pix_fmt','yuv420p','-c:a','aac','-b:a','160k','-movflags','+faststart',str(dest)]
  if (only is None or key in only) and (not dest.exists() or '--force' in sys.argv):
   with (O/(stem+'-encode.log')).open('w') as log:
    r=subprocess.run(cmd,stderr=log);assert r.returncode==0,key
  manifest.append({'id':key,'title':scene['title'],'source_status':c['status'],'source_start':c['start'],'source_end':c['end'],'ranges':ranges,'seconds':length,'narration_seconds':audio,'caption_segments':captions,'file':str(dest),'note':scene.get('note','')})
  print(key,round(length,2),mode,flush=True)
 (O/('timeline-'+mode+'.json')).write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
