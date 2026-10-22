"""Assemble the audited mobile captures into playable, chaptered deliverables."""
from pathlib import Path
from PIL import Image,ImageDraw
import subprocess,json,shutil,re,hashlib,cv2
from compose import B,R,WORK,O,FF,font,dur,ass

D=R/'docs/competition/deliverables/演示视频';D.mkdir(parents=True,exist_ok=True)
narr=json.loads((B/'narration.json').read_text())
def run(cmd,log):
    with log.open('w') as f:subprocess.run(cmd,stderr=f,check=True)
def stamp(x):
    ms=round(x*1000);return f'{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02},{ms%1000:03}'
def textcaps(key):
    scene=narr[key];voice=WORK/'voices'/f'{key}.mp3';sub=O/f'{key}-global.ass';shutil.copyfile(voice,sub.with_suffix('.mp3'))
    return ass(scene,dur(voice)+2.5,sub)
def portrait_animation(key):
    dest=O/(key+'-portrait.mp4')
    if dest.exists() and dest.stat().st_mtime>=max((O/f'{key}.mp4').stat().st_mtime,(B/'narration.json').stat().st_mtime):
        return dest
    im=Image.new('RGB',(1080,2400),'#F6F8FC');d=ImageDraw.Draw(im)
    d.text((65,80),'错题帮  /  2026 仓颉杯',font=font(32,True),fill='#2454CE')
    for i,t in enumerate((['让每一道错题','成为下一步。'] if key=='intro' else ['从一道错题','把学习接起来。'])):
        d.text((65,275+i*110),t,font=font(80,True),fill='#15243B')
    d.text((65,585),'学生使用情境 · 完整手机实录',font=font(35),fill='#52647B')
    d.text((65,1630),'录入  ·  诊断  ·  订正',font=font(44,True),fill='#15243B')
    d.text((65,1720),'训练  ·  考试  ·  复习',font=font(44,True),fill='#15243B')
    d.text((65,2320),'中文合成旁白  /  真实系统操作',font=font(29),fill='#52647B')
    bg=O/(key+'-portrait-bg.png');im.save(bg)
    sub=O/(key+'-portrait.ass');shutil.copyfile(WORK/f'voices/{key}.mp3',sub.with_suffix('.mp3'))
    ass(narr[key],dur(O/f'{key}.mp4'),sub,True)
    run([FF,'-y','-filter_complex_threads','2','-loop','1','-framerate','25','-i',str(bg),'-i',str(O/f'{key}.mp4'),'-filter_complex',f'[1:v]crop=1920:926:0:0,scale=1080:521[v0];[0:v][v0]overlay=0:825:shortest=1,ass={sub}[v]','-map','[v]','-map','1:a','-t',str(dur(O/f'{key}.mp4')),'-r','25','-c:v','libx264','-threads','4','-preset','fast','-crf','20','-pix_fmt','yuv420p','-c:a','copy',str(dest)],O/(key+'-portrait-final.log'))
    return dest

