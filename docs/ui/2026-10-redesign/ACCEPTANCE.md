# 本轮验收清单

当前状态：执行中。所有最终数量与结论须在完整验收结束后更新。

| 要求 | 权威证据 | 当前状态 |
| --- | --- | --- |
| 技能发现与选择 | WORKLOG中的实际技能入口、未安装项与查询取舍 | 已完成 |
| 当前页面与数据关系 | pages.csv、CONTENT_MODEL.md、实际pages.json | 48路由已登记 |
| 可核验竞品与用户场景研究 | WORKLOG中的官方来源与平台访问边界 | 已完成；无虚构访谈 |
| 导航、视觉规范与产品文案 | NAVIGATION.md、SITEMAP.mmd、docs/final/UI_SPEC.md、frontend/src | 已实施，最终浏览器复查中 |
| 今日、详情、订正及AI讲解 | 实际Qwen/MySQL固定样本报告；learning-tasks/task-entry/recovery等浏览器用例 | 真实固定样本通过，完整回归中 |
| 全部学生、教师、家长、管理页面 | redesign-acceptance.spec.ts动态读取48路由，手机/桌面各一轮 | 待最终通过 |
| 拍照/OCR/手动录题与原图保留 | new-user/recovery浏览器用例及仓颉ingest回归 | 完整回归中 |
| 题库、考试、变式与复习 | bank-study/review-queue/review-origin/review-recovery/functional-audit | 完整回归中 |
| 等价答案与提交、草稿不串题 | 真实0.5与1/2提交；SymPy/Pydantic算法测试；双设备与丢回执用例 | 固定样本通过，完整回归中 |
| 手机/桌面、200%文字、错误/空/等待状态 | account-access/functional-audit/redesign-acceptance及人工截图 | 完整回归中 |
| 架构与数据不退化 | 仓颉/MySQL业务，Python内部算法，Qwen/ApiPoolProvider；无新SQLite/生成JS执行 | 已保留；完整回归中 |
| 工程检查 | make verify-final；兼容pytest backend/tests；Ruff | 单项已通过，主线最终结果待确认 |
| Git与交付 | git log、git status --short、最终记录与截图 | 待完成 |

测试层次：完整隔离回归使用真实仓颉、MySQL、算法模块及受控计算夹具，部分既有浏览器用例显式拦截响应以验证失败恢复；新48路由用例不拦截API，但参考分析是明确的隔离种子。真实Qwen另用当前应用配置与独立学生核验，结果不与替身混计。
