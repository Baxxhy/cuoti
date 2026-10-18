# 103 条接口的实际用途审计

按现有页面、动态请求、响应中的资源 URL、脚本调用及接口行为逐条检查。没有页面入口不等于没有能力；测试引用不计为产品实际调用。未使用的别名、空操作及废弃入口已删除。

不做运维或部署，不新增页面凑接口使用量。学生学习与作业下发、作答、判题、反馈所需接口保留。仓颉接口迁移状态：94/94 verified；实现和验证入口见 routes.json，验收范围见 FINAL_ACCEPTANCE.md。

原清单 103 条，删除 9 条，保留 94 条。分类：`{'existing_support': 1, 'independent_api': 15, 'removed': 9, 'returned_media': 1, 'script_workflow': 5, 'ui': 72}`。

| 方法 | 路径 | 分类 | 实际用途/处理 | 页面调用证据 |
|---|---|---|---|---|
| POST | `/api/v1/auth/register` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/store/index.js:31 |
| POST | `/api/v1/auth/login` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/store/index.js:24 |
| POST | `/api/v1/auth/reset-password` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/forgot/forgot.vue:87 |
| GET | `/api/v1/auth/me` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/review/review.vue:518、frontend/src/store/index.js:38、frontend/src/utils/task-entry.js:11 |
| PATCH | `/api/v1/auth/me` | independent_api | 账号改名能力；当前资料页没有编辑入口，不属于学生主页面必需接口。 |  |
| GET | `/api/v1/system/health` | existing_support | 既有检查脚本依赖；本轮不做运维、不扩展或部署该能力。 |  |
| GET | `/api/v1/system/providers` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/system/system.vue:105 |
| POST | `/api/v1/system/providers/probe` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/system/system.vue:114 |
| GET | `/api/v1/system/voice` | independent_api | 独立语音验收脚本查询能力状态；学生页面未接语音，不算页面已使用。 |  |
| GET | `/api/v1/admin/workbench` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/admin/workbench.vue:656 |
| GET | `/api/v1/admin/students/{student_id}` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/admin/workbench.vue:667 |
| GET | `/api/v1/admin/sessions/{session_id}` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/admin/workbench.vue:676 |
| GET | `/api/v1/dashboard` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/index/index.vue:413、frontend/src/pages/manual/manual.vue:159、frontend/src/pages/profile/profile.vue:124、frontend/src/pages/review/review.vue:660、frontend/src/store/index.js:53 |
| POST | `/api/v1/questions/ingest` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/capture/capture.vue:104 |
| GET | `/api/v1/questions` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/problem/list.vue:355、frontend/src/utils/learning.js:82 |
| GET | `/api/v1/questions/{question_id}` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/crop/crop.vue:203、frontend/src/pages/crop/crop.vue:236、frontend/src/pages/crop/crop.vue:253、frontend/src/pages/detail/detail.vue:406、frontend/src/pages/diagnosis/diagnosis.vue:895、frontend/src/pages/knowledge/knowledge.vue:170、frontend/src/pages/ocr/ocr.vue:314、frontend/src/pages/ocr/ocr.vue:352、frontend/src/pages/repair/repair.vue:136、frontend/src/pages/replay/replay.vue:217 |
| PATCH | `/api/v1/questions/{question_id}` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/detail/detail.vue:473 |
| POST | `/api/v1/questions/{question_id}/crop` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/crop/crop.vue:225 |
| DELETE | `/api/v1/questions/{question_id}` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/detail/detail.vue:510 |
| POST | `/api/v1/questions/{question_id}/draft` | independent_api | 保存未确认内容；有功能测试，当前页面直接 confirm，不宣称页面自动保存。 |  |
| POST | `/api/v1/questions/{question_id}/confirm` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/ocr/ocr.vue:435、frontend/src/pages/ocr/ocr.vue:450 |
| POST | `/api/v1/questions/{question_id}/ocr` | independent_api | 同步识别工具入口；当前页面使用异步 crop/reprocess，独立脚本仍调用。 |  |
| POST | `/api/v1/questions/{question_id}/reprocess` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/detail/detail.vue:494 |
| POST | `/api/v1/questions/{question_id}/analyze` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/diagnosis/diagnosis.vue:924、frontend/src/pages/ocr/ocr.vue:451 |
| POST | `/api/v1/questions/{question_id}/student-work` | independent_api | 独立追加作答版本、步骤并使旧结果失效；用于功能验证，当前页面走 confirm。 |  |
| POST | `/api/v1/questions/{question_id}/diagnose` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/diagnosis/diagnosis.vue:926、frontend/src/pages/ocr/ocr.vue:452 |
| POST | `/api/v1/questions/{question_id}/diagnosis/counterfactual` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/diagnosis/diagnosis.vue:901 |
| GET | `/api/v1/questions/{question_id}/diagnosis` | independent_api | 单独读取诊断证据；当前页面从题目详情聚合读取，独立返回契约仍有验证。 |  |
| PATCH | `/api/v1/questions/{question_id}/diagnosis` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/diagnosis/diagnosis.vue:1007 |
| GET | `/api/v1/jobs/{job_id}` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/crop/crop.vue:241、frontend/src/pages/ocr/ocr.vue:343 |
| POST | `/api/v1/jobs/{job_id}/retry` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/ocr/ocr.vue:329 |
| POST | `/api/v1/answers/handwriting` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/assignment/assignment.vue:53、frontend/src/pages/practice/practice.vue:80、frontend/src/pages/review/review.vue:131、frontend/src/pages/tutor/tutor.vue:371 |
| POST | `/api/v1/tutor/sessions/{session_id}/activity/answer` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/tutor/tutor.vue:699 |
| POST | `/api/v1/tutor/sessions` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/detail/detail.vue:460 |
| GET | `/api/v1/tutor/sessions/{session_id}` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/tutor/tutor.vue:686 |
| POST | `/api/v1/tutor/sessions/{session_id}/turns` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/tutor/tutor.vue:794 |
| POST | `/api/v1/tutor/sessions/{session_id}/advance` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/tutor/tutor.vue:767 |
| POST | `/api/v1/tutor/sessions/{session_id}/rewind` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/tutor/tutor.vue:779 |
| POST | `/api/v1/tutor/sessions/{session_id}/teach-back` | script_workflow | functional_flow.py、verify_agent_branches.py 的分步教学脚本仍调用；学生页面走 activity/answer。 |  |
| GET | `/api/v1/tutor/sessions/{session_id}/visualization` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/visualization/visualization.vue:74 |
| POST | `/api/v1/tutor/sessions/{session_id}/visualization` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/visualization/visualization.vue:86 |
| GET | `/api/v1/visualizations/types` | independent_api | 可视化验收脚本读取类型目录，页面未调用，不计为页面必需。 |  |
| GET | `/api/v1/visualizations/{visualization_id}` | independent_api | 独立按 ID 读取图形规范；页面使用会话可视化接口，脚本验证此独立能力。 |  |
| POST | `/api/v1/tutor/sessions/{session_id}/variant` | script_workflow | 脚本分步生成练习；页面会话读取与作答路径自动补题，不能把内部生成函数调用算成直接调用此 HTTP 路由。 |  |
| POST | `/api/v1/variants/{variant_id}/attempt` | script_workflow | 分步教学脚本提交练习并写入认知证据；页面走 activity/answer。 |  |
| POST | `/api/v1/tutor/sessions/{session_id}/finish` | script_workflow | functional_flow.py、smoke_demo.py 结束教学；页面由活动流程自动结束。 |  |
| GET | `/api/v1/reviews/today` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/repair/repair.vue:142、frontend/src/pages/review/review.vue:519、frontend/src/pages/review/review.vue:755 |
| POST | `/api/v1/reviews/{plan_id}/attempt` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/review/review.vue:740 |
| POST | `/api/v1/reviews/{plan_id}/grade` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/review/review.vue:805 |
| GET | `/api/v1/reviews/history` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/review/review.vue:657、frontend/src/pages/review/review.vue:811 |
| GET | `/api/v1/knowledge/cards` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/library/library.vue:131 |
| GET | `/api/v1/knowledge/cards/{code}` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/library/library.vue:145 |
| GET | `/api/v1/analytics/overview` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/analysis/analysis.vue:276 |
| GET | `/api/v1/analytics/cognition-graph` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/analysis/analysis.vue:301 |
| POST | `/api/v1/papers` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/paper/paper-center.vue:348 |
| GET | `/api/v1/papers/candidates` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/paper/paper-center.vue:321 |
| GET | `/api/v1/papers` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/paper/paper-center.vue:303、frontend/src/pages/paper/paper-center.vue:355、frontend/src/pages/paper/paper-center.vue:396 |
| GET | `/api/v1/papers/{paper_id}` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/paper/paper-center.vue:368、frontend/src/pages/paper/paper-center.vue:457 |
| PATCH | `/api/v1/papers/{paper_id}` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/paper/paper-center.vue:389 |
| DELETE | `/api/v1/papers/{paper_id}` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/paper/paper-center.vue:425 |
| POST | `/api/v1/papers/{paper_id}/export` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/paper/paper-center.vue:443 |
| GET | `/api/v1/papers/{paper_id}/download` | script_workflow | 试卷验收脚本按 kind 下载最新导出；页面实际消费 exports[].url 中的 /reports 签名链接，不调用此接口。 |  |
| POST | `/api/v1/voice/transcribe` | independent_api | 语音验收脚本使用的独立专业能力；当前学生页面没有语音入口。保留算法，不追加页面。 |  |
| POST | `/api/v1/voice/synthesize` | independent_api | 语音验收脚本使用的独立专业能力；当前学生页面没有语音入口。保留算法，不追加页面。 |  |
| GET | `/api/v1/guardians/students` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/guardian/home.vue:68 |
| GET | `/api/v1/guardians/students/{student_id}/overview` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/guardian/report.vue:37 |
| GET | `/api/v1/teachers/students/{student_id}/report` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/teacher/student.vue:112 |
| GET | `/api/v1/teachers/classes` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/teacher/assignment.vue:113、frontend/src/pages/teacher/classes.vue:60 |
| GET | `/api/v1/teachers/classes/{class_id}` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/teacher/class-detail.vue:62 |
| POST | `/api/v1/practice/recommend` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/practice/practice.vue:199 |
| GET | `/api/v1/practice/questions/{question_id}/images/{image_index}` | returned_media | 练习推荐响应产生签名图片 URL，练习页面 image 消费；属于必要资源接口。 |  |
| POST | `/api/v1/practice/attempt` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/practice/practice.vue:217 |
| GET | `/api/v1/teachers/dashboard` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/teacher/dashboard.vue:102 |
| POST | `/api/v1/teachers/classes` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/teacher/classes.vue:65 |
| POST | `/api/v1/teachers/classes/{class_id}/students` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/teacher/class-detail.vue:67 |
| DELETE | `/api/v1/teachers/classes/{class_id}/students/{student_id}` | independent_api | 教师移除成员并撤销班级报告/计划权限，有 HTTP 验证；当前班级页面只提供添加入口。 |  |
| GET | `/api/v1/teachers/reviews` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/teacher/reviews.vue:85 |
| GET | `/api/v1/teachers/reviews/{task_id}` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/teacher/review-detail.vue:183 |
| POST | `/api/v1/teachers/reviews/{task_id}/decision` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/teacher/review-detail.vue:200 |
| POST | `/api/v1/teachers/reviews/{task_id}/revoke` | independent_api | 教师撤销已发布复核及其学习效果，有独立语义；当前页面未放撤销按钮，不等同 decision。 |  |
| POST | `/api/v1/teachers/reviews/{task_id}/regrade` | independent_api | 教师重新判定既有复核，有独立语义；当前页面未提供按钮，不等同首次 decision。 |  |
| POST | `/api/v1/teachers/reviews/{task_id}/transfer` | independent_api | 教师转交复核任务，有独立权限与审计语义；当前页面未提供按钮。 |  |
| GET | `/api/v1/teachers/questions` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/teacher/assignment.vue:114、frontend/src/pages/teacher/questions.vue:45 |
| POST | `/api/v1/teachers/questions` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/teacher/question-edit.vue:109 |
| POST | `/api/v1/teachers/assignments` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/teacher/assignment.vue:126 |
| GET | `/api/v1/teachers/assignments` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/teacher/assignment.vue:115 |
| GET | `/api/v1/students/assignments` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/assignment/assignment.vue:154 |
| POST | `/api/v1/students/assignments/{student_assignment_id}/attempts` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/assignment/assignment.vue:170 |
| GET | `/api/v1/students/teacher-feedback` | independent_api | 独立反馈历史，返回结果与任务；首页/作业只返回相应摘要，不是完全相同的响应。 |  |
| GET | `/api/v1/teachers/students/{student_id}/plans` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/teacher/plans.vue:74 |
| PATCH | `/api/v1/teachers/plans/{plan_id}` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/teacher/plans.vue:91 |
| GET | `/api/v1/teachers/audit-logs` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/teacher/audit.vue:45 |
| POST | `/api/v1/questions/manual` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/manual/manual.vue:139 |
| GET | `/api/v1/questions/{question_id}/journey` | ui | 现有页面或组件存在直接 API 调用；保留。 | frontend/src/pages/detail/detail.vue:407、frontend/src/pages/journey/journey.vue:163、frontend/src/pages/repair/repair.vue:137 |
| POST | `/api/v1/auth/refresh` | removed | 无人调用的 local_mode 空操作；不会续期令牌，重新登录仍走 login。 |  |
| POST | `/api/v1/auth/logout` | removed | 无人调用的 local_mode 空操作；学生端 store.logout 已清除本地令牌，不做服务端撤销。 |  |
| GET | `/api/v1/system/readiness` | removed | 无页面或检查脚本调用；重复拼装 provider.health_check，已有 providers 规范入口。 |  |
| GET | `/api/v1/system/models` | removed | 无调用的 providers 别名；系统页面实际调用 providers。 |  |
| GET | `/api/v1/system/features` | removed | 无人消费的固定 true 清单，不能证明实际可用，删除。 |  |
| POST | `/api/v1/tutor/sessions/{session_id}/understanding-check` | removed | 旧理解检查入口没有页面或脚本调用，当前活动作答由 activity/answer 承担。 |  |
| GET | `/api/v1/analytics/knowledge-points` | removed | 与 overview 完全相同的响应；学习统计页面只使用 overview。 |  |
| GET | `/api/v1/analytics/misconceptions` | removed | 与 overview 完全相同的响应；学习统计页面只使用 overview。 |  |
| GET | `/api/v1/analytics/study-trend` | removed | 与 overview 完全相同的响应；学习统计页面只使用 overview。 |  |
