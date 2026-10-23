"""An original, continuously animated student-at-desk opening."""
import math
from PIL import Image, ImageDraw

BG='#F6F8FC';INK='#17263F';BLUE='#2454CE';MUTED='#52647B'
SKIN='#F2CFB1';HAIR='#283449';SHIRT='#6E89A7';WOOD='#D9C4A7'

def ease(x):
    x=max(0,min(1,x));return x*x*(3-2*x)

class StudentIntro:
    def __init__(self,font,text,words):
        self.font=font;self.text=text;self.words=words
        self.titles=['抄完错题，下次还会做错','做错的是哪一步？','换一道题，又卡住了','错题越积越多，先看哪道？','把错题学习接成三步']
        self.starts=[0]+[self.cue(k) for k in ['有时','换一个条件','错题越积越多','错题帮']]
        assert self.starts==sorted(self.starts),self.starts

    def cue(self,phrase):
        at=self.text.index(phrase);cursor=0
        for word in self.words:
            pos=self.text.find(word['text'],cursor)
            assert pos>=0,(phrase,word)
            cursor=pos+len(word['text'])
            if cursor>at:return word['start']+.45
        raise ValueError(phrase)

    def text_at(self,d,xy,text,size=32,bold=False,fill=INK):
        d.text(xy,text,font=self.font(size,bold),fill=fill)

    def line(self,d,points,fill,width=10):
        d.line(points,fill=fill,width=width,joint='curve')
        r=width/2
        for x,y in [points[0],points[-1]]:d.ellipse((x-r,y-r,x+r,y+r),fill=fill)

    def paper(self,title,rows,width=490,height=340,highlight=False,write=None):
        im=Image.new('RGBA',(width+20,height+20));d=ImageDraw.Draw(im)
        d.rounded_rectangle((12,12,width+12,height+12),radius=13,fill='#DCE2EA80')
        d.rounded_rectangle((2,2,width+2,height+2),radius=13,fill='white',outline='#CBD6E4',width=2)
        d.line((30,67,width-25,67),fill='#D9E2EE',width=2)
        self.text_at(d,(35,20),title,24,True,MUTED)
        for i,row in enumerate(rows):
            yy=96+i*67
            size=35
            while self.font(size).getlength(row)>width-75:size-=1
            d.line((32,yy+49,width-26,yy+49),fill='#E6EBF2',width=1)
            if write is None or write>=i+1:
                self.text_at(d,(39,yy),row,size,True if i==0 else False)
            elif write>i:
                layer=Image.new('RGBA',im.size);ld=ImageDraw.Draw(layer)
                self.text_at(ld,(39,yy),row,size)
                cutoff=int(39+(width-70)*(write-i));im.alpha_composite(layer.crop((0,0,cutoff,height+20)),(0,0))
        if highlight:
            d.rounded_rectangle((29,156,width-27,216),radius=8,outline='#C96358',width=4)
            d.line((width-18,184,width+3,184),fill='#C96358',width=3)
        return im

    def clock(self,d,t):
        cx,cy,r=1585,386,62
        d.ellipse((cx-r,cy-r,cx+r,cy+r),fill='white',outline='#B9C9DC',width=4)
        for i in range(12):
            a=i*math.pi/6;x=cx+math.sin(a)*(r-12);y=cy-math.cos(a)*(r-12)
            d.ellipse((x-2,y-2,x+2,y+2),fill=MUTED)
        for angle,length,w in [(t*.85,r-17,4),(t*.071+.7,r*.5,6)]:
            self.line(d,[(cx,cy),(cx+math.sin(angle)*length,cy-math.cos(angle)*length)],INK,w)
        d.ellipse((cx-4,cy-4,cx+4,cy+4),fill=BLUE)

    def room(self,d):
        d.ellipse((276,875,1644,924),fill='#E6EBF2')
        d.rounded_rectangle((290,513,395,809),radius=27,fill='#D6E2DE',outline='#B8CCC5',width=3)
        self.line(d,[(325,794),(316,894)],'#95ACA3',12)
        self.line(d,[(512,796),(529,894)],'#95ACA3',12)
        self.line(d,[(566,782),(541,888)],'#AE9679',15)
        self.line(d,[(1545,782),(1571,888)],'#AE9679',15)
        # A schoolbag sits beside the chair.
        d.rounded_rectangle((222,748,317,864),radius=22,fill='#9BAEB6',outline='#728995',width=3)
        d.arc((242,721,295,775),180,360,fill='#728995',width=7)
        d.rounded_rectangle((238,790,300,838),radius=8,outline='#728995',width=3)

    def student(self,d,t,phase):
        lean=4*math.sin(t*.65);hx,hy=446+lean,407
        # Body and bent legs, drawn behind the desktop.
        self.line(d,[(424,704),(522,794),(592,866)],'#40536D',39)
        self.line(d,[(402,710),(401,803),(441,877)],'#4B607C',38)
        self.line(d,[(576,874),(625,874)],HAIR,18)
        self.line(d,[(432,886),(477,886)],HAIR,18)
        d.rounded_rectangle((355,489,539,735),radius=47,fill=SHIRT,outline='#526E8D',width=3)
        d.polygon([(418,492),(448,520),(477,491)],fill='#EEF3F8')
        d.line((448,521,448,700),fill='#A9BECE',width=3)
        d.rounded_rectangle((466,590,518,637),radius=7,outline='#A9BECE',width=2)
        d.rounded_rectangle((426,458,466,508),radius=11,fill=SKIN)
        d.ellipse((hx-66,hy-74,hx+67,hy+83),fill=SKIN,outline='#D7AE91',width=2)
        d.ellipse((hx-77,hy+5,hx-46,hy+45),fill=SKIN)
        d.pieslice((hx-70,hy-91,hx+68,hy+65),180,355,fill=HAIR)
        d.polygon([(hx-69,hy-20),(hx-39,hy-52),(hx-4,hy-38),(hx+24,hy-54),(hx+65,hy-13),(hx+62,hy-57),(hx+7,hy-91),(hx-55,hy-67)],fill=HAIR)
        # Small blinks and head motion keep the character alive between actions.
        ey=hy+13;blink=t%3.7<.12
        for ex in [hx+9,hx+45]:
            if blink:d.line((ex-4,ey,ex+4,ey),fill=HAIR,width=3)
            else:d.ellipse((ex-3,ey-4,ex+3,ey+4),fill=HAIR)
        d.arc((hx-6,ey-13,hx+27,ey+12),0,359,fill='#62728A',width=2)
        d.arc((hx+31,ey-13,hx+64,ey+12),0,359,fill='#62728A',width=2)
        d.line((hx+27,ey-1,hx+32,ey-1),fill='#62728A',width=2)
        d.line((hx+31,hy+32,hx+35,hy+36),fill='#BC8F73',width=2)
        if phase in [1,2]:d.arc((hx+18,hy+51,hx+45,hy+68),190,330,fill='#AA7462',width=3)
        else:d.arc((hx+19,hy+43,hx+45,hy+63),15,155,fill='#AA7462',width=3)

    def desktop(self,d):
        d.polygon([(535,726),(1621,726),(1681,782),(497,782)],fill=WOOD,outline='#BEA586')
        d.line((509,783,1666,783),fill='#AF9577',width=5)
        # Two stacked textbooks and a pencil cup ground the scene.
        d.rounded_rectangle((1375,686,1550,719),radius=5,fill='#8CA59F',outline='#6D8982',width=2)
        d.line((1392,709,1540,709),fill='#E9F0E9',width=7)
        d.rounded_rectangle((1390,655,1559,689),radius=5,fill='#C3B296',outline='#AA9676',width=2)
        d.rounded_rectangle((1570,659,1631,724),radius=8,fill='#A4B7CD')
        for x,tilt in [(1582,-9),(1601,4),(1620,10)]:
            d.line((x,676,x+tilt,615),fill=INK,width=5)
            d.line((x+tilt,614,x+tilt-1,605),fill='#D0A477',width=4)

    def arms(self,d,t,phase):
        # Actual wrist, elbow and pen movement, rather than moving captions.
        speed=4.1 if phase in [0,2] else 2.3
        wx=773+39*math.sin(t*speed);wy=675+9*math.cos(t*speed*1.7)
        if phase==1:wx=785+13*math.sin(t*2);wy=649+10*math.sin(t*1.2)
        if phase==3:wx=805+38*math.sin(t*2.7);wy=658+12*math.sin(t*2.7)
        if phase==4:wx=790+20*math.sin(t*2);wy=649+12*math.cos(t*2)
        self.line(d,[(512,527),(610,630),(wx-16,wy)],SHIRT,36)
        self.line(d,[(516,532),(611,635),(wx-18,wy+2)],'#526E8D',3)
        d.ellipse((wx-21,wy-15,wx+17,wy+14),fill=SKIN,outline='#D7AE91',width=2)
        self.line(d,[(wx-7,wy-27),(wx+24,wy+20)],'#324A72',7)
        d.polygon([(wx+20,wy+15),(wx+28,wy+26),(wx+27,wy+12)],fill='#AE8967')

    def scene(self,phase,t,total):
        im=Image.new('RGB',(1920,1080),BG);d=ImageDraw.Draw(im);u=max(0,t-self.starts[phase])
        self.text_at(d,(110,52),'错题帮',37,True,BLUE)
        self.text_at(d,(110,112),'2026“仓颉杯”智能编程大赛',25,False,MUTED)
        self.text_at(d,(110,204),self.titles[phase],67,True)
        self.room(d);self.student(d,t,phase);self.desktop(d)
        tiny=self.paper('数学错题',['3x + 2 = 17','3x = 17 + 2'],width=365,height=216)
        tiny=tiny.resize((290,171));im.paste(tiny,(680,578),tiny)
        if phase==0:
            sheet=self.paper('我的解题过程',['3x + 2 = 17','3x = 17 + 2','3x = 19','x = 19/3'],write=min(4,u*.55))
            im.paste(sheet,(1036,344),sheet)
        elif phase==1:
            sheet=self.paper('回看自己的步骤',['3x + 2 = 17','3x = 17 + 2','x = 19/3'],highlight=True)
            im.paste(sheet,(1036,344),sheet)
            # A hand-drawn circle is traced around the erroneous sign.
            d.arc((1367,498,1432,557),-45,-45+min(359,u*150),fill='#C96358',width=4)
        elif phase==2:
            old=self.paper('刚看过的题目',['3x + 2 = 17','x = 5'],width=430,height=320)
            x=1017-int(105*ease(u/1.1));im.paste(old,(x,365),old)
            new=self.paper('换一个条件',['4x + 3 = 19','4x = ...','x = ?'],width=480,height=350)
            angle=-10*(1-ease(u/1.3));new=new.rotate(angle,resample=Image.Resampling.BICUBIC,expand=True)
            nx=int(1900-785*ease(u/1.3));im.paste(new,(nx,326),new)
        elif phase==3:
            self.clock(d,t*1.3)
            count=min(8,int(u/.7)+1)
            for i in range(count):
                fall=ease((u-i*.7)/.65)
                sheet=self.paper(['方程','几何','函数'][i%3],['待复习'],width=395,height=180)
                sheet=sheet.rotate((i%3-1)*3,resample=Image.Resampling.BICUBIC,expand=True)
                yy=int(370+(245-i*10)*fall);im.paste(sheet,(1026+i%2*9,yy),sheet)
            # The student turns a page in the notebook on the desk.
            w=max(20,int(270*abs(math.cos(u*2.4))))
            page=Image.new('RGBA',(w,137),'#FFFFFFE8');pd=ImageDraw.Draw(page)
            for line in range(4):pd.line((8,25+line*27,w-8,25+line*27),fill='#CCD7E6',width=2)
            im.paste(page,(686+270-w,585),page)
        else:
            # A mobile device receives the student's question; the paper keeps
            # moving along the learning route while the labels stay fixed.
            d.rounded_rectangle((1328,331,1634,838),radius=35,fill='#E4EBF5',outline='#748AA7',width=4)
            d.rounded_rectangle((1342,355,1620,811),radius=24,fill='white')
            d.rounded_rectangle((1430,343,1530,359),radius=7,fill='#748AA7')
            self.text_at(d,(1392,391),'错题帮',32,True,BLUE)
            card=self.paper('数学',['3x + 2 = 17'],width=225,height=178)
            im.paste(card,(1365,468),card)
            d.ellipse((1453,716,1506,769),fill='#E5F0E9',outline='#87AA94',width=2)
            d.line((1466,742,1476,751,1494,731),fill='#517C60',width=5)
            progress=(u%2.4)/2.4
            px=int(760+650*ease(progress));py=int(655-144*math.sin(progress*math.pi/2))
            fly=self.paper('我的题目',['3x + 2 = 17'],width=210,height=158)
            size=1-.45*progress;fly=fly.resize((int(fly.width*size),int(fly.height*size)))
            if progress<.92:im.paste(fly,(px,py),fly)
            for i,label in enumerate(['拍题诊断','订正训练','复习巩固']):
                x=705+i*355
                d.ellipse((x,860,x+39,899),fill='#E5EDFC')
                self.text_at(d,(x+13,864),str(i+1),22,True,BLUE)
                self.text_at(d,(x+57,860),label,29,True)
                if i<2:d.line((x+214,879,x+309,879),fill='#AFC0D8',width=3)
        self.arms(d,t,phase)
        return im

    def frame(self,t,total):
        phase=max(i for i,start in enumerate(self.starts) if t>=start)
        current=self.scene(phase,t,total)
        if phase and t-self.starts[phase]<.28:
            previous=self.scene(phase-1,t,total)
            current=Image.blend(previous,current,ease((t-self.starts[phase])/.28))
            # Scene objects dissolve; the complete title stays sharp and fixed.
            d=ImageDraw.Draw(current);d.rectangle((90,185,1830,305),fill=BG)
            self.text_at(d,(110,204),self.titles[phase],67,True)
        return current