def build(mode):
    timeline=json.loads((O/f'timeline-{mode}.json').read_text());portrait=mode=='portrait'
    suffix='-portrait' if portrait else ''
    intro=portrait_animation('intro') if portrait else O/'intro.mp4'
    outro=portrait_animation('outro') if portrait else O/'outro.mp4'
    entries=[{'id':'intro','title':'开场：学生的三个问题','file':str(intro),'caption_segments':textcaps('intro')}]
    for c in timeline:
        entries.append(c)
        if c['id']=='49-open-exports':
            entries.append({'id':'49b-export-preview','title':'实际导出文件预览','file':str(O/f'49b-export-preview{suffix}.mp4'),'caption_segments':textcaps('49b-export-preview')})
    entries.append({'id':'outro','title':'总结：把学习接起来','file':str(outro),'caption_segments':textcaps('outro')})
    ready=O/('concat-ready-'+mode);ready.mkdir(exist_ok=True)
    # Normalize audio formats before concat: the original TTS and UI scenes can
    # have different sample rates. Copy H.264 video without another generation loss.
    for c in entries:
        source=Path(c['file']);target=ready/(c['id']+'.mp4')
        if not target.exists() or target.stat().st_mtime<source.stat().st_mtime:
            run([FF,'-y','-i',str(source),'-map','0:v','-map','0:a','-c:v','copy','-af','loudnorm=I=-16:TP=-1.5:LRA=9,aresample=48000','-ar','48000','-ac','2','-c:a','aac','-b:a','160k',str(target)],ready/(c['id']+'.log'))
        capture=cv2.VideoCapture(str(target))
        frames=capture.get(cv2.CAP_PROP_FRAME_COUNT);fps=capture.get(cv2.CAP_PROP_FPS);capture.release()
        assert frames>0 and abs(fps-25)<.01,(c['id'],frames,fps)
        c['normalized_file']=str(target);c['actual_seconds']=frames/fps
    # AAC priming/padding must not insert a gap between otherwise continuous
    # 25-fps video tracks. Chapter and subtitle offsets follow the video frames.
    listing=ready/'concat.txt';listing.write_text('\n'.join("file '"+c['normalized_file']+"'\nduration "+str(c['actual_seconds']) for c in entries))
    meta=[';FFMETADATA1','title=错题帮：学生全流程手机实录','artist=错题帮项目组','comment=独立演示账号；学生为演示角色；中文合成旁白。复习预置到期计划已在画面披露。']
    at=0;subs=[];chapters=[]
    for c in entries:
        seconds=c['actual_seconds'];c['film_start']=at;c['film_end']=at+seconds
        meta += ['[CHAPTER]','TIMEBASE=1/1000',f'START={round(at*1000)}',f'END={round((at+seconds)*1000)}','title='+c['title']]
        chapters.append(f'{int(at//60):02}:{int(at%60):02}  {c["title"]}')
        for a,b,t in c['caption_segments']:
            subs.append(f'{len(subs)+1}\n{stamp(at+a)} --> {stamp(min(at+b,at+seconds))}\n{t}\n')
        at+=seconds
    metadata=ready/'metadata.txt';metadata.write_text('\n'.join(meta)+'\n')
    name='错题帮_手机竖屏完整演示' if portrait else '错题帮_完整作品演示_手机实录'
    dest=D/(name+'.mp4')
    # Re-time the concatenated AAC stream to remove encoder priming overlaps at
    # chapter boundaries; the H.264 recording is copied without quality loss.
    run([FF,'-y','-f','concat','-safe','0','-i',str(listing),'-i',str(metadata),'-map','0:v','-map','0:a','-map_metadata','1','-map_chapters','1','-c:v','copy','-af','aresample=async=1:first_pts=0','-ar','48000','-ac','2','-c:a','aac','-b:a','160k','-movflags','+faststart',str(dest)],ready/'final.log')
    (D/(name+'.srt')).write_text('\n'.join(subs),encoding='utf-8-sig')
    (D/(name+'_章节.txt')).write_text('\n'.join(chapters)+'\n')
    (O/f'final-timeline-{mode}.json').write_text(json.dumps(entries,ensure_ascii=False,indent=2)+'\n')
    print(mode,'seconds',dur(dest),'MB',round(dest.stat().st_size/1048576,1),dest,flush=True)
    if not portrait:
        script=['# 错题帮完整演示讲解稿','','演示角色：初二学生小林。旁白为中文合成语音。','']
        for c in entries:script += ['## '+c['title'],'',narr[c['id']]['text'],'']
        (D/'错题帮_演示讲解稿.md').write_text('\n'.join(script))
    return entries

def cover():
    im=Image.new('RGB',(1920,1080),'#F6F8FC');d=ImageDraw.Draw(im)
    d.rectangle((0,0,16,1080),fill='#2454CE')
    d.text((110,70),'错题帮  /  2026 仓颉杯',font=font(32,True),fill='#2454CE')
    for y,t in [(255,'让每一道错题'),(382,'成为下一步。')]:d.text((110,y),t,font=font(100,True),fill='#15243B')
    d.text((115,583),'初二学生的一次完整学习',font=font(42),fill='#52647B')
    d.text((115,690),'注册 · 录题 · 诊断 · 订正',font=font(34),fill='#15243B')
    d.text((115,755),'训练 · 考试 · 复习 · 导出',font=font(34),fill='#15243B')
    shot=Image.open(WORK/'take2/06-evidence-replay.png').convert('RGB');shot.thumbnail((432,936))
    d.rounded_rectangle((1250,55,1706,1024),radius=28,fill='white',outline='#CAD6E6',width=3)
    im.paste(shot,(1262,72))
    d.text((115,960),'手机浏览器实录  |  中文讲解  |  功能完整演示',font=font(29),fill='#2454CE')
    im.save(D/'错题帮_演示视频封面.png')

if __name__=='__main__':
    import sys
    build(sys.argv[1] if len(sys.argv)>1 else 'landscape');cover()
