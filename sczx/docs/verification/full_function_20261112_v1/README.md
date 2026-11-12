# 全功能专项验收证据

2026-11-12 · v35 · 基准f6b4b5d · Linux本地Web

[统一验收表](../../planning/全功能正确性与入口合理性验收表.md) · [完整功能JSON](inventory.json) · [CSV](inventory.csv) · [统计](summary.json) · [20项返修](repairs.json)

169个实质主功能单元均已尝试：167通过，2项原生语音设备阻塞；未把设备回退当语音成功。确认重复入口1处已合并；保留后台重试后近期状态缓存联动P3。没有新一轮全站视觉重构，也不用AI角色评分代替功能证据。

## 操作方法与证据边界

三个AI代理分别在全新Chrome会话扮演学生、教师、管理员，仅从8103根URL正常登录，经可见菜单、鼠标、键盘及表单完成任务。禁止其读业务源码、手工输入业务路由、直接调用API完成业务或修改Vue状态。可读取现有CDP基础驱动、观察点击产生的网络；必要的角色间任务交接由消息协调。它们是模拟角色，未冒称真人受试者或教师评阅。

主代理另行扫描源码、盘点169项、核对API/MySQL/原文件、构造损坏storage/受控503/崩溃和权限边界。技术补验与角色寻路分开标注。真实AI任务通过本机Codex CLI的gpt-6-luna/low；自动回归中受控提供者与真实模型结果分开。

独立实例8103/MySQL23325，教师2人、学生3人、管理员1人及至少2个班级由实际UI创建/加入。另有导航诊断教师、非成员技术学生，只用于主代理技术核对。初始5个课程任务是准备数据，不能计作六条业务链成功；六链均用本轮新材料/任务/原答/试卷/课堂实际走通。

## 三角色原报告

| 角色 | 基准 | R1 | R2 |
|---|---|---|---|
| 学生 | [22场景](student/baseline.readable.md) / [原JSON](student/baseline.json) | [9项定点](student/retest-r1.readable.md) | [3项定点](student/retest-r2.readable.md) |
| 教师 | [35场景](teacher/baseline.readable.md) / [原JSON](teacher/baseline.json) | [14项及补项](teacher/retest-r1.readable.md) | [4项定点](teacher/retest-r2.readable.md) |
| 管理员 | [21场景](admin/baseline.readable.md) / [原JSON](admin/baseline.json) | [6项及新目标课时](admin/retest-r1.readable.md) | [中断恢复、空名](admin/retest-r2.readable.md) |

原始报告保持冻结。`.readable.md`只重定位链接，未改变事实；JSON中的`/tmp/sczx-full/角色`映射到当前目录下对应角色。日志行号、动作号、截图及DOCX可互相对照。凭据、浏览器profile、用户数据库及私有上传未打包；[文件哈希清单](evidence-manifest.json)记录拷贝与来源摘要。

## 技术及真实业务核对

- [无编辑导航基准](root/navigation-baseline.json)：5页切换产生6次PUT；[R1复测](root/root-browser-r1.json)：0次、断网可导航，修改失败仍保护并能重试。
- [不存在记录、无会话、角色不符和破损旧记录](root/route-boundaries.json)。
- [30项权限/固定答卷检查](root/permission-matrix.json)：30通过；其他教师/真正非成员分别验证。早期把已加入班级的学生误当非成员，以及给公开课程附加无效admin参数的预期均撤回，不列产品缺陷。
- [六链数据与原文件](root/chain-readbacks.json)、[真实教师语义重排](root/teacher-rerank-readback.json)。
- [实际启动恢复死锁](root/restart-deadlock-baseline.json)、[崩溃恢复](root/crash-recovery-r2.json)、[重试最终两次执行](root/recovery-result-final.json)。首次优雅退出恰好等模型成功，未算中断；第二次仅终止核对过身份的专用QA进程，确实留下running，修复后启动自动标中断，管理员UI手动重试成功。没有手写成功任务状态。
- [本机8099更新](root/main-runtime-v35.json)：私有备份已完成，仅增加收藏表；所有旧业务表行摘要与上传清单不变；qmx登录及平台读取200。

## 检查结果

[41/41浏览器](root/browser-final-clean.log)、[12/12JS](root/unit-final.log)、[181项独立新MySQL全量](root/mysql-final.log)通过。随后新增启动恢复检查，相关[12/12本地运行工具回归](root/release-recovery-final.log)通过；合计182个不同后端检查的有效证据，最终同源码全量由GitHub MySQL CI复核。[构建](root/build-r2.log)完成。

前一轮证据保留。中途修改源码后的Vite热更新导致测试覆写了不同模块实例，已重启本轮自己的Vite并全量复跑41通过；迁移计划的旧0016测试期望已随0017更新。CDP原生确认等待、初始路由尚未稳定及诊断连接池阻止预检等工具问题单独记录，不算产品缺陷或悄悄跳过。

[异常及权限矩阵](异常与权限矩阵.md) · [六链记录](六条业务链.md) · [重复入口分析](重复入口分析.md) · [测试覆盖说明](覆盖与冻结.md)。CI运行链接在最终报告及`remote-ci.json`中补齐。
