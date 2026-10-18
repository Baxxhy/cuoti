# 错题帮运行版交付说明

当前范围是整个系统能运行、主要功能能实际使用，界面简单清楚。架构为uni-app前端、仓颉业务/MySQL、Python内部算法。手机签名安装后置，备份恢复不开发；不定位为课程作业，也不只完善学生作业模块。

最新[AI内容补充验收](EXTENDED_AI_ACCEPTANCE_2026_10.md)记录12道实际模型样本、三条新增任务闭环，以及首错定位误判、类别和提示修复。按用户最新要求，等待时间、手机安装包与Git历史不再列为本轮待办；当前服务配置保留。

最新[三种学生情境试用与问题登记](THREE_STUDENT_AUDIT_2026_10.md)记录逐功能检查、实际Qwen固定样本，以及步号、修正失败反馈和本题复习定位修复；这些工程角色模拟不代替真人学生试用。

随后新增的[全系统输入与证据加固](RELEASE_HARDENING_2026_10.md)记录11类缺陷修复、模型输出验证、历史声明降级和实际智能体完整闭环。最新逐功能状态以[最终提交复核](FINAL_SUBMISSION_AUDIT_2026_10.md)为准：补齐人工改步后的缺参考反馈与真正只读验收，保留历史结果，不叠加通过次数。

源码交付只包含`api_pool.example.json`安全示例，实际池仍保留在本机后端并已移出新提交跟踪；首次接手按QUICK_START填写自己的资源配置。旧Git历史曾包含实际凭据，不能直接公开或作为交付包分发；源码ZIP排除`.git`与私有配置，详见最终提交复核。

## 启动与使用

首次安装按[当前架构启动指南](QUICK_START.md)准备Python/前端依赖、仓颉工具链和独立MySQL。`make install-final`会创建缺失的`.venv`并安装两端依赖，不创建业务数据库或改私有配置。

已有环境在项目根目录运行：

```bash
make dev-final
# 另一个终端
make check-final
```

打开启动器输出的H5地址，注册学生账号，按“今日 / 错题 / 学习 / 我的”使用。Ctrl+C停止本次启动的三端服务；MySQL独立管理。服务就绪检查不调用模型，不能代替外部模型与题库资源验证。

教师、家长和管理员通过[本地专用账号入口](LOCAL_IDENTITIES.md)创建账号。家长只读报告需要学生明确授权；学生不能自行切换高权限身份。真实练习资源按[题库准备说明](QUESTION_BANK_IMPLEMENTATION.md)配置，使用仓颉写入MySQL，不向新库运行旧Python业务版导入命令。

## 功能与边界

| 场景 | 当前支持 |
| --- | --- |
| 账号与整理错题 | 注册/登录/改密、拍照/相册/手动录题、框选与OCR核对、搜索/分类/收藏/归档，保留原图和当时作答 |
| 本题学习 | 分析与诊断、完整引导学习（理解检查、讲回、近远迁移）、局部订正、独立作答、已验证单条件对照、自检要点与学习档案 |
| 学生体验升级 | 学习方向保存/修改、无题知识卡与例题起点、按持久化ID错因回放、按学科可追溯易错地图、按档案决定下一步的修复路线；详见[调研与交付记录](PRODUCT_UPGRADE_2026_10.md) |
| 学习智能体 | 读取受控记忆、规划、工具执行、验证、按反馈调整；任务持久保存，支持恢复、取消和停止重开 |
| 图文辅助 | 手写照片先转文字并由学生确认；有限图形标注核对、等式与一次/二次函数图示及观察 |
| 巩固与回顾 | 真实题库练习、到期复习/历史、知识卡/关系、学习报告/图谱；复习有多题切换、草稿、回执及回原题恢复 |
| 组卷导出 | 按范围选题、修改标题/分值/排序，题目PDF、答案PDF和学习表格三类导出；打开顺序与失败恢复已补验 |
| 教师协作 | 班级/学生、发布题目、布置、学生文字/手写提交、人工复核、反馈和相关学习记录 |
| 家长与管理 | 学生授权的只读报告、双方解除；管理员分区查询与敏感字段过滤 |

- 仓颉负责业务事实、权限和MySQL；Python只做内部计算。旧Python业务版保留作兼容参照，不作为当前前端的静默回退。
- 原图、原作答与后续订正分别保存；模型结构化输出经Pydantic校验，前端只消费受控可视化结构，不执行模型生成的JavaScript。
- 局部订正与单条件对照重点支持已验证的一元一次方程。独立多项式方程/不等式按已实现的原题解集规则核对；未覆盖题型不能据此宣称正确，任意手绘几何证明不在已实现能力中。
- 看答案、用提示、局部订正或保存自检要点不等于独立掌握。证据不足显示待核对，任务完成与知识掌握分开记录。
- 逻辑模型固定Qwen，经ApiPoolProvider轮询。OCR、分析和智能教学需要有效模型资源；无模型时明确失败或使用已标记的受控规则，不补造AI结果。学生端使用文字/照片；内部语音接口按需核验。

