# 最终交付验收矩阵

2026-10-18最新逐项核对见[最终收尾验收](FINALIZATION_2026_10_18.md)：当前主线206项前端、601项算法、34项仓颉、52项浏览器及类型/资源构建通过，0跳过；兼容后端304项通过。下表各批原始数字保留为历史证据，不与本轮混算。

> 当前按[系统运行与使用说明](SYSTEM_DELIVERY.md)验收整个系统的主要流程，不定位为课程作业或仅验证学生作业模块。备份恢复取消，签名安装后置；真实质量、学生试用和进阶几何继续按实际证据标识，不能凭接口回归宣称通过。

2026-10-17最新功能升级与三种学生模拟情境的逐功能记录见[产品升级](PRODUCT_UPGRADE_2026_10.md)和[问题登记](THREE_STUDENT_AUDIT_2026_10.md)。下表原有批次数字是历史证据，最新统计以实施进度及问题登记的执行结果为准；模拟学生不能把Q02的真人参与者验收改为通过。

2026-10-17—18本轮扩大输入与反事实证据测试的当前状态见[提交前加固](RELEASE_HARDENING_2026_10.md)，逐项对应F02/F03/F04/F06/F11及U01—U03。特别区分参考文本一致、源方程规则验证、原正确步骤保留与独立学习结果，不用同一个“已验证”覆盖它们。

要求来自 [产品方案](README.md)、[UI规格](UI_SPEC.md)、[智能体规格](AGENT_SPEC.md)、[手机交付](MOBILE_DELIVERY.md) 与 [实施计划](DELIVERY_PLAN.md)。现有功能以仓颉 `c31890e` 的接口证据为起点；新增需求必须有本轮实际证据。原接口94条只是迁移基线，新功能可以增加接口，不固守旧分母。

