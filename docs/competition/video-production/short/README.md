# 三步学习参赛精简版

目标是5–6分钟的比赛展示：背景动机、简短账号入口、拍题诊断、订正训练、复习巩固、技术协作与总结。不是将原片整体加速，也不把一次拍题中的多个按钮拆成多个功能。

`storyboard.json`保存新旁白、三步阶段、镜头区间和必要说明。`produce.py`从原始手机浏览器录像取材，重新制作动画、背景、字幕与音轨；`check_delivery.py`检查成片并生成说明及交付包。它们不修改业务数据和程序配置。

在项目根目录按顺序执行：

1. `.venv/bin/python docs/competition/video-production/short/produce.py voices`
2. `.venv/bin/python docs/competition/video-production/short/produce.py render`
3. `.venv/bin/python docs/competition/video-production/short/produce.py finish`
4. `.venv/bin/python docs/competition/video-production/short/check_delivery.py audit`
5. 实际查看`.runtime/competition-video/short/qa/`中的逐段抽帧，再执行`check_delivery.py package`。

旁白通过TTS逐词时间生成字幕，程序检查字幕与旁白文字一致、时间不重叠、字幕不越界。仅修正已制作的字幕时，可运行`produce.py recaption`：它只覆盖设计好的字幕背景带，不改变手机屏幕区域；修改镜头或标题时，使用`render 镜头ID,...`重建相应片段，再合并及复核。

最终交付位于`docs/competition/deliverables/演示视频/比赛精简版/`。上一版横屏与竖屏完整影片保留在上级目录，并经SHA-256校验确认不变。赛事依据和时间说明在交付目录的《赛事对照与验收》中。
