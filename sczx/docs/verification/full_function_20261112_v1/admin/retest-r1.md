# 管理员 R1 定点复测

新 profile，确认 `index-CConNtCE.js` / `index-CO-yA6Fi.css`。基准文件哈希保持不变，未启动新的 AI 任务。

检索后的任务列表/详情500已修复；旧检索、文字和OCR结果及单次执行记录均可恢复。管理分类刷新返回、帮助队列入口以及停用课时历史/修订路径均通过。没有发现新的阻断。

|复测项|结果|
|---|---|
|AD17 检索后历史、详情、执行记录|通过；4条历史恢复，E01 v1命中，AD06撤回样例排除|
|AD15/16 文字/OCR原结果与执行记录|通过；原问题/识别文本与gpt-6-luna记录恢复|
|models/accounts刷新与离开返回|通过；无section查询的返回页再次刷新也保留分类|
|帮助与反馈进入队列|通过；明确section=queue，不落到上次账号/模型分类|
|AD11 停用历史、修订、学生隐藏|通过；历史可读，修订后仍withdrawn，学生目录仍隐藏|
|AD10 空知识点提示|422保护有效；原P3泛化提示保留|

## R1-AD17 · 检索后任务列表、详情与执行记录恢复

路径：8103首页→管理员登录 → 管理与运行→能力验证 → 最近任务→已有10:59案例检索 → 展开E01结果与执行记录。

- 全新profile确认index-CConNtCE.js、index-CO-yA6Fi.css。
- 最近任务恢复4条，已配置状态显示最近调用成功。
- 旧job-bbc83f964c224fafa4dbc63716b46455详情200，UI恢复原查询与E01案例、旧示例两条结果；AD06已撤回案例不在结果。
- 响应result.variant及runs[0].result.variant均保留字符串B3，详情及运行展开不再500。
- 同一已有真实结果rerankApplied=true、rerankAttempted=true、rerankModel=gpt-6-luna，E01版本仍1/version-96c75b97037c4cc8b0bae23c9412505c。
- 执行记录可见第1次成功、BM25基础检索标签；本次未重新发AI任务。

证据：r1-AD17-retrieval-restored.png、r1-AD17-result-version-run.png。

实际点击请求：

- GET /api/ai/jobs → 200；r1-network.jsonl:13 (n=18)。
- GET /api/ai/capabilities → 200；r1-network.jsonl:14 (n=17)。
- GET /api/ai/jobs → 200；r1-network.jsonl:15 (n=21)。
- GET /api/ai/capabilities → 200；r1-network.jsonl:16 (n=20)。
- GET /api/ai/jobs/job-bbc83f964c224fafa4dbc63716b46455 → 200；r1-network.jsonl:20 (n=25)。
- GET /api/ai/jobs → 200；r1-network.jsonl:21 (n=27)。
- GET /api/ai/capabilities → 200；r1-network.jsonl:22 (n=26)。
- GET /api/ai/jobs → 200；r1-network.jsonl:25 (n=35)。
- GET /api/ai/capabilities → 200；r1-network.jsonl:27 (n=34)。
- GET /api/ai/jobs → 200；r1-network.jsonl:35 (n=44)。
- GET /api/ai/capabilities → 200；r1-network.jsonl:38 (n=43)。
- GET /api/ai/jobs → 200；r1-network.jsonl:84 (n=106)。
- GET /api/ai/capabilities → 200；r1-network.jsonl:86 (n=105)。
- GET /api/ai/jobs → 200；r1-network.jsonl:88 (n=109)。
- GET /api/ai/capabilities → 200；r1-network.jsonl:90 (n=108)。
- GET /api/ai/jobs → 200；r1-network.jsonl:93 (n=115)。
- GET /api/ai/capabilities → 200；r1-network.jsonl:94 (n=114)。
- GET /api/ai/jobs → 200；r1-network.jsonl:97 (n=119)。
- GET /api/ai/capabilities → 200；r1-network.jsonl:98 (n=118)。

范围说明：检索诊断卡只展示摘要与匹配依据，版本ID由点击触发的实际响应核对，未手工请求接口。。

## R1-AD15-16 · 原文字/OCR指导及运行明细回读

路径：能力验证→最近任务→10:48文字指导→执行记录 → 最近任务→10:54题图识别→执行记录 → 失败与重试。

- 文字指导恢复原合成问题、引导文本及第1次成功/gpt-6-luna。
- OCR恢复自有题图识别文本、2x+3=11及原错误作答，并展开第1次成功/gpt-6-luna。
- 失败与重试显示暂无失败任务，列表请求200。

证据：r1-AD15-text-run-restored.png、r1-AD16-ocr-run-restored.png、r1-failure-widget-no-failures.png。

实际点击请求：

