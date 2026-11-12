# 学生 R1 定点复测

环境：http://127.0.0.1:8103/；新profile；JS index-CConNtCE.js，CSS index-CO-yA6Fi.css。

离线逐条冲突、OCR空主框确认、负数实例、归档原答和补充反馈已得到对应证据。原考试解析格式仍失败。基准文件未修改。

## R1-S20 E06每条草稿独立冲突、重编辑与明确确认

修复通过。位置第一次409；确认本机位置后仅位置200，答案仍以原base单独409，显示本机x4/服务器x5；第二在线档案刷新仍x5。重编辑本机为x4.0并改说明后，答案请求仍使用旧base，409再显示x5，在线刷新仍x5。断网关闭Chrome、重新从根URL打开离线学习并解锁，x4.0和冲突比较保留。最后明确确认本机答案、接受原生后果确认，答案200并0条待同步，在线刷新才变为x4.0；再次同步无POST，无重复写。

可见路径：学生2新档案→离线学习→设置口令→下载E01短课→断网保存位置及x4；第二新档案在线保存x5→联网同步→仅确认位置→重编辑本机x4.0→再同步→断网关闭重开→确认本机答案
写入与回读：被动网络精确顺序：POST offline/sync 409位置→200确认位置→409答案x4→409重编辑x4.0→200确认答案；原base为1994a2…直到独立确认才使用728c76…。只改本轮新离线草稿，formalSubmission=false。
边界：本轮真实断网/重开/两档案并发/原生确认/重同步已做；复杂多题冲突、服务500、权限过期由主代理技术补测。

证据：[r1-offline/shots/r1-E06-initial-conflict-two-records.png](r1-offline/shots/r1-E06-initial-conflict-two-records.png), [r1-offline/shots/r1-E06-position-confirmed-answer-still-conflict.png](r1-offline/shots/r1-E06-position-confirmed-answer-still-conflict.png), [r1-online/shots/r1-E06-online-five-after-position-only.png](r1-online/shots/r1-E06-online-five-after-position-only.png), [r1-offline/shots/r1-E06-reedited-still-conflict.png](r1-offline/shots/r1-E06-reedited-still-conflict.png), [r1-online/shots/r1-E06-online-five-after-local-edit.png](r1-online/shots/r1-E06-online-five-after-local-edit.png), [r1-offline/shots/r1-E06-offline-reopen-retains-edited-conflict.png](r1-offline/shots/r1-E06-offline-reopen-retains-edited-conflict.png), [r1-offline/shots/r1-E06-answer-explicitly-confirmed.png](r1-offline/shots/r1-E06-answer-explicitly-confirmed.png), [r1-online/shots/r1-E06-online-after-explicit-answer-confirm.png](r1-online/shots/r1-E06-online-after-explicit-answer-confirm.png)

## R1-S07 OCR主提问空白时直接确认已修订题目

修复通过。OCR真实识别3x+5=20与原答x6。人工修订为R1合成题后，主learning-question仍为空，确认按钮立即创建真实文字指导job-4b6cf6a89f6d473d980c8c5f82c15e74，得到先消去+5、两边同时减5的提示与追问；没有再要求填主框。

可见路径：等式课→问一问→新一轮→上传自有合成题图→识别题图→人工修订→保持主框空→确认题目并获取指导
写入与回读：真实OCR job-eb731339299348a38d61ac2b156b466e和指导任务均succeeded；完整input/result/runs在r1-ai-observed-results.json，不以一次成功代替内容检查。
边界：本轮空主框确认/人工修订/真实模型回报已做；未新增长AI异常请求。

证据：[r1-main/shots/r1-OCR-confirm-empty-main-before.png](r1-main/shots/r1-OCR-confirm-empty-main-before.png), [r1-main/shots/r1-OCR-empty-main-real-guidance.png](r1-main/shots/r1-OCR-empty-main-real-guidance.png), [r1-main/shots/r1-OCR-guidance-steps.png](r1-main/shots/r1-OCR-guidance-steps.png), [r1-ai-observed-results.json](r1-ai-observed-results.json)

## R1-S06 5=5同减负数的模型语义与核对范围

本示例修复通过。真实新job-bd18256daa1d41588a5945d6b2ef2f14。提示将减负数改写为加相反数；三步依次明确5=5两边同减-2、两边均为(5)-(-2)、均为7；追问要求写出两边表达式。核验提示范围为“仅核对声明关系和可解析数值等式；未验证自然语言及完整教学适切性。”此次未出现基准混用5和-2或只改变一边的表达。

可见路径：原等式课同加同减→问一问→开始新一轮→原文重问→一步步看三步→Tab打开核对范围
写入与回读：输入原文保持“为什么等式两边都减去同一个负数仍然相等？请用5=5、c=-2说明。”；完整提示/3步/追问/mathClaims/verification及实际上下文均落盘。
边界：只对本次真实返回作结论；不扩张为所有模型输出正确或自然语言已被程序证明。

证据：[r1-main/shots/r1-AI-negative-step-two.png](r1-main/shots/r1-AI-negative-step-two.png), [r1-main/shots/r1-AI-negative-step-three.png](r1-main/shots/r1-AI-negative-step-three.png), [r1-main/shots/r1-AI-scope-visible.png](r1-main/shots/r1-AI-scope-visible.png), [r1-ai-observed-results.json](r1-ai-observed-results.json)

## R1-S17 课堂及考试归档进入原答记录

修复通过。两个入口均直接进入学习记录并自动展开对应任务。课堂原答2*x+3=11→x4、1次作答可见；原考试两题x7与x5、2次作答可见，无空答案编辑器。

