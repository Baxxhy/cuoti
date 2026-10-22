"""Verify the rendered competition cut and package the reviewed deliverables."""
import json,subprocess,re,hashlib,zipfile,sys
from pathlib import Path
from PIL import Image,ImageDraw
from produce import ROOT,WORK,O,D,FF,SCENES,CLIPS,font,duration,txt,BG,INK,BLUE,MUTED,captions

movie=D/'错题帮_参赛演示_三步学习版.mp4'
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
    srt=(D/'错题帮_参赛演示_三步学习版.srt').read_text(encoding='utf-8-sig')
    ranges=re.findall(r'(\d\d:\d\d:\d\d,\d{3}) --> (\d\d:\d\d:\d\d,\d{3})',srt)
    end=0
    for a,b in ranges:
        a,b=sec(a),sec(b);assert a>=end-.002 and b>a and b<=seconds+.03;end=b
    first=next(s for s in SCENES if s['id']=='intro');account=next(s for s in timeline if s['id']=='account')
    assert first['seconds']>=35 and account['actual_seconds']<=10
    assert {s['stage'] for s in timeline if s['shots']}=={0,1,2,3}
    partial={'39-review-answer':8.3,'41-review-schedule':16.9}
    for scene in SCENES:
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
    result=dict(file=movie.name,seconds=seconds,bytes=movie.stat().st_size,sha256=hashlib.sha256(movie.read_bytes()).hexdigest(),resolution='1920x1080',fps=25,audio='AAC / 48000 Hz / stereo',chapters=6,subtitle_segments=len(ranges),max_volume_dbfs=peak,mean_volume_dbfs=mean,full_decode='passed',script_subtitle_match='passed',source_ranges='passed',previous_full_films_preserved='passed',account_seconds=account['actual_seconds'],intro_seconds=first['seconds'])
    (D/'视频校验.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False),flush=True)

def package():
    qa=json.loads((D/'视频校验.json').read_text());assert hashlib.sha256(movie.read_bytes()).hexdigest()==qa['sha256']
    def clock(t):return f'{int(t//60):02}:{int(t%60):02}'
    groups=[]
    for c in timeline:
        key='背景与入口' if c['id'] in ['intro','account'] else ('第'+str(c['stage'])+'步：'+c['title'] if c['stage'] else c['title'])
        if groups and groups[-1]['name']==key:groups[-1]['end']=c['film_end']
        else:groups.append(dict(name=key,start=c['film_start'],end=c['film_end']))
    table='\n'.join(f'| {g["name"]} | {clock(g["start"])}–{clock(g["end"])} |' for g in groups)
    readme=f'''# 错题帮参赛演示：三步学习版

建议提交和展示本目录中的《错题帮_参赛演示_三步学习版.mp4》。时长约5分20秒（{qa['seconds']}秒），1920×1080，25帧/秒，H.264视频与AAC双声道音频；文件约{qa['bytes']/1048576:.1f} MiB。

内容以初二学生“小林”的学习情境展开：背景动机 → 简短账号入口 → 拍题诊断 → 订正训练 → 复习巩固 → 技术协作与应用价值。学生为演示角色，旁白为中文合成语音。原始手机浏览器实录的结果保持原样，重新编排旁白、画面和字幕。

| 内容 | 时间 |
|---|---|
{table}

注册登录合计约8秒。三个核心阶段始终使用统一的三步导航，相关操作作为同一段学习过程呈现。影片保留错因证据、订正、互动图解、类似题与迁移、复习、易错地图、报告、模拟考试和组卷导出；改密码、反复筛选和复杂参数题的长篇解析不再展开。

复习镜头包含一条预置到期计划，作答、核对与再次调度实际运行，画面和旁白均有说明。考试过程为实录节选，仍保留“已确认20分、一题待核对”。订正记录明确保留辅助使用情况，没有将其改为独立掌握。

本目录另附字幕、章节导航、讲解稿、封面、赛事对照及校验记录。MP4已经烧录字幕，普通观看不需要重复加载SRT。上一版16分55秒的完整横屏和竖屏视频保留在上级目录。
'''
    (D/'README.md').write_text(readme)
    compliance='''# 赛事要求与本版调整

## 核验依据

依据团队提供、落款2026年9月28日的《2026“仓颉杯”智能编程大赛通知》和《2026“仓颉杯”智能编程大赛章程》。已核对文件哈希，与此前完整读取的原件相同：

- 通知：SHA-256 `d0be79ada46dddb823463e228c60ae3e62dad39d841b9e507e6a776084ff77a6`。
- 章程：SHA-256 `b53e8d238e578fe961f8d77dae85dbec8322d041f8f137062217d6ed75b9d9c4`。
- 官方活动索引：[仓颉编程语言官网](https://cangjie-lang.cn/article/classify)，已查询2026“仓颉杯”报名活动。具体视频内容要求以附件通知正文为本次对照依据。

通知物理第3页要求综合系统赛道视频展示“系统主要业务流程和核心智能功能”。本版以学生的三步学习展示真实运行：录题与错因证据、订正与训练反馈、复习及考试后的持续学习。22秒技术协作说明仓颉业务/MySQL与Python算法服务的职责，保持单协调器口径，与当前README和源码一致。

现有通知和章程没有把初赛作品视频硬性限定为5–6分钟；本版按用户要求与展示节奏控制在该区间。通知物理第4页、章程物理第7页的决赛安排为项目陈述5分钟、实机演示8–10分钟及专家问答，不能混为初赛视频时长要求。实际提交仍应核对组委会后续补充通知。

## 与上一版的区别

- 约17分钟改为约5分20秒；56项逐操作标题改为三条学生主线。
- 注册登录缩为约8秒，取消改密等外围流程的详细演示。
- 背景增加为45秒，集中解释找不准错因、理解难迁移、复习缺少顺序；技术实现放在核心演示之后。
- 同一功能中的选图、框选、识别和核对合并到拍题过程，不再分别包装成独立功能。
- 统一简短标题与字号，重写旁白；依据新配音逐词时间生成字幕，保留实际页面名称和结果。
- 剔除与主线无关、公式连写密集的复杂题镜头；没有改写原生页面、替换判定或宣称已修复业务代码中的排版。
- 提示、图解和图片识别仍按实际使用记录展示。考试待核对、复习预置日期如实披露，不包装为学生实验或提分证明。

## 本次验收

全片已完整解码；音轨格式、峰值、时长、6个章节、字幕时序及字幕与旁白全文一致性检查通过。每组镜头抽取中段与末段，共32张画面，供视觉检查。原始录像与镜头区间保留在本地制作目录；交付包不包含账号、模型凭据或内部回执。

本次只修改视频及其交付材料，未修改业务代码、数据库或运行配置。原完整版文件通过SHA-256检查，保持不变。
'''
    (D/'赛事对照与验收.md').write_text(compliance)
    im=Image.new('RGB',(1920,1080),BG);d=ImageDraw.Draw(im)
    d.rectangle((0,0,13,1080),fill=BLUE);txt(d,(110,60),'错题帮  /  2026“仓颉杯”智能编程大赛',29,True,BLUE)
    txt(d,(110,233),'从一道错题',90,True);txt(d,(110,363),'走完三步学习',90,True)
    for i,(a,b) in enumerate([('拍题诊断','找到具体偏差'),('订正训练','修复思路与验证'),('复习巩固','回顾、检验与继续学习')]):
        y=563+i*105;txt(d,(116,y),str(i+1).zfill(2),34,True,BLUE);txt(d,(190,y-4),a,40,True);txt(d,(418,y+6),b,28,False,MUTED)
    shot=Image.open(WORK/'take2/05-photo-confirm.png').convert('RGB');shot.thumbnail((432,936))
    d.rounded_rectangle((1225,40,1681,1030),radius=26,fill='white',outline='#CCD7E7',width=3);im.paste(shot,(1237,64))
    txt(d,(115,966),'学生视角  ·  约5分20秒  ·  核心功能实录',31,False,BLUE)
    im.save(D/'视频封面.png')
    (D/'.gitignore').write_text('*.zip\n')
    archive=D/'错题帮_参赛演示_三步学习版_交付包.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=5) as z:
        for p in sorted(D.iterdir()):
            if p.is_file() and not p.name.startswith('.') and p.suffix!='.zip':z.write(p,p.name)
    with zipfile.ZipFile(archive) as z:assert z.testzip() is None
    print('packaged',archive,flush=True)

if __name__=='__main__':
    if sys.argv[1]=='audit':audit()
    elif sys.argv[1]=='package':package()
