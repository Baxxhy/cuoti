# 最终提交复核

后续按用户要求补查AI内容，最新结果见[补充题型验收](EXTENDED_AI_ACCEPTANCE_2026_10.md)。本页保留原提交批次的数量和凭据处理记录；用户随后明确不处理Git历史，不将其列为本机最终版使用的阻断项。

日期：2026-10-18；起始提交：`50c0cba`。范围沿用[当前产品规格](README.md)与[验收矩阵](ACCEPTANCE_MATRIX.md)：uni-app前端、仓颉业务/MySQL、Python内部算法，覆盖学生和现有协作角色。签名安装、备份恢复与真人效果研究仍按既有约定处理，不因“最终提交”重新混入已后置范围。

本记录核查当前代码和实际服务，不把测试全绿解释为任意输入、任意模型响应永久无错。未被规则证明的建议应保持待核对；功能错误要修复，证据不足不得伪装成正确。

## 新增问题登记

| 编号 | 复现与风险 | 修复及证据 |
| --- | --- | --- |
| FS-001 / P1 | 人工改到另一行且缺少步骤ID对应参考时，虽有旧证明失效提示，仍会把旧recommended_strategy展示为“正确做法”，并标勾；人工说明仍标“AI分析” | 不再回退旧建议：显示“这一步还需核对”和明确缺参考说明；人工修正使用“当前诊断说明”。有实际ID对应或本步有效修复证明时保留具体做法。新回归先失败再通过，学生乙增加刷新后的文本/标题检查，实际甲页面三种宽度通过 |
| FS-002 / P1（验收工具） | `check_live_release_task.py --verify-existing`遇到未完成任务会继续进入作答循环，且重写原报告；“只读复核”可能改变被检查对象 | 未完成任务立即失败；除登录外禁止所有非GET请求；只读模式不保存报告。7种状态检查通过，实际已完成任务复核通过且原报告字节不变。它是验收可靠性缺陷，不冒充学生端业务缺陷 |
| FS-003 / P0（交付凭据） | 提交前扫描发现实际模型池仍被Git跟踪，包含真实凭据，不能直接随源码分发；此前“私有池未纳入提交”的笼统表述不准确 | 保留本机实际文件及内容，权限设为0600，从Git索引移除并忽略；添加默认禁用、空凭据的安全示例和首次配置说明。最终提交包必须排除实际配置和Git历史，并逐文件检查已知凭据不在包内。旧Git历史仍需单独处理，详见下文 |

改动入口：[诊断页面](../../frontend/src/pages/diagnosis/diagnosis.vue)、[页面回归](../../frontend/tests/knowledge-diagnosis.test.ts)、[学生场景](../../frontend/e2e/student-personas.spec.ts)、[隔离夹具](../../scripts/smoke_cangjie_personas.py)、[实际任务核验命令](../../scripts/check_live_release_task.py)、[只读行为测试](../../backend/tests/test_release_task_check.py)。没有改动仓颉/MySQL架构、模型轮询方式、原作答或权限规则。

## 逐项核对当前交付要求

下表按验收矩阵逐项登记。验证入口由本轮完整主线统一运行，结果须以文末实际退出状态为准；既有历史质量样本保留其原有范围，不叠加成新的测试数量。

