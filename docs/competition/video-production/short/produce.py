"""Three-step competition cut built from the original, unchanged mobile capture."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from functools import lru_cache
import asyncio, json, subprocess, math, re, html, hashlib, shutil, sys, zipfile
import edge_tts, imageio_ffmpeg, cv2

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
WORK=ROOT/'.runtime/competition-video'
O=WORK/'short';O.mkdir(exist_ok=True)
V=O/'voices';V.mkdir(exist_ok=True)
D=ROOT/'docs/competition/deliverables/演示视频/比赛精简版';D.mkdir(parents=True,exist_ok=True)
FF=imageio_ffmpeg.get_ffmpeg_exe()
MOVIE_NAME='错题帮_参赛演示_动画修订版.mp4'
SCENES=json.loads((HERE/'storyboard.json').read_text())
CLIPS={c['id']:c for c in json.loads((WORK/'take2/clips.json').read_text())}
RAW=Path((WORK/'take2/raw-path.txt').read_text().strip())
INK='#17263F';BLUE='#2454CE';MUTED='#52647B';BG='#F6F8FC'
STEPS=['拍题诊断','订正训练','复习巩固']

@lru_cache(maxsize=60)
def font(size,bold=False):
    name='NotoSansCJK-Bold.ttc' if bold else 'NotoSansCJK-Regular.ttc'
    # TTC index 2 is Simplified Chinese; index 0 selects Japanese glyph forms.
    return ImageFont.truetype('/usr/share/fonts/opentype/noto/'+name,size,index=2)
def duration(p):
    r=subprocess.run([FF,'-i',str(p)],capture_output=True,text=True)
    m=re.search(r'Duration: (\d+):(\d+):([\d.]+)',r.stderr)
    assert m,str(p)
    return int(m[1])*3600+int(m[2])*60+float(m[3])
def txt(d,xy,s,size=32,bold=False,color=INK):d.text(xy,s,font=font(size,bold),fill=color)
def lines(text,width,size):
    result=[];s=''
    for c in text:
        if s and font(size).getlength(s+c)>width:result.append(s);s=c
        else:s+=c
    if s:result.append(s)
    return result
def run(cmd,log):
    with log.open('w') as f:subprocess.run(cmd,stderr=f,check=True)
def stamp(t):
    ms=round(t*1000);return f'{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02},{ms%1000:03}'
def ass_time(t):return f'{int(t//3600)}:{int(t//60)%60:02}:{int(t)%60:02}.{int(t*100)%100:02}'

async def voices():
    sem=asyncio.Semaphore(2)
    async def one(s):
        key=s['id'];dest=V/(key+'.mp3');meta=V/(key+'.json')
        signature=hashlib.sha256((s['text']+'Yunxi+4%').encode()).hexdigest()
        if dest.exists() and meta.exists() and json.loads(meta.read_text()).get('signature')==signature:return
        async with sem:
            for attempt in range(3):
                events=[]
                try:
                    async def record():
                        with dest.open('wb') as f:
                            async for chunk in edge_tts.Communicate(s['text'],'zh-CN-YunxiNeural',rate='+4%',boundary='WordBoundary').stream():
                                if chunk['type']=='audio':f.write(chunk['data'])
                                elif chunk['type']=='WordBoundary':events.append(dict(start=chunk['offset']/1e7,end=(chunk['offset']+chunk['duration'])/1e7,text=chunk['text']))
                    await asyncio.wait_for(record(),80)
                    assert events
                    meta.write_text(json.dumps(dict(signature=signature,words=events),ensure_ascii=False,indent=2))
                    print('voice',key,duration(dest),flush=True);return
                except Exception:
                    if attempt==2:raise
                    await asyncio.sleep(1)
    await asyncio.gather(*(one(s) for s in SCENES))

def captions(s):
    """Keep punctuation from the script and timing from actual TTS word events."""
    words=json.loads((V/(s['id']+'.json')).read_text())['words']
    cursor=0;tokens=[]
    for w in words:
        text=html.unescape(w['text']);at=s['text'].find(text,cursor)
        assert at>=0,(s['id'],text,cursor)
        token=s['text'][cursor:at+len(text)];cursor=at+len(text)
        tokens.append(dict(text=token,start=w['start']+.45,end=w['end']+.45))
    if cursor<len(s['text']):tokens[-1]['text']+=s['text'][cursor:]
    groups=[];part=[]
    for token in tokens:
        trial=''.join(t['text'] for t in part)+token['text']
        if part and (font(34).getlength(trial)>855 or (len(''.join(t['text'] for t in part))>=13 and token['text'].startswith(('。','！','？','；')))):
            groups.append(part);part=[]
        part.append(token)
    if part:groups.append(part)
    if len(groups)>1 and len(''.join(t['text'] for t in groups[-1]))<6:
        if font(34).getlength(''.join(t['text'] for t in groups[-2]+groups[-1]))<=1020:
            tail=groups.pop()
            groups[-1].extend(tail)
    result=[]
    for i,g in enumerate(groups):
        text=''.join(t['text'] for t in g).strip()
        if text[0] in '，。；！？、' and result:
            result[-1][2]+=text[0];text=text[1:]
        if not text:continue
        start=g[0]['start'];end=min(g[-1]['end']+.12,groups[i+1][0]['start'] if i+1<len(groups) else g[-1]['end']+.18)
        result.append([start,end,text])
    return result

def write_ass(s,dest,full=False):
    x,y=(960,972) if full else (595,862)
    cues=captions(s)
    header='''[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 2
[V4+ Styles]
Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding
Style: Voice,Noto Sans CJK SC,34,&H003F2617,&H003F2617,&H00FCF8F6,&H00FCF8F6,0,0,0,0,100,100,0,0,1,2,0,5,25,25,30,1
[Events]
Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
'''
    events=[f'Dialogue: 0,{ass_time(a)},{ass_time(b)},Voice,,0,0,0,,{{\\pos({x},{y})\\fad(70,70)}}{text}' for a,b,text in cues]
    dest.write_text(header+'\n'.join(events)+'\n');return cues

@lru_cache(maxsize=1)
def intro_animation():
    from student_animation import StudentIntro
    intro=next(s for s in SCENES if s['id']=='intro')
    return StudentIntro(font,intro['text'],json.loads((V/'intro.json').read_text())['words'])

def background(s):
    im=Image.new('RGB',(1920,1080),BG);d=ImageDraw.Draw(im)
    txt(d,(110,53),'错题帮',38,True,BLUE)
    txt(d,(110,117),'2026“仓颉杯”智能编程大赛',25,False,MUTED)
    txt(d,(110,355),s['title'],78,True)
    yy=500
    for line in lines(s['detail'],980,39):txt(d,(114,yy),line,39,False,MUTED);yy+=58
    d.line((114,675,1090,675),fill='#D9E2EF',width=2)
    for i,line in enumerate(lines(s.get('note',''),990,25)):
        txt(d,(114,708+i*37),line,25,False,BLUE)
    d.rounded_rectangle((1206,42,1662,1030),radius=26,fill='white',outline='#CCD7E7',width=3)
    txt(d,(1725,65),'手机端',25,True,BLUE)
    return im

def motion(s,t,total):
    if s['id']=='intro':
        return intro_animation().frame(t,total)
    im=Image.new('RGB',(1920,1080),BG);d=ImageDraw.Draw(im)
    txt(d,(110,50),'错题帮  /  2026“仓颉杯”智能编程大赛',28,True,BLUE)
    d.line((110,110,1810,110),fill='#DAE3F0',width=2)
    if s['id']=='architecture':
        txt(d,(110,164),s['title'],68,True)
        blocks=[(110,'学生端','uni-app / Vue 3',['录入与作答','任务与学习记录']),(710,'业务与数据','仓颉服务 + MySQL',['业务状态与资格校验','学习数据的统一管理']),(1310,'智能计算','Python / FastAPI',['诊断、规划与判定工具','检索与模型计算'])]
        for x,title,tech,body in blocks:
            d.rounded_rectangle((x,325,x+500,720),radius=15,fill='#E9F1ED' if x==710 else '#EBF0FA',outline='#C9D6E7',width=2)
            txt(d,(x+30,355),title,43,True);txt(d,(x+30,444),tech,32,True,BLUE)
            for j,label in enumerate(body):txt(d,(x+30,539+j*66),label,29,False,MUTED)
            if x<1310:d.line((x+516,512,x+580,512),fill=BLUE,width=3);d.polygon([(x+580,512),(x+567,504),(x+567,520)],fill=BLUE)
        txt(d,(110,810),'单协调器  →  组织上下文  →  调用工具  →  接收反馈与推进任务',34,True)
    else:
        txt(d,(110,204),'让每一道错题',97,True)
        txt(d,(110,345),'成为下一步。',97,True)
        for i,label in enumerate(STEPS):
            x=120+i*590
            d.ellipse((x,615,x+65,680),fill='#E5EDFC')
            txt(d,(x+22,624),str(i+1),31,True,BLUE);txt(d,(x+94,618),label,43,True)
        txt(d,(115,809),'从一道错题，开始下一次学习。',36,False,MUTED)
    return im

def render(only=None):
    manifest=[]
    for s in SCENES:
        key=s['id'];voice=V/(key+'.mp3')
        padding=.6 if key in ('intro','account') else 1.1
        length=max(s['seconds'],duration(voice)+padding)
        assert length<=55,(key,length)
        sub=O/(key+'.ass');cues=write_ass(s,sub,not s['shots'])
        dest=O/(key+'.mp4')
        if only and key not in only and dest.exists():
            manifest.append(dict(**s,file=str(dest),actual_seconds=length,captions=cues));continue
        if not s['shots']:
            silent=O/(key+'-motion.mp4')
            cmd=[FF,'-y','-f','rawvideo','-pixel_format','rgb24','-video_size','1920x1080','-framerate','25','-i','pipe:0','-t',str(length),'-c:v','libx264','-threads','4','-preset','fast','-crf','19','-pix_fmt','yuv420p',str(silent)]
            with (O/(key+'-motion.log')).open('w') as log:
                p=subprocess.Popen(cmd,stdin=subprocess.PIPE,stderr=log)
                for n in range(math.ceil(length*25)):p.stdin.write(motion(s,n/25,length).tobytes())
                p.stdin.close();assert p.wait()==0,key
            cmd=[FF,'-y','-i',str(silent),'-i',str(voice),'-vf','ass='+str(sub),'-af','adelay=450|450,loudnorm=I=-16:TP=-1.5:LRA=9,aresample=48000,apad','-t',str(length),'-r','25','-c:v','libx264','-threads','4','-preset','fast','-crf','19','-pix_fmt','yuv420p','-ar','48000','-ac','2','-c:a','aac','-b:a','160k',str(dest)]
        else:
            bg=O/(key+'-bg.png');background(s).save(bg)
            cmd=[FF,'-y','-filter_complex_threads','2','-loop','1','-framerate','25','-i',str(bg),'-i',str(voice)]
            parts=[];labels=[]
            for j,shot in enumerate(s['shots']):
                idx=j+2;label=f'p{j}';labels.append('['+label+']')
                if 'clip' in shot:
                    c=CLIPS[shot['clip']];a=shot['start'];b=shot['end']
                    assert 0<=a<b<=c['end']-c['start']+.03,(key,shot)
                    cmd+=['-ss',str(c['start']+a),'-i',str(RAW)]
                    parts.append(f'[{idx}:v]trim=duration={b-a},setpts=PTS-STARTPTS,crop=432:936:0:0,fps=25,setsar=1[{label}]')
                else:
                    image=Image.open(WORK/('take2/exports/'+shot['image'])).convert('RGB');image.thumbnail((424,920))
                    preview=Image.new('RGB',(432,936),'white');preview.paste(image,((432-image.width)//2,(936-image.height)//2));pp=O/(key+'-document.png');preview.save(pp)
                    cmd+=['-loop','1','-framerate','25','-t',str(shot['seconds']),'-i',str(pp)]
                    parts.append(f'[{idx}:v]trim=duration={shot["seconds"]},setpts=PTS-STARTPTS,fps=25,setsar=1[{label}]')
            parts.append(''.join(labels)+f'concat=n={len(labels)}:v=1:a=0[phone]')
            parts.append(f'[0:v][phone]overlay=1218:64:eof_action=repeat:repeatlast=1:shortest=0,ass={sub}[v]')
            parts.append('[1:a]adelay=450|450,loudnorm=I=-16:TP=-1.5:LRA=9,aresample=48000,apad[a]')
            cmd+=['-filter_complex',';'.join(parts),'-map','[v]','-map','[a]','-t',str(length),'-r','25','-c:v','libx264','-threads','4','-preset','fast','-crf','19','-pix_fmt','yuv420p','-ar','48000','-ac','2','-c:a','aac','-b:a','160k',str(dest)]
        run(cmd,O/(key+'-encode.log'))
        cap=cv2.VideoCapture(str(dest));frames=cap.get(cv2.CAP_PROP_FRAME_COUNT);fps=cap.get(cv2.CAP_PROP_FPS);cap.release()
        assert abs(fps-25)<.01 and abs(frames/25-length)<.08,(key,frames,fps,length)
        manifest.append(dict(**s,file=str(dest),actual_seconds=frames/25,captions=cues))
        print('rendered',key,frames/25,flush=True)
    (O/'timeline.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')

def finish():
    entries=json.loads((O/'timeline.json').read_text());listing=O/'concat.txt';meta=O/'metadata.txt'
    # Follow actual video frames; do not accumulate the AAC encoder's padding.
    for c in entries:
        v=cv2.VideoCapture(c['file']);c['actual_seconds']=v.get(cv2.CAP_PROP_FRAME_COUNT)/v.get(cv2.CAP_PROP_FPS);v.release()
    listing.write_text('\n'.join("file '"+c['file']+"'\nduration "+str(c['actual_seconds']) for c in entries))
    m=[';FFMETADATA1','title=错题帮：学生三步学习','artist=错题帮项目组','comment=手机视口真实录制节选；学生为演示角色；中文合成旁白。']
    chapters=[];subtitles=[];at=0;groups=[]
    for c in entries:
        c['film_start']=at;c['film_end']=at+c['actual_seconds'];at=c['film_end']
        title={0:'背景与学习入口',1:'第一步：拍题诊断',2:'第二步：订正训练',3:'第三步：复习巩固'}[c['stage']]
        if c['id']=='architecture':title='技术协作'
        if c['id']=='outro':title='应用价值'
        if not groups or groups[-1]['title']!=title:groups.append(dict(title=title,start=c['film_start'],end=at))
        else:groups[-1]['end']=at
        for a,b,text in c['captions']:subtitles.append(f'{len(subtitles)+1}\n{stamp(c["film_start"]+a)} --> {stamp(c["film_start"]+b)}\n{text}\n')
    for g in groups:
        m+=['[CHAPTER]','TIMEBASE=1/1000',f'START={round(g["start"]*1000)}',f'END={round(g["end"]*1000)}','title='+g['title']]
        chapters.append(f'{int(g["start"]//60):02}:{int(g["start"]%60):02}  {g["title"]}')
    meta.write_text('\n'.join(m)+'\n')
    dest=D/MOVIE_NAME
    run([FF,'-y','-f','concat','-safe','0','-i',str(listing),'-i',str(meta),'-map','0:v','-map','0:a','-map_metadata','1','-map_chapters','1','-c:v','copy','-af','aresample=async=1:first_pts=0','-ar','48000','-ac','2','-c:a','aac','-b:a','160k','-movflags','+faststart',str(dest)],O/'final.log')
    (D/Path(MOVIE_NAME).with_suffix('.srt')).write_text('\n'.join(subtitles),encoding='utf-8-sig')
    (D/'章节导航.txt').write_text('\n'.join(chapters)+'\n')
    (O/'final-timeline.json').write_text(json.dumps(entries,ensure_ascii=False,indent=2)+'\n')
    (D/'讲解稿.md').write_text('# 错题帮参赛演示讲解稿\n\n'+'\n\n'.join('## '+s['title']+'\n\n'+s['text'] for s in SCENES)+'\n')
    print('final',duration(dest),'seconds',round(dest.stat().st_size/1048576,1),'MiB',flush=True)

def recaption():
    """Correct only the designed subtitle band; keep the recorded UI untouched."""
    entries=json.loads((O/'timeline.json').read_text());previous={c['id']:c for c in entries}
    revised=[]
    for s in SCENES:
        c=previous[s['id']];sub=O/(s['id']+'.ass');cues=write_ass(s,sub,not s['shots'])
        if cues!=c['captions']:
            source=Path(c['file']);temp=O/(s['id']+'-recaption.mp4')
            band='drawbox=x=175:y=932:w=1570:h=76:color=0xF6F8FC:t=fill' if not s['shots'] else 'drawbox=x=45:y=818:w=1100:h=89:color=0xF6F8FC:t=fill'
            run([FF,'-y','-i',str(source),'-vf',band+',ass='+str(sub),'-map','0:v','-map','0:a','-c:v','libx264','-threads','4','-preset','fast','-crf','18','-pix_fmt','yuv420p','-c:a','copy',str(temp)],O/(s['id']+'-recaption.log'))
            temp.replace(source);print('recaptioned',s['id'],flush=True)
        c['captions']=cues;revised.append(c)
    (O/'timeline.json').write_text(json.dumps(revised,ensure_ascii=False,indent=2)+'\n')

if __name__=='__main__':
    action=sys.argv[1]
    if action=='voices':asyncio.run(voices())
    elif action=='render':render(set(sys.argv[2].split(',')) if len(sys.argv)>2 else None)
    elif action=='finish':finish()
    elif action=='recaption':recaption()
