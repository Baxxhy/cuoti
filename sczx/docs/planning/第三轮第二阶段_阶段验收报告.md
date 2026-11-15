# 第三轮第二阶段阶段验收报告

2026-11-15。已交付独立实验目录、16条冻结模拟情境、A/B/C提示词、只读语料快照、统一CLI执行器、配置/代码哈希、断点续跑、原始输出、盲包与两份空评分表。业务源码、数据库及日常数据均未修改。

最终v3：4项工程检查通过；engineering-v3完成144个受控试次，仅测试编排；pilot-v3完成6次真实Codex调用，2个情境×3组×1次，不是144次正式实验。结果、失败和时延以results/pilot-v3/summary.json为准。来源ID检查仅为结构，不代表教学语义支持。

初版失败未删除：engineering-v1因未登记无经验知识点中断，预定144分母及中断目录保留；pilot-v1和pilot-v2各有6次真实小规模输出，但公开知识过于接近当前题参考，均排除效果比较。v3把特定参考移至仅评阅字段，原题、预期策略、禁用行为与独立题评分未根据模型输出改写。共18次小规模真实调用，三轮分别保留，不拼成正式144次结果。

|交付/检查|状态|说明|
|---|---|---|
|16个冻结情境及评分锚点|已通过|4类各4；材料为AI辅助拟稿模拟情境，非教师已审核数据|
|B/C相同候选与预算；不传评分答案|已通过|工程检查及完整input.json可核对|
|统一模型/low/结构/时限/1次调用/0修复|已通过|独立CLI命令；精确返回模型快照不可得时null|
|原始结果不覆盖及断点续跑|已通过|已有目录包括中断不覆盖；配置不一致拒绝；原始输入输出完整保留|
|小规模真实执行|已通过|v3共6次，逐例状态见原始结果|
|盲包、配对及两份评分表|已通过|分组键须单独保管，不发送评阅者|
|教学适切性/内容/引用语义评阅|未测试|未邀请到两名合格评阅者，评分全部为空|
|独立新题学习表现|未测试|无真实学生作答，不以模型推演冒充学习收益|
|C优于A/B、课堂收益与显著性|未测试|工程结果不能支持这些结论|
|完整144次真实实验|未测试|本阶段明确禁用，不擅自启动|

C对B增加历史信息与匹配机制，不能单独归因于策略算法。SQL学习记忆采集未在本离线实验复测。小规模只覆盖语言配对，不能声称16情境或19学科的效果均已验证。时延可观测，计费未知留null；调用版本字符串固定但精确服务端快照可能不公开。

下一阶段：先由相应学科人员复核16情境与通用知识/参考分离，邀请两名独立评阅者，确认信息匹配归因方案和正式执行预算；得到明确授权后新建正式run。当前停止，不追加普通业务功能或UI改造。

实际v3运行摘要：

```json
{
  "A": {
    "scheduled": 2,
    "succeeded": 2,
    "failed_or_missing": 0,
    "mean_latency_seconds": 5.667829450685531,
    "model_strategy_choices": {
      "hint": 2,
      "example": 0,
      "foundation": 0,
      "rephrase": 0,
      "try": 0
    },
    "failure_rate": 0.0,
    "strategy_appropriateness": null,
    "difficulty_accuracy": null,
    "content_error_rate": null,
    "citation_correctness": null,
    "differentiation_success": null,
    "independent_performance": null,
    "cost": null,
    "review_status": "pending two qualified independent reviewers"
  },
  "B": {
    "scheduled": 2,
    "succeeded": 2,
    "failed_or_missing": 0,
    "mean_latency_seconds": 8.1365493577905,
    "model_strategy_choices": {
      "hint": 2,
      "example": 0,
      "foundation": 0,
      "rephrase": 0,
      "try": 0
    },
    "failure_rate": 0.0,
    "strategy_appropriateness": null,
    "difficulty_accuracy": null,
    "content_error_rate": null,
    "citation_correctness": null,
    "differentiation_success": null,
    "independent_performance": null,
    "cost": null,
    "review_status": "pending two qualified independent reviewers"
  },
  "C": {
    "scheduled": 2,
    "succeeded": 2,
    "failed_or_missing": 0,
    "mean_latency_seconds": 8.281701364088804,
    "model_strategy_choices": {
      "hint": 1,
      "example": 0,
      "foundation": 1,
      "rephrase": 0,
      "try": 0
    },
    "failure_rate": 0.0,
    "strategy_appropriateness": null,
    "difficulty_accuracy": null,
    "content_error_rate": null,
    "citation_correctness": null,
    "differentiation_success": null,
    "independent_performance": null,
    "cost": null,
    "review_status": "pending two qualified independent reviewers"
  }
}
```
