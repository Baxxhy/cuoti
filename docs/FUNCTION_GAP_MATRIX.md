> 历史快照：以下结论仅对应原文标注的验证日期，不代表 2026-10-13 当前版本。当前修复与验证请参见 [参赛完善说明](competition/2026-10-13-参赛完善说明.md)。

# 最终功能完成矩阵

`COMPLETE` 表示已有真实前端操作、后端接口、MySQL 持久化和运行证据。

| 功能 | 前端 | 后端接口/服务 | MySQL 表 | 状态 | 验收结果 |
|---|---|---|---|---|---|
| 账号密码登录、固定角色 | Login/Register/Profile | `/auth/*` | users, student_profiles | COMPLETE | 四类账号分别登录，个人中心不能切换身份 |
| 首页、错题本、搜索、分析 | Dashboard/Collection/Analytics | `/dashboard`, `/questions`, `/analytics/*` | questions, mastery_states, review_plans | COMPLETE | 全部来自 MySQL 聚合 |
| 上传、裁剪、图像派生 | Upload/Crop/Question | `/questions/ingest`, `/questions/{id}/crop` | questions, question_assets, processing_jobs | COMPLETE | 24 图原图保留、清洁/掩码/叠加生成 |
| Qwen 多模态图像识别 | OCRConfirm | `/questions/{id}/ocr` | ocr_runs, question_assets | COMPLETE | 裁剪图结构化识别、视觉区域落库与红色批注像素校验 |
| OCR 人工确认 | OCRConfirm | `/questions/{id}/confirm` | student_works, student_steps, teacher_marks | COMPLETE | 题干、公式、步骤、批注可改并持久化 |
| 参考路径与首错点 | Diagnosis | `/questions/{id}/analysis`, `/diagnosis` | analyses, reference_steps, diagnoses, evidence | COMPLETE | 首错步骤和类型 24/24 |
| 教学 Agent 与教回 | Tutor/TeachBack | `/tutor/sessions/*` | tutor_sessions, turns, agent_runs, tool_calls | COMPLETE | 12 分支全部通过并留审计轨迹 |
| 近迁移、远迁移 | Near/FarTransfer | `/tutor/sessions/{id}/variant`, `/variants/*` | variant_questions, variant_attempts | COMPLETE | 两类生成、校验、作答闭环 |
| 认知孪生与复习 | Analytics/Reviews | `/analytics/*`, `/reviews/*` | mastery, misconception, cognitive_updates, review_* | COMPLETE | 跨题证据、评分和间隔原因落库 |
| 知识库与认知错因图 | CognitionGraph | `/knowledge/*`, `/analytics/cognition-graph` | knowledge_points, knowledge_relations | COMPLETE | 65 卡、62 关系、图交互 |
| 16 类受控可视化 | Visualization | `/visualizations/*` | visualization_specs, interactions | COMPLETE | Pydantic + Zod 白名单，16/16 Canvas 渲染 |
| 语音 | Voice | `/voice/transcribe`, `/voice/synthesize` | voice_records | COMPLETE | Whisper small 和 edge-tts 真实文件 |
| 组卷与导出 | Paper/Export | `/papers/*`, `/exports/*` | papers, paper_items, export_jobs | COMPLETE | 筛选、分值、排序、删除、双 PDF、Excel |
| 家长与教师端 | Guardian/Teacher | `/guardians/*`, `/teachers/*` | guardian links, teacher classes/students | COMPLETE | 家长 5 学生、教师班级 5 人真实聚合 |
| 系统状态和池轮询 | System/Providers | `/system/*` | 调用状态由 Provider 管理 | COMPLETE | 仅启用 13 个 CSU Qwen 条目；非 CSU 禁用并由主机白名单拒绝 |
| 30 页面 | 18 个独立页面组件 | 对应真实 API | 对应业务表 | COMPLETE | 60/60 双视口，无占位和未处理错误 |
| 固定验收数据与脚本 | `data/functional_validation` | `scripts/verify_*` | 验收链写入全部业务表 | COMPLETE | 24 图、24 诊断、12 分支、6 E2E、三轮通过 |

## 未完成

无核心功能缺口。性能压测、生产级鉴权与安全审计按本地功能版范围明确不做。
