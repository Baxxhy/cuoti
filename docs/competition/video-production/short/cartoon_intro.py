"""Blue cartoon cover and animated opening, matching the demonstration layout."""
from PIL import Image, ImageDraw
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
        self.text_at(d,(106,283),'错题帮',113,True)
        self.text_at(d,(114,448),'AI 错题学习助手',39,False,BLUE)
        self.text_at(d,(110,574),'让每一道错题',54,True)
        self.text_at(d,(110,653),'成为下一步。',54,True)
        self.text_at(d,(114,838),'拍题诊断  /  订正训练  /  复习巩固',29,False,BLUE)
        self.text_at(d,(114,969),'作品演示',25,False,MUTED)
        # Reuse the identical animated character and scene objects on the cover.
        # This keeps the cover, opening and demonstration typography consistent.
        scene=self.scene(0,5,34.48)
        art=scene.crop((210,310,1700,925)).resize((1080,446),Image.Resampling.LANCZOS)
        im.paste(art,(770,353))
        return im

    def frame(self,t,total):
        if t<COVER_SECONDS:return self.cover.copy()
        current=super().frame(t,total)
        if t<COVER_SECONDS+.28:
            current=Image.blend(self.cover,current,(t-COVER_SECONDS)/.28)
        return current
