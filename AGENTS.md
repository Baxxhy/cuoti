# 错题帮开发约定

- 项目是本地单用户错题教学应用，功能正确优先。
- 当前主线：前端使用 uni-app、Vue 3、TypeScript、uni-ui；仓颉承担业务后端与 MySQL 交互，Python/FastAPI 只提供内部算法计算。旧 Python 业务版保留为兼容入口。
- 最终产品规格以 `docs/final/README.md` 为准，实施与验收进度见 `docs/final/IMPLEMENTATION_STATUS.md`。
- 数据库只允许 MySQL，不添加 SQLite 回退。
- API 池项目副本位于 `backend/config/api_pool.json`。
- 逻辑模型固定为 `Qwen`。
- AI 请求必须通过 ApiPoolProvider 轮询，不直接访问单个条目。
- 不在日志、报错或报告中打印池内凭据。
- 原始上传图片不得被清洁图覆盖。
- 模型结构化输出必须通过 Pydantic 校验。
- 数学结论尽量通过 SymPy 验证。
- 前端不执行模型生成的 JavaScript，仅消费 VisualizationSpec JSON。
- 页面数据必须来自后端和 MySQL；演示种子数据除外。
- 后端测试：`pytest backend/tests`。
- 前端测试：`npm --prefix frontend test`。
- 完整检查：`make verify`。
- 当前仓颉主线检查：`make verify-final`；`make verify` 继续检查保留的 Python 业务版。
- 功能阶段完成后提交 Git，最终保持工作区干净。
