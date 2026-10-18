# 30 页面最终审计

Playwright 使用 390×844 与 1440×1000 两个视口，以本轮创建的真实题目、会话、学生和班级 ID 逐路由访问。最终截图位于 `reports/page-audit/final/{mobile,desktop}`。

| # | 路由 | 功能结论 | 状态 |
|---:|---|---|---|
| 1 | `/` | 启动与本地入口 | COMPLETE |
| 2 | `/login` | 邮箱本地登录 | COMPLETE |
| 3 | `/register` | 创建用户和学生档案 | COMPLETE |
| 4 | `/forgot-password` | 本地模式账号找回说明与登录入口 | COMPLETE |
| 5 | `/dashboard` | MySQL 首页聚合与最近学习 | COMPLETE |
| 6 | `/upload` | 图片上传和任务创建 | COMPLETE |
| 7 | `/crop/:id` | 裁剪预览与派生资源保存 | COMPLETE |
| 8 | `/questions/:id` | 原图、派生图、题目与学习记录 | COMPLETE |
| 9 | `/questions/:id/ocr` | 双流 OCR 字段、框、步骤与批注确认 | COMPLETE |
| 10 | `/questions/:id/diagnosis` | 参考/学生路径对齐、首错与传播证据 | COMPLETE |
| 11 | `/tutor/:id` | 多轮教学、状态恢复和策略分支 | COMPLETE |
| 12 | `/visualization/:id` | 16 类可视化切换、交互与保存 | COMPLETE |
| 13 | `/teach-back/:id` | 教回问题、评分与重试 | COMPLETE |
| 14 | `/near-transfer/:id` | 近迁移生成与作答 | COMPLETE |
| 15 | `/far-transfer/:id` | 远迁移生成与作答 | COMPLETE |
| 16 | `/reviews` | 今日复习、评分和历史 | COMPLETE |
| 17 | `/collection` | 错题列表、筛选与操作 | COMPLETE |
| 18 | `/search` | 关键词、学科和知识点搜索 | COMPLETE |
| 19 | `/analytics` | 掌握、错因和趋势分析 | COMPLETE |
| 20 | `/cognition-graph` | 跨题知识/错因/证据图 | COMPLETE |
| 21 | `/papers` | 选题、分值、排序、删除和历史 | COMPLETE |
| 22 | `/papers/export` | 题目 PDF、答案 PDF、Excel 导出 | COMPLETE |
| 23 | `/voice` | 录音、转写、合成与浏览器回退 | COMPLETE |
| 24 | `/profile` | 档案和四角色视角切换 | COMPLETE |
| 25 | `/guardian` | 5 名关联学生概览 | COMPLETE |
| 26 | `/guardian/students/:id` | 单学生真实学习报告 | COMPLETE |
| 27 | `/teacher/classes` | 班级 5 人聚合与错因分布 | COMPLETE |
| 28 | `/teacher/students/:id` | 教师单学生报告 | COMPLETE |
| 29 | `/system` | MySQL、OCR、语音和功能健康 | COMPLETE |
| 30 | `/providers` | 模型、可用条目、索引和最近轮询 | COMPLETE |

最终统计：30 个路由、60 次加载全部成功，明显占位命中 0，未处理页面错误 0。16 类可视化另有逐类型浏览器交互截图和像素变化验证。