| 要求 | 当前实现与验证入口 | 核对边界 |
| --- | --- | --- |
| F01 账号/角色 | accounts、school、system_admin HTTP/MySQL；account-access、deployment-readiness浏览器 | 注册不可提权，跨账号拒绝、改密/重试/会话、双方解除授权 |
| F02 录题/OCR/原图 | manual_questions、media、recognition、student_work；new-user、recovery浏览器 | 原图字节保留，步骤/选项校对、异步恢复；真实PNG质量沿用原记录 |
| F03 错题整理 | list、questions、edit；functional-audit | 搜索、筛选、收藏、归档、题干编辑与失效来源 |
| F04 分析/错因/修正 | diagnosis、release-inputs；knowledge-diagnosis、student-personas | 首错范围、来源、改步后旧证明降级、FS-001缺参考不猜测 |
| F05 原教学与记忆 | tutor_dialogue、learning_memory；functional-audit | 原完整讲解、讲回和六类受控记忆保留 |
| F06 持久智能体 | learning_tasks、task_contract、task_budget、task_sources；learning-tasks、task-entry | 规划/工具/验证/重规划、预算、权限、取消、重启与幂等，十类行为见[智能体验收](AGENT_ACCEPTANCE.md) |
| F07 局部订正 | learning_task_compute、task_sources；learning-tasks | 原步骤ID与原作答保留；一次方程局部正确不等于整题掌握 |
| F08 条件对照 | variant_compute、learning_tasks；learning-tasks | 已实现的一次方程单条件对照；已曝光答案不计新的独立证据 |
| F09 自检要点 | self_checks HTTP/MySQL | 确认、CRUD、版本/权限、回滚；保存不增加掌握 |
| F09a 图示/观察 | task_visuals、task_figures；learning-tasks | 三类受控图示、参数和观察来源、辅助证据；不承诺任意几何证明 |
| F10 知识/图谱/检索 | insights、retrieval；product-experience、functional-audit | 真实知识卡、学科分类、按ID回放和地图来源；资源数量与CPU匹配等待仍见原记录 |
| F11 练习/手写/复习 | practice、handwriting、reviews；review-queue、review-origin、review-recovery | 答案类型、重复拒绝、草稿隔离、本题定位、判题/评价回执恢复 |
| F12 组卷/导出 | papers；functional-audit、paper-recovery | 当前范围、标题/排序/分值、保存/删除失败恢复及PDF/答案/表格导出 |
| F13 教师/家长/管理 | assignments、school、guardian_links、system_admin；functional-audit | 教师布置→学生提交→人工复核；家长只读授权/撤回；管理字段脱敏 |
| U01 今日/学习/报告 | new-user、product-experience、functional-audit | 冷启动可行动，数据来自后端，空记录不伪造成绩 |
| U02 列表/详情/教学 | functional-audit、task-entry、recovery | 信息分区、主行动、草稿与失败恢复，旧入口保留 |
| U03 内容/可达性 | math与前端组件测试；account-access、learning-tasks布局 | 普通文本转义、KaTeX trust=false、受控JSON图示、窄屏/文字放大/键盘；不把H5当原生读屏认证 |
| M01 资源/连接 | api-base等前端测试，类型/H5/App本地构建、check-final | 业务指向仓颉，算法内部调用；四项实际服务就绪 |
| M02 签名安装 | 按用户已确定要求后置 | 当前未发行APK/IPA，资源编译不等于实体手机验收 |
| D01 数据与升级 | verify_cangjie隔离库初始化、迁移、重启恢复 | MySQL独立库保护；不添加SQLite或备份恢复 |
| Q01 实际算法 | 本轮当前真实模型固定方程：分析、首错诊断、订正推进与原作答保留 | 仅为固定样本，不等于全学科广样本教学效果；原模型与CPU检索记录范围不变 |
| Q02 真人学生 | 按当前约定保留后续现场试用 | 工程模拟三名学生不冒充真人参与者，不编造教学效果 |
| D02 完整交付 | make verify-final、兼容后端pytest、静态/链接检查、实际页面、Git提交 | 当前主线与兼容测试分别说明；未运行的跨机器安装/发行不标通过 |

## 实际执行记录

