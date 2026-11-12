原始报告保留于同名 .md；此副本仅重定位证据链接，原始结构化JSON保持冻结内容。

# 管理员独立 UI 基准验收

日期：2026-11-12；版本：f6b4b5d / index-CxoPIcBj.js；初始地址仅 8103 首页；独立数据库 23325。

共记录21项实质功能。案例、材料、课程、知识点、账号、反馈及并发保护均实际写入并回读；AD17 检索后的任务详情/列表500阻断结果恢复。旧记录导入缺自有旧数据；语音仅通过客观设备限制与文字回退，均未伪称成功。

所有内容为合成工程验收，不代表教学效果。仅使用可见入口、表单和按钮；未读业务源码、未手输业务路由、未调用脚本业务API、未修改Vue状态。

## 需统一修复或判断

- **D-ADMIN-01 / P1 / AD17**：真实语义检索SSE已完成，但任务详情与任务列表连续500，历史指导/OCR也无法从页面恢复；同批能力配置成功却UI误显示未配置。见 AD17 截图与网络日志。
- **N-ADMIN-01 / P2 / AD11**：已停用课时仍可点击，右侧却只显示“选择或新建课时”；历史详情和可逆恢复入口均不可见。
- **N-ADMIN-02 / P3 / AD10**：空知识点名仅泛化“操作未能完成，请重试”，应标出具体行/名称。
- 数学状态候选已撤销：编辑会使核验失效；有效/错误列式重新核对与保存刷新均正确。

## 功能清单

|编号|功能|基准结果|
|---|---|---|
|AD01|账号创建、角色与重复错误|通过（已列范围）|
|AD02|原材料上传、解析、阅读与元信息保存|通过（已列范围）|
|AD03|真实AI提取新案例及来源链|通过（已列范围）|
|AD04|案例编辑、人工确认与发布交接|通过（已列范围）|
|AD05|识别文本修订与原文保留|通过（已列范围）|
|AD06|案例数学核验、失效提示与恢复|通过（已列范围）|
|AD07|案例修订新版本、历史预览与撤回|通过（已列范围）|
|AD08|课程与单元创建、目录元信息保存|通过（已列范围）|
|AD09|课时内容、题目、知识出处、预览核对发布|通过（已列范围）|
|AD10|知识点、别名与前置关系循环保护|通过，提示缺口|
|AD11|课时修订版本、历史预览与停用|业务通过，入口缺口|
|AD12|问题筛选、回复、追加往来与处理状态|通过（已列范围）|
|AD13|连接检查、断网错误与恢复|通过（已列范围）|
|AD14|旧浏览器记录导入入口|未测：无旧数据|
|AD15|真实文字指导与任务记录恢复、权限边界|检索回归前通过，后被AD17阻断|
|AD16|真实题图识别与结果恢复|检索回归前通过，后被AD17阻断|
|AD17|案例检索与语义重排后的任务记录回归|失败|
|AD18|本机文字朗读、停止准备与文字回退|设备受限；文字回退通过|
|AD19|语音输入权限失败与文字回退|权限受限；文字回退通过|
|AD20|问题处理并发冲突、保留草稿与重新读取重试|通过（已列范围）|
|AD21|课时排序及刷新恢复|通过（已列范围）|

## 分项记录

### AD01 · 账号创建、角色与重复错误

**目标与首击意图**：由管理员创建独立教师/学生合成账号，并验证刷新与重复反馈。 首击“管理与运行”。

**实际路径**：管理与运行 → 账号 → 新建账号 → 填写登录账号/显示名称/身份/初始密码 → 创建账号。

**操作**：空表单点击创建，必填校验阻止。；创建合成验收教师2、学生2、学生3；角色仅教师/学生。；重复教师2账号提交。；字符边界输入 bad account/1112；产品未规定字符模式，实际接受为第四个纯合成教师账号，立即私存凭据。。

**完成确认与实际写入**：前三个账号POST201并在列表出现正确角色；重复POST409明确“此账号名已存在”，无重复写入。字段边界账号也POST201，未在无产品约束下误判非法。凭据仅私存既定extra-accounts.json，报告不含密码。

**刷新/重登录**：刷新后账号仍在；退出登录、重新登录管理员后再次在账号页读到全部本轮账号。

**异常**：未发现创建或角色错配。账号名含空格/斜线可接受是产品边界观察，需产品决定是否限制。

**寻路记录**：{"wrongTurns": [], "backtrack": false, "sameNameConfusion": false, "hiddenEntry": false}。

**位置与精简建议**：管理与运行→账号合理，角色下拉没有创建管理员的隐蔽入口。 保留一个“新建账号”入口；无需另设教师/学生两个建号页面。

**点击观察到的 API**：

- POST /api/auth/login → 200；例证 network.jsonl:3 (n=7)。
- GET /api/accounts → 200；例证 network.jsonl:29 (n=33)。
- POST /api/accounts → 201；例证 network.jsonl:34 (n=38)。
- POST /api/accounts → 409；例证 network.jsonl:47 (n=55)。
- POST /api/auth/logout → 200；例证 network.jsonl:1355 (n=1417)。

**证据**：AD01-empty-account.png、AD01-accounts-created.png、AD01-duplicate-account.png、AD01-account-invalid.png、AD01-account-relogin.png。

**未测/边界**：短密码、超长字段、账号停用/重置（本轮未找到可见入口）、直接越权接口未测。。

### AD02 · 原材料上传、解析、阅读与元信息保存

**目标与首击意图**：保留自有原文件，解析可读并更新来源信息。 首击“资料与案例”。

