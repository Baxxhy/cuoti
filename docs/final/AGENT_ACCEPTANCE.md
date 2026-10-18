# 智能体十类行为验收

本记录核对[智能体规格](AGENT_SPEC.md)第9节。目标是证明当前任务如何读取反馈、选择行动、拒绝无效证据和保存进度；不把工具名称或模型自述作为完成依据。

## 场景与证据

| 场景 | 可观察结果 | 验证入口 |
| --- | --- | --- |
| 1. 知识零命中 | `knowledge_search/rejected`后转`step_alignment/verified`，没有虚构知识卡 | [算法行为](../../backend-algorithms/tests/test_learning_task_compute.py)的`test_incorrect_observation_causes_bounded_replan_after_zero_hit`；[真实HTTP/MySQL](../../scripts/smoke_cangjie_learning_tasks.py)读取实际工具步骤 |
| 2. 首次证据不满足 | 同一学生动作出现不同工具及新的计划版本，第二步使用原题关系 | 上述用例核对执行顺序与`planner_source=verification`；仓颉步骤按计划版本持久化 |
| 3. 学生答错/答对 | 错误答案留在订正并补支持，正确订正进入独立作答，再进入单条件对照 | `test_local_correction_then_original_then_verified_single_condition`及同一HTTP专项；浏览器任务流程已回归 |
| 4. JSON合法但数学错误 | 参考`x=7`与原方程冲突时返回`source_conflict/needs_review`，没有掌握更新 | `test_plausible_but_mathematically_wrong_reference_is_rejected`；数学结论按原题SymPy验证，不以结构合法代替结论正确 |
| 5. 看答案后答对 | 动作记为辅助，不能产生新的独立迁移证据 | `test_reveal_is_explicit_and_never_automatically_counts_as_mastery`；HTTP专项的显式`reveal`及MySQL证据计数 |
| 6. 题干越权/伪工具 | 题干保留为数据；非法模型计划回退；客户端非法动作422；绕过Python校验的非法工具回执由仓颉拒绝，前置写入回滚，之后可恢复 | 新增[仓颉合同专项](../../scripts/smoke_cangjie_task_contract.py)，真实MySQL检查工具步骤、运行记录、动作状态与认知更新；本轮终态结果见下文 |
| 7. 记忆撤销/题目改变 | 来源/版本/时效检查排除旧引用；在途变化不提交旧证据 | [记忆HTTP专项](../../scripts/smoke_cangjie_learning_memory.py)的编辑、删除、撤销和在途核对；[来源专项](../../scripts/smoke_cangjie_task_sources.py)；[记忆合同](MEMORY_IMPLEMENTATION.md) |
| 8. 模型不可用 | 使用受控规则或可恢复失败，轨迹标明实际来源；不补造模型结果 | 记忆专项设定上游失败后读取规则选择；`test_planner_timeout_returns_bounded_rule_support`验证超时原因与有界支持 |
| 9. 重启/重复/取消 | 恢复同一检查点、同请求不重复计证据，取消后迟到结果不提交 | [任务HTTP专项](../../scripts/smoke_cangjie_learning_tasks.py)、[主验证器](../../scripts/smoke_cangjie.py)真实进程重启；[预算专项](../../scripts/smoke_cangjie_task_budget.py)延迟回执与取消 |
| 10. 持续循环 | 24回合/72执行上限停止受理新动作，可取消和重开；不丢历史 | 预算专项核对HTTP拒绝、幂等重放、过期租约收尾与停止重开；算法回合上限测试；[预算合同](BUDGET_IMPLEMENTATION.md) |

## 本轮合同专项

命令：`CANGJIE_VERIFY_FOCUS=task-contract make verify-cangjie`。在随机隔离MySQL库、本地Qwen协议模拟与测试代理中运行，不读取真实模型池。

1. 保存一道夹带伪工具指令的固定题，启动任务后主动请求提示；模拟模型提出`delete_database`，检查合法规则回退、原题保留与无认知更新。
2. 伪造客户端动作，检查422且任务版本未被推进。
3. 让真实Python先完成合法工具计算，再由仅用于验收的代理追加非法工具轨迹。非法轨迹放在合法轨迹之后，验证仓颉事务会连同前置步骤及运行记录一起回滚。
4. 失败动作保留可恢复状态；移除代理干预后恢复原任务，不写入学习证据。

运行记录按`agent_runs.result.task_id`定位，兼容没有教学会话ID的独立任务；步骤、运行和工具调用探针必须先匹配非零记录，才比较拒绝后的计数。首轮脚本误用了不存在的`question_id`字段，其失败不计产品通过。

最终专项已正常退出0：171项算法、31组仓颉原生、真实HTTP/MySQL拒绝/回滚/恢复、无数据库配置的就绪拒绝与媒体基础检查通过。日志`/tmp/zhiwei-agent-contract-v3.log`。Ruff格式与检查通过。

## 证据边界

上一轮完整`make verify-final`已退出0：前端179项、算法171项、仓颉31组、HTTP/MySQL/重启及浏览器47项零跳过，日志`/tmp/zhiwei-paper-final.log`。本轮只补验收脚本和记录，产品源码未变，复用该完整证据；新增合同场景必须另有复测通过结果，不能借用旧日志冒称已覆盖。

该专项验证受控协议与业务边界，不是对真实Qwen进行广泛对抗评测。真实模型的固定题执行另见[实际运行](ACTUAL_RUNTIME_IMPLEMENTATION.md)、[高中样本](INEQUALITY_IMPLEMENTATION.md)和[图形核对](FIGURE_REVIEW_IMPLEMENTATION.md)；它们不证明所有学科和任意手绘题都能正确教学。学生现场使用、单轮/任务循环效果对比按当前交付范围保留为后续改进，不编造参与者或优越性结论。
