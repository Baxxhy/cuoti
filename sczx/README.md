# SCZX：错题帮网页版

这里把原来的 uni-app 页面改成普通 Vue 网页，把仓颉业务服务改成 Python。数据库仍用 MySQL，原项目和原数据库保留。

目前已接入原版83条接口，后台学习任务可以执行和恢复。独立环境下已通过99项后端测试、33项算法入口/学习流程/掌握度测试、18项前端测试及网页构建。账号、资料、录题、裁剪、练习、考试、复习及恢复等41项浏览器验收已完整一轮通过。真实浏览器已走通“订正一步→独立解原题→完成对照题”，并通过实际HTTP服务生成和下载PDF、答案PDF、Excel。

接下来继续核对其余网页操作、原版页面呈现和真实模型/语音。具体记录见 [MIGRATION_STATUS.md](MIGRATION_STATUS.md)。

## 安装和启动

本轮验证环境：Linux x86_64、Python 3.13、Node.js 24、MySQL 8.0。所有命令从 `sczx` 目录运行。

先安装依赖：

```bash
bash scripts/setup.sh
```

脚本会建立本目录的 `.venv`，并按 `requirements.lock` 和 `frontend/package-lock.json` 安装依赖；前端不再借用原项目的依赖目录。

复制配置文件并填写自己的独立MySQL连接信息：

```bash
cp .env.example .env
```

- 数据库名称必须以 `sczx_` 开头，例如 `sczx_local`。先在自己的MySQL中创建这个空数据库，并授予专用账号建表和读写权限。
- `SCZX_AUTH_SECRET` 和 `SCZX_ALGORITHM_SECRET` 各填一个至少32字符的随机值。后者用于两个Python服务之间的身份核对。
- `SCZX_API_POOL_PATH` 填模型池配置文件路径，识别和需要模型的分析功能会使用它。原模型凭据没有复制进本目录。

可以用 `.venv/bin/python -c 'import secrets; print(secrets.token_hex(32))'` 生成一个随机值。

配置好后，只对新建的空数据库初始化一次：

```bash
PYTHONPATH=backend .venv/bin/python -c "from dotenv import load_dotenv; load_dotenv('.env'); from sczx_api.schema import initialize_database; initialize_database()"
```

该命令拒绝已有表的数据库。接着导入项目自带的250张公开知识卡和65条知识关系：

```bash
.venv/bin/python scripts/seed_knowledge.py
```

这一步对应原版的知识初始化，可重复执行，保留已有卡片编号，不重复建立关系。然后启动：

```bash
.venv/bin/python scripts/run_local.py
```

打开 `http://127.0.0.1:5176`。脚本会同时启动网页、业务服务和内部算法服务；按 Ctrl+C 停止本次启动的进程。需要换端口时，在 `.env` 设置 `SCZX_WEB_PORT`、`SCZX_BACKEND_PORT`、`SCZX_ALGORITHM_PORT`。后台任务默认有2个执行线程；`SCZX_TASK_WORKERS=0` 仅用于隔离接口测试。

## PDF公式排版和浏览器验收

公式PDF和公式Excel会使用本目录的KaTeX排版及Chromium，需要另外安装浏览器：

```bash
PLAYWRIGHT_BROWSERS_PATH="$PWD/.runtime/playwright-browsers" node frontend/node_modules/@playwright/test/cli.js install chromium
```

普通文本导出使用ReportLab/openpyxl。可用 `SCZX_PDF_CHROMIUM` 指定已有Chromium路径。

## 检查

```bash
npm --prefix frontend test
npm --prefix frontend run build
PYTHONPATH=backend .venv/bin/python -m pytest backend/tests -q
PYTHONPATH=algorithms .venv/bin/python -m pytest algorithms/tests/test_service.py algorithms/tests/test_learning_workflow.py algorithms/tests/test_mastery_tracker.py -q
.venv/bin/python scripts/integration_smoke.py
```

最后一个命令会启动临时MySQL、网页和两个Python服务，再让真实浏览器完成作答和刷新恢复，并验证导出。它使用固定分析样例，不调用外部模型；结束后关闭本次启动的服务并删除临时数据库目录，截图、导出样本和报告保存在 `.runtime/http-smoke/`。

`node scripts/browser_smoke.mjs` 可对已启动网页单独检查登录错误、注册页及文件选择。这个小检查使用受控接口响应；`SCZX_WEB_URL` 可指定网页地址。

## 目录

- `frontend/`：普通Vue网页，保留原36个页面的业务逻辑。
- `backend/`：Python业务服务，负责账号、错题、学习记录和MySQL。
- `algorithms/`：识别、数学校验、学习计算及语音服务，不读写业务数据库。
- `reference/`：原版源码对照快照。
- `api_parity_inventory.json`：原接口的接入及验收情况。

上传图片和导出文件由 `SCZX_MEDIA_ROOT` 指定；启动脚本默认使用 `.runtime/media/`。题库配图位置通过 `SCZX_QUESTION_BANK_ROOT` 指定。


迁移后的浏览器用例可以和隔离HTTP联调一起运行：

```bash
SCZX_RUN_E2E=1 .venv/bin/python scripts/integration_smoke.py
```

它会创建临时MySQL和测试账号，结束后停止本次进程；不会连接现有学生数据库。测试报告保存在 `.runtime/http-smoke/` 对应运行目录。

只复核裁剪时可在上述命令前加 `SCZX_E2E_GREP=裁剪`，报告会注明实际选择范围。

原版71项浏览器用例的迁移清单见 [e2e_parity_inventory.json](e2e_parity_inventory.json)。目前仍有31项待接入，不能把现有用例通过视为全部一致。
