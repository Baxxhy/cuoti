# Python内部算法服务

仅负责OCR、结构化AI分析、错因定位、判题、类似题、学习策略、知识讲解、检索计算、语音与导出。业务数据、账号、权限、学习任务和MySQL由仓颉服务管理。

`learning_core/` 保存当前实际使用的共用算法、Pydantic结构与ApiPoolProvider。项目不再包含旧Python业务后端，也不导入ORM或读写业务数据库。

在项目根目录执行 `make install` 安装，`make dev` 同时启动三层服务。单独启动算法服务：设置至少32字符的 `CANGJIE_ALGORITHM_SECRET` 后运行 `make algorithms-cangjie`。API池默认读取 `config/api_pool.json`，也可通过 `CANGJIE_API_POOL_PATH` 指定。当前模型为xiaojing的gpt-6-luna，通过池轮询调用（兼容旧Qwen配置）；启动与健康检查不调用模型。

服务监听本地8012端口，`/v1/compute` 必须携带内部密钥，不能直接提供给前端。图像计算使用临时目录；结构化输出经过Pydantic，数学尽量经过SymPy核验。模型不足或核验失败不伪造成功。

测试：项目根目录 `make test-algorithms`。完整验收：`make verify`。

模型密钥通过算法服务进程的 `XIAOJING_API_KEY` 环境变量提供；API池使用 `api_key_env` 引用，不在示例配置中保存密钥。修改模型配置后需重启算法服务。
