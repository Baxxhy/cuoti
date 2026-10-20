# 长期学习系统页面清单

2026-10-20，从当前 `frontend/src/pages.json` 与各页面源码提取，共 50 个注册页面。浏览器验收以真实接口、页面操作和双宽度渲染为准。

| 归属 | 页面标题 | 路由 |
| --- | --- | --- |
| 账户 | login | `pages/login/login` |
| 账户 | 创建账号 | `pages/register/register` |
| 账户 | 修改登录密码 | `pages/forgot/forgot` |
| 学生 | 今日 | `pages/index/index` |
| 学生 | 学习设置 | `pages/preferences/preferences` |
| 学生 | 错因回放 | `pages/replay/replay` |
| 学生 | 易错地图 | `pages/error-map/error-map` |
| 学生 | 学习安排 | `pages/repair/repair` |
| 学生 | 录入错题 | `pages/capture/capture` |
| 学生 | 框选题目 | `pages/crop/crop` |
| 学生 | 确认题目 | `pages/ocr/ocr` |
| 学生 | 手动录入 | `pages/manual/manual` |
| 学生 | 学习记录 | `pages/journey/journey` |
| 学生 | 错题详情 | `pages/detail/detail` |
| 学生 | hasStudentWork ? '错因诊断' : '本题解析' | `pages/diagnosis/diagnosis` |
| 学生 | id ? '错题订正' : '订正记录' | `pages/task/task` |
| 学生 | AI 讲解 | `pages/tutor/tutor` |
| 学生 | 互动图解 | `pages/visualization/visualization` |
| 学生 | 到期复习 | `pages/review/review` |
| 学生 | 查找复习题 | `pages/review-search/review-search` |
| 学生 | 知识框架 | `pages/framework/framework` |
| 学生 | 我的作业 | `pages/assignment/assignment` |
| 学生 | 类似题练习 | `pages/practice/practice` |
| 学生 | purpose === 'practice' ? '选择错题' : '错题本' | `pages/problem/list` |
| 学生 | 搜索错题 | `pages/search/search` |
| 学生 | 学习报告 | `pages/analysis/analysis` |
| 学生 | 相关知识 | `pages/knowledge/knowledge` |
| 学生 | 错题组卷 | `pages/paper/paper-center` |
| 学生 | 我的 | `pages/profile/profile` |
| 家长 | 家长查看权限 | `pages/guardian/access` |
| 家长 | 家长中心 | `pages/guardian/home` |
| 家长 | 学生学习报告 | `pages/guardian/report` |
| 教师 | 教师工作台 | `pages/teacher/dashboard` |
| 教师 | 班级与学生 | `pages/teacher/classes` |
| 教师 | data?.name || '班级详情' | `pages/teacher/class-detail` |
| 教师 | data?.student?.name || '学生详情' | `pages/teacher/student` |
| 教师 | 待核对队列 | `pages/teacher/reviews` |
| 教师 | 人工复核 | `pages/teacher/review-detail` |
| 教师 | 学习计划管理 | `pages/teacher/plans` |
| 教师 | 题目管理 | `pages/teacher/questions` |
| 教师 | 新增题目 | `pages/teacher/question-edit` |
| 教师 | 题目布置 | `pages/teacher/assignment` |
| 教师 | 教师操作记录 | `pages/teacher/audit` |
| 管理 | 系统与智能服务 | `pages/system/system` |
| 管理 | 管理工作台 | `pages/admin/workbench` |
| 学生 | 学习 | `pages/learning/learning` |
| 学生 | 知识卡片 | `pages/library/library` |
| 学生 | 使用指南 | `pages/help/help` |
| 学生 | 题库练习 / 模拟考试 | `pages/bank/bank` |
| 学生 | 练习与考试 | `pages/study-session/study-session` |