**实际路径**：资料与案例 → 上传材料 → 选择原始DOCX → 上传并解析 → 材料→编辑信息→保存信息。

**操作**：空上传提示请选择原文件。；生成并上传自有合成DOCX，14个片段。；观察7/14处理中至14/14已就绪，阅读原文。；通过编辑信息保存标题、作者、来源链接、来源说明、年级和学科。。

**完成确认与实际写入**：创建material-a0181fa6e8e34617965d08b69267b69，原文件file-d066a3bad1d348c8a51a4ba89b330eab保留；14/14片段就绪。保存标题“合成工程验收 E01 方程材料”和明确合成来源说明。最初标题未填是测试选择器不匹配，已按实际UI纠正，非产品缺陷。

**刷新/重登录**：随后跨页、重开浏览器/刷新均可看到保存后的材料标题、来源链接和原文。

**异常**：列出的操作未发现异常。

**寻路记录**：{"wrongTurns": [], "backtrack": false, "sameNameConfusion": false, "hiddenEntry": false}。

**位置与精简建议**：资料与案例中的材料工作台合理。 空状态与页头的上传按钮在空列表时重复但便于开始；有材料后保留页头即可。

**点击观察到的 API**：

- GET /api/library/materials → 200；例证 network.jsonl:8 (n=12)。
- POST /api/library/materials → 201；例证 network.jsonl:92 (n=100)。
- GET /api/library/materials/material-{id} → 200；例证 network.jsonl:96 (n=104)。
- PUT /api/library/materials/material-{id} → 200；例证 network.jsonl:163 (n=171)。

**证据**：AD02-empty-upload.png、AD05-original-preserved.png。

**未测/边界**：PDF、PNG/JPEG材料解析、30MB/30页/300片段上限、损坏文件未测；OCR能力另见AD16。。

### AD03 · 真实AI提取新案例及来源链

**目标与首击意图**：从可见原文片段发起真实提取，不预置成功。 首击“资料与案例”。

**实际路径**：资料与案例 → 材料 → 整理成案例 → 逐项选择原文 → 提取为新案例 → 案例→新草稿。

**操作**：第一次实际提交仅段落8，页面任务排队后输出“等式平衡与移项”草稿。；第二次逐项选择段落4/5/6/7，界面确认4/8后提取，输出方程解法草稿。；任务执行期间离开页面，后从案例列表找到结果。。

**完成确认与实际写入**：真实POST /library/extract创建job-3808741ae57b4b49bef1d99bda458cd0与job-c31f856a8ef343d9873d57b103b598a8，分别产生case-39e79087817f47218264ed6506c303f9与case-65714f3a9bf544dfa47b444520e61b9d。来源引用包含材料ID、段落、原文摘录。E01方程例子为管理员后续人工补充，未声称AI从段落8直接生成全部例题。

**刷新/重登录**：离开后后台继续；重开案例列表仍有草稿/发布记录。

**异常**：最初同一JS循环同步点多个复选框最终只选最后一项；操作日志和POST如实记录1项，后改逐项点击确认4/8。属自动化时序问题，不作为产品缺陷。

**寻路记录**：{"wrongTurns": [], "backtrack": false, "sameNameConfusion": false, "hiddenEntry": false}。

**位置与精简建议**：材料阅读旁的整理成案例合理。 “提取为新案例”和“手动整理”是两种有用方法，保留在同一区域，不新增平行主页面。

**点击观察到的 API**：

- POST /api/library/extract → 201；例证 network.jsonl:175 (n=183)。
- GET /api/ai/jobs/job-{id} → 200；例证 network.jsonl:177 (n=185)。
- GET /api/ai/jobs/job-{id}/events → 200，net::ERR_ABORTED；例证 network.jsonl:195 (n=189)。
- GET /api/library/cases/case-{id} → 200；例证 network.jsonl:313 (n=334)。

**证据**：AD03-extraction-start.png、AD06-math-preview.png。

**未测/边界**：选择8项上限、提取服务超时重试、本账号提取失败场景未发生，未伪造失败。。

### AD04 · 案例编辑、人工确认与发布交接

**目标与首击意图**：完成可供教师引用的新发布案例，保留来源与版本。 首击“资料与案例”。

**实际路径**：资料与案例 → 案例 → 本轮新草稿 → 正文/教学经验/出处 → 对照原文 → 已对照原文核对内容 → 发布案例→确认发布。

**操作**：编辑标题、正文，明确人工合成工程验收。；补教学目标、学生基础、学生困难，保存修改。；预览与对照段落8。；人工确认前发布按钮禁用；确认后出现二次发布确认。。

**完成确认与实际写入**：“合成工程验收 E01 等式平衡与移项”发布v1；case-39e79087817f47218264ed6506c303f9，version-96c75b97037c4cc8b0bae23c9412505c，来源材料段落8。已把标题/ID/来源和v1通知教师用于E01，未再改该交接v1。

**刷新/重登录**：发布后刷新显示已发布v1；后续重登录案例列表仍保留。

**异常**：列出的操作未发现异常。

**寻路记录**：{"wrongTurns": [], "backtrack": false, "sameNameConfusion": false, "hiddenEntry": false}。

**位置与精简建议**：案例工作台内正文、经验、出处与发布合并合理。 保存按钮“保存草稿/保存修改/保存中”会随脏状态变化；无需再复制一个保存入口。

**点击观察到的 API**：