- 前端诊断专项：修复前1项失败/16项通过，修复后17项通过。日志 `/tmp/zhiwei-final-submission-diagnosis-before.log`、`/tmp/zhiwei-final-submission-diagnosis-after.log`。
- 只读命令7种任务状态通过；兼容后端全部304项通过。日志 `/tmp/zhiwei-final-submission-readonly.log`、`/tmp/zhiwei-final-submission-legacy.log`。本轮不将pytest结果冒称旧Python业务版完整`make verify`。
- 当前真实Qwen固定方程：分析得到规则验证的x=4（1.21秒），首错定位第1步（2.18秒），真实任务订正后推进到独立作答；原错误x=7及原步骤保留。使用独立新QA账号和私有报告目录，不覆盖旧学生核验账号。日志 `/tmp/zhiwei-final-submission-actual-ai.log`，不是广样本或性能基准。
- 原已完成真实任务另经新只读命令核对，原报告字节不变，未增加答案或学习证据。日志 `/tmp/zhiwei-final-submission-actual-readonly.log`。
- 当前人工改步页360/390/1280布局、缺参考标题与提示、脚本错误0通过，核验后恢复专用QA题原步号。[实际页面截图](screenshots/final-submission-manual-correction.png)已目视检查。日志 `/tmp/zhiwei-final-submission-actual-manual.log`。
- 当前四项服务就绪；全量`ruff check backend/app backend/tests scripts backend-algorithms`通过。首次检查发现既有学生夹具的import排序不符合I001，已仅调整顺序；这是静态检查问题，不计作新的学生功能缺陷。`git diff --check`通过。
- 37份最终目录Markdown的本地链接、源码与截图目标均存在。旧路由用途清单的源码证据位置已过期，刷新后`audit_route_usage.py --check`通过；对比确认保留接口、分类、状态和处理理由均未改变。该清单只审计103条迁移基线中的94条保留接口，不拿它替代新增智能体等接口的完整HTTP验收。日志 `/tmp/zhiwei-final-submission-routes-refresh.log`、`/tmp/zhiwei-final-submission-routes-after.log`。
- 最新`make verify-final`完整命令已正常退出0：前端202项/43文件、类型检查、H5/App本地资源、算法586项、仓颉34项、完整HTTP/MySQL与进程恢复、浏览器52项全部通过，0跳过。日志 `/tmp/zhiwei-final-submission-gate-v1.log`。包含FS-001的学生改步、缺参考与刷新回归；没有用旧门禁冒充当前代码结果。
- 当前实际BGE与Qdrant均HTTP200，向量与重排模型均已加载，GPU数量0；此检查未做索引或检索写入，也不替代检索延迟测试。日志 `/tmp/zhiwei-final-submission-retrieval-health.log`。
- 凭据移出跟踪后，兼容测试改用临时Qwen配置并通过MockTransport禁止未显式模拟的模型联网；不再读取实际池，安全示例的模型/禁用/空凭据也纳入检查。全部304项再次通过，日志 `/tmp/zhiwei-final-submission-legacy-isolated.log`；旧兼容门禁的模型迁移dry-run只检查安全示例，不修改本机私有池。
- 已从排除实际池的暂存文件树生成候选ZIP，扫描确认没有实际池、环境配置、Git历史、私有运行目录或已知池凭据。解压后，在没有私有池和本机`.env`的条件下，使用本机既有Python依赖分别运行兼容304项、算法586项，全部通过；这不是跨机器重新下载依赖的证明。日志 `/tmp/zhiwei-final-submission-source-tests.log`。实际池文件内容哈希与处理前相同，权限0600，仍可读取；安全示例没有可调用条目。

## 完成判据

当前规格内F01—F13/U01—U03/M01/D01/D02的代码、数据库、界面和实际恢复证据应闭合；新缺陷必须复测。M02与Q02明确后置，Q01仅按真实样本和已实现规则说明，不宣称无限题型自动正确。CPU首次匹配约32秒的已登记体验限制没有在本轮被消除，不能用本轮方程耗时替代检索计时。

签名、外部模型或资源失效、未知模型答案、未支持的题型和未来任意输入不应被写成“零错误保证”。产品应如实展示失败/待核对、保留原始材料与作答，并支持恢复。

FS-001、FS-002均修复并通过对应验证，未发现新的运行功能阻断；FS-003的当前源码文件树与候选包也已完成凭据排除检查。当前预览已使用修复后的前端，业务及算法未更换架构或重写数据。运行账号和原报告不纳入提交，实际池在新提交文件树中移除；正式ZIP由完成后的提交生成，并再次核对文件与凭据排除。具体提交号见Git历史，工作区状态以提交后检查为准。

## 提交文件与Git历史

实际池继续留在本机使用，不改动其中的条目或凭据；安全示例不包含真实地址或密钥。提交包由提交后的`git archive`生成，包含完整已跟踪项目源码、依赖清单与文档，排除`.git`、私有配置、数据库、上传材料、模型缓存和依赖目录；首次安装仍按QUICK_START准备独立MySQL与自己的模型资源。

移出跟踪不会抹除旧Git提交中的凭据。未获用户明确授权，不重写仓库历史或撤换外部账号密钥。对外分享Git仓库前，需要撤换相关凭据并清理历史；不能拿干净的新提交文件树冒充整个历史都没有秘密。当前可交付的应是经检查的源码ZIP，不应直接分发包含旧历史的`.git`目录。

提交完成后可以使用`git archive --format=zip --output=dist-final/zhiwei-final-submission.zip HEAD`导出源码（先创建`dist-final`目录）。本轮正式文件使用提交号后缀并附SHA-256校验文件；生成目录被忽略，不把ZIP再次提交进源码。交付前须确认包内文件与该提交一致、没有私有配置及已知凭据。当前本机仍可直接`make dev-final`，接手者按QUICK_START配置自己的独立MySQL与模型资源。
