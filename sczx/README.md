# 师承智学

日期 2026-11-08　版本 v11

师承智学提供教师经验、备课、班级任务、学生学习与学情反馈的完整流程。产品面向桌面 Web，前端使用 **Vue 3 + JavaScript**，业务服务使用 **FastAPI + MySQL**。模型默认通过本机 Codex CLI 调用外部服务，统一使用 gpt-6-luna 和 low 思考强度。教学案例采用 BM25 检索与可选语义重排；语音输入和朗读使用浏览器能力，不支持时保留文字操作。

- [第五步使用与实现说明](docs/planning/第五步使用与实现说明_20261108_v3.md)
- [第五步开发提示词与推荐回答](docs/planning/第五步开发提示词与推荐回答_20261108_v1.md)
- [第五步实施与验收（替代方案）](docs/planning/第五步实施与验收_20261108_v3.md)
- [第四步使用与实现说明](docs/planning/第四步使用与实现说明_20261108_v1.md)
- [第四步实施计划](docs/planning/第四步实施计划_20261108_v1.md)
- [第三步使用与实现说明](docs/planning/第三步使用与实现说明_20261107_v1.md)
- [当前视觉与交互设计](docs/design/前端视觉与交互设计_20261107_v5.md)
- [平台结构与首课流程](docs/planning/平台结构与首课使用流程_20261107_v1.md)

按第四步说明配置 `backend-business/.env`、安装 Python 依赖并迁移 MySQL，再运行 FastAPI；安装前端依赖后执行 `npm --prefix frontend run dev`。前端生产构建使用 `npm --prefix frontend run build`。