- PUT /api/library/cases/case-{id}/draft → 200；例证 network.jsonl:345 (n=366)。
- POST /api/library/cases/case-{id}/review → 200；例证 network.jsonl:386 (n=407)。
- POST /api/library/cases/case-{id}/publish → 200；例证 network.jsonl:423 (n=444)。

**证据**：AD04-unconfirmed-publish.png、AD04-case-published.png、AD04-case-confirmed-published.png。

**未测/边界**：多个管理员并发编辑同一案例未测；发布后跨角色检索/引用由教师独立报告。。

### AD05 · 识别文本修订与原文保留

**目标与首击意图**：修订识别内容并确认原文件与原文不被覆盖。 首击“资料与案例”。

**实际路径**：资料与案例 → 材料 → 阅读材料 → 识别文本 → 核对识别文本→保存识别文本 → 原文。

**操作**：把段落8识别文本置空并保存，得到明确422。；恢复原文并追加“合成工程验收识别修订1112”标记保存。；刷新后重新进入识别文本读到标记；切原文仍为原始DOCX段落。。

**完成确认与实际写入**：PUT /library/units/unit-78f53218ed3c39753cf803486353d03a先422后200；仅识别文本发生修订，原文/原文件保留。

**刷新/重登录**：刷新重开识别文本完整恢复修订；发布案例v1正文未被隐式修改。

**异常**：空文本提示“请填写有效原文，最多10万字”。

**寻路记录**：{"wrongTurns": [], "backtrack": false, "sameNameConfusion": false, "hiddenEntry": false}。

**位置与精简建议**：原文/识别文本并列合理。 编辑应集中识别文本；原文保持来源事实，避免再新增可覆盖原文件的编辑入口。

**点击观察到的 API**：

- PUT /api/library/units/unit-{id} → 422；例证 network.jsonl:538 (n=567)。
- PUT /api/library/units/unit-{id} → 200；例证 network.jsonl:539 (n=568)。

**证据**：AD05-recognized-revision-refresh.png、AD05-original-preserved.png。

**未测/边界**：原文件直接修改不属于当前可见功能；10万字上限未测。。

### AD06 · 案例数学核验、失效提示与恢复

**目标与首击意图**：以真实方程检验正确、错误以及保存刷新后的核验状态。 首击“资料与案例”。

**实际路径**：资料与案例 → 案例 → 自有AD06样例 → 创建修订 → 教学经验 → 课堂过程 → 编辑核对表达式 → 重新核对列出的等式 → 预览→数学核对。

**操作**：真实AI提取方程2*x+3=11与x=4。；标题/正文编辑后状态变需核对。；重新核对有效方程，编辑与预览均已核对。；把右式改x=7再核对，明确不一致。；恢复x=4重新核对并保存，刷新仍已核对。。

**完成确认与实际写入**：三次POST /library/cases/case-65714f3a9bf544dfa47b444520e61b9d/verify均200，响应状态依次verified/inconsistent/verified（以原始响应为准）；UI正确显示已核对/不一致/已核对。数学校验仅列式范围，人工核对仍单独保留。

**刷新/重登录**：恢复正确表达式并保存后刷新，仍显示已核对。样例为已撤回v2＋未发布修订草稿，不影响E01v1。

**异常**：早期将编辑后UI“需核对”与较早GET verified比较，曾报候选；补齐刷新和重新核对后证实是正确失效保护，已撤销，不计缺陷。

**寻路记录**：{"wrongTurns": ["先在知识与适用范围/知识关联寻找数学核验，未找到；后在课堂过程发现。"], "backtrack": true, "sameNameConfusion": false, "hiddenEntry": true}。

**位置与精简建议**：核验属于案例编辑，但嵌在教学经验→课堂过程较深。 保留一个核验动作；可在“需核对”旁加跳转至现有课堂过程的入口，避免另建数学管理页面。

**点击观察到的 API**：

- POST /api/library/cases/case-{id}/verify → 200；例证 network.jsonl:1086 (n=1127)。

**证据**：AD06-math-preview.png、AD06-preview-valid-corrected.png、AD06-incorrect-math-flag.png、AD06-verified-refresh.png。

**未测/边界**：多变量方程、条件矛盾、危险表达式边界、核验超时未测。。

### AD07 · 案例修订新版本、历史预览与撤回

**目标与首击意图**：在自有另一案例验证版本冻结和撤回，保持E01案例可引用。 首击“资料与案例”。

**实际路径**：资料与案例 → 案例 → AD06方程核验样例 → 发布v1 → 创建修订→保存/人工确认→发布v2 → 已发布版本→版本1 → 撤回→确认撤回。

**操作**：v1发布后增加非零除数边界，发布v2。；版本1预览仍显示原正文而不是v2补充。；确认撤回，仅本轮自有AD06样例。。

**完成确认与实际写入**：同一case-65714f3a9bf544dfa47b444520e61b9d保留v1/v2，版本1 version-ab258ce5fa284bf1b74fe80ec56c09e8；撤回v2后页面说明新检索排除、历史引用保留。

**刷新/重登录**：刷新显示已撤回v2，E01案例仍已发布v1。

**异常**：列出的操作未发现异常。

**寻路记录**：{"wrongTurns": [], "backtrack": false, "sameNameConfusion": false, "hiddenEntry": false}。

**位置与精简建议**：已发布案例详情内创建修订、撤回合理。 版本列表折叠可保留；无需把每个版本变成列表中的独立案例。

**点击观察到的 API**：