- GET /api/ai/failures → 200；r1-network.jsonl:12 (n=19)。
- GET /api/ai/failures → 200；r1-network.jsonl:17 (n=22)。
- GET /api/ai/failures → 200；r1-network.jsonl:26 (n=36)。
- GET /api/ai/failures → 200；r1-network.jsonl:34 (n=45)。
- GET /api/ai/failures → 200；r1-network.jsonl:85 (n=107)。
- GET /api/ai/failures → 200；r1-network.jsonl:87 (n=110)。
- GET /api/ai/jobs/job-e62b2f88eca64027a116fe512e56e83d → 200；r1-network.jsonl:92 (n=113)。
- GET /api/ai/jobs/job-d2ec9d675b2c4db48da758863e77794c → 200；r1-network.jsonl:95 (n=117)。

范围说明：管理员本人的已有任务均单次成功；无多次重试任务可UI回读，未伪称该特例通过。学生/教师重试由相应角色另行报告。；普通管理员能力验证任务stop仍按能力边界不适用，本次未新发任务。。

## R1-NAV-01 · 管理models/accounts刷新及离开返回

路径：管理与运行→能力验证→刷新 → 课程内容→管理与运行 → 账号→刷新 → 资料与案例→管理与运行→刷新。

- models直接刷新保留能力验证分类。
- 离开课程内容后主导航返回，URL可为/issues，实际仍能力验证，最近任务4条。
- accounts直接刷新、离开资料与案例返回、返回后无section查询的页面再刷新，都保留账号分类与本轮账号列表。

证据：r1-models-refresh-section.png、r1-models-leave-return.png、r1-accounts-refresh-section.png、r1-accounts-leave-return.png、r1-accounts-return-refresh.png。

## R1-NAV-02 · 帮助与反馈明确进入问题队列

路径：账号分类 → 帮助与反馈。

- 帮助与反馈直接转至/issues?section=queue，实际显示问题反馈队列、搜索/状态筛选、合成反馈1112；没有错误恢复到上次账号或模型分类。

证据：r1-help-explicit-queue.png。

## R1-AD11 · 停用课时历史、创建修订及学生继续隐藏

路径：课程内容→课程下拉→本轮合成课程 → 已停用AD11课时→历史发布版本→版本1 → 创建修订→刷新 → 学生代理独立新profile→学习→课程。

- 已停用课时现在打开只读详情，显示1节1题、预览、创建修订和历史版本。
- 版本1预览仍原正文，版本1/2均列出。
- 创建修订POST200，返回status=withdrawn、published=null、draft存在；刷新后列表仍已停用，编辑器显示草稿，未重新发布。
- 学生代理独立确认本轮课程仅1课时E01等式平衡短课，AD11停用课时仍不展示。

证据：r1-AD11-disabled-details.png、r1-AD11-disabled-history-v1.png、r1-AD11-revision-still-withdrawn.png、r1-AD11-draft-refresh.png。

实际点击请求：

- POST /api/curriculum/lessons/lesson-8bcb06fbd1bd4ab2b8ee49a569394e4f/revise → 200；r1-network.jsonl:71 (n=88)。

范围说明：学生侧证据由/root/full_student提供：/tmp/sczx-full/student/r1-online/shots/r1-catalog-disabled-lesson-hidden.png；DOM和课程响应保存在其r1-online日志。；本次唯一成功业务变更为对自有停用AD11创建修订；没有发布、改E01v1或改学生数据。。

## R1-AD10 · 空知识点名称校验提示复查

路径：课程内容→知识前置关系→知识点 → 保持空名称→保存知识关系 → 离开该编辑区，不保存新节点。

- 服务器仍422阻止空知识点，既有知识图未写入新节点。
- UI仍只显示“操作未能完成，请重试”，未定位名称为空；原P3提示改进项保留，非R1新阻断。

证据：r1-AD10-empty-name-hint.png。

实际点击请求：

- PUT /api/curriculum/knowledge → 422；r1-network.jsonl:80 (n=101)。

## 保留限制

- 无本管理员多次重试样本，未把已有单次运行恢复说成重试全部通过；失败区当前为空。
- 旧导入仍无浏览器数据，由root另做合成fixture技术补测；真实语音效果与baseline其他未测边界保持原限制。
- 空知识点名泛化提示为原P3项，未出现新的阻断，不要求无问题返修。
- 本次只对自有AD11已停用课时创建修订，未重新发布；未改E01v1、账号、学生任务或既有知识点。
- baseline.json / baseline.md 已与基准证据索引校验哈希不变。R1日志为 r1-actions.jsonl / r1-network.jsonl。
- 98条点击观察网络记录：96个200、1个首次未登录401、1个预期空名422；无500，无新POST AI任务。
- 私有浏览器 profile-r1/ 及其他 profile 目录不得进入公开证据包。
