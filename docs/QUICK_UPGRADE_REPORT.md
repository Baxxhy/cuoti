# 轻量 Agent 升级记录

2026-10-20，实施中。目标来自本次任务的 ECED / AEMT / ARPP 与单一 LangGraph 学习闭环要求。

## 当前实际改动

- `backend-algorithms/error_diagnosis.py`：ECED 对已有诊断与真实步骤、参考记录、符号核验结果进行证据评分，不增加模型调用链。
- `backend-algorithms/diagnosis_compute.py`：原诊断计算附带结构化 `evidence_diagnosis`。
- `backend-algorithms/mastery_tracker.py`：AEMT 复用 BKT 后验计算，区分独立作答、提示、完整答案曝光和无效作答；适配已有 `cognition_update` 正式提交接口。
- `backend-algorithms/learning_planner.py`：ARPP 根据状态选择学习动作，并对合格候选题排序，保留到期复习优先、时间限制、重复惩罚和缺题反馈。
- `backend-algorithms/learning_workflow.py`：真正的 StateGraph，包含 ECED、确认分支、原有作答处理、AEMT、ARPP。每轮有界执行后结束，继续使用已有任务检查点。
- `backend-algorithms/service.py`：内部 `learning_task` 操作已调用协调图。
- `backend-algorithms/learning_task_compute.py`：以兼容字段扩展上下文、检查点与学生视图，保留原有作答核验。
- 仓颉 `learning_tasks.cj`、`learning_task_planning.cj`：传入真实诊断确认状态、MySQL 掌握估计、到期题、可练题库、近期练习与偏好；保存推荐前核对候选范围。
- 仓颉 `learning_task_mastery.cj`、`learning_task_worker.cj`、`learning_memory_sources.cj`：复用已锁定的任务事务核对作答事件，通过现有认知更新接口保存 AEMT；保留来源校验、请求去重和对照题并发曝光限制。
- 仓颉 `diagnosis_api.cj`、`question_detail.cj`：将 ECED 结果保存在已有证据 JSON 中，无数据库迁移。
- 前端 `pages/task/task.vue`、`pages/diagnosis/diagnosis.vue`：显示诊断证据、核对入口与推荐操作，推荐按钮进入实际题目或创建单题练习。
- 新增四组算法与图测试；原超时测试使用已诊断的检查点，继续验证 25ms 预算对模型请求的取消。

## 已观察到的验证

- 改动前相关基线：36 项通过。
- 三算法与 LangGraph、预算针对性检查：27 项通过。
- 算法全量回归从 660、663、665 项增加至 666 项通过；最新待核验作答的推荐限制仍需最终回归。
- 新前端任务页面 13 项通过，包含推荐按钮跳转和诊断确认入口；完整前端阶段 259 项通过后又新增了两项用例，最终需重跑相应检查。
- `make verify-final` 已启动：前端测试、类型检查、H5/App 构建、算法 663 项与仓颉 38 项通过，真实 HTTP/MySQL 和浏览器部分仍在运行。不能记作全量通过。
- `make check-final` 首次因业务与算法服务未启动而失败；启动后四项检查通过。后续修复代码在最终交付前仍需重启并复核。
- 兼容 Python 后端 332 项通过，最新诊断位置与辅助追踪相关 28 项通过。
- 两次全量检查尚未通过：第一次内部接口新旧进程混用导致诊断 422；第二次新增证据的 `alignment` 写入 NULL，违反旧表非空约束，导致 503。已修正为现有列允许的字符串，无结构迁移；现先运行 `CANGJIE_VERIFY_FOCUS=agent-upgrade make verify-cangjie`。
- Ruff 与差异空白检查通过。
- 日志目前保存在本机 `/tmp/zhiwei-agent-baseline.log`、`/tmp/zhiwei-upgrade-algorithms-final-candidate.log`、`/tmp/zhiwei-quick-upgrade-verify-final.log`，不是可跨机器复现的交付证据。

## 尚未完成的必需工作

1. 完成真实 HTTP/MySQL 链路核验，修复发现的问题；当前代码接入不等于已验证。
2. 扩充对确认分支、辅助作答、延迟迁移、推荐来源和掌握状态幂等的集成断言。
3. 运行当前主线服务，通过 `make check-final`；完成最新代码的 `make verify-final` 与浏览器验收。
4. 逐项核对目标文件，检查时间、目标、先修和重复错误规则在真实学习中的表现，修复遗漏。
5. 按最终结果更新三份文档和简要功能说明，保存必要证据、提交代码并保持工作区干净。

未改数据库结构、模型配置、题库或已有正式学习记录；没有引入新的模型训练、多 Agent 框架或业务数据库。

## 兼容与业务修正

- 保留无检索资料字段的旧任务指纹表示，避免升级本身使保存的任务失效；增加仓颉回归用例。
- ECED 已核验的错误步号同时驱动 Python 订正目标与仓颉来源步骤，防止仍沿用旧的默认第 1 步。
- 证据不足的几何与非规则题先返回核对状态；通过原有诊断修正 API 确认后才继续。相关工具验收样本增加真实确认步骤，不将人工确认当成符号证明。
- 有效独立作答即通过 AEMT 更新；看过答案不刷新有效学习时间。更新后安排复习，已有待复习安排不后移。
- 重复对照题继续使用已有曝光去重；并发失败的一方不能再通过 AEMT 计入独立迁移。
- 作答后遗忘风险从本次有效学习重新计算；长时间未练习的风险不直接覆盖刚刚独立答对的保持证据。
- 后续发现并修复：候选查询统计列不能直接进入严格原表解析器；任务准备失败现在明确返回可重试状态；公开任务视图补齐确认入口需要的结束原因。
- 原有“只在对照题完成后更新”的总条数断言已按新行为调整：独立原题与有效对照分别记录，预算超时仍必须完全回滚，恢复后只增加本次有效事件。
- 已设置的每日目标接入真实已交卷作答与完成题量，当前题完成后再扣除；预计时间不冒充实际计时。
- 新增正式业务边界检查：算法不能把局部订正伪装成独立作答，阶段必须与仓颉保存的任务阶段相符；长期记忆区分新的原题作答与迁移结果。

## 启动与验证入口

沿用 `make dev-final` 启动主线，`make check-final` 检查运行状态，`make verify-final` 执行完整检查。聚焦算法测试：`PYTHONPATH=backend:backend-algorithms .venv/bin/python -m pytest -q backend-algorithms/tests`。聚焦业务检查只用于排查，不替代完整浏览器验收。