- POST /api/library/cases/case-{id}/publish → 200；例证 network.jsonl:843 (n=876)。
- POST /api/library/cases/case-{id}/revise → 200；例证 network.jsonl:871 (n=904)。
- GET /api/ai/cases/case-{id}?versionId=version-ab258ce5fa284bf1b74fe80ec56c09e8 → 200；例证 network.jsonl:917 (n=950)。
- POST /api/library/cases/case-{id}/withdraw → 200；例证 network.jsonl:950 (n=983)。

**证据**：AD07-case-revision-v2.png、AD07-case-version1-retained.png、AD07-withdraw-refresh.png。

**未测/边界**：撤回后新检索排除由AD17验证被500阻塞，尚未看到检索结果。。

### AD08 · 课程与单元创建、目录元信息保存

**目标与首击意图**：创建全新合成课程与单元，实际保存目录信息。 首击“课程内容”。

**实际路径**：课程内容 → 新建课程 → 单元 → 编辑课程目录 → 保存目录。

**操作**：空课程创建必填阻止。；创建“合成工程验收 E01 方程短课”和独立单元。；目录设置课程顺序1，单元顺序先试0被接受再恢复1；单元名增加“目录已核对”。。

**完成确认与实际写入**：新course-55846dec2d6d4874b99a7909dd04a1d2与unit-8c1745431e5c43b8abad81db5f43f75d；目录保存后单元名“合成工程验收单元：等式平衡（目录已核对）”。0没有产品禁令，接受不判非法缺陷。

**刷新/重登录**：刷新再打开编辑课程目录，名称与顺序1均恢复。

**异常**：列出的操作未发现异常。

**寻路记录**：{"wrongTurns": [], "backtrack": false, "sameNameConfusion": false, "hiddenEntry": false}。

**位置与精简建议**：课程内容→编辑课程目录合理。 单元、课时按钮仅短名，建议保留加号视觉或明确新建意图，不新设重复目录模块。

**点击观察到的 API**：

- POST /api/curriculum/courses → 201；例证 network.jsonl:202 (n=210)。
- POST /api/curriculum/units → 201；例证 network.jsonl:206 (n=214)。
- PUT /api/curriculum/courses/course-{id} → 200；例证 network.jsonl:1302 (n=1351)。
- PUT /api/curriculum/units/unit-{id} → 200；例证 network.jsonl:1303 (n=1352)。

**证据**：AD08-course-empty.png、AD08-directory-refresh.png。

**未测/边界**：删除课程/单元无可见入口；重复课程名、跨单元移动未测。。

### AD09 · 课时内容、题目、知识出处、预览核对发布

**目标与首击意图**：新建完整短课供教师任务链引用，校验缺项阻止发布。 首击“课程内容”。

**实际路径**：课程内容 → 本轮合成课程 → 课时 → 课时设置 → 课时内容→添加内容块 → 题目→添加题目 → 知识与出处 → 保存草稿 → 预览 → 核对内容 → 发布。

**操作**：新建E01等式平衡短课，8分钟，目标明确合成。；添加讲解块与练习块，2道有方程/答案/解释/提示的题，分别practice/check；关联等式性质与来源。；缺目标及独立题时核对422明确指出；补齐后核对成功。；预览讲解与随堂练习实际渲染，发布v1。。

**完成确认与实际写入**：lesson-23043753a56245f28d0962f35b85c40f发布v1，lessonversion-bd09c2239c894f36aaba1da016，2节内容/2题；已交接教师E01，从发布后未改正文。

**刷新/重登录**：发布刷新保持；后续重登录从课程下拉可重新找到本轮课程及课时。

**异常**：第一次关闭预览后CDP输入与Runtime超时，未发发布请求；重开私有浏览器后重走可见入口发布成功。记工具故障，不计页面通过或产品缺陷。

**寻路记录**：{"wrongTurns": [], "backtrack": false, "sameNameConfusion": false, "hiddenEntry": false}。

**位置与精简建议**：课时下内容、题目、知识与出处分组合理。 已发布课时页“预览”和“打开学生预览”功能重复，可留一个主入口。

**点击观察到的 API**：

- POST /api/curriculum/lessons → 201；例证 network.jsonl:209 (n=217)。
- PUT /api/curriculum/lessons/lesson-{id} → 200；例证 network.jsonl:214 (n=222)。
- POST /api/curriculum/lessons/lesson-{id}/review → 422；例证 network.jsonl:229 (n=237)。
- POST /api/curriculum/lessons/lesson-{id}/review → 200；例证 network.jsonl:233 (n=241)。
- POST /api/curriculum/lessons/lesson-{id}/publish → 200；例证 network.jsonl:266 (n=283)。

**证据**：AD09-empty-lesson-publish.png、AD09-draft-preview.png、AD09-preview-practice.png、AD09-lesson-published.png、AD09-published-refresh.png。

**未测/边界**：图片插图、天平内容块配置、同课时双管理员并发写入未测；学习执行/学生题目流由独立角色报告。。

### AD10 · 知识点、别名与前置关系循环保护

**目标与首击意图**：新建自有知识节点并验证循环阻止及保存恢复。 首击“课程内容”。

**实际路径**：课程内容 → 知识前置关系 → 知识点 → 知识点名称/别名/前置知识 → 保存知识关系。

**操作**：新增空知识点保存被422阻止，但UI仅泛化错误。；新增合成知识A/B，A别名合成别名A1112。；A依赖B且B依赖A保存，明确循环错误；解除B依赖A，保留A→B。。

**完成确认与实际写入**：PUT /curriculum/knowledge成功保存新增节点；既有8知识点内容未改。循环422未写入，合法A→B后200。

**刷新/重登录**：刷新重开，A别名和A→B、B无前置均恢复。

