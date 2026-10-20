# 页面清单与验收

来源：当前 `frontend/src/pages.json`。48 条路由包含已确认的登录页及其余 47 页；每条路由在 375px / 1280px 下均有真实浏览器结果。46 页使用共享紧凑页头，管理页单独适配；登录页保留品牌布局。

非登录页共 94 次渲染，导航标题均为 17px、中等字重、居中；最大中心偏移为 22px。未出现页面横向溢出或运行异常。逐页存在可见可编辑字段时，检查首个文本输入或选择框没有外围 outline。

原始结果见 [all-route-rendering.json](evidence/all-route-rendering.json)。搜索路由按原行为跳转至错题本；数据来自隔离仓颉 / MySQL 环境。

| 路由 | 实际标题 | 页头 | 375 / 1280 |
| --- | --- | --- | --- |
| `pages/login/login` | 错题帮 | 品牌布局 | 通过 / 通过 |
| `pages/register/register` | 创建账号 | 17px 居中导航 | 通过 / 通过 |
| `pages/forgot/forgot` | 修改登录密码 | 17px 居中导航 | 通过 / 通过 |
| `pages/index/index` | 今日 | 17px 居中导航 | 通过 / 通过 |
| `pages/preferences/preferences` | 学习设置 | 17px 居中导航 | 通过 / 通过 |
| `pages/replay/replay` | 错因回放 | 17px 居中导航 | 通过 / 通过 |
| `pages/error-map/error-map` | 易错地图 | 17px 居中导航 | 通过 / 通过 |
| `pages/repair/repair` | 学习安排 | 17px 居中导航 | 通过 / 通过 |
| `pages/capture/capture` | 录入错题 | 17px 居中导航 | 通过 / 通过 |
| `pages/crop/crop` | 框选题目 | 17px 居中导航 | 通过 / 通过 |
| `pages/ocr/ocr` | 确认题目 | 17px 居中导航 | 通过 / 通过 |
| `pages/manual/manual` | 手动录入 | 17px 居中导航 | 通过 / 通过 |
| `pages/journey/journey` | 学习记录 | 17px 居中导航 | 通过 / 通过 |
| `pages/detail/detail` | 错题详情 | 17px 居中导航 | 通过 / 通过 |
| `pages/diagnosis/diagnosis` | 错因诊断 | 17px 居中导航 | 通过 / 通过 |
| `pages/task/task` | 错题订正 | 17px 居中导航 | 通过 / 通过 |
| `pages/tutor/tutor` | AI 讲解 | 17px 居中导航 | 通过 / 通过 |
| `pages/visualization/visualization` | 互动图解 | 17px 居中导航 | 通过 / 通过 |
| `pages/review/review` | 到期复习 | 17px 居中导航 | 通过 / 通过 |
| `pages/assignment/assignment` | 我的作业 | 17px 居中导航 | 通过 / 通过 |
| `pages/practice/practice` | 类似题练习 | 17px 居中导航 | 通过 / 通过 |
| `pages/problem/list` | 错题本 | 17px 居中导航 | 通过 / 通过 |
| `pages/search/search` | 错题本 | 17px 居中导航 | 通过 / 通过 |
| `pages/analysis/analysis` | 学习报告 | 17px 居中导航 | 通过 / 通过 |
| `pages/knowledge/knowledge` | 相关知识 | 17px 居中导航 | 通过 / 通过 |
| `pages/paper/paper-center` | 错题组卷 | 17px 居中导航 | 通过 / 通过 |
| `pages/profile/profile` | 我的 | 17px 居中导航 | 通过 / 通过 |
| `pages/guardian/access` | 家长查看权限 | 17px 居中导航 | 通过 / 通过 |
| `pages/guardian/home` | 家长中心 | 17px 居中导航 | 通过 / 通过 |
| `pages/guardian/report` | 学生学习报告 | 17px 居中导航 | 通过 / 通过 |
| `pages/teacher/dashboard` | 教师工作台 | 17px 居中导航 | 通过 / 通过 |
| `pages/teacher/classes` | 班级与学生 | 17px 居中导航 | 通过 / 通过 |
| `pages/teacher/class-detail` | 全站路由验收班 | 17px 居中导航 | 通过 / 通过 |
| `pages/teacher/student` | 全站路由验收 | 17px 居中导航 | 通过 / 通过 |
| `pages/teacher/reviews` | 待核对队列 | 17px 居中导航 | 通过 / 通过 |
| `pages/teacher/review-detail` | 人工复核 | 17px 居中导航 | 通过 / 通过 |
| `pages/teacher/plans` | 学习计划管理 | 17px 居中导航 | 通过 / 通过 |
| `pages/teacher/questions` | 题目管理 | 17px 居中导航 | 通过 / 通过 |
| `pages/teacher/question-edit` | 新增题目 | 17px 居中导航 | 通过 / 通过 |
| `pages/teacher/assignment` | 题目布置 | 17px 居中导航 | 通过 / 通过 |
| `pages/teacher/audit` | 教师操作记录 | 17px 居中导航 | 通过 / 通过 |
| `pages/system/system` | 系统与智能服务 | 17px 居中导航 | 通过 / 通过 |
| `pages/admin/workbench` | 全局概览 | 17px 居中导航 | 通过 / 通过 |
| `pages/learning/learning` | 学习 | 17px 居中导航 | 通过 / 通过 |
| `pages/library/library` | 知识卡片 | 17px 居中导航 | 通过 / 通过 |
| `pages/help/help` | 使用指南 | 17px 居中导航 | 通过 / 通过 |
| `pages/bank/bank` | 题库练习 | 17px 居中导航 | 通过 / 通过 |
| `pages/study-session/study-session` | 数学练习 | 17px 居中导航 | 通过 / 通过 |
