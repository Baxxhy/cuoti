# 103 条接口的实际用途审计

按现有页面、动态请求、响应中的资源 URL、脚本调用及接口行为逐条检查。没有页面入口不等于没有能力；测试引用不计为产品实际调用。未使用的别名、空操作及废弃入口已删除。

不做运维或部署，不新增页面凑接口使用量。学生学习与作业下发、作答、判题、反馈所需接口保留。仓颉接口迁移状态：69/69 verified；实现和验证入口见 routes.json，验收范围见 FINAL_ACCEPTANCE.md。

原清单 103 条，删除 34 条，保留 69 条。分类：`{'existing_support': 1, 'independent_api': 9, 'removed': 34, 'returned_media': 1, 'script_workflow': 5, 'ui': 53}`。

| 方法 | 路径 | 分类 | 实际用途/处理 | 页面调用证据 |
|---|---|---|---|---|
| POST | `/api/v1/auth/register` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/store/index.js:29 |
| POST | `/api/v1/auth/login` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/store/index.js:22 |
| POST | `/api/v1/auth/reset-password` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/forgot/forgot.vue:86 |
| GET | `/api/v1/auth/me` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/review/review.vue:542、frontend/src/store/index.js:36、frontend/src/utils/task-entry.js:11 |
| PATCH | `/api/v1/auth/me` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/profile/edit.vue:142 |
| GET | `/api/v1/system/health` | existing_support | 既有检查脚本依赖；本轮不做运维、不扩展或部署该能力。 |  |
| GET | `/api/v1/system/providers` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/system/system.vue:108 |
| POST | `/api/v1/system/providers/probe` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/system/system.vue:117 |
| GET | `/api/v1/system/voice` | independent_api | 独立语音验收脚本查询能力状态；学生页面未接语音，不算页面已使用。 |  |
| GET | `/api/v1/admin/workbench` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/admin/workbench.vue:730 |
| GET | `/api/v1/admin/students/{student_id}` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/admin/workbench.vue:741 |
| GET | `/api/v1/admin/sessions/{session_id}` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/admin/workbench.vue:750 |
| GET | `/api/v1/dashboard` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/index/index.vue:376、frontend/src/pages/manual/manual.vue:182、frontend/src/pages/profile/profile.vue:133、frontend/src/pages/review/review.vue:684、frontend/src/store/index.js:51 |
| POST | `/api/v1/questions/ingest` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/capture/capture.vue:112 |
| GET | `/api/v1/questions` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/problem/list.vue:368、frontend/src/utils/learning.js:82 |
| GET | `/api/v1/questions/{question_id}` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/crop/crop.vue:211、frontend/src/pages/crop/crop.vue:244、frontend/src/pages/crop/crop.vue:261、frontend/src/pages/detail/detail.vue:455、frontend/src/pages/diagnosis/diagnosis.vue:951、frontend/src/pages/knowledge/knowledge.vue:195、frontend/src/pages/ocr/ocr.vue:326、frontend/src/pages/ocr/ocr.vue:364、frontend/src/pages/repair/repair.vue:148、frontend/src/pages/replay/replay.vue:220 |
| PATCH | `/api/v1/questions/{question_id}` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/detail/detail.vue:522 |
| POST | `/api/v1/questions/{question_id}/crop` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/crop/crop.vue:233 |
| DELETE | `/api/v1/questions/{question_id}` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/detail/detail.vue:559 |
| POST | `/api/v1/questions/{question_id}/draft` | independent_api | 保存未确认内容；有功能测试，当前页面直接 confirm，不宣称页面自动保存。 |  |
| POST | `/api/v1/questions/{question_id}/confirm` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/ocr/ocr.vue:447、frontend/src/pages/ocr/ocr.vue:462 |
| POST | `/api/v1/questions/{question_id}/ocr` | independent_api | 同步识别工具入口；当前页面使用异步 crop/reprocess，独立脚本仍调用。 |  |
| POST | `/api/v1/questions/{question_id}/reprocess` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/detail/detail.vue:543 |
| POST | `/api/v1/questions/{question_id}/analyze` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/diagnosis/diagnosis.vue:980、frontend/src/pages/ocr/ocr.vue:463、frontend/src/pages/paper/paper-center.vue:522 |
| POST | `/api/v1/questions/{question_id}/student-work` | independent_api | 独立追加作答版本、步骤并使旧结果失效；用于功能验证，当前页面走 confirm。 |  |
| POST | `/api/v1/questions/{question_id}/diagnose` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/diagnosis/diagnosis.vue:982、frontend/src/pages/ocr/ocr.vue:464 |
| POST | `/api/v1/questions/{question_id}/diagnosis/counterfactual` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/diagnosis/diagnosis.vue:957 |
| GET | `/api/v1/questions/{question_id}/diagnosis` | independent_api | 单独读取诊断证据；当前页面从题目详情聚合读取，独立返回契约仍有验证。 |  |
| PATCH | `/api/v1/questions/{question_id}/diagnosis` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/diagnosis/diagnosis.vue:1063 |
| GET | `/api/v1/jobs/{job_id}` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/crop/crop.vue:249、frontend/src/pages/ocr/ocr.vue:355 |
| POST | `/api/v1/jobs/{job_id}/retry` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/ocr/ocr.vue:341 |
| POST | `/api/v1/answers/handwriting` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/practice/practice.vue:99、frontend/src/pages/review/review.vue:138、frontend/src/pages/tutor/tutor.vue:384 |
| POST | `/api/v1/tutor/sessions/{session_id}/activity/answer` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/tutor/tutor.vue:787 |
| POST | `/api/v1/tutor/sessions` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/detail/detail.vue:509、frontend/src/pages/library/library.vue:215 |
| GET | `/api/v1/tutor/sessions/{session_id}` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/tutor/tutor.vue:774 |
| POST | `/api/v1/tutor/sessions/{session_id}/turns` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/tutor/tutor.vue:882 |
| POST | `/api/v1/tutor/sessions/{session_id}/advance` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/tutor/tutor.vue:855 |
| POST | `/api/v1/tutor/sessions/{session_id}/rewind` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/tutor/tutor.vue:867 |
| POST | `/api/v1/tutor/sessions/{session_id}/teach-back` | script_workflow | functional_flow.py、verify_agent_branches.py 的分步教学脚本仍调用；学生页面走 activity/answer。 |  |
| GET | `/api/v1/tutor/sessions/{session_id}/visualization` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/visualization/visualization.vue:99 |
| POST | `/api/v1/tutor/sessions/{session_id}/visualization` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/visualization/visualization.vue:111 |
| GET | `/api/v1/visualizations/types` | independent_api | 可视化验收脚本读取类型目录，页面未调用，不计为页面必需。 |  |
| GET | `/api/v1/visualizations/{visualization_id}` | independent_api | 独立按 ID 读取图形规范；页面使用会话可视化接口，脚本验证此独立能力。 |  |
| POST | `/api/v1/tutor/sessions/{session_id}/variant` | script_workflow | 脚本分步生成练习；页面会话读取与作答路径自动补题，不能把内部生成函数调用算成直接调用此 HTTP 路由。 |  |
| POST | `/api/v1/variants/{variant_id}/attempt` | script_workflow | 分步教学脚本提交练习并写入认知证据；页面走 activity/answer。 |  |
| POST | `/api/v1/tutor/sessions/{session_id}/finish` | script_workflow | functional_flow.py、smoke_demo.py 结束教学；页面由活动流程自动结束。 |  |
| GET | `/api/v1/reviews/today` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/repair/repair.vue:154、frontend/src/pages/review/review.vue:543、frontend/src/pages/review/review.vue:779 |
| POST | `/api/v1/reviews/{plan_id}/attempt` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/review/review.vue:764 |
| POST | `/api/v1/reviews/{plan_id}/grade` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/review/review.vue:829 |
| GET | `/api/v1/reviews/history` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/review/review.vue:681、frontend/src/pages/review/review.vue:835 |
| GET | `/api/v1/knowledge/cards` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/library/library.vue:179 |
| GET | `/api/v1/knowledge/cards/{code}` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/library/library.vue:193 |
| GET | `/api/v1/analytics/overview` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/analysis/analysis.vue:261 |
| GET | `/api/v1/analytics/cognition-graph` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/analysis/analysis.vue:281 |
| POST | `/api/v1/papers` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/paper/paper-center.vue:418 |
| GET | `/api/v1/papers/candidates` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/paper/paper-center.vue:391 |
| GET | `/api/v1/papers` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/paper/paper-center.vue:373、frontend/src/pages/paper/paper-center.vue:425、frontend/src/pages/paper/paper-center.vue:466 |
| GET | `/api/v1/papers/{paper_id}` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/paper/paper-center.vue:438、frontend/src/pages/paper/paper-center.vue:529、frontend/src/pages/paper/paper-center.vue:551 |
| PATCH | `/api/v1/papers/{paper_id}` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/paper/paper-center.vue:459 |
| DELETE | `/api/v1/papers/{paper_id}` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/paper/paper-center.vue:495 |
| POST | `/api/v1/papers/{paper_id}/export` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/paper/paper-center.vue:536 |
| GET | `/api/v1/papers/{paper_id}/download` | script_workflow | 试卷验收脚本按 kind 下载最新导出；页面实际消费 exports[].url 中的 /reports 签名链接，不调用此接口。 |  |
| POST | `/api/v1/voice/transcribe` | independent_api | 语音验收脚本使用的独立专业能力；当前学生页面没有语音入口。保留算法，不追加页面。 |  |
| POST | `/api/v1/voice/synthesize` | independent_api | 语音验收脚本使用的独立专业能力；当前学生页面没有语音入口。保留算法，不追加页面。 |  |
| POST | `/api/v1/practice/recommend` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/practice/practice.vue:309 |
| GET | `/api/v1/practice/questions/{question_id}/images/{image_index}` | returned_media | 练习推荐响应产生签名图片 URL，练习页面 image 消费；属于必要资源接口。 |  |
| POST | `/api/v1/practice/attempt` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/practice/practice.vue:353 |
| POST | `/api/v1/questions/manual` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/manual/manual.vue:162、frontend/src/pages/study-session/study-session.vue:554 |
| GET | `/api/v1/questions/{question_id}/journey` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/detail/detail.vue:456、frontend/src/pages/journey/journey.vue:170、frontend/src/pages/repair/repair.vue:149 |
| POST | `/api/v1/auth/refresh` | removed | 无人调用的 local_mode 空操作；不会续期令牌，重新登录仍走 login。 |  |
| POST | `/api/v1/auth/logout` | removed | 无人调用的 local_mode 空操作；学生端 store.logout 已清除本地令牌，不做服务端撤销。 |  |
| GET | `/api/v1/system/readiness` | removed | 无页面或检查脚本调用；重复拼装 provider.health_check，已有 providers 规范入口。 |  |
| GET | `/api/v1/system/models` | removed | 无调用的 providers 别名；系统页面实际调用 providers。 |  |
| GET | `/api/v1/system/features` | removed | 无人消费的固定 true 清单，不能证明实际可用，删除。 |  |
| POST | `/api/v1/tutor/sessions/{session_id}/understanding-check` | removed | 旧理解检查入口没有页面或脚本调用，当前活动作答由 activity/answer 承担。 |  |
| GET | `/api/v1/analytics/knowledge-points` | removed | 与 overview 完全相同的响应；学习统计页面只使用 overview。 |  |
| GET | `/api/v1/analytics/misconceptions` | removed | 与 overview 完全相同的响应；学习统计页面只使用 overview。 |  |
| GET | `/api/v1/analytics/study-trend` | removed | 与 overview 完全相同的响应；学习统计页面只使用 overview。 |  |
| GET | `/api/v1/guardians/students` | removed | 学生个人使用版移除教师与家长协作 |  |
| GET | `/api/v1/guardians/students/{student_id}/overview` | removed | 学生个人使用版移除教师与家长协作 |  |
| GET | `/api/v1/teachers/students/{student_id}/report` | removed | 学生个人使用版移除教师与家长协作 |  |
| GET | `/api/v1/teachers/classes` | removed | 学生个人使用版移除教师与家长协作 |  |
| GET | `/api/v1/teachers/classes/{class_id}` | removed | 学生个人使用版移除教师与家长协作 |  |
| GET | `/api/v1/teachers/dashboard` | removed | 学生个人使用版移除教师与家长协作 |  |
| POST | `/api/v1/teachers/classes` | removed | 学生个人使用版移除教师与家长协作 |  |
| POST | `/api/v1/teachers/classes/{class_id}/students` | removed | 学生个人使用版移除教师与家长协作 |  |
| DELETE | `/api/v1/teachers/classes/{class_id}/students/{student_id}` | removed | 学生个人使用版移除教师与家长协作 |  |
| GET | `/api/v1/teachers/reviews` | removed | 学生个人使用版移除教师与家长协作 |  |
| GET | `/api/v1/teachers/reviews/{task_id}` | removed | 学生个人使用版移除教师与家长协作 |  |
| POST | `/api/v1/teachers/reviews/{task_id}/decision` | removed | 学生个人使用版移除教师与家长协作 |  |
| POST | `/api/v1/teachers/reviews/{task_id}/revoke` | removed | 学生个人使用版移除教师与家长协作 |  |
| POST | `/api/v1/teachers/reviews/{task_id}/regrade` | removed | 学生个人使用版移除教师与家长协作 |  |
| POST | `/api/v1/teachers/reviews/{task_id}/transfer` | removed | 学生个人使用版移除教师与家长协作 |  |
| GET | `/api/v1/teachers/questions` | removed | 学生个人使用版移除教师与家长协作 |  |
| POST | `/api/v1/teachers/questions` | removed | 学生个人使用版移除教师与家长协作 |  |
| POST | `/api/v1/teachers/assignments` | removed | 学生个人使用版移除教师与家长协作 |  |
| GET | `/api/v1/teachers/assignments` | removed | 学生个人使用版移除教师与家长协作 |  |
| GET | `/api/v1/students/assignments` | removed | 学生个人使用版移除教师与家长协作 |  |
| POST | `/api/v1/students/assignments/{student_assignment_id}/attempts` | removed | 学生个人使用版移除教师与家长协作 |  |
| GET | `/api/v1/students/teacher-feedback` | removed | 学生个人使用版移除教师与家长协作 |  |
| GET | `/api/v1/teachers/students/{student_id}/plans` | removed | 学生个人使用版移除教师与家长协作 |  |
| PATCH | `/api/v1/teachers/plans/{plan_id}` | removed | 学生个人使用版移除教师与家长协作 |  |
| GET | `/api/v1/teachers/audit-logs` | removed | 学生个人使用版移除教师与家长协作 |  |