**异常**：空节点名Pydantic422只显示“操作未能完成，请重试”，未指出知识点名称为空；为提示改进项。

**寻路记录**：{"wrongTurns": [], "backtrack": false, "sameNameConfusion": false, "hiddenEntry": false}。

**位置与精简建议**：知识前置关系在课程内容内合理。 既有点与新增点同一编辑器即可；应把空字段错误定位到具体行，不增加独立错误页。

**点击观察到的 API**：

- PUT /api/curriculum/knowledge → 422；例证 network.jsonl:1004 (n=1041)。
- PUT /api/curriculum/knowledge → 200；例证 network.jsonl:1005 (n=1042)。

**证据**：AD10-knowledge-cycle-rejected.png、AD10-knowledge-refresh.png。

**未测/边界**：重名/别名冲突、较大知识图性能、并发图更新未测。。

### AD11 · 课时修订版本、历史预览与停用

**目标与首击意图**：用另一自有课时验证版本保留和停用。 首击“课程内容”。

**实际路径**：课程内容 → 本轮课程→课时 → 创建AD11版本与停用 → 保存/核对/发布v1 → 创建修订→保存/核对/发布v2 → 历史发布版本→版本1 → 停用。

**操作**：创建5分钟、1独立检查块/1题的自有AD11课时。；修订正文保存后发布按钮禁用，重新核对后可发布v2。；打开版本1预览，正文仍原内容。；停用并刷新，再点击列表已停用课时。。

**完成确认与实际写入**：lesson-8bcb06fbd1bd4ab2b8ee49a569394e4f保留v1/v2且withdrawn；E01在用课时不受停用影响。

**刷新/重登录**：刷新仍已停用；版本1在停用前已预览确认冻结。

**异常**：列表已停用条目仍可点击，但右侧仅“选择或新建课时”，不能读历史或看到停用状态说明/恢复动作，形成可见死入口。

**寻路记录**：{"wrongTurns": [], "backtrack": false, "sameNameConfusion": false, "hiddenEntry": false}。

**位置与精简建议**：创建修订/停用放在课时详情合理。 已停用应打开只读详情和版本历史，或禁用条目并解释；若停用需可逆，应提供明确恢复入口。

**点击观察到的 API**：

- PUT /api/curriculum/lessons/lesson-{id} → 200；例证 network.jsonl:1268 (n=1313)。
- POST /api/curriculum/lessons/lesson-{id}/review → 200；例证 network.jsonl:1271 (n=1316)。
- POST /api/curriculum/lessons/lesson-{id}/publish → 200；例证 network.jsonl:1274 (n=1319)。
- POST /api/curriculum/lessons/lesson-{id}/revise → 200；例证 network.jsonl:1277 (n=1322)。
- POST /api/curriculum/lessons/lesson-{id}/withdraw → 200；例证 network.jsonl:1290 (n=1335)。

**证据**：AD11-lesson-v1.png、AD11-lesson-v2-history.png、AD11-lesson-v1-retained.png、AD11-disabled-refresh.png。

**未测/边界**：停用后的历史学生任务冻结由其他角色/后续复测覆盖，管理员可见恢复入口未发现。。

### AD12 · 问题筛选、回复、追加往来与处理状态

**目标与首击意图**：处理学生3真实提交的合成反馈，并验证跨角色回看及状态筛选。 首击“管理与运行”。

**实际路径**：管理与运行 → 问题反馈 → 搜索问题/状态筛选 → 学生3合成反馈1112 → 填写处理意见→保存处理。

**操作**：搜索不存在问题显示无匹配。；空处理不提交；填写管理员回复保存已回复。；学生独立回看并追加后，管理员读到追加与回待处理。；管理员补关闭回复，保存已关闭；已关闭筛选命中，刷新待处理筛选为空。。

**完成确认与实际写入**：issue-1962f5a7b09243be9f9fca5e901c9440回复与状态实际写入；原反馈、两次学生追加、管理员回复完整保留。

**刷新/重登录**：刷新、重登录管理员后仍可读完整往来；学生已独立确认管理员回复。

**异常**：列出的操作未发现异常。

**寻路记录**：{"wrongTurns": [], "backtrack": false, "sameNameConfusion": false, "hiddenEntry": false}。

**位置与精简建议**：管理与运行默认问题反馈合理。 列表与详情不另设“回复中心”；保存后处理状态下拉默认已回复需用户知道这是下一次处理选择，可显示当前状态更明确。

**点击观察到的 API**：

- GET /api/support? → 200；例证 network.jsonl:28 (n=31)。
- POST /api/support/issue-{id}/events → 200；例证 network.jsonl:481 (n=506)。
- POST /api/support/issue-{id}/events → 409；例证 network.jsonl:1379 (n=1440)。

**证据**：AD12-feedback-replied.png、AD12-closed-filter.png、AD12-pending-empty-after-close.png。

**未测/边界**：管理员自己提交新问题未测（学生提交已覆盖）；处理中状态单独落库未测。。

### AD13 · 连接检查、断网错误与恢复

**目标与首击意图**：确认服务/数据库连接状态及断网后可恢复反馈。 首击“管理与运行”。

**实际路径**：管理与运行 → 账号 → 检查连接。

**操作**：在线检查显示服务与数据库已连接。；仅本浏览器CDP切offline，点击检查连接，真实请求失败。；恢复网络，再检查恢复在线。。

**完成确认与实际写入**：GET /api/health在线status/database均ok；断网UI明确“无法连接到学习服务，请检查网络后重试”，恢复后可继续账号及业务。

