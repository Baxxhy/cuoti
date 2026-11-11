# 学生角色基线走查（2026-11-12）

结论：**89/100，未达到95。** 这是AI模拟学生视角的浏览器走查，不是真人研究或真实学生满意度。全部评分沿用固定规则，未按目标抬分。

## 范围与方法

8102 静态前端（主代理确认3f64基线），1440×1000。只从登录入口开始用真实指针与键盘操作；未读取路由源码猜入口、未直接改hash、未脚本调用业务API、未改源码。学生账号私读，不输出密码。所有写入是隔离QA环境的新模拟记录，原答案保留。

## 路径与结果

### T1 登录、任务、学习/目录/求助、独立练习与结果（4/5）

入口点击数：1（从相应可见主界面计算，不含填写）。

登录→首页继续学习（1次入口点击）→目录→独立检查→开始练习→逐题提交→完成练习→学习结果

4道新独立题均保存且显示正确；随堂旧原答未改。求助请求已发送但恢复后未看到结果。结果确认提交提示缺少6块学习，返回本课补齐一次，未宣称已交给教师。

绕路：一次：结果提交才获知学习未完成，返回本课。

证据：[15-submit-check.png](./15-submit-check.png)、[28-check-result.png](./28-check-result.png)、[32-submit-confirmed.png](./32-submit-confirmed.png)

### T2 找错题、订正与复习（5/5）

入口点击数：1（从相应可见主界面计算，不含填写）。

错题帮→x+7=12→分析这道题→开始订正→下一步×2→填写解释→练一道类似的题→输入8与过程→提交；返回错题帮→更多功能→复习（复习2次入口点击）

原题原答0保留；新类似题x+5=13答8保存且显示答案核对正确。复习页可见新的练习次数。

绕路：入口直接找到；额外查看原列表是主动观察恢复，不算绕路。

证据：[35-wrong-list.png](./35-wrong-list.png)、[49-repair-submitted.png](./49-repair-submitted.png)、[52-review-page.png](./52-review-page.png)

### T3 回看学习记录（5/5）

入口点击数：2（从相应可见主界面计算，不含填写）。

更多功能→学习记录→等式性质/2026-11-12/5次作答→查看学习结果

可回看已存答案、正确状态，并回到对应任务结果/本课。首次记录入口需展开更多；已展开时1次。

绕路：无错误路径。

证据：[54-record-expanded.png](./54-record-expanded.png)、[22-record-to-result.png](./continued/22-record-to-result.png)

### T4 找班级、考试、课堂（5/5）

入口点击数：{'class': 2, 'exams': 1, 'live': 1}（从相应可见主界面计算，不含填写）。

更多功能→我的班级→查看学习任务回首页；我的考试→进入考试→开始考试→填写2与过程→保存草稿→刷新；重新登录→我的课堂→回看课堂

三个入口均可点击找到。新考试草稿刷新恢复成功；课堂为已结束，可回看原答案。考试确认交卷触发CDP超时，未宣称交卷成功。

绕路：无产品阻断入口。浏览器工具故障单独记录。

证据：[55-class-page.png](./55-class-page.png)、[63-exam-recovery.png](./63-exam-recovery.png)、[03-live-replay.png](./continued/03-live-replay.png)

### T5 找到离线学习并返回（5/5）

入口点击数：2（从相应可见主界面计算，不含填写）。

更多功能→离线学习→首次使用设置口令→启用并加密保存→下载课时→打开下载课时→师承智学品牌回首页

全新浏览器档案成功下载一个课时并打开，点品牌可返回在线首页。未清除已有学生数据。

绕路：无。

证据：[05-offline-entry.png](./continued/05-offline-entry.png)、[12-offline-read.png](./continued/12-offline-read.png)、[13-offline-return-home.png](./continued/13-offline-return-home.png)

### T6 提交反馈并查看记录入口（4/5）

入口点击数：1（从相应可见主界面计算，不含填写）。

帮助与反馈→填写模拟学生意见→提交反馈→重新打开帮助与反馈→查看反馈记录→Escape关闭遮挡弹窗

系统反馈成功保存，记录中看到本次意见。教师教学反馈仅观察到首页已有消息入口，未完成本次教师回评闭环。

绕路：一次：跳转记录后额外关闭旧帮助弹窗。

证据：[16-feedback-submit.png](./continued/16-feedback-submit.png)、[18-feedback-records.png](./continued/18-feedback-records.png)、[19-feedback-close.png](./continued/19-feedback-close.png)

## 问题清单

### S01 P1

实际观察：类似题 x+5=13 的引导仍让学生抵消 +7，和新题不对应。

推断：学生照提示操作会减错数。

建议位置/修复：类似题提示绑定当前题；没有可信提示时仅保留题目与输入。

证据：[46-repair-new-question-ready.png](./46-repair-new-question-ready.png)

### S02 P2

实际观察：主栏5项，更多功能再列复习、学习记录、离线学习、我的班级、问题与回复5项；复习与错题、班级与课堂/考试分散。

推断：相关活动之间需要跨分组寻找，更多功能标签无法预测内容。

建议位置/修复：使用学习、错题与复习、班级三个稳定分组；记录归入学习，考试/课堂归入班级，离线归入课程，反馈归入帮助。

证据：[34-more-open-independent.png](./34-more-open-independent.png)、[52-review-page.png](./52-review-page.png)、[55-class-page.png](./55-class-page.png)

