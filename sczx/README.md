# SCZX：Vue网页端与Python后端迁移

本目录将原错题帮迁移为普通Vue网页和Python业务服务，业务数据库仍为MySQL。原项目保持原样。

## 当前状态

- `frontend/`：原36个页面已转换为普通Vue源码，使用Vite构建；浏览器操作由原生Web API承担。
- `backend/`：Python/FastAPI业务层，已接入账号、学习偏好、错题列表、题目详情、编辑、归档、手动录题、图片上传、识别任务与重试、裁剪、草稿/确认、签名图片、题目分析、作答提交、诊断及修正、开始/恢复辅导、类似题与阶段导航、讲清提交、活动作答/判分、结课、手写上传、直接类似题作答和健康检查。
- `reference/`：原版源码与测试样例的对照快照，不是新程序的运行依赖。
- `api_parity_inventory.json`：原83个注册路径的接入清单。
- `MIGRATION_STATUS.md`：已验证的内容及下一批任务。

目前前端构建与一部分浏览器交互、Python账号和学习偏好测试通过，完整业务迁移继续进行。

## 运行

前端在本目录安装独立依赖后启动：

```bash
cd frontend
npm install
npm run dev
```

网页地址为 `http://127.0.0.1:5176`，默认把业务请求转发到 `http://127.0.0.1:8010`；可通过 `SCZX_BACKEND_URL` 更改。

后端安装 `backend/requirements.txt`，设置以下环境变量后，在 `backend/` 中运行 `python -m uvicorn sczx_api.main:app --host 127.0.0.1 --port 8010`：

- `SCZX_AUTH_SECRET`：至少32字符的本地随机会话密钥。
- `SCZX_DB_NAME`：新建的 `sczx_` 前缀数据库。
- `SCZX_DB_HOST`、`SCZX_DB_PORT`、`SCZX_DB_USER`、`SCZX_DB_PASSWORD`：该独立MySQL数据库的连接信息。
- `SCZX_DB_SOCKET`：可选的本地MySQL socket。

空数据库可通过 `python -c 'from sczx_api.schema import initialize_database; initialize_database()'` 初始化。该命令拒绝已有表的数据库。程序不会读取原项目的数据库配置。

## 检查

在 `frontend/` 运行 `npm test` 和 `npm run build`。后端安装pytest后，从 `sczx/` 运行 `PYTHONPATH=backend python -m pytest backend/tests`。MySQL测试会新建临时实例，仅使用临时数据目录和本地socket。

`node scripts/browser_smoke.mjs` 检查已启动网页中的登录错误、注册页和图片选择；使用受控HTTP响应，不作为真实后端完整流程验收。

## 内部算法服务

`algorithms/`保存独立算法代码。按其中README安装并启动8012端口，业务服务设置相同的`SCZX_ALGORITHM_SECRET`及`SCZX_ALGORITHM_URL=http://127.0.0.1:8012`。模型池由`SCZX_API_POOL_PATH`指定，凭据通过环境变量提供，本次未复制原凭据。图片与导出文件写入`SCZX_MEDIA_ROOT`（默认当前工作目录的media），题库配图根通过`SCZX_QUESTION_BANK_ROOT`指定。
