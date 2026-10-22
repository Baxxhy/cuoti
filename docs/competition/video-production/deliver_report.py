"""Write the delivery index, functional evidence map, and final archive."""
from pathlib import Path
import json,hashlib,zipfile
from compose import R,O,WORK

D=R/'docs/competition/deliverables/演示视频'
qa=json.loads((D/'视频文件校验.json').read_text());assert {x['mode'] for x in qa}=={'landscape','portrait'}
for q in qa:assert q['sha256']==hashlib.sha256((D/q['file']).read_bytes()).hexdigest()
timeline=json.loads((O/'final-timeline-landscape.json').read_text());lookup={x['id']:x for x in timeline}
def clock(t):return f'{int(t//60):02}:{int(t%60):02}'
def where(a,b=None):return clock(lookup[a]['film_start'])+'–'+clock(lookup[b or a]['film_end'])
groups=[
('注册与个性设置','01-register','02-login-settings','注册初二账号、退出重登，设置数学、巩固目标及十分钟预算。'),
('选图与错因分析','03-photo-upload','06-evidence-replay','真实上传演示题纸、框选、OCR、核对、分析、查看依据、人工修正、逐步回放及学习安排。'),
('订正与独立对照','07-task-start','12-journey','局部订正、重新作答、草稿刷新和任务恢复、互动图解、图片答案识别、条件对照、自检要点与学习档案。最终明确显示“在帮助下完成”，没有改成独立掌握。'),
('手动录题与收藏','13-manual-entry',None,'填写题干、原答案和分步作答，保存、收藏并分析。'),
('AI讲解完整流程','14-tutor-start','20-tutor-transfer','理解检查、解释、根据反馈补充、类似题练习、围绕疑惑追问、历史对话、生活情境迁移，直到“本轮已经完成”。'),
('类似题与变式','21-similar-start','25-variation-recovery','真实选题和作答；复杂题保留待核对状态；变式选项A通过核对；已保存结果可恢复。选题等待有明确剪辑标注。'),
('知识学习','26-related-knowledge','30-knowledge-framework','相关知识入口、跨年级搜索、知识卡、AI老师、概念解释与章节框架。'),
('题库练习','31b-bank-list','32-bank-practice','当前年级题库、关键词筛选、实际作答、判定和刷新恢复，示例答案为−5。'),
('模拟考试','33-exam-setup','38-exam-mistake','五题十分钟、答题卡、逐题作答、刷新后恢复答案和计时、交卷、核对、加入错题本及考试记录。已确认20/25，四题答对、一题待核对。'),
('到期复习','39-review-answer','42-review-range','预置一条到期计划后，真实提交解法、判题、基本掌握自评、再次调度、历史、搜索及保存专项范围。下一日期显示为2026-10-30。'),
('地图与学习报告','43-error-map','45-knowledge-relations','易错线索关联原题和核对依据，学习报告显示当前记录估计，知识关系支持图形、列表及跳回错题。'),
('检索与专项组卷','46-notebook-filter','49b-export-preview','关键词、收藏筛选、带入三道题、命名、排序、分值、保存，生成并实际打开题目PDF、答案PDF和学习表格；另展示真实PDF文件预览。'),
('账号与使用帮助','50-profile-help','51c-new-login','修改昵称、保存、使用指南，验证原密码后修改密码，再以新密码登录，原有资料保留。'),
('题目管理','53-question-manage',None,'使用单独的整理示例，修改题干并保存，再经确认移出错题本；没有删除核心演示题。'),
('独立图解入口','54-standalone-diagram',None,'从讲解进入图解、调整参数、查看观察提示、填写自己的观察并保存返回。'),
('回到学习起点','52-final-home',None,'回看资料与学习中心，返回今日页。'),
]
rows=['| 功能 | 横屏版位置 | 实际结果 |','|---|---|---|']
rows += [f'| {name} | {where(a,b)} | {text} |' for name,a,b,text in groups]
table='\n'.join(rows)
checks='\n'.join(f'| {"横屏" if x["mode"]=="landscape" else "竖屏"} | {clock(x["seconds"])} | {x["bytes"]/1048576:.1f} MiB | {x["chapters"]} | {x["caption_segments"]} | {x["peak_db"]} dBFS | 通过 |' for x in qa)
report=f'''# 功能覆盖与验收

制作日期：2026年10月23日（北京时间）。演示角色为虚构初二学生“小林”，旁白为中文合成语音。

## 录制范围

真实 Chromium 手机视口432×936，演示uni-app/Vue 3学生端。请求由实际仓颉业务服务、MySQL和Python算法服务处理。没有拦截接口替换结果，也没有修改页面DOM伪造通过状态。动画、章节文字和文件预览属于后期制作，操作区域来自真实浏览器录像。

本片覆盖学生可用的全部主要功能类别，56段操作，加上开场、真实文件预览和结尾，共59个章节。管理员入口不属于学生权限范围；影片不是Android安装包或真机摄像头录像。

## 功能与证据

{table}

## 素材与剪辑

题目纸和答案图片为本次自行制作的演示材料，OCR、诊断、作答和数据保存实际运行。到期复习仅把该演示账号一条已生成计划的时间设为到期，并在页面、旁白和字幕中披露；没有预置答案、判分或后续调度结果。下一次复习由实际业务逻辑生成。

只压缩标注过的计算等待，删除录制定位失败及无关等待；不加速学生操作。四段定位超时素材仅采用超时前经画面检查的成功操作部分，后续结果由另一个真实片段接续。保留了原始录像、逐段时间和接口回执，内部资料位于本地`.runtime/competition-video/`，不放入交付包。

旁白长于操作时，保留最后一帧实际页面并继续播放字幕。修复了初次合成的短段画面提前结束问题，最终章节按实际视频帧对齐，避免AAC补齐时间造成累计漂移。

## 运行与修复

- 修复练习模式切换后H5地址未同步的问题，防止刷新回到错误练习模式；已补充切换、刷新与结果恢复测试。
- 前端52个测试文件、300项测试通过；TypeScript检查、H5构建和App本地资源构建通过。App资源构建不等于签名安装包验证。
- 新浏览器会话实测模式切换URL正确；首页进入错题搜索连续三次复测，无页面异常。
- 录制结束后，仓颉服务、MySQL与表版本、Python算法服务、5175前端健康检查全部通过。
- 两份真实导出PDF可解析并渲染，均为一页；学习表格为有效XLSX，含工作表。

## 成片检查

两版均为H.264视频、AAC双声道音频、48kHz，标称25帧/秒。完整解码、章节数量、字幕顺序和字幕边界自动检查通过；逐章抽帧检查另有内部留档。

| 版本 | 时长 | 大小 | 章节 | 字幕段 | 音频峰值 | 全片解码 |
|---|---|---|---|---|---|---|
{checks}

画面抽查覆盖开场、录题、诊断、订正、AI讲解、练习、考试、复习、地图、报告、导出、账户和结尾；字幕位于操作区外。音量数据为程序检测结果。

## 保留的真实状态

复杂类似题和考试中的范围题仍有“待核对”状态，影片没有改成正确或错误的确定结论。报告中的18%是当前记录估计，不是提分结果或学生实验。变式题部分原始解析公式排版较密，影片保留真实页面内容。

早期录制在一次页面快速切换时记录到两条uni-app空节点异常，未阻断操作；新会话三次同路径复测未复现。未以本片宣称整个系统绝无缺陷。

SHA-256与文件属性见《视频文件校验.json》。
'''
(D/'功能覆盖与验收.md').write_text(report)
readme='''# 错题帮作品演示视频

建议先观看**错题帮_完整作品演示_手机实录.mp4**：1920×1080横屏，左侧为章节重点，右侧为真实手机界面。竖屏版为1080×2400，同一套完整内容，方便手机全屏观看。

以初二学生小林的情境，从注册登录走到错题录入、诊断、订正、讲解、训练、模拟考试、复习、知识学习、学习报告、组卷导出和账号管理。开头及结尾有原创动画，全程中文合成旁白与烧录字幕；另附独立SRT及章节时间表。

学生是演示角色，使用独立新注册账号和自行制作的题纸。复习预置的一条到期计划、计算等待压缩、AI待核对结果均在影片中说明。真实结果没有替换。

文件说明：

- 两个MP4：完整横屏与竖屏作品演示。
- SRT：需要单独编辑字幕时使用；MP4已内嵌画面字幕，普通观看无需再次加载。
- 章节TXT：按功能直接跳转观看。
- 演示讲解稿：可编辑的完整中文旁白。
- 功能覆盖与验收：主要流程、实际结果、测试与保留事项。
- 视频文件校验JSON：时长、大小、SHA-256、音轨与解码检查结果。
- 封面PNG：用于提交页预览。

本包不包含账号密码、登录令牌、模型配置、原始录屏和内部定位记录。
'''
(D/'README.md').write_text(readme)
(D/'.gitignore').write_text('*.zip\n')
archive=D/'错题帮_作品演示视频_交付包.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=5) as z:
    for p in sorted(D.iterdir()):
        if p.is_file() and p.suffix!='.zip' and not p.name.startswith('.'):
            z.write(p,p.name)
with zipfile.ZipFile(archive) as z:assert z.testzip() is None
print('Delivered',len(qa),'videos;',len(timeline),'chapters; archive MB',round(archive.stat().st_size/1048576,1))
