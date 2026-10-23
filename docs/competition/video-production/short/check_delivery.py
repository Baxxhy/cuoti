"""Verify the rendered competition cut and package the reviewed deliverables."""
import json,subprocess,re,hashlib,zipfile,sys
import numpy as np
from pathlib import Path
from PIL import Image,ImageDraw
from produce import ROOT,WORK,O,D,FF,V,SCENES,CLIPS,STEPS,MOVIE_NAME,font,duration,txt,BG,INK,BLUE,MUTED,captions,intro_animation,background

movie=D/MOVIE_NAME
Q=O/'qa';Q.mkdir(exist_ok=True)
timeline=json.loads((O/'final-timeline.json').read_text())

def audit():
    seconds=duration(movie);assert 300<=seconds<=360,seconds
    info=subprocess.run([FF,'-hide_banner','-i',str(movie)],capture_output=True,text=True).stderr
    (Q/'streams.txt').write_text(info)
    assert all(s in info for s in ['1920x1080','25 fps','h264','aac','48000 Hz','stereo'])
    assert len(re.findall('Chapter #',info))==6
    decode=subprocess.run([FF,'-v','error','-i',str(movie),'-f','null','-'],capture_output=True,text=True)
    (Q/'decode.txt').write_text(decode.stderr);assert decode.returncode==0 and not decode.stderr.strip(),decode.stderr
    volume=subprocess.run([FF,'-hide_banner','-i',str(movie),'-vn','-af','volumedetect','-f','null','-'],capture_output=True,text=True).stderr
    (Q/'volume.txt').write_text(volume)
    peak=float(re.search(r'max_volume: ([\-\d.]+)',volume)[1]);mean=float(re.search(r'mean_volume: ([\-\d.]+)',volume)[1])
    assert -15<peak<0 and -35<mean<-8,(peak,mean)
    def sec(t):
        h,m,x=t.replace(',','.').split(':');return int(h)*3600+int(m)*60+float(x)
    srt=(D/Path(MOVIE_NAME).with_suffix('.srt')).read_text(encoding='utf-8-sig')
    ranges=re.findall(r'(\d\d:\d\d:\d\d,\d{3}) --> (\d\d:\d\d:\d\d,\d{3})',srt)
    end=0
    for a,b in ranges:
        a,b=sec(a),sec(b);assert a>=end-.002 and b>a and b<=seconds+.03;end=b
    first=next(s for s in timeline if s['id']=='intro');account=next(s for s in timeline if s['id']=='account')
    assert 25<=first['actual_seconds']<=38 and account['actual_seconds']<=6
    assert 2.5<=first['actual_seconds']-duration(V/'intro.mp3')<=2.75
    import cartoon_intro,student_animation
    assert all(getattr(module,key)==value for module in [cartoon_intro,student_animation] for key,value in [('BG',BG),('INK',INK),('BLUE',BLUE),('MUTED',MUTED)])
    assert font(44).getname()[0]=='Noto Sans CJK SC'
    assert font(44,True).getname()[0]=='Noto Sans CJK SC'
    assert {s['stage'] for s in timeline if s['shots']}=={0,1,2,3}
    partial={'39-review-answer':8.3,'41-review-schedule':16.9}
    for scene in SCENES:
        assert not any(bad in scene['text'] for bad in ['偏差','不是','不只是','而不只是','原图会保留'])
        if scene['shots']:
            canvas=np.asarray(background(scene))
            assert np.ptp(canvas[:,0:12],axis=(0,1)).max()==0
            assert np.ptp(canvas[1008:1064,80:1130],axis=(0,1)).max()==0
            assert scene['title']!='复习巩固'
        text=''.join(x[2] for x in captions(scene))
        assert re.sub(r'\s','',text)==re.sub(r'\s','',scene['text']),(scene['id'],text)
        for a,b,t in captions(scene):assert font(34).getlength(t)<=1040,(scene['id'],t)
        for shot in scene['shots']:
            if 'clip' not in shot:continue
            clip=CLIPS[shot['clip']]
            assert clip['status']=='ok' or (shot['clip'] in partial and shot['end']<=partial[shot['clip']])
    assert '符号错误' in CLIPS['05-photo-confirm']['finalText']
    assert '本轮已经完成' in CLIPS['20-tutor-transfer']['finalText']
    assert '待核对' in CLIPS['37-exam-submit']['finalText']
    assert '回答正确' in CLIPS['40-review-grade']['finalText']
    # Check that both previously delivered full films remain byte-for-byte intact.
    old=json.loads((D.parent/'视频文件校验.json').read_text())
    for entry in old:assert hashlib.sha256((D.parent/entry['file']).read_bytes()).hexdigest()==entry['sha256']
    # Check actual wrist/arm animation in the encoded cartoon scene,
    # excluding titles and subtitles.
    motion=[]
    for i,start in enumerate(intro_animation().starts):
        samples=[]
        for j,t in enumerate([start+.45,start+1.15]):
            path=Q/f'intro-action-{i}-{j}.png'
            subprocess.run([FF,'-v','error','-y','-ss',str(t),'-i',str(movie),'-frames:v','1',str(path)],check=True)
            samples.append(np.asarray(Image.open(path).convert('RGB')).astype(np.int16))
        changed=int(np.count_nonzero(np.max(np.abs(samples[0][500:738,480:925]-samples[1][500:738,480:925]),axis=2)>20))
        assert changed>400,(i,changed)
        motion.append(dict(beat=i,seconds=[start+.45,start+1.15],changed_character_pixels=changed))
    # The separately delivered poster must actually appear at the movie opening.
    first_frame=Q/'cover-first-frame.png'
    subprocess.run([FF,'-v','error','-y','-i',str(movie),'-frames:v','1',str(first_frame)],check=True)
    expected=np.asarray(intro_animation().cover).astype('int16')
    actual=np.asarray(Image.open(first_frame).convert('RGB')).astype('int16')
    cover_mae=float(np.abs(expected-actual).mean());assert cover_mae<4,cover_mae
    sheets=[[],[]]
    for n,c in enumerate(timeline):
        for j,fraction in enumerate([.52,.91]):
            path=Q/f'{n+1:02}-{c["id"]}-{j}.png'
            t=c['film_start']+c['actual_seconds']*fraction
            subprocess.run([FF,'-v','error','-y','-ss',str(t),'-i',str(movie),'-frames:v','1',str(path)],check=True)
            im=Image.open(path).convert('RGB');assert im.getextrema()!=((0,0),(0,0),(0,0))
            im.thumbnail((480,270));tile=Image.new('RGB',(480,306),'white');tile.paste(im,(0,33))
            ImageDraw.Draw(tile).text((7,5),c['id']+' / '+c['title'],font=font(17),fill='black');sheets[j].append(tile)
    for j,tiles in enumerate(sheets):
        im=Image.new('RGB',(1920,1224),'#D9E1EE')
        for n,tile in enumerate(tiles):im.paste(tile,((n%4)*480,(n//4)*306))
        im.save(Q/f'contact-{j}.png')
    result=dict(file=movie.name,seconds=seconds,bytes=movie.stat().st_size,sha256=hashlib.sha256(movie.read_bytes()).hexdigest(),resolution='1920x1080',fps=25,audio='AAC / 48000 Hz / stereo',chapters=6,subtitle_segments=len(ranges),max_volume_dbfs=peak,mean_volume_dbfs=mean,full_decode='passed',script_subtitle_match='passed',source_ranges='passed',previous_full_films_preserved='passed',account_seconds=account['actual_seconds'],intro_seconds=first['actual_seconds'],chinese_font=font(44).getname()[0],intro_motion=motion,cover_first_frame_mae=cover_mae,opening_visuals='blue cartoon student with writing and page-turn animation',removed_overlay_checks='passed',cover_intro_body_palette='matched: #F6F8FC / #17263F / #2454CE')
    (D/'视频校验.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False),flush=True)

def package():
    qa=json.loads((D/'视频校验.json').read_text());assert hashlib.sha256(movie.read_bytes()).hexdigest()==qa['sha256']
    rounded=round(qa['seconds']);human=f'{rounded//60}分{rounded%60:02}秒'
    def clock(t):return f'{int(t//60):02}:{int(t%60):02}'
    groups=[]
    for c in timeline:
        if c['id'] in ['intro','account']:key='背景与入口'
        elif c['stage']:key='第'+str(c['stage'])+'步：'+STEPS[c['stage']-1]
        else:key=c['title']
        if groups and groups[-1]['name']==key:groups[-1]['end']=c['film_end']
        else:groups.append(dict(name=key,start=c['film_start'],end=c['film_end']))
    table='\n'.join(f'| {g["name"]} | {clock(g["start"])}–{clock(g["end"])} |' for g in groups)
    readme=f'''# 错题帮参赛演示：品牌封面版

当前推荐文件：《{MOVIE_NAME}》。片长{human}（{qa['seconds']}秒），1920×1080，25帧/秒，H.264视频与AAC双声道音频；约{qa['bytes']/1048576:.1f} MiB。

视频前2秒显示独立品牌封面，以蓝色书本、纸页与学习路径表达主题；封面不含人物、产品界面、具体题目或学习数据。主视觉使用内置图片生成工具制作，提示词与原始素材保存在制作目录。开场保留动笔、翻页、错题堆叠及题目进入手机的连续动画，场景切换与旁白同步；背景、标题、服装和书桌统一采用主体演示的浅蓝与深蓝配色。开场音轨结束后直接进入账号镜头。

| 内容 | 时间 |
|---|---|
{table}

主体保留学生三步学习结构，画面使用拍题诊断、订正训练、到期回顾、易错地图、模拟考试及专项组卷等标题。顶部重复导航、左侧蓝条、底部实录说明及重复的“复习巩固”大标题均已移除。图示、封面和字幕统一使用简体中文字体。

学生“小林”为演示角色，旁白为中文合成语音。主体来自实际浏览器操作录像。到期任务作了演示用时间预置，作答、判定与再次调度实际运行；考试保留已确认20分及一题待核对的结果，订正保留辅助使用记录。

附有字幕、章节导航、讲解稿、封面、赛事对照和校验记录。MP4已烧录字幕。原16分55秒的完整影片保留在上级目录。
'''
    (D/'README.md').write_text(readme)
    compliance=f'''# 本轮画面修订与验收

## 用户标注的六处画面

1. 封面使用独立蓝色纸艺品牌主视觉，移除人物、截图、题目和学习数据。后续开场保留卡通学生与连续动作。全片统一蓝色系，正式封面作为视频前2秒，同时单独交付PNG。
2. 删除“学生使用情境 · 浏览器手机视口实录”底部说明。
3. 删除主体画面上方重复的三步导航。
4. 删除画面及封面左侧蓝色竖条。
5. 第三阶段按当前内容显示到期回顾、易错地图、模拟考试、专项组卷，移除重复的“复习巩固”大标题。
6. 删除动画画面底部的角色与配音说明，相关来源集中放在本文件及README中。

## 字体与旁白

绘图字体明确指定Noto Sans CJK SC字形集，常规与粗体均使用简体中文；字幕同样指定该字体。原字体集合默认选中日文字形，本轮修正了具体字形集的选择。

旁白直接说明学生的上传、核对、订正、作答和回顾操作，使用“哪一步做错了”等具体表达；捕题段落围绕学生实际操作展开。已删除抽象的错误定位措辞、原图后台保存说明和对比句式。使用anti-defensive-writing技能整理表达，并保留演示任务预置、待核对与辅助使用记录的真实范围。

封面停留2秒，开场按配音逐词时间切换五个叙事段落。卡通场景及动作由student_animation.py维护，cartoon_intro.py负责同风格封面与开场连接。开场音轨长{duration(V/'intro.mp3'):.2f}秒，画面长{qa['intro_seconds']:.2f}秒，随后直接进入账号操作；账号段约{qa['account_seconds']:.2f}秒。

## 赛事依据

依据团队提供、落款2026年9月28日的《2026“仓颉杯”智能编程大赛通知》和章程。通知物理第3页要求展示系统主要业务流程和核心智能功能。本版保留拍题、诊断、订正、练习、复习、考试及导出的业务衔接，补充仓颉/MySQL与Python算法服务的职责。

通知SHA-256：`d0be79ada46dddb823463e228c60ae3e62dad39d841b9e507e6a776084ff77a6`。
章程SHA-256：`b53e8d238e578fe961f8d77dae85dbec8322d041f8f137062217d6ed75b9d9c4`。
官方活动索引：[仓颉编程语言官网](https://cangjie-lang.cn/article/classify)。

本版按用户要求保持5–6分钟。原件中的决赛陈述和实机演示另有时间安排，提交时沿用相应阶段的要求及组委会补充通知。

## 实际验证

- 全片解码、视频音轨格式、峰值、6个章节、字幕顺序及字幕与旁白全文一致性检查通过。
- 五个开场段落分别抽取两帧，在人物手臂区域检查实际动作变化，比较区域避开标题和字幕；另检查视频第一帧与正式封面的一致性。
- 主体背景的左侧边缘和底部说明区域已检查；字体常规与粗体均为简体中文。
- 每组主体镜头另抽取中段与末段检查，原始录像与镜头区间保留。
- 原16分55秒的两份影片SHA-256保持不变；本轮修改限于视频、字幕和交付材料。

数据与文件摘要见《视频校验.json》。
'''
    (D/'赛事对照与验收.md').write_text(compliance)
    intro_animation().cover.save(D/'视频封面.png')
    (D/'.gitignore').write_text('*.zip\n')
    parent=D.parent/'README.md';ptext=parent.read_text()
    ptext=re.sub(r'当前推荐观看.*?(?=\n\n本目录的)',f'当前推荐观看[品牌封面版](比赛精简版/README.md)：约{human}，前2秒为独立蓝色纸艺品牌封面，后续保留卡通学生及连续动作，全片采用统一的浅蓝与深蓝配色；主体保留真实操作演示，文字使用简体中文字体。',ptext,flags=re.S)
    parent.write_text(ptext)
    archive=D/(Path(MOVIE_NAME).stem+'_交付包.zip')
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=5) as z:
        for p in sorted(D.iterdir()):
            if p.is_file() and not p.name.startswith('.') and p.suffix!='.zip' and (p.suffix not in ['.mp4','.srt'] or p.stem==Path(MOVIE_NAME).stem):z.write(p,p.name)
    with zipfile.ZipFile(archive) as z:assert z.testzip() is None
    print('packaged',archive,flush=True)

if __name__=='__main__':
    if sys.argv[1]=='audit':audit()
    elif sys.argv[1]=='package':package()
