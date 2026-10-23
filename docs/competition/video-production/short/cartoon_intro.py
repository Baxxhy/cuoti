"""Blue abstract brand cover and cartoon opening, matching the demonstration layout."""
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
        self.text_at(d,(110,85),'2026“仓颉杯”智能编程大赛',27,False,MUTED)
        self.text_at(d,(102,340),'错题帮',142,True)
        self.text_at(d,(113,541),'AI 错题学习助手',41,False,BLUE)
        self.text_at(d,(114,969),'作品演示',25,False,MUTED)
        # Independent brand art: no people, interface, exercise or learner data.
        art=Image.open(Path(__file__).resolve().parent/'assets/brand-cover-art.png').convert('RGBA')
        art.thumbnail((1090,670),Image.Resampling.LANCZOS)
        im.paste(art,(785,285+(670-art.height)//2),art)
        return im

    def frame(self,t,total):
        if t<COVER_SECONDS:return self.cover.copy()
        current=super().frame(t,total)
        if t<COVER_SECONDS+.28:
            current=Image.blend(self.cover,current,(t-COVER_SECONDS)/.28)
        return current
