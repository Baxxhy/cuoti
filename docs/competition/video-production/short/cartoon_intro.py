"""Blue product-screen cover and cartoon opening, matching the demonstration layout."""
from PIL import Image, ImageDraw
from pathlib import Path
from student_animation import StudentIntro as AnimatedStudent

BG='#F6F8FC';INK='#17263F';BLUE='#2454CE';MUTED='#52647B'
COVER_SECONDS=2.0

class StudentIntro(AnimatedStudent):
    def __init__(self,font,text,words):
        super().__init__(font,text,words)
        self.starts=[s+COVER_SECONDS for s in self.starts]
        self.cover=self.make_cover()

    def make_cover(self):
        im=Image.new('RGB',(1920,1080),BG);d=ImageDraw.Draw(im)
        self.text_at(d,(110,53),'错题帮',38,True,BLUE)
        self.text_at(d,(110,117),'2026“仓颉杯”智能编程大赛',25,False,MUTED)
        self.text_at(d,(106,278),'错题帮',113,True)
        self.text_at(d,(114,445),'AI 错题学习助手',39,False,BLUE)
        self.text_at(d,(110,583),'让每一道错题',53,True)
        self.text_at(d,(110,661),'成为下一步。',53,True)
        self.text_at(d,(114,845),'诊断  /  训练  /  复习',30,False,BLUE)
        self.text_at(d,(114,969),'作品演示',25,False,MUTED)
        assets=Path(__file__).resolve().parent/'assets'
        # All three screens are actual captures, with no regenerated UI or avatar.
        screens=[('错因定位','cover-diagnosis.png'),('互动订正','cover-interactive.png'),('易错地图','cover-map.png')]
        for i,(label,name) in enumerate(screens):
            x=820+i*340;y=267
            self.text_at(d,(x+14,192),f'0{i+1}',23,True,BLUE)
            self.text_at(d,(x+67,181),label,32,True)
            d.rounded_rectangle((x+7,y+9,x+321,y+701),radius=23,fill='#E2E9F5')
            d.rounded_rectangle((x,y,x+314,y+692),radius=23,fill='white',outline='#B8CAE6',width=2)
            shot=Image.open(assets/name).convert('RGB')
            shot=shot.resize((294,637),Image.Resampling.LANCZOS)
            im.paste(shot,(x+10,y+27))
        return im

    def frame(self,t,total):
        if t<COVER_SECONDS:return self.cover.copy()
        current=super().frame(t,total)
        if t<COVER_SECONDS+.28:
            current=Image.blend(self.cover,current,(t-COVER_SECONDS)/.28)
        return current
