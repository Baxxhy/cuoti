# 学生角色首轮返修复测（2026-11-12）

结论：**98/100**，超过95门槛。基线89/100。沿用同一固定评分表，两个剩余轻问题各扣1分；未因目标分数调整规则。此报告是AI模拟角色浏览器走查，不是真人研究或真实学生满意度。

## 版本与方法

8102静态候选：index-BxirpJC8 / index-BRBChled，主代理确认本轮保持稳定。全新Chrome profile，1440×1000。真实鼠标和键盘点击，未查路由猜首次入口、未直接改hash或脚本调用业务API、未改源码。模型由界面真实发起；断网/恢复由CDP浏览器网络仿真。

## 六故事与点击路径

### T1 登录、任务、学习/目录/求助、独立练习与结果（5/5）

入口点击数：1（不计填表和后续业务步骤）。

登录→首页开始学习→1—8块依次学习→天平同加1并解释→随堂两题→真实求助→独立4题→完成练习→交给老师→确认提交

task-4a0bc55e09bc401d707d0204362460a4 全新任务：天平解释、2随堂+4独立新答案均保存；求助真实回复可见、Escape归焦、重开恢复；完整提交成功。

绕路：无。提交后的教师反馈另见T6。

证据：[12-helper-result.png](./retest1/12-helper-result.png)、[14-helper-reopen.png](./retest1/14-helper-reopen.png)、[47-check-4-saved.png](./retest1/47-check-4-saved.png)、[51-submitted.png](./retest1/51-submitted.png)

### T2 找错题、订正与复习（5/5）

入口点击数：1（不计填表和后续业务步骤）。

错题与复习→待订正2x+6=10→分析→4步订正→填写解释→生成类似题→离页后返回恢复→需要一点提示→给我提示→填写3与过程→提交→错题帮→复习建议

新题3x+8=17题干为通用解题要求；真实提示指向当前题+8，无原题+6残留；答案3正确并记录这次用过帮助；复习页找到更新练习信息。

绕路：无。模型后台运行时离页处理其他任务，再返回成功恢复，是主动验证。

证据：[96-variant-restored.png](./retest1/96-variant-restored.png)、[100-variant-hint-finished.png](./retest1/100-variant-hint-finished.png)、[105-variant-saved.png](./retest1/105-variant-saved.png)、[107-review-tab.png](./retest1/107-review-tab.png)

### T3 回看学习记录（5/5）

入口点击数：1（不计填表和后续业务步骤）。

学习→学习记录→等式性质/2026-11-12/6次作答→查看学习结果→刷新

2随堂+4独立答案可回看；通过结果显示本次教师反馈。旧5次作答单独保留，未改旧原答。

绕路：无。

证据：[67-records-expand.png](./retest1/67-records-expand.png)、[69-feedback-result-refreshed.png](./retest1/69-feedback-result-refreshed.png)

### T4 找班级、考试、课堂（5/5）

入口点击数：{'class': 1, 'exam_from_class': 1, 'live_from_class': 1}（不计填表和后续业务步骤）。

班级→考试→最新考试→开始→填写→保存草稿→刷新恢复→确认交卷；课堂→回看课堂；教师发布成绩后班级→考试→最新进入考试回看

新考试exam-a15978b2fecf4111917264153ce812e4真实交卷，处理原生confirm且保留不可改后果提示。随后教师批阅发布，学生实际看到10/10与本轮讲评。已结束课堂可回看原答。班级双分隔符已消失。

绕路：无。原生confirm处理解决基线工具故障。

证据：[70-class-group.png](./retest1/70-class-group.png)、[73-live-replay.png](./retest1/73-live-replay.png)、[91-new-exam-draft-recovered.png](./retest1/91-new-exam-draft-recovered.png)、[93-new-exam-submitted.png](./retest1/93-new-exam-submitted.png)、[145-exam-final-current.png](./retest1/145-exam-final-current.png)

### T5 找到离线学习并返回（5/5）

入口点击数：2（不计填表和后续业务步骤）。

学习→离线学习→首次设置口令→启用并加密保存→下载→打开→真实断网→读到这里→下一节→联网→同步进度→返回学习

全新浏览器档案下载、断网读课时、保存本机位置、联网同步、返回学习均成功。未删除任何原有下载或学生答案。

绕路：无。学习组已经打开时只需1次tab点击。

证据：[116-offline-downloaded.png](./retest1/116-offline-downloaded.png)、[119-offline-reading.png](./retest1/119-offline-reading.png)、[120-offline-progress.png](./retest1/120-offline-progress.png)、[124-offline-synced.png](./retest1/124-offline-synced.png)、[126-home-after-offline.png](./retest1/126-home-after-offline.png)

### T6 提交反馈并查看记录入口（5/5）

入口点击数：1（不计填表和后续业务步骤）。

帮助与反馈→提交问题→填写→人为断网→提交失败→恢复网络→同表单提交重试→记录详情；学习记录→本次结果→刷新读取教师反馈

统一帮助页无旧帮助弹窗遮挡。真实网络失败保留输入并显示恢复提示，联网重试保存成功。教学闭环也看到教师刚回写“复测反馈：已能说明两边共同运算，请继续核对非零条件。”。