## 界面与实际页面

延续蓝白与系统中文字体，核心页突出当前任务，长解释、图谱、证据和历史按需打开。正常任务作答默认是一个提交主按钮与“给点提示 / 更多方式”两个辅助入口；拍照、图示和参考答案在更多方式中可达，不删除功能。

本批[首次起点](screenshots/product-cold-start.png)、[跨题地图·手机](screenshots/product-evidence-map-mobile.png)/[桌面](screenshots/product-evidence-map-desktop.png)、[回放](screenshots/product-live-replay.png)与[修复路线](screenshots/product-live-repair.png)均有实际渲染。九个核心页的360/1280宽度共18个组合通过，无页面横向溢出、脚本错误0；其中练习使用明确标注的布局夹具，其余读实际运行数据，不混同为模型质量或学生试用。

前批次六页及任务辅助入口核验保留：[今日](screenshots/release-today.png)、[错题本](screenshots/release-notebook.png)、[详情](screenshots/release-detail.png)、[本题学习](screenshots/release-task.png)、[学习中心](screenshots/release-learning.png)、[报告](screenshots/release-report.png)、[展开更多方式](screenshots/release-task-more.png)。任务辅助入口的360/390/430宽度、放大菜单文字、键盘及草稿保留行为继续纳入回归。

## 当前范围验收

| 要求 | 证据与结果 |
| --- | --- |
| 架构与运行 | 实际仓颉、MySQL/009表版本、Python算法、前端四项就绪；启动/停止和独立库保护有专项 |
| 学生及多角色主要流程 | [验收矩阵](ACCEPTANCE_MATRIX.md)F01—F13关联页面、仓颉业务、算法、MySQL与浏览器；涵盖学习、复习、三类导出及师生/家长协作 |
| 智能体确有行动闭环 | [十类行为验收](AGENT_ACCEPTANCE.md)及原生非法工具拒绝/事务回滚/恢复通过；不是仅凭规划字段或工具名称判定 |
| 页面与异常恢复 | 本轮10项任务页行为与实际页面检查通过；原有空/失败状态、账号、草稿、跨设备及长内容测试纳入完整回归 |
| 实际算法与数据 | 真实Qwen固定题、PNG原件/OCR、题库推荐与错配拒绝已有实际记录；前批次核对1770题、1442条独立向量及BGE向量/重排模型已加载，本轮不把历史模型结果当作新增质量评测 |
| 安装交接 | [启动指南](QUICK_START.md)与最终版依赖入口已补齐；make执行展开、临时全新venv/pip入口及当前依赖检查通过；未宣称跨机器全新依赖下载已完成 |
| 完整软件回归 | 最新提交门禁退出0：前端206项、算法601项、仓颉34项、HTTP/MySQL/重启与52项浏览器，0跳过，类型/H5/App本地资源通过；兼容后端304项通过。详见[最终收尾验收](FINALIZATION_2026_10_18.md) |

实际固定样本与发现问题后的修复分别见[实际运行](ACTUAL_RUNTIME_IMPLEMENTATION.md)、[原图合同](UPLOAD_ORIGINAL_IMPLEMENTATION.md)、[诊断对齐](DIAGNOSIS_ALIGNMENT_IMPLEMENTATION.md)、[高中样本](INEQUALITY_IMPLEMENTATION.md)、[图形核对](FIGURE_REVIEW_IMPLEMENTATION.md)、[练习相关性](PRACTICE_ALIGNMENT_IMPLEMENTATION.md)和[内部语音](VOICE_RUNTIME_IMPLEMENTATION.md)。语音固定文本存在“移项”误转，不等于逐字准确；这些样本也不证明全学科任意题的教学质量。

具体恢复与页面记录见[账号](ACCOUNT_ACCESS_IMPLEMENTATION.md)、[学习入口](TASK_ENTRY_IMPLEMENTATION.md)、[复习](REVIEW_RECOVERY_IMPLEMENTATION.md)、[多题切换](REVIEW_QUEUE_IMPLEMENTATION.md)、[原题/旧稿](REVIEW_ORIGIN_IMPLEMENTATION.md)、[报告](REPORT_PRESENTATION_IMPLEMENTATION.md)和[组卷](PAPER_RECOVERY_IMPLEMENTATION.md)。阶段版本与完整命令结果保留在[实施进度](IMPLEMENTATION_STATUS.md)。

## 后置事项

Android/iOS签名安装、真机与发行按用户要求后置；H5可运行、App本地资源可编译不代表已生成APK/IPA。真实学生现场使用、广样本教学效果及单轮/任务循环效果对比作为后续改进，未编造完成结果。本次不开发备份恢复、商业多租户、广告付费、社交或生产运维平台。

当前约定范围的运行版已完成本次交付核对；完整功能与界面按上述证据验收，后置事项单列，不以本次通过冒称已完成手机发行或教学效果研究。