| 编号/要求 | 页面/代码入口 | 数据、算法与验证入口 | 交付状态 |
| --- | --- | --- | --- |
| F01 账号/角色隔离 | login/register/profile；仓颉accounts | MySQL users；smoke_cangjie_accounts.py、school.py、system_admin.py | 角色隔离HTTP、学生授权/双方解除与28项零跳过浏览器通过；本地专用角色账号创建/预检已通过CLI/MySQL/HTTP专项；账号标签/错误反馈/原地重试及注册改密4项实际浏览器专项通过 |
| F02 录题/OCR/原图保护 | capture/crop/ocr/manual；仓颉recognition | 题目/作答/资源/job；normalize/crop/recognize；smoke_cangjie_media.py、student_work.py | 新增原始上传字节保留与原图选择修复；实际PNG核验通过，App仍待真机 |
| F03 搜索/收藏/筛选/归档 | problem/list、search、detail | questions；smoke_cangjie_list.py、questions.py、edit.py | 已完成筛选面板与详情分区；真实学生验证后续 |
| F04 分析/错因/人工修正 | diagnosis；仓颉diagnosis | 分析/诊断/证据；analyze/diagnose；smoke_cangjie_diagnosis.py | 实际固定一次/二次方程、欧姆定律、氢气燃烧及高中不等式/英语/生物已核对；不等式按解集保留正确步骤与端点，重复原式不计完成；广样本/学生质量仍待验 |
| F05 本题教学/工具/记忆 | tutor；tutor_dialogue.cj | sessions/turns/agent_runs/tool_calls；dialogue_prepare/finish；smoke_cangjie_tutor_dialogue.py | 既有单轮能力保留；持久任务见F06，来源/时效受控的六类记忆已接入，当前证据见实施进度 |
| F06 持久智能体/预算/重规划 | 新learning-tasks业务及任务呈现 | 新迁移、task/step、租约/幂等/取消/恢复；AGENT_SPEC十类行为测试 | 诊断/详情默认统一持久任务，回执丢失重试与返回保护已验证，完整讲解入口保留；主链路与[十类行为证据](AGENT_ACCEPTANCE.md)已核对；非法计划回退、原生非法工具拒绝/无会话审计回滚及恢复专项通过；租约/幂等/取消/重启/MySQL通过；记忆来源/时效与在途变化已接入验证；共享预算/迟到结果/事务末尾回滚/停止重开已通过；有限图形标注/原题关系核对已接入，任意几何证明仍不支持 |
| F07 关键步骤订正 | task/详情；learning_task_compute | learning_task_actions持久尝试、原题指纹与提示曝光；HTTP/MySQL与浏览器重读 | 一元一次方程局部订正已实现，原作答与原步骤ID/来源快照保留；任务照片异步转写与本人确认已接入，图形候选观察与原题核对已接入，属于辅助证据，不能冒称任意几何证明 |
| F08 单条件对照练习 | tutor/practice | 变化项、原题指纹、验证与判题资格；variant_compute.py | 既有迁移题保留；一元一次方程单条件对照已验证，重复/曝光不增加独立证据 |
| F09 自检要点 | 任务结束/学习档案 | learning_self_checks；确认、CRUD、关联题、版本/权限、事务审计；smoke_cangjie_self_checks.py | 已接入，当前回归结果见实施进度；不计掌握证据 |
| F09a 任务图示/观察 | task-visualization、task_visualization_compute、learning_task_visuals | checkpoint/actions；原式数学验证、参数/权限/幂等、保存回滚/照片与进程恢复；smoke_cangjie_task_visuals.py | 三类受控图示已接入，当前验证见实施进度；几何关系推理不属于该成果 |
| F10 知识/图谱/检索 | library/knowledge/analysis | 250卡/65关系初始化；BGE/Qdrant；smoke_cangjie_retrieval.py、insights.py | 实际独立库1770题、1442条BGE索引；原CMMU重复跳过已验证；覆盖与教学质量仍按样本范围说明 |
| F11 独立练习/手写/复习 | practice/review | attempts/reviews/推荐版本；grade/cognition；smoke_cangjie_practice.py、handwriting.py、reviews.py | 复习增加原题往返、旧文字核对/失效安排恢复、上下题切换、缓存失败本页保留及来源版本保护，真实Qwen浏览器专项通过，见[复习恢复记录](REVIEW_RECOVERY_IMPLEMENTATION.md)；真实题库链路、配图、作答与重复提交保护通过；单选/多选及公式排版已修复；已增加准入/版本凭据；实际旧错配题拒绝无写入，匹配方程题判对且归属正确，见相关性记录；App后置 |
| F12 组卷与三类导出 | paper-center | paper/导出资源；render_paper；smoke_cangjie_papers.py | 组卷打开顺序、保存/删除恢复、导出回执与窄屏按钮已补验，见[组卷恢复记录](PAPER_RECOVERY_IMPLEMENTATION.md)；三类导出完整浏览器回归通过；App打开后置 |
| F13 教师/家长/管理 | teacher/guardian/admin | 班级/关联/下发/复核/审计；smoke_cangjie_assignments.py、school.py、system_admin.py | 完整47项浏览器零跳过，包含家长报告/学生授权/双方解除及刷新拒绝、多作业单项展开、教师布置与人工复核闭环；真实家庭使用后续 |
| U01 今日/学习中心/报告 | index、learning、analysis | UI_SPEC信息预算、空/失败/真实数据；窄屏截图与行为测试 | 已实现；首页/学习页及三角色真实报告已检查，当前180项前端/41文件、47项完整浏览器通过；学生试用后续 |
| U02 列表/详情/本题学习 | problem/list、detail、tutor | 筛选面板、本地分区、单问题；旧导航/组卷范围回归 | 知识页减负与三页诊断状态已实现；主学习入口/重试/草稿恢复及完整引导入口已核对，见[学习入口记录](TASK_ENTRY_IMPLEMENTATION.md)；六个实际390px页面检查通过，180项前端、47项完整浏览器通过；完整结果见实施进度，真实学生试用后续 |
| U03 内容与无障碍 | math-text、受控内容块、全局样式 | 禁止盲切公式/执行模型JS；360/390/430、200%字、键盘、安全区、读屏/焦点 | 受控块、长说明展开与草稿恢复已实现；步号隔离与双设备专项见实施进度；账号三页已补原生标签/自动填充/键盘与360/390/430、200%文字/容器边界和小视口可达检查；完整无障碍与真机分开验收 |
| M01 App资源/服务连接 | vite/API/manifest；final.sh | 构建环境、HTTPS、缓存规则、启动/就绪与停止；api-base.test.ts | 已提交11caf53；启动/停止、构建配置验证通过 |
| M02 Android/iOS安装 | manifest、签名/本机打包 | 身份/图标/权限、安装升级、退后台/杀进程、相机/Canvas/公式/导出；MOBILE_DELIVERY逐项 | 按用户2026-10-16要求暂缓 |
| D01 数据准备与升级 | schema、seed/import/索引 | 独立MySQL初始化/升级；原备份/迁入要求按本轮范围移出 | 初始化和迁移已有专项；备份恢复按用户要求不做 |
| Q01 真实算法与对照评估 | 固定样本/版本/结果报告 | 真Qwen/BGE/语音；原单轮与新循环比较；人工核对正确性/延迟/调用量 | 固定一元一次方程已在实际Qwen池验证分析/诊断/订正；实际PNG的OCR与原始字节保留已验证；实际1770题入库、1442条BGE索引；固定练习正向与错配拒绝已验证；另有三个自编高中样本与中间变形补全的实际任务通过；内部语音合成/转写实际恢复，固定文本存在“移项”误转，学生端仍无语音入口，见[语音运行记录](VOICE_RUNTIME_IMPLEMENTATION.md)；更多题型和单轮/循环对照仍待完善 |
| Q02 学生使用验证 | UI_SPEC核心任务 | 初高中6—8名实际参与者；任务成功/误操作/信息过量，目标80%非结果 | 后续改进，待实际参与者；当前运行交付不冒称试用已完成 |
| D02 完整项目交付 | 根README/配置/指南/验收记录 | make verify-final、兼容版make verify、签名包后续交付、版本/来源、无私钥凭据入Git、干净提交 | 当前系统以make verify-final验收；发行与进阶范围按新版交付说明 |

具体算法operation、表字段和函数以当前源码为准；目录内已实现接口的完整清单见 [仓颉路由用途](../cangjie/ROUTE_USAGE.md)，不复制维护另一份易失真的接口清单。本文状态只有在观察到对应层级的证据后更新。

多题复习的实际无写入、缓存失效、窄屏/200%文字和完整主线结果见[多题复习记录](REVIEW_QUEUE_IMPLEMENTATION.md)。

原题往返、来源变化与旧安排失效的实际Qwen核对、前端行为及46项完整浏览器见[复习原题与旧稿记录](REVIEW_ORIGIN_IMPLEMENTATION.md)。

本轮运行版收尾：完整`make verify-final`退出0，前端180项/41文件、算法171项、仓颉31组、HTTP/MySQL与重启恢复、浏览器47项零跳过，见`/tmp/zhiwei-release-final.log`。任务默认提示/更多方式两个辅助入口，六页实际截图和安装入口见[系统交付说明](SYSTEM_DELIVERY.md)。
