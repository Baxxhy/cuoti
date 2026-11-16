# 错题帮开发约定

- 项目是本地学生个人错题应用，功能正确优先。
- 唯一主线：uni-app/Vue 3/TypeScript 前端，仓颉业务服务与MySQL，Python/FastAPI内部算法计算。旧Python业务后端已删除，不重新引入。
- 当前说明见 README.md、docs/final/README.md 与 docs/final/IMPLEMENTATION_STATUS.md。
- 数据库只允许MySQL；Python算法服务不读写业务数据库。
- API池配置位于 config/api_pool.json；当前模型为xiaojing的gpt-6-luna（兼容旧Qwen配置），请求通过ApiPoolProvider轮询，不输出凭据。
- 保留原始上传图片；结构化模型输出通过Pydantic校验，数学尽量通过SymPy验证。
- 前端只消费VisualizationSpec JSON，不执行模型生成的JavaScript。
- 页面数据来自仓颉后端和MySQL，演示种子除外。
- 算法测试：PYTHONPATH=backend-algorithms .venv/bin/pytest backend-algorithms/tests。
- 前端测试：npm --prefix frontend test。
- 完整检查：make verify；make verify-final为同一检查入口。
- 功能完成后提交Git，保持工作区干净。禁止为了清理空间丢弃其他工作树的改动、学生资料或数据库。
- 用户偏好（2026-11-16，cuoti 项目）：每次完成改动及相应验证后，提交本次改动并推送到 GitHub 的 origin 当前工作分支。推送失败时说明具体原因，保留本地提交。
