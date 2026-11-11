# 教师角色模拟评审：首次返修复测

AI模拟角色评审，非真人可用性研究。与基线采用同一6故事、100分量表。**98/100，达到95门槛**。

版本：index-BxirpJC8.js / index-BRBChled.css；8102，1440×1000，空profile登录。

|分项|基线|本轮|
|---|---:|---:|
|tasks|25/30|30/30|
|navigation|20/25|24/25|
|information|18/20|20/20|
|typography|12/15|14/15|
|feedback_keyboard|9/10|10/10|

## 实际点击与结果

### T1 概览→案例阅读选用：5/5

教学资源 → 输入“两边同时加3” → 检索 → 阅读案例（共同运算追问） → 用于备课

本轮真实提交检索并阅读选用结果，未通过手工hash找页面。

证据：retest1/actions.json#10-20, retest1/case-search.png, retest1/case-detail.png

### T2 备课编辑保存、学生预览、AI入口：5/5

修改课堂说明 → 保存 → 学生预览 → AI 备课 → 我的教案

实际保存QA教案，查看学生预览、AI任务页和已有任务列表。未执行新AI生成，不将入口可用等同本轮模型验收。

证据：retest1/actions.json#21-29, retest1/prepare-preview.png

### T3 发布班级任务并找成员：5/5

发布任务 → 确认发布 → 成员与邀请 → 学习任务

实际新发布一条QA任务，读取2名班级成员；任务固定版本后果保留。

证据：retest1/actions.json#30-37, retest1/publish-task.png, retest1/class-members.png

### T4 查看当前作答并保存反馈：5/5

班级教学 → 1/2已提交的等式性质：查看学情 → 演示学生：查看与反馈 → 作答 → 求助 → 补救 → 教师反馈 → 输入反馈 → 保存反馈

task-4a0bc55e09bc401d707d0204362460a4：读到本轮6次原答、天平观察、1次求助；补救为空。新反馈保存后已反馈0→1，学生代理从学习记录→学习结果刷新已确认可见。基线弹窗阻断修复。

证据：retest1/actions.json#50-73, retest1/student-original-answers.png, retest1/student-help-history.png, retest1/teacher-feedback-saved.png, /tmp/sczx-persona/student/retest1/69-feedback-result-refreshed.png

### T5 题库→试卷→考试答卷：5/5

题库与考试 → 题库 → 组卷 → 打开本轮1题QA试卷 → 发布考试 → 确认发布考试 → 考试与批阅 → 查看答卷 → 演示学生 → 填写讲评 → 保存批阅 → 发布成绩（提示仍有未交卷） → 专项学生二新profile：班级→考试→最新考试→开始→填写→确认交卷 → 教师重新读取新考试 → 保存学生二批阅 → 发布成绩

复用本轮新建1题10分QA试卷发布exam-a15978b2fecf4111917264153ce812e4，02:05—03:06北京时间。学生代理提交演示学生新答卷；本评审用专项学生二独立空profile只提交这个新考试。教师分别保存讲评（均10分）；1/2交卷时发布被明确拒绝，2/2后发布成功。学生代理已从UI回看10/10和本轮讲评。未改写任何旧考试成绩。

证据：retest1/actions.json#45-49, retest1/actions.json#75-83, retest1/actions.json#113-124, retest1/actions.json#142-150, retest1/bank-fonts.png, retest1/exam-beijing-time.png, retest1/exam-grading-saved.png, retest1/exam-results-published.png, retest1/student2/actions.json, retest1/student2/new-exam-second-submitted.png

### T6 实时课堂、分层、教研、复习依据与返回：5/5

班级教学 → 实时课堂 → 回看课堂 → 分层教学 → 新建安排 → 等式性质→读取分组建议 → 返回列表 → 学生复习 → 等式性质详情 → 收起 → 教学资源 → 教研交流 → 分享内容 → 关闭 → 备课

班级子页签把实时课堂、分层、学生复习放在同一语境，query保留class-demo；分层确实读到2名学生证据与建议。教研归教学资源。未新发分层或教研分享，按原故事入口和返回验收。

证据：retest1/actions.json#84-112, retest1/actions.json#125-130, retest1/live-review.png, retest1/layer-suggestions-loaded.png, retest1/memory-detail.png, retest1/community-share.png

## 基线修复与残余扣分

基线P1反馈弹窗、分组、概览、公式继承、记忆双列、北京时间和失败提示均已验证修复。

- P3 备课AI入口轻微重复：后续可合并全局AI备课页签与教案AI备课快捷按钮；当前均指向正确位置，不阻断。 证据 retest1/save-failure.png
- P3 学生预览行内公式字号仍略大：可将行内简单式限制为接近正文大小，独立公式保留更大字号。 证据 retest1/prepare-preview.png, retest1/actions.json#25

## 边界

- 采用与基线相同六故事/100分rubric；98是本次模拟评审分数，不代表真人研究结果或所有页面绝对无改进空间。
- AI入口和教研分享弹窗只按入口可达范围验收；未新运行AI备课、未发布分层安排、未发布教研分享。
- 新考试师生闭环实际完成，复用了本轮已审核QA试卷；基线已验证新建/审核试卷，复测未重复建立相同卷。
- 错误恢复仅当前profile一次PUT故障注入；恢复fetch后重新保存成功，无服务端故障推论。
- actions.json中少量no clickable match来自页面过渡中点击过早，以及一次测试器select:last-of-type误选班级字段；均等待完成/纠正selector后重试，未伪称产品故障。
- 根代理后续两处列表/题数小改尚未部署，不属于本次版本，本报告分数只针对记录assets。

## QA数据写入

- 案例用于备课后课堂说明保存为“先预测，再让两边同时加3；用x=8代回原式检查。”。
- 新发布一条QA等式性质任务。
- 本轮学生新任务task-4a0bc55e09bc401d707d0204362460a4新增教师反馈。
- 新发布考试exam-a15978b2fecf4111917264153ce812e4，两个新答卷均由本轮UI提交；新增两条批阅并发布成绩（10/10）。
- 未修改既有学生原答、旧考试分数或正式8099/qmx环境。