### S03 P2

实际观察：帮助弹窗点查看反馈记录后路由已到问题与回复，但弹窗仍保持打开；额外按 Escape 才能看记录。

推断：入口已完成导航而覆盖层仍遮挡目的地，产生一次额外回退操作。

建议位置/修复：导航前关闭帮助弹窗，保留一个反馈中心。

证据：[18-feedback-records.png](./continued/18-feedback-records.png)、[19-feedback-close.png](./continued/19-feedback-close.png)

### S04 P2

实际观察：目录可直接进入独立检查；4题答完结果显示准备交给老师。确认提交才提示6项学习未完成，一整行列出缺项。

推断：结果主操作与实际完成条件不一致，需要返回本课补齐。

建议位置/修复：结果页在主按钮前呈现可点击未完成项，主按钮直接继续未完成学习；完成后再显示交给老师。

证据：[11-check-entry.png](./11-check-entry.png)、[28-check-result.png](./28-check-result.png)、[32-submit-confirmed.png](./32-submit-confirmed.png)、[23-result-to-lesson.png](./continued/23-result-to-lesson.png)

### S05 P2

实际观察：正文/控件计算字体为Geist Variable/Noto Sans CJK SC/Microsoft YaHei；数学公式计算字体另用Cambria Math/STIX Two Math/Times New Roman serif。练习公式47.52px，题干15px，公式x为明显衬线斜体。

推断：数学与普通文本的字形切换是当前异体感的可证来源；未发现普通控件随意使用多个字族。

建议位置/修复：网页数学统一一套与界面协调的字族、字重和比例；保留必需的数学语义，不牵动DOCX导出字体。

证据：[02-continue-learning.png](./02-continue-learning.png)、[33-help-click-stable.png](./continued/33-help-click-stable.png)、actions.json action=fonts、continued/actions.json action=fonts

### S06 P2

实际观察：首次问一问弹窗能发送请求并显示处理中。换浏览器登录回同一任务同一题后，再点问一问仅短暂显示保存中，等待3秒后仍无弹窗、结果或错误。

推断：可能存在恢复/请求状态与打开弹窗之间的时序问题，需实现方复现；本次未看到真实指导结果。

建议位置/修复：弹窗立即打开并呈现加载、恢复结果或可重试错误；不让保存阻止入口却无说明。

证据：[03-ask-dialog.png](./03-ask-dialog.png)、[05-help-request.png](./05-help-request.png)、[33-help-click-stable.png](./continued/33-help-click-stable.png)、[34-help-after-save.png](./continued/34-help-after-save.png)

### S07 P3

实际观察：首页学习工具重复给出整理错题、我的考试、进入课堂；已有相同侧栏目的地，名称也不同。

推断：轻度重复，增加页面常驻信息。

建议位置/修复：保留当前任务、待办和消息，重复工具改为上下文需要时出现。

证据：[01-home.png](./01-home.png)

### S08 P3

实际观察：我的班级卡副文案为“七年级数学 · · 演示教师”，存在双分隔符。

推断：空字段没有过滤。

建议位置/修复：仅拼接有值的字段。

证据：[55-class-page.png](./55-class-page.png)

## 固定评分

| 项 | 得分 | 扣分依据 |
|---|---:|---|
|任务|28/30|T1结果后才要求补课，T6转记录弹窗遮挡，各一次绕路|
|导航|20/25|分组S02扣2；重复S07扣1；子功能S02扣1；返回S03扣1|
|信息主次|18/20|首页重复工具S07扣1；订正旧提示S01扣1；学习与记录各5|
|字体|14/15|UI字族和正文层级各5；数学异体S05扣1|
|反馈与键盘|9/10|恢复求助缺少结果/错误反馈S06扣1；Escape关弹窗并归焦5|
|总分|**89/100**||

评分项详表与每个扣分关联见 [baseline.json](./baseline.json)。同一问题在不同指标产生的实际成本分别计入；没有把页面中读屏专用名称重复算作视觉冗余。

## 限制与未完成项

- 考试确认交卷后CDP Input.dispatchMouseEvent/Page.captureScreenshot超时；外部处理原生对话框返回No dialog，不以工具超时判产品bug。新浏览器重新登录后继续其余路径。考试交卷未验收。
- 本轮课程结果提交被未读学习块校验拦住，之后只补齐天平活动和一部分课时；未宣称教学任务已交给教师。
- 求助真实请求已发起，初次弹窗关闭后未看到结果；恢复后入口问题需要主代理定位。
- 教学反馈仅观察入口，未验证本次教师反馈回写。
- 未人为制造接口断网失败；已验证必填禁用、异步处理中、保存成功、提交校验失败、刷新恢复和Escape归焦。
- 普通界面字体一致，字体问题只按实测数学异体扣1分；SR-only重复可访问名称未计入可见文案堆叠。

## 原始证据

[第一段点击日志](./actions.json)， [恢复浏览器后的点击日志](./continued/actions.json)。两段共99条成功记录，截图、URL、可见控件、输入和字体计算值随动作保存。两段浏览器脚本错误数组均为空；CDP工具超时单独记录，不当成产品错误。

建议先修S01/S03/S04/S06，随后按S02合并入口与S05统一数学排版，再按同一任务和同一评分表复测。