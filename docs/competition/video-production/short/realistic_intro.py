"""Photographic opening: generated study scenes with editorial camera movement.

These are fictional scene-setting assets, never evidence of real student use.
The product screenshot in the closing beat is an unchanged browser capture.
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageOps
import numpy as np

HERE=Path(__file__).resolve().parent
ASSETS=HERE/'assets'
INK='#20322F';GREEN='#365E54'
COVER_SECONDS=2.0

def fitted(path):
    return ImageOps.fit(Image.open(path).convert('RGB'),(1920,1080),method=Image.Resampling.LANCZOS)

class StudentIntro:
    def __init__(self,font,text,words):
        self.font=font;self.text=text;self.words=words
        self.photos=[fitted(ASSETS/name) for name in ['study-cover.png','study-detail.png','study-review.png']]
        self.starts=[COVER_SECONDS]+[self.cue(k) for k in ['有时','换一个条件','错题越积越多','错题帮']]
        self.titles=[('抄过的错题，','怎样真正学会？'),('看过解析，','哪一步做错了？'),('条件一变，','还会解吗？'),('错题积累之后，','先复习什么？'),('从一道错题，','开始下一步学习。')]
        # Warm editorial veil keeps all Chinese typography readable over photographs.
        x=np.linspace(0,1,1920)[None,:];y=np.linspace(0,1,1080)[:,None]
        a=np.maximum(np.clip((.61-x)/.36,0,1)*.91,np.clip((y-.77)/.14,0,1)*.97)
        self.veil=Image.new('RGBA',(1920,1080),(248,246,239,0))
        self.veil.putalpha(Image.fromarray((a*255).astype('uint8')))
        root=HERE.parents[3]
        self.screen=Image.open(root/'.runtime/competition-video/take2/05-photo-confirm.png').convert('RGB')
        self.screen=ImageOps.fit(self.screen,(322,698),method=Image.Resampling.LANCZOS)
        self.cover=self.make_cover()

    def cue(self,phrase):
        at=self.text.index(phrase);cursor=0
        for w in self.words:
            pos=self.text.find(w['text'],cursor);assert pos>=0
            cursor=pos+len(w['text'])
            if cursor>at:return w['start']+.45+COVER_SECONDS
        raise ValueError(phrase)

    def text_at(self,d,xy,s,size,bold=False,fill=INK):
        d.text(xy,s,font=self.font(size,bold),fill=fill)

    def camera(self,index,u):
        # Gentle, real camera-like crop movement. No simulated human motion.
        u=max(0,min(1,u));zoom=1.015+.045*u
        w,h=int(1920/zoom),int(1080/zoom)
        px=.63 if index==0 else .70
        xx=int((1920-w)*(px+.12*u));yy=int((1080-h)*(.35+.20*u))
        return self.photos[index].crop((xx,yy,xx+w,yy+h)).resize((1920,1080),Image.Resampling.BICUBIC)

    def editorial(self,photo):
        return Image.alpha_composite(photo.convert('RGBA'),self.veil).convert('RGB')

    def make_cover(self):
        im=self.editorial(self.photos[0]);d=ImageDraw.Draw(im)
        self.text_at(d,(112,76),'2026“仓颉杯”智能编程大赛',26,False,GREEN)
        self.text_at(d,(104,215),'错题帮',146,True)
        self.text_at(d,(113,404),'AI 错题学习助手',42,False,GREEN)
        self.text_at(d,(110,568),'让每一道错题',59,True)
        self.text_at(d,(110,655),'成为下一步。',59,True)
        self.text_at(d,(113,867),'拍题诊断   /   订正训练   /   复习巩固',30,False,GREEN)
        self.text_at(d,(113,969),'作品演示',24,False,GREEN)
        return im

    def scene(self,beat,u):
        photo_index=[0,1,1,2,0][beat]
        im=self.editorial(self.camera(photo_index,u));d=ImageDraw.Draw(im)
        self.text_at(d,(112,72),'错题帮',33,True,GREEN)
        if beat<4:
            self.text_at(d,(114,298),'学习中的三个问题' if beat else '从学生的错题整理出发',27,False,GREEN)
            for i,line in enumerate(self.titles[beat]):self.text_at(d,(109,391+i*99),line,65,True)
            if beat in [1,2]:
                self.text_at(d,(115,661),'理解错误  /  独立迁移',29,False,GREEN)
        else:
            for i,line in enumerate(self.titles[beat]):self.text_at(d,(109,300+i*90),line,59,True)
            for j,label in enumerate(['拍题诊断','订正训练','复习巩固']):
                self.text_at(d,(116,555+j*86),f'0{j+1}',27,False,GREEN)
                self.text_at(d,(188,548+j*86),label,38,True)
            # Actual UI capture, clearly framed as a product screen.
            d.rounded_rectangle((1274,127,1628,865),radius=30,fill='#17221F')
            im.paste(self.screen,(1290,147))
        return im

    def frame(self,t,total):
        if t<COVER_SECONDS:
            return self.cover.copy()
        beat=max(i for i,s in enumerate(self.starts) if t>=s)
        end=self.starts[beat+1] if beat+1<len(self.starts) else total
        u=(t-self.starts[beat])/max(.1,end-self.starts[beat])
        im=self.scene(beat,u)
        # Short dissolves connect photographic scenes and the cover without abrupt flashes.
        transition=.40
        if t-self.starts[beat]<transition:
            previous=self.cover if beat==0 else self.scene(beat-1,1)
            im=Image.blend(previous,im,(t-self.starts[beat])/transition)
        return im
