# 错题帮 Cuoti

面向学生个人使用的错题学习系统，支持图片录题、错因诊断、教学对话、练习与复习，以及错题试卷导出。

## 当前状态（2026-11-17）

默认源码启动入口已切换为 **uni-app + Vue 3 + TypeScript → Python + FastAPI → SQLAlchemy 2.x + MySQL**。现有 Python 算法在统一后端进程内调用；LangGraph 编排教学 Agent，BGE + Qdrant 提供检索。算法模块接收业务快照，不直接读写业务数据库。

Python 已接入原仓颉实际注册的全部 83 个路径，并提供兼容的账号、错题、图片、识别任务、诊断、教学、学习任务、题库练习、复习、组卷导出、语音及管理员入口。路径覆盖不代表所有模型效果已经验收，实际验证范围见各迁移记录。

仓颉源码暂作兼容参照；`make dev`、`make backend`、管理员及题库维护入口不再编译或启动仓颉。竞赛容器入口和新离线镜像也已切到 Python，并完成独立容器验证；**现有运行中的旧服务与已发出的旧程序包尚未替换**。整体迁移仍需完成实际切换、Alembic 收口及最终依赖审查。

## 从源码运行

需要 Python 3.11+、Node 24+、pnpm 和 MySQL 8。安装项目依赖与 PDF 排版浏览器：

```bash
make install
make install-browser
```

模型配置：复制 `config/api_pool.example.json` 为本机 `config/api_pool.json` 并填入有效配置；也支持通过 `XIAOJING_API_KEY` 等服务端环境变量提供凭据。真实密钥、数据库、图片和生成文件不提交 Git。

已有开发数据库时，使用原配置即可。默认优先读取 `.env.python`，没有时读取 `.env.cangjie`；通过 `CUOTI_ENV_FILE` 可以指定配置文件。新配置参考 [.env.python.example](.env.python.example)。`CUOTI_*` 配置优先于同名兼容的 `CANGJIE_*` 配置，进程环境变量优先于配置文件中的同名项。

```bash
make dev       # 同时启动 Python 后端和前端
make check     # 只读检查后端、MySQL 结构与前端，不调用付费模型
make backend   # 只启动 Python 后端
```

默认前端端口 5175，统一后端 8002。端口已被占用时启动器会拒绝启动，保留已有服务。并行验证可以显式选择其他端口，前端代理随启动器自动连接对应 Python 后端：

```bash
CUOTI_PORT=8003 ZHIWEI_FRONTEND_PORT=5176 make dev
```

首次准备全新本地库时才使用 `make mysql setup-local`。该入口创建新的 `cuoti_local` 库与账号；已有配置、同名数据库或账号时拒绝覆盖。已有学生数据库不要重新初始化。

首次通过启动器运行会生成缺失的服务密钥并存入 `.runtime`。迁移时自动复用原认证/算法密钥文件；不要更换原认证密钥，否则原登录令牌将失效。旧图片目录存在时继续读取，`CUOTI_MEDIA_ROOT` 可指定原有目录；全新项目默认使用项目根目录的 `media`。没有搬移或删除历史图片。

`make dev` 和 `make backend` 默认启用学习任务执行器，显式设置 `CUOTI_LEARNING_TASK_WORKER_ENABLED=false` 可关闭。直接构造 FastAPI 应用时保持关闭默认值，便于迁移对照和测试。部署时只应有一套实际服务接收学生请求，避免与旧实现同时处理同一工作流。

## 数据与管理员维护

以下命令使用已配置的 MySQL，不执行自动重建：

```bash
.venv/bin/python -m cuoti_backend.manage_db status
.venv/bin/python -m cuoti_backend.manage_db backup
.venv/bin/python -m cuoti_backend.manage_db upgrade
make seed-knowledge
make import-questions
bash scripts/local_user.sh --email admin@example.com --role admin --check
```

管理员命令去掉 `--check` 后交互设置密码，支持显式 `--password-stdin` 供本地自动化使用；不允许覆盖已有账号或将学生提升为管理员。不要把密码放在命令参数中。

已有数据库升级、知识卡准备及批量题库导入前会备份到 `.runtime/backups`。备份失败停止写入。`manage_db init` 仅接受空库；MySQL DDL 隐式提交，初始化中断时不会自动清空已产生的表。历史 `cangjie_schema_versions` 表名继续保留，与仓颉运行时无关。后续 Alembic 版本管理仍在收口，不把空迁移目录视为升级流程已经完成。

## 测试与实际验证

```bash
PYTHONPATH=backend-python:backend-algorithms .venv/bin/python -m pytest backend-python/tests backend-algorithms/tests -q
CUOTI_TEST_MYSQL=1 PYTHONPATH=backend-python:backend-algorithms .venv/bin/python -m pytest backend-python/tests -q
```

MySQL 测试使用临时账号及自己的临时记录并清理；`CUOTI_TEST_MAINTENANCE=1` 额外启用随机临时数据库的建表与备份恢复测试，需要本地测试管理权限。`CUOTI_TEST_DEV_HTTP=1` 启用真实前端、后端启动与代理检查。真实模型测试需要对应的显式开关和可用配置，默认跳过的用例没有计为通过。

数学 PDF 与 Excel 使用既有排版模块，依赖 Node、前端依赖和 Chromium；浏览器位置可通过 `ZHIWEI_PDF_CHROMIUM` 指定。模型识别、诊断和语音效果取决于提供方与输入质量；保留人工核对流程，具体已知问题在验收记录中说明。

## 迁移记录

- [迁移审计校准报告](docs/迁移方案/迁移审计校准报告.md)
- [错题核心业务与智能录入对照](docs/迁移方案/第三阶段全面迁移对照清单.md)
- [诊断与作答迁移](docs/迁移方案/诊断与作答迁移补全记录.md)
- [教学对话与学习记忆](docs/迁移方案/教学对话与学习记忆迁移记录.md)
- [真实模型学习任务闭环](docs/迁移方案/学习任务真实模型闭环验收记录.md)
- [题库练习迁移](docs/迁移方案/练习推荐与作答业务迁移记录.md)
- [复习与筛选迁移](docs/迁移方案/复习与筛选业务迁移记录.md)
- [题库浏览与学习卷](docs/迁移方案/题库浏览与学习卷迁移记录.md)
- [试卷与文件导出](docs/迁移方案/试卷组卷与文件导出迁移记录.md)
- [语音、系统状态与管理视图](docs/迁移方案/语音系统状态与管理视图迁移记录.md)
- [数据库与题库维护命令](docs/迁移方案/数据库初始化与题库维护命令迁移记录.md)
- [本地启动与配置切换](docs/迁移方案/本地启动与配置切换迁移记录.md)

新 Python 镜像的构建、离线资源复用和程序包组装见 [竞赛部署目录](deployment/competition/README.md)；实际验证见[竞赛容器迁移验收](docs/迁移方案/竞赛容器与离线镜像迁移验收记录.md)。旧程序包的镜像保持原实现，不能当作 Python 迁移版本。