可见路径：学习首页→已提交→课堂记录进入任务；返回首页已提交→考试讲评进入任务
写入与回读：原任务记录由GET platform重读；没有提交任何归档题新答。
边界：本轮入口与原答回看通过；归档导出基准已做，未重复。

证据：[r1-main/shots/r1-class-archive-opens-raw-record.png](r1-main/shots/r1-class-archive-opens-raw-record.png), [r1-main/shots/r1-exam-archive-opens-raw-record.png](r1-main/shots/r1-exam-archive-opens-raw-record.png)

## R1-S16 原考试发布解析的格式及流程尾注

残留失败。仍显示字面\n\n和“本题为待教师审核的候选题。”；18/30及原错答x8、原解释均只读保留。本轮确认index-CConNtCE.js，仍在同一真实学生入口复现。

可见路径：学生2新档案→班级→考试→原E04已发布卷→第2题
写入与回读：原卷GET读取，未改旧答；DOM额外核对input/textarea readOnly=true。
边界：可能仅新生成候选已修复；原考试展示此路径仍失败，已及时报主代理。

证据：[r1-online/shots/r1-original-exam-comment-format.png](r1-online/shots/r1-original-exam-comment-format.png), [r1-online/r1-snapshots.jsonl](r1-online/r1-snapshots.jsonl)

## R1-S19 补充后续反馈修复后的学生回看

修复通过。主学生读到完整“全量合成验收E03后续反馈R1：你的说明已完整解释相同、可逆的运算保持等式相等，并用代入检验x=4成立。”；原提交学习说明保留。教师侧另有真实PUT200及刷新回读证据。

可见路径：原E02任务→更多学习操作→学习结果→本课资料与进度
写入与回读：学生新profile从原任务重新GET补充读取，教师反馈与原说明均实际可见。
边界：原405由教师重发验证，学生没有以脚本替代教师写入；学生观察与教师网络证据区分。

证据：[r1-main/shots/r1-supplement-feedback-readable.png](r1-main/shots/r1-supplement-feedback-readable.png)

## R1-S04 停用课时建草稿后仍隐藏

通过。合成工程验收 E01 方程短课显示1课时，仅E01等式平衡短课；管理员处于停用但新建修订草稿的AD11版本与停用课时未显示。

可见路径：学生2新档案→学习→课程
写入与回读：课程目录真实GET与DOM；已通知管理员交叉核对。
边界：没有读取管理员隐藏路由或业务源码。

证据：[r1-online/shots/r1-catalog-disabled-lesson-hidden.png](r1-online/shots/r1-catalog-disabled-lesson-hidden.png)

## R1-S23 辅助教师单题顺序批阅的新提交

学生提交通过，教师顺序批阅回执待补。全新卷exam-29dabdaaf2cf428c9aa699b2ef96e1b0，第1题x+5=12答x7并解释共同减5/代入，第2题x+4=9答x5并解释差0/代入；真实交卷200后刷新显示已交卷、等待教师发布成绩。

可见路径：班级→考试→R1顺序批阅验收1112→开始→两题新答→保存草稿→原生确认交卷
写入与回读：草稿保存、提交与刷新；未改任何旧考试答案。初次input[type=text]未匹配默认type属性，已取消原生交卷、改用可见input填妥两题再真实提交，属于driver定位纠正。
边界：本轮仅支援教师定点单题顺序批阅，未重跑全考试平台。

证据：[r1-main/shots/r1-new-exam-draft-two.png](r1-main/shots/r1-new-exam-draft-two.png), [r1-main/shots/r1-new-exam-submitted-readonly.png](r1-main/shots/r1-new-exam-submitted-readonly.png)

## R1-S15 移班后历史草稿只读且另一个班保留

UI只读边界通过。新草稿x4及解释在刷新后保存。教师UI移出一班后，原课明确显示“已移出班级，此任务仅可回看”；原x4/解释保留，答案与解释disabled=true，提交作答与需要提示disabled=true。首页待完成/学习中0，班级页仅保留教师2隔离班，一班不再显示。

可见路径：学生3新profile→首页E01短课→保存新草稿并刷新→教师UI移出一班→刷新原课→首页→班级
写入与回读：新草稿由真实保存进度PUT200；教师移班后GET重读保留原值且禁用提交。E01补发为主代理技术操作，另一课堂归档补发/移出为教师真实UI操作，来源区分。
边界：没有对已禁用输入强制改值或绕过按钮；服务器权限边界由主代理技术补测。刷新前保存中触发原生beforeunload确认，接受后草稿保留；等待该原生对话造成的driver超时未归为产品失败。

证据：[r1-student3/shots/r1-student3-new-draft-before-removal.png](r1-student3/shots/r1-student3-new-draft-before-removal.png), [r1-student3/shots/r1-student3-removed-task-readonly.png](r1-student3/shots/r1-student3-removed-task-readonly.png), [r1-student3/shots/r1-student3-removed-task-home-history.png](r1-student3/shots/r1-student3-removed-task-home-history.png), [r1-student3/shots/r1-student3-isolation-class-preserved.png](r1-student3/shots/r1-student3-isolation-class-preserved.png)

## 未测及待补

- 语音设备限制沿用基准：仅文字回退已测，无可用麦克风/中文TTS不记通过。
- 故障500、超时、完整权限过期/撤回边界由主代理技术补测；本代理不伪称已覆盖。
- 教师补发给学生3的原E01任务由主代理技术验证操作产生，不归为教师UI补发；学生自己的寻路、保存与移班回读仍独立记录。
- 教师新卷顺序批阅回执。