**刷新/重登录**：恢复网络后检查成功；未更改服务器/8099/数据库。

**异常**：列出的操作未发现异常。

**寻路记录**：{"wrongTurns": [], "backtrack": false, "sameNameConfusion": false, "hiddenEntry": false}。

**位置与精简建议**：当前放账号页下方，连接检查属于运行项，可移至同一管理页的运行区域。 保留一个运行状态入口，避免账号页与能力页重复多处刷新健康。

**点击观察到的 API**：

- GET /api/health → 200；例证 network.jsonl:27 (n=32)。
- GET /api/health → None，net::ERR_INTERNET_DISCONNECTED；例证 network.jsonl:644 (n=677)。

**证据**：AD13-offline-connection.png、AD01-account-relogin.png。

**未测/边界**：服务进程宕机、MySQL断连、实际HTTP超时未主动注入；AD17实际服务500另列。。

### AD14 · 旧浏览器记录导入入口

**目标与首击意图**：在可见入口尝试自有旧记录预览/去重/归属。 首击“管理与运行”。

**实际路径**：管理与运行 → 账号 → 导入旧记录。

**操作**：新独立浏览器点击导入旧记录。。

**完成确认与实际写入**：弹窗只有“没有可导入的旧记录”和关闭，无文件/文本输入。按UI盲测边界未注入localStorage或伪造旧数据。

**刷新/重登录**：未发生导入写入，无可恢复记录。

**异常**：缺可见方式为新浏览器准备旧记录；本项预览/去重/隔离归属未测，不判通过。

**寻路记录**：{"wrongTurns": [], "backtrack": false, "sameNameConfusion": false, "hiddenEntry": false}。

**位置与精简建议**：账号/本机记录迁移区合理。 保留一个旧记录迁移入口；可提供自有导入文件预览以支持新浏览器迁移，但需产品范围确定。

**API**：无业务HTTP写入；本机浏览器动作或无可导入数据。

**证据**：动作日志中的可见弹窗记录。

**未测/边界**：去重、指定归属、跨账号隔离、确认导入、错误旧结构全部未测。。

### AD15 · 真实文字指导与任务记录恢复、权限边界

**目标与首击意图**：通过现有Codex获得指导并从最近任务恢复。 首击“管理与运行”。

**实际路径**：管理与运行 → 能力验证 → 文字指导 → 问题→获取指导 → 离开后重进→最近任务 → 执行记录/失败与重试。

**操作**：空问题POST422明确“请填写问题”。；以合成移项错误请求真实指导，任务执行。；离开后重进，选择最近任务恢复原问题和引导。；执行记录显示第1次成功、gpt-6-luna。；他人AI备课失败条目显示脱敏原因与仅原提交账号可重试，重试禁用。；为找停止曾发起第二次本账号文字指导，近期列表可见运行中，未暴露停止；任务实际成功。。

**完成确认与实际写入**：job-e62b2f88eca64027a116fe512e56e83d及第二文字任务均真实成功，第一结果为引导等式两边同时减3且未直接给最终答案。页面恢复原输入和输出，非GET200即通过。

**刷新/重登录**：本轮检索前已验证跨页恢复成功；检索后任务列表500导致再次恢复被回归阻塞，见AD17。

**异常**：普通管理员能力验证文字任务不属于当前可停止的学生/教师指导业务任务；按任务能力边界记停止不适用。；本账号未发生失败任务，未伪造自身失败或重试成功；他人任务重试权限正确。

**寻路记录**：{"wrongTurns": [], "backtrack": false, "sameNameConfusion": false, "hiddenEntry": false}。

**位置与精简建议**：管理员能力验证放管理与运行合理。 能力下拉集中诊断功能可保留；“搜索页面、任务”若只列主页面，应更名或接入实际任务搜索。

**点击观察到的 API**：

- GET /api/ai/jobs → 200；例证 network.jsonl:646 (n=680)。
- GET /api/ai/failures → 200；例证 network.jsonl:648 (n=681)。
- GET /api/ai/capabilities → 200；例证 network.jsonl:649 (n=679)。
- POST /api/ai/jobs → 422；例证 network.jsonl:655 (n=688)。
- POST /api/ai/jobs → 201；例证 network.jsonl:656 (n=689)。
- GET /api/ai/jobs/job-{id} → 200；例证 network.jsonl:657 (n=690)。
- GET /api/ai/jobs/job-{id}/events → 200；例证 network.jsonl:658 (n=691)。
- GET /api/ai/jobs → 500；例证 network.jsonl:1332 (n=1387)。

**证据**：AD15-guidance-start.png、AD15-guidance-restored-result.png、AD15-real-model-record.png。

**未测/边界**：管理员自身失败任务重试未发生/未测，学生/教师可停止任务由对应角色验收。。

### AD16 · 真实题图识别与结果恢复

**目标与首击意图**：对自有合成题图实际识别题目和学生步骤。 首击“管理与运行”。

**实际路径**：管理与运行 → 能力验证 → 验证能力→题图识别 → 选择文件→识别题图 → 重进→最近任务→题图识别。

**操作**：未选文件提示请先选择文件。；用浏览器渲染生成合成数学PNG，上传并提交真实OCR。；重进能力页从最近任务恢复结果，核对方程及错误步骤。。

**完成确认与实际写入**：file-e1cedcc9e2cb4b0d9f0a660654bbc179，job-d2ec9d675b2c4db48da758863e77794c成功；识别文本保留2x+3=11与原作答2x=11+3、x=7及合成标记。

