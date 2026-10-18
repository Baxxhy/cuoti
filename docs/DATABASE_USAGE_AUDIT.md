# MySQL 最终使用审计

## 结论

- 仅使用 MySQL 8 + `asyncmy`，没有 SQLite 回退。
- Alembic 版本 `20260807_0003`，36 张业务表 + `alembic_version`。
- `verify_database_usage.py` 从注册、上传、Qwen 图像识别、确认、分析、诊断、教学、可视化、迁移、复习到组卷导出执行全新链路。
- 36 张业务表均存在真实写入路径；核心外键孤儿记录总数为 0。

## 第三轮结束时实际记录数

| 业务域 | 表与记录数 |
|---|---|
| 用户与角色 | users 40；student_profiles 37；guardian_student_links 5；teacher_classes 1；teacher_class_students 5 |
| 题目与处理 | questions 47；question_assets 170；processing_jobs 43；ocr_runs 188 |
| 学生证据 | student_works 49；student_steps 87；teacher_marks 35 |
| 分析与诊断 | problem_analyses 43；reference_steps 155；diagnoses 38；diagnosis_evidence 134 |
| Agent | tutor_sessions 133；tutor_turns 648；agent_runs 599；agent_tool_calls 599 |
| 可视化与迁移 | visualization_specs 104；interactions 104；variant_questions 107；attempts 86 |
| 知识与认知 | knowledge_points 65；relations 62；mastery_states 40；misconception_states 41；cognitive_updates 232 |
| 复习 | review_plans 113；review_records 30 |
| 组卷、语音、导出 | papers 39；paper_items 47；voice_records 13；export_jobs 57 |

这些计数来自功能验收多轮真实写入，因此高于演示种子数量。验证脚本还对本轮独立用户限定查询，确认资产、识别结果、步骤、诊断证据、Agent 工具、变式作答、复习、组卷项和可视化交互均属于同一条完整业务链。
