# 核心教学能力对照实验

本阶段交付16个冻结模拟情境和可复现工具，不是教学效果结论。所有材料为项目自编、AI辅助拟稿，无真实学生参与，尚待学科专家复核。57条经验只读快照加2个显式负例夹具，不是新业务库，程序不导入数据库模块、不连接任何数据库。

A仅当前题目/原答/困难与公开知识；B增加相同BM25检索候选；C在相同检索预算上调用现有diagnose、match_experiences并加入范围相关的模拟历史。C的历史已经按冻结范围提供，未在此离线实验中验证业务SQL记忆采集。三组共用gpt-6-luna、low、JSON结构、115秒、每试次1次调用、0次修复；随机种子及temperature不受CLI支持。实际服务返回的精确模型快照若不可得写null，不伪造版本固定。

直接用业务ModelProvider会自动添加教学上下文，污染A/B；实验只复用相同CLI命令约束和纯函数，独立目录禁用工具/网络搜索，不加载项目AGENTS或业务提示词。A不因没有来源直接判内容差；B候选可能被C筛除，这是预定方法差异，不额外补召回。参考答案、评分标准、预期策略、独立题答案不传给任一模型。

```bash
.venv/bin/python -m unittest discover -s experiments/teaching_ablation/runner -p 'test_*.py' -v
.venv/bin/python experiments/teaching_ablation/runner/run.py --mode controlled --run 自定新目录名
.venv/bin/python experiments/teaching_ablation/runner/run.py --mode real --pilot --run 自定新目录名
.venv/bin/python experiments/teaching_ablation/evaluation/report.py experiments/teaching_ablation/results/自定目录名
```

controlled是工程夹具，144个受控响应不等于144次模型实验。real仅允许2情境×3组×1次的小规模验证；完整实调用入口明确拒绝，后续须用户另外授权和新版本实现。相同run参数可以续跑；已有试次目录即使中断也不会覆盖，记录为interrupted。重试失败需新run目录，原失败仍留原分母。summary是可再生派生文件，不允许覆盖trials输入、raw、events或result。不要在有个人资料的目录运行实验；CLI临时目录与业务目录隔离。

先冻结数据、提示词、配置及核心执行代码，再输出；freeze.json为初次冻结，freeze-release.json额外校验发布评分文档与测试/分析文件。试验运行保存自己使用的manifest摘要。正式人工评阅前复核整个release。版本改变必须新建冻结版本和run，不能沿用旧输出拼接成新版本结果。

评分见evaluation/RUBRIC.md。向两名合格评阅者分别发blind-packet、blind-pairs、完整corpus及空reviewer1/2.csv；**不要发送unblinding-key或trials输入、组别提示词**。CSV原评分不覆盖；所有评分待人工填写。引用内容可能暴露是否检索，不能声称完全不可推断的双盲。

对照局限：C比A/B多了学习历史，增益不能单独归因于算法；需要后续额外信息匹配消融，本阶段不增加第四组。16情境覆盖有限，单次pilot没有显著性或跨学科效果结论。独立新题仅冻结评分材料，未让真实学生作答，不报告学习收益。成本不可得是null，失败/超时/拒绝保留，不删除。