**刷新/重登录**：识别后跨页重进，任务恢复成功；后续AD17列表回归另列。

**异常**：列出的操作未发现异常。

**寻路记录**：{"wrongTurns": [], "backtrack": false, "sameNameConfusion": false, "hiddenEntry": false}。

**位置与精简建议**：能力验证中的题图诊断合理。 保留原图选择与实际识别结果，避免重复自动演示识别文本。

**点击观察到的 API**：

- POST /api/ai/jobs → 422；例证 network.jsonl:655 (n=688)。
- POST /api/ai/jobs → 201；例证 network.jsonl:656 (n=689)。
- POST /api/files → 201；例证 network.jsonl:989 (n=1026)。
- GET /api/ai/jobs/job-{id} → 200；例证 network.jsonl:992 (n=1029)。
- GET /api/ai/jobs/job-{id}/events → 200；例证 network.jsonl:993 (n=1030)。

**证据**：AD16-ocr-restored-result.png。

**未测/边界**：多图、模糊图、格式不符、尺寸上限未测。。

### AD17 · 案例检索与语义重排后的任务记录回归

**目标与首击意图**：真实检索新发布案例，排除已撤回样例，并恢复结果。 首击“管理与运行”。

**实际路径**：管理与运行 → 能力验证 → 验证能力→案例检索 → 填写E01标题与困难→语义重排勾选 → 检索案例 → 离开后重进/刷新模型与任务。

**操作**：查询“合成工程验收 E01 等式平衡与移项：学生移项未改变符号”，语义重排保持勾选。；POST创建任务，SSE观察queued/running/succeeded。；详情GET500，稍后重进与刷新任务列表也连续500。；同批capabilities200 configured=true，但UI显示未配置/最近任务0。。

**完成确认与实际写入**：job-bbc83f964c224fafa4dbc63716b46455提交201，事件流最终succeeded；GET任务详情及任务列表返回Internal Server Error，UI无法呈现结果/历史，无法验证命中E01或排除已撤回AD06。不能记成功。

**刷新/重登录**：重进与可见刷新按钮重复失败；真实历史文字/OCR记录也被页面整体置空，健康仍ok。

**异常**：D-ADMIN-01：检索成功产物导致任务详情与列表序列化500，进一步把已配置能力错误显示为未配置。首轮由root统一修复，当前未复测。

**寻路记录**：{"wrongTurns": [], "backtrack": false, "sameNameConfusion": false, "hiddenEntry": false}。

**位置与精简建议**：案例检索诊断位置合理。 能力状态、任务历史加载应分别容错，单个坏任务不得隐藏其他记录或把能力状态改未配置。

**点击观察到的 API**：

- GET /api/ai/jobs → 200；例证 network.jsonl:646 (n=680)。
- GET /api/ai/capabilities → 200；例证 network.jsonl:649 (n=679)。
- POST /api/ai/jobs → 422；例证 network.jsonl:655 (n=688)。
- POST /api/ai/jobs → 201；例证 network.jsonl:656 (n=689)。
- GET /api/ai/jobs/job-{id} → 200；例证 network.jsonl:1245 (n=1290)。
- GET /api/ai/jobs/job-{id}/events → 200；例证 network.jsonl:1246 (n=1291)。
- GET /api/ai/jobs/job-{id} → 500；例证 network.jsonl:1247 (n=1292)。
- GET /api/ai/jobs → 500；例证 network.jsonl:1332 (n=1387)。

**证据**：AD17-job-list-500-unconfigured.png、AD17-job-list-500-repeat.png。

**未测/边界**：检索结果命中/来源版本/撤回排除未完成；独立材料重排表单未测。。

### AD18 · 本机文字朗读、停止准备与文字回退

**目标与首击意图**：实际尝试朗读并记录客观设备能力。 首击“管理与运行”。

**实际路径**：管理与运行 → 能力验证 → 验证能力→文字朗读 → 输入文字→朗读 → 停止朗读。

**操作**：合成文字发起朗读，先显示准备朗读与停止朗读。；等待约5秒明确没有中文声音，继续阅读文字。；再发起并立即停止，回到朗读状态。。

**完成确认与实际写入**：浏览器本机语音接口未能产出可听中文音频，UI明确“设备没有可用的中文朗读声音，请继续阅读文字”；准备阶段停止有效，文字保持。未声称实际发声通过。

**刷新/重登录**：文字在当前表单保留；本功能不生成业务数据库记录。

**异常**：列出的操作未发现异常。

**寻路记录**：{"wrongTurns": [], "backtrack": false, "sameNameConfusion": false, "hiddenEntry": false}。

**位置与精简建议**：能力验证诊断项合理，正文朗读可复用同一组件。 多个页面朗读按钮属于场景动作，不需另设语音管理主页面。

**API**：无业务HTTP写入；本机浏览器动作或无可导入数据。

**证据**：AD18-speech-stop.png、AD18-stop-during-prepare.png。

**未测/边界**：有中文语音设备的实际播放、朗读中停止、播放后恢复未测。。

### AD19 · 语音输入权限失败与文字回退

**目标与首击意图**：实际请求麦克风并保持无设备文字输入可用。 首击“管理与运行”。

**实际路径**：管理与运行 → 能力验证 → 验证能力→语音输入 → 语音输入按钮 → 输入文字。

**操作**：点击实际语音输入动作。；浏览器未获麦克风权限，提示继续文字输入。；合成文字回退可输入编辑，保留于表单。。

**完成确认与实际写入**：UI明确“未获得麦克风权限，请继续文字输入”；文字回退可用。无真实录音/识别成功证据，不记语音成功。

