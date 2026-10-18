# 错题帮 Round 1 全量回归

- 结果：通过
- 开始提交：`8934c5a69cf91885aa5dd6fa1c7046f187d8180e`
- 验证提交：`aa51934d86ec0cead921b6ec78acc2e7f144c048`
- Qwen逻辑模型：`Qwen3.6-35B-A3B`
- API池：总计 13，文本 7，视觉 6
- MySQL表：37（含Alembic），孤立记录 0
- PaddleOCR图像：24/24
- 首错点：步骤 24/24，类型 24/24
- Agent分支：12/12
- 可视化：16/16
- Live E2E：6/6
- 页面：60/60，占位 0，异常 0
- 语音：faster-whisper small + edge-tts 真实文件
- 角色数据：家长 5 名学生，教师班级 5 人
- 自动化测试：后端 pytest 12/12，前端 Vitest 3/3，Playwright 核心用例 2/2，TypeScript、Ruff、mypy、生产构建均通过

## 实际补齐的功能

- 双流图像证据：原图保留、校正、红笔掩码、清洁图、原图/清洁图 PaddleOCR 与 Qwen 多模态融合、局部重识别和人工确认。
- 首错点与教学：参考路径、SymPy 校验、学生路径逐步对齐、根因/传播证据、12 类 Agent 分支、教回、近迁移、远迁移和复习计划。
- 认知与交互：65 张知识卡、62 条关系、认知错因图、16 类白名单可视化及交互证据落库。
- 完整应用：30 个真实功能页面、组卷编辑、题目/答案 PDF、Excel、Whisper 转写、edge-tts、家长 5 学生和教师 5 人班级聚合。

## 模型、数据库与固定验收数据

- 实际模型：Qwen3.6-35B-A3B；逻辑模型固定为 `Qwen3.6-35B-A3B`。
- API 池当前启用 13 条 CSU 条目，当前文本可用 7 条、图片可用 6 条；非 CSU 条目禁用且运行时白名单拒绝。
- MySQL 共 37 张表（36 张业务表 + Alembic），核心孤儿记录 0。
- 固定数据：24 张图（数学16/物理5/历史3；清晰/批注/退化各8）、24 个诊断、12 个 Agent 分支、6 个完整 E2E。

## 本轮发现与修复

- 前端Router遗漏RouteRecordRaw类型导入，修复后TypeScript通过。
- 诊断合成案例最初类型命中16/24，修正案例表达后达到24/24。
- 模型生成的畸形方程先后触发SyntaxError和SymPy内部IndexError，数学解析层统一按不可验证处理并回退验证模板。
- Whisper模型首次下载受代理连接阻塞，释放旧进程、Range续传并校验官方SHA-256后恢复。

## 导出文件

- question: `/root/Baxxhy/zhiwei/reports/3818621d-cfa7-4f8b-824d-5079d3a84dee-question.pdf` (36198 bytes)
- answer: `/root/Baxxhy/zhiwei/reports/3818621d-cfa7-4f8b-824d-5079d3a84dee-answer.pdf` (36509 bytes)
- excel: `/root/Baxxhy/zhiwei/reports/3818621d-cfa7-4f8b-824d-5079d3a84dee-excel.xlsx` (5103 bytes)

## 启动与账号

- 启动：`make mysql migrate seed`，然后 `make dev`
- 学生：`student@minddimension.local`
- 家长：`guardian@minddimension.local`
- 教师：`teacher@minddimension.local`
- 管理员：`admin@minddimension.local`
- 前端：http://127.0.0.1:5173
- 后端：http://127.0.0.1:8000
- API文档：http://127.0.0.1:8000/docs

## 尚未完成

无核心功能缺口。未执行论文实验、性能压测和生产级鉴权，符合本地功能版范围。

## 完成度矩阵

| 范围 | 结论 | 运行证据 |
|---|---|---|
| OCR 与双流融合 | COMPLETE | PaddleOCR 24/24，原图哈希保持，五类来源落库 |
| 首错点诊断 | COMPLETE | 步骤 24/24、类型 24/24 |
| 教学 Agent 与认知更新 | COMPLETE | 12/12 分支，运行/工具/复习记录写入 MySQL |
| 可视化与知识库 | COMPLETE | 16/16 渲染交互，65 卡/62 关系 |
| 语音、组卷与导出 | COMPLETE | Whisper、TTS、题目 PDF、答案 PDF、Excel 均生成 |
| 家长、教师与 30 页面 | COMPLETE | 5 名学生聚合，60/60 双视口，无占位和页面错误 |
| 多学科端到端 | COMPLETE | 6/6：数学3、物理2、历史1 |
| 未完成 | 无核心缺口 | 仅排除范围内的性能与生产安全工程 |
