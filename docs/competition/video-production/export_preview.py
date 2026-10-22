"""Create a clearly labelled preview from the PDFs actually exported in the UI."""
from pathlib import Path
from PIL import Image, ImageDraw
import subprocess, shutil
from compose import WORK, O, FF, font, dur, ass
import json

narr=json.loads((Path(__file__).parent/'narration.json').read_text())
scene=narr['49b-export-preview'];voice=WORK/'voices/49b-export-preview.mp3'
for portrait in (False,True):
    W,H=(1080,2400) if portrait else (1920,1080)
    im=Image.new('RGB',(W,H),'#F6F8FC');d=ImageDraw.Draw(im)
    d.text((65,42),'错题帮  /  实际导出文件预览',font=font(34,True),fill='#2454CE')
    d.text((65,103),'由本次三道真实错题组成，非设计示意图',font=font(25),fill='#52647B')
    for i,(name,label) in enumerate([('questions','题目版 PDF'),('answers','答案解析版 PDF')]):
        page=Image.open(WORK/f'take2/exports/{name}.png').convert('RGB')
        if portrait:
            page.thumbnail((690,910));x=(W-page.width)//2;y=235+i*980
        else:
            page.thumbnail((670,760));x=220+i*910;y=210
        d.text((x,y-50),label,font=font(29,True),fill='#15243B')
        d.rectangle((x-3,y-3,x+page.width+3,y+page.height+3),fill='#CAD6E6')
        im.paste(page,(x,y))
    stem='49b-export-preview'+('-portrait' if portrait else '')
    bg=O/(stem+'.png');im.save(bg)
    sub=O/(stem+'.ass');shutil.copyfile(voice,sub.with_suffix('.mp3'))
    length=dur(voice)+2
    # Place narration in a dedicated bottom area on this document preview.
    ass(scene,length,sub,portrait)
    st=sub.read_text().replace('\\pos(558,820)','\\pos(960,1045)').replace('\\pos(540,2220)','\\pos(540,2300)')
    sub.write_text(st)
    with (O/(stem+'-encode.log')).open('w') as log:
        subprocess.run([FF,'-y','-loop','1','-framerate','25','-i',str(bg),'-i',str(voice),'-vf','ass='+str(sub),'-af','adelay=700|700,loudnorm=I=-16:TP=-1.5:LRA=9,apad','-t',str(length),'-r','25','-c:v','libx264','-threads','4','-preset','fast','-crf','20','-pix_fmt','yuv420p','-c:a','aac','-b:a','160k',str(O/(stem+'.mp4'))],stderr=log,check=True)
    print(stem,length,flush=True)
