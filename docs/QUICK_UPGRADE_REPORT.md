# 轻量 Agent 升级交付

更新：2026-10-20。基于现有学习任务增量接入三个算法和一个 LangGraph 协调图，保留仓颉业务主线、MySQL、原有 OCR / RAG / SymPy 与旧 Python 兼容入口。

## 实际改动

| 文件或模块 | 完成内容 |
| --- | --- |
| `backend-algorithms/error_diagnosis.py`、`diagnosis_compute.py` | ECED 复用原模型诊断、真实步骤和符号核验；新增有来源的证据评分、首错定位与证据不足确认。分数不宣称是真实概率。 |
| `backend-algorithms/mastery_tracker.py` | AEMT 复用现有 BKT 后验与熵；区分独立作答、提示、答案曝光、延迟迁移及无效证据，避免重复或虚假掌握更新。 |
| `backend-algorithms/learning_planner.py` | ARPP 复用信息增益，新增八类学习动作、到期复习优先、先修补充、失败提示、重复惩罚、学习量与预计时间限制。无题时返回知识卡或明确提示。 |
| `backend-algorithms/learning_workflow.py`、`service.py` | 实际编译并调用单一 `StateGraph`；`learning_task` 操作进入 ECED、条件确认、原有作答处理、AEMT、ARPP。每轮有界执行，无多 Agent 或第二套任务数据库。 |
| `backend-algorithms/learning_task_compute.py` | 兼容扩展上下文、检查点与学生视图，记录提示和完整答案曝光，保留原判题。订正前不自动展示参考答案，完成后不重复旧的错误提示。 |
| `backend-cangjie/src/learning_tasks.cj`、`learning_task_planning.cj` | 读取真实掌握、本人到期题、合格题库、近期练习、目标和预计剩余时间；保存前验证推荐及备选 ID。 |
| `backend-cangjie/src/learning_task_mastery.cj`、`learning_task_worker.cj` | 在已有事务、来源版本和租约检查内核验真实作答，再保存 AEMT 与复习安排；阶段不可伪造，重试不重复计数，超时全部回滚。准备失败返回可重试状态。 |
| `backend-cangjie/src/learning_memory.cj`、`learning_memory_sources.cj`、`learning_task_sources.cj` | 正确区分原题独立证据和迁移证据；来源步骤采用实际核验的首错位置，保留曝光去重。 |
| `backend-cangjie/src/diagnosis_api.cj`、`question_detail.cj` | ECED 使用已有证据 JSON 保存和读取；保留旧任务来源指纹，无数据库结构迁移。 |
| `frontend/src/pages/task/task.vue`、`pages/diagnosis/diagnosis.vue` | 展示简短证据、确认入口、作答反馈与下一步操作；推荐实际打开错题、知识卡或创建真实单题练习。 |
| 算法测试、仓颉测试、`scripts/smoke_cangjie_*.py`、前端任务测试与浏览器用例 | 覆盖规则边界、确认、恢复、辅助程度、答案曝光、幂等、每日目标、超时与推荐题实际加载。 |

## 完整链路

前端提交 → 仓颉校验并读取任务与 MySQL 上下文 → Python 内部 `learning_task` → LangGraph 诊断 / 作答 / 掌握计算 / 规划 → 仓颉核对来源、阶段、事件和候选范围 → 同一事务保存检查点、有效学习证据及复习安排 → 前端显示结果和下一步按钮。

算法只能提出建议，不能直接写业务库。人工确认沿用原诊断修改接口；等待学生时结束本轮，再从已有检查点恢复。模型继续由 ApiPoolProvider 调用 Qwen，不另建模型链。详见 [算法设计](ALGORITHM_DESIGN.md)与[工作流](AGENT_WORKFLOW.md)。

## 验证

最终运行源码版本：`910b189`（之后仅更新文档与验收证据）。`make verify-final` **整条命令退出 0**，结果：

| 检查 | 实际结果 |
| --- | --- |
| 前端单元测试 | 261 项通过 / 49 文件 |
| TypeScript、H5 / App 本地资源构建 | 全部通过 |
| 算法服务 | 668 项通过 |
| 仓颉 | 40 项通过，0 跳过 |
| 真实 HTTP / MySQL、重启恢复 | 通过；覆盖每日目标、辅助证据、推荐来源、超时回滚、幂等和恢复 |
| Playwright | 59 项通过，0 跳过；包含推荐题实际创建并加载题干 |
| 全路由渲染 | 48 路由 × 375 / 1280 宽度 = 96 次；无运行异常或横向溢出 |
| 运行状态 | 最新主线重启后 `make check-final` 四项通过 |
| 兼容 Python 后端 | 332 项通过；对应代码未变，复用该次有效证据 |
| 静态与文档 | Ruff、差异空白与本地引用检查通过 |

验收摘要见 [validation.json](quick-upgrade/evidence/validation.json)，路由结果见 [all-route-rendering.json](quick-upgrade/evidence/all-route-rendering.json)。已人工查看最新[订正页](quick-upgrade/evidence/task-repair.png)、[完成页](quick-upgrade/evidence/task-completed.png)和[推荐练习](quick-upgrade/evidence/recommended-practice.png)截图。原始命令日志留在本机 `/tmp/zhiwei-quick-upgrade-verify-delivery-v2.log`、`/tmp/zhiwei-quick-upgrade-check-final-delivery.log`，不把临时日志当作跨机器交付物。

此前完整运行暴露的参考答案提前展示、候选统计列解码、证据非空约束、确认入口字段、收藏请求未完成就刷新、历史页同路由刷新及重复反馈选择器问题，均已修正并保留相应断言；不把失败运行计为通过。

## 启动和复验

已有本地配置、MySQL 和依赖就绪后：

```sh
make dev-final
make check-final
make verify-final
```

`make check-final` 检查主线服务是否运行；`make verify-final` 包含前端测试、类型、H5 / App 资源构建、算法、仓颉、真实业务接口 / MySQL 与浏览器检查。兼容后端可单独运行 `.venv/bin/python -m pytest backend/tests`。

## 使用范围与限制

- 测试使用真实仓颉、MySQL、算法服务和浏览器，但模型、检索及语音上游使用受控夹具；不据此宣称真实远程 Qwen 的教学质量或实际学习提分效果。
- BKT 与推荐权重是冷启动参数，未经学生数据拟合。每日时间按题量估算（订正 3 分钟、题库作答 1 分钟），不是实际屏幕计时。
- 现有题库 1770 道、1430 道可练，语文 / 英语缺失，知识标注有限；仍不足以支撑初一至高三全科长期练习。
- 本轮不训练模型、不更换数据库和供应商、不改数据库结构，不覆盖已有题库、正式学习历史、原图或 API 池配置。
- App 资源构建不等于签名安装包交付。生产环境部署与远程模型实效评估不属于本轮已验证结果。

本轮轻量学习闭环目标已完成，没有阻塞本地使用的问题；上述题库覆盖、参数拟合、远程模型教学效果和签名安装包仍为明确的未覆盖范围。