**刷新/重登录**：当前表单文字不因权限失败清空；没有创建语音业务记录。

**异常**：列出的操作未发现异常。

**寻路记录**：{"wrongTurns": [], "backtrack": false, "sameNameConfusion": false, "hiddenEntry": false}。

**位置与精简建议**：输入字段旁的语音动作位置合理。 能力选择“语音输入”和表单动作同名，需保持动作与选择器视觉层级区分。

**API**：无业务HTTP写入；本机浏览器动作或无可导入数据。

**证据**：AD19-voice-no-device.png、AD19-text-fallback.png。

**未测/边界**：真实麦克风录音、识别结果、录音停止、语音超时未测。。

### AD20 · 问题处理并发冲突、保留草稿与重新读取重试

**目标与首击意图**：两个真实浏览器同时读取合成反馈，避免后保存覆盖先保存。 首击“管理与运行”。

**实际路径**：管理与运行 → 问题反馈 → 同一合成反馈1112 → 两浏览器分别填处理意见 → B保存→A保存 → 重新读取→再次保存。

**操作**：两个浏览器均读取revision5。；B先保存关闭回复成功revision6。；A旧revision5保存收到409，输入保留。；点击重新读取，B回复出现且A输入不丢；再保存成功revision7。；刷新确认A/B两条均保留，状态仍关闭。。

**完成确认与实际写入**：expectedRevision保护有效；409没有覆盖B或清空A。重新读取后同requestKey及revision6重试成功200。

**刷新/重登录**：刷新回读包含原反馈、学生追加、管理员回复、并发B及并发A，状态已关闭。

**异常**：列出的操作未发现异常。

**寻路记录**：{"wrongTurns": [], "backtrack": false, "sameNameConfusion": false, "hiddenEntry": false}。

**位置与精简建议**：冲突提示与重新读取放在同一处理页合理。 不需要额外冲突页面；保留输入并在原位置重新读取即可。

**点击观察到的 API**：

- POST /api/support/issue-{id}/events → 200；例证 network.jsonl:481 (n=506)。
- POST /api/support/issue-{id}/events → 409；例证 network.jsonl:1379 (n=1440)。

**证据**：AD20-concurrent-B-saved.png、AD20-concurrent-A-conflict.png、AD20-concurrent-reread-retry-refresh.png。

**未测/边界**：同一按钮双击幂等、并发取消/删除未测。。

### AD21 · 课时排序及刷新恢复

**目标与首击意图**：用自有两课时验证上移/下移顺序写入与恢复。 首击“课程内容”。

**实际路径**：课程内容 → 课程下拉→合成工程验收E01课程 → AD11课时上移 → 刷新 → AD11课时下移 → 刷新。

**操作**：重新登录后课程选择回默认，先通过可见课程下拉选择本轮课程。；上移自有已停用AD11，刷新列表序号变AD11第一、E01第二。；下移AD11，刷新恢复E01第一、AD11第二。。

**完成确认与实际写入**：四次PUT lesson position分别交换6/7再恢复；没有更改课时正文、来源或版本。

**刷新/重登录**：上移与恢复均刷新确认，最终回到原顺序。

**异常**：最初未先选本轮课程导致目标按钮未找到，已纠正；未触碰默认原有课时按钮。

**寻路记录**：{"wrongTurns": ["重登录后仍在默认课程，目标箭头不存在；改从可见课程下拉选自有课程。"], "backtrack": true, "sameNameConfusion": false, "hiddenEntry": false}。

**位置与精简建议**：列表行内上下移箭头合理。 保留行内排序，不另设重复排序页面；箭头有含课时名的aria-label。

**点击观察到的 API**：

- PUT /api/curriculum/lessons/lesson-{id} → 200；例证 network.jsonl:214 (n=222)。

**证据**：AD08-reorder-success-refresh.png、AD08-order-restored-success.png。

**未测/边界**：跨单元拖拽、跨课程排序未测。。

## 交接与保留状态

- E01案例：合成工程验收 E01 等式平衡与移项 / case-39e79087817f47218264ed6506c303f9 / v1 / version-96c75b97037c4cc8b0bae23c9412505c；已通知教师，发布后未再改。
- E01课时：合成工程验收 E01 等式平衡短课 / lesson-23043753a56245f28d0962f35b85c40f / v1 / lessonversion-bd09c2239c894f36aaba1da016；8分钟2节2题，发布后正文未改。
- 自有AD06案例保留已撤回v2与正确核验的未发布修订草稿；自有AD11课时已停用并保留v1/v2。课时排序已恢复原序。
- 合成反馈1112保持已关闭，并发A/B回复均保留。未更改既有8知识点、用户原资料、8099实例或其他工作树。

## 证据与限制

- baseline.json 含逐功能结构、实际接口URL/状态/日志行索引；actions*.jsonl记录点击及DOM可见文本；network*.jsonl只记录点击引发的真实请求/响应，密码及token已脱敏。
- 截图名称中的早期尝试（例如 AD08-directory-invalid-order、AD08-reorder-refresh）仅是动作尝试，不表示0非法或排序成功；采用带 success 的最终排序截图及本报告结果。
- **不得打包 profile/ 与 profile-concurrent/**：私有浏览器会话目录包含登录状态。私有extra-accounts.json也不得进入公开证据。
- 未做的场景已逐项列明。旧导入、真实语音效果、管理员本人失败任务重试、独立材料重排、实际超时不计通过。
- 基准冻结，等待第一轮统一修复后定向复测；本代理未修改源码、未提交。