绕路：无。人为断网是计划内状态验证。

证据：[74-feedback-center.png](./retest1/74-feedback-center.png)、[79-feedback-error.png](./retest1/79-feedback-error.png)、[82-feedback-saved.png](./retest1/82-feedback-saved.png)、[69-feedback-result-refreshed.png](./retest1/69-feedback-result-refreshed.png)

## 基线返修逐项验证

- **S01 已实测修复**：新变式题3x+8=17使用通用任务提示；真实求助准确询问如何消去+8。 证据：[96-variant-restored.png](./retest1/96-variant-restored.png)、[100-variant-hint-finished.png](./retest1/100-variant-hint-finished.png)
- **S02 已实测修复**：主栏只保留学习/错题与复习/班级；子tab记录、离线、复习、考试、课堂都能由相关组找到。 证据：[137-home-final.png](./retest1/137-home-final.png)、[107-review-tab.png](./retest1/107-review-tab.png)、[70-class-group.png](./retest1/70-class-group.png)
- **S03 已实测修复**：帮助入口直接到统一页面，提交成功后记录详情可见，没有旧弹窗遮挡。 证据：[74-feedback-center.png](./retest1/74-feedback-center.png)、[82-feedback-saved.png](./retest1/82-feedback-saved.png)
- **S04 已实测修复**：基线旧未完成任务结果直接显示还有3项待完成、下一项随堂练习；继续完成实际落到5/8。新任务完整学习后可提交。 证据：[130-pending-result-ready.png](./retest1/130-pending-result-ready.png)、[132-pending-continue-ready.png](./retest1/132-pending-continue-ready.png)、[51-submitted.png](./retest1/51-submitted.png)
- **S05 已实测修复**：数学span与普通控件均为Geist Variable/Noto Sans CJK SC/Microsoft YaHei sans-serif，公式34px/500；字体计算证据在actions.json全部fonts动作。 证据：[96-variant-restored.png](./retest1/96-variant-restored.png)、[132-pending-continue-ready.png](./retest1/132-pending-continue-ready.png)
- **S06 已实测修复**：新任务求助真实生成后可关闭重开；原基线旧任务/旧题也从数据库恢复旧问题及指导。 证据：[12-helper-result.png](./retest1/12-helper-result.png)、[14-helper-reopen.png](./retest1/14-helper-reopen.png)、[134-old-helper-recovered-ready.png](./retest1/134-old-helper-recovered-ready.png)
- **S07 已实测修复**：首页重复学习工具区已移除；主要信息为任务、消息与反馈、接着练习。 证据：[137-home-final.png](./retest1/137-home-final.png)
- **S08 已实测修复**：班级卡只显示七年级数学·演示教师，不再有空字段双分隔符。 证据：[70-class-group.png](./retest1/70-class-group.png)

## 剩余问题与分数

| 项 | 得分 | 实际扣分 |
|---|---:|---|
|任务|30/30|六故事均直接完成；本轮真实提交、教师回评、学生回看均验证|
|导航|24/25|R1-02同班同名任务入口缺少发布批次区分，扣1|
|信息主次|19/20|R1-01介绍2题与实际4题不符，扣1|
|字体|15/15|普通界面、数学字族统一；正文层级与公式比例协调|
|反馈与键盘|10/10|断网失败保留输入、联网重试成功；Escape关闭并恢复可见焦点|
|总分|**98/100**||

### R1-01 P3

实际观察：独立检查介绍仍写2道题，开始后实际有1—4四题。

建议：按实际独立题集合计数或移除固定数量。

证据：[27-check-intro.png](./retest1/27-check-intro.png)、[28-check-start.png](./retest1/28-check-start.png)

### R1-02 P3

实际观察：同班同名的等式性质有多条；两条同样无截止时间且同状态时，仅凭列表可见字段难以区分发布批次。

建议：显示必要发布时间，过滤无截止时间空文案；保留真实任务并不删数据。

证据：[137-home-final.png](./retest1/137-home-final.png)

## 本次师生闭环实证

任务 task-4a0bc55e09bc401d707d0204362460a4：学生2随堂+4独立答案、天平观察、真实求助→完整提交→独立教师评审员实际回看并保存反馈→学生从学习记录进入结果并刷新看到本轮反馈。

考试 exam-a15978b2fecf4111917264153ce812e4：学生新答卷保存草稿、刷新恢复、原生确认交卷→教师保存批阅并发布→学生从班级考试列表进入看到10/10及本轮讲评。原生confirm文本为“提交后答卷只读，无法继续修改。确认交卷？”，由真实事件捕获并确认，基线CDP卡住不再出现。

## 限制与证据

- 这是固定六故事的AI角色模拟走查和主观UI量表，不能称真实学生满意度或真人测试。
- 本轮只桌面网页1440×1000；未做手机适配、真实语音设备或课堂现场验证。
- 后端模型生成会经历排队/处理中；本轮实际等待后均返回。
- R1-01/R1-02未在本轮版本修复；需后续仅对这两项定向复测。

本轮148条动作记录，浏览器脚本错误0，工具错误0；截图与字体计算值见 [actions.json](./retest1/actions.json)，固定分项与缺陷关联见 [retest1.json](./retest1.json)。baseline报告完整保留。