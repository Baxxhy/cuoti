# SCZX：错题帮网页版

先看 [核对说明](核对说明.md)，了解已经做到了什么、实际检查结果和剩余差异。

这里把原来的 uni-app 页面改成普通 Vue 网页，把仓颉业务服务改成 Python。数据库仍用 MySQL，原项目和原数据库保留。

目前已接入原版83条接口，后台学习任务可以执行和恢复。独立环境下已通过99项后端测试、694项算法全量测试、25项前端测试及网页构建。账号、资料、录题、裁剪、练习、考试、复习、任务恢复、函数图及全站手机/桌面等72项浏览器验收已完整一轮通过。真实浏览器已走通“订正一步→独立解原题→完成对照题”，并通过实际HTTP服务生成和下载PDF、答案PDF、Excel。

已实际检查当前模型的文字/图片连通性，以及一条合成中文语音的合成、转写、保存和下载。另已通过一张合成方程题的真实识别、分析诊断及手机网页确认与刷新。原版网页没有录音入口；接下来继续核对剩余页面差异。具体记录见 [MIGRATION_STATUS.md](MIGRATION_STATUS.md)。

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

原版71项浏览器用例的迁移清单见 [e2e_parity_inventory.json](e2e_parity_inventory.json)。原版场景已全部接入，其中一项裁剪扩展为电脑和触屏两项，共72项；视觉细节及实际模型、语音联调仍需核对，不能把用例通过视为全部一致。

浏览器验收会启动一个本地受控判题与图形转写接口，只接受已登记的测试样本，其他请求拒绝；不会使用真实模型账号，也不会改变正常启动的模型配置。

页面外观也在和原版逐项对照。最近一轮96组页面状态的文字和脚本检查通过，98对截图中90对逐像素相同；另7对只有1级RGB差异，1对为尚待决定的短列表差异。已有对照目录可用下面的命令生成逐图差异记录：

```bash
.venv/bin/python scripts/compare_pixels.py .runtime/page-compare/full-input-layer
```

选择器正在对齐原版：手机使用底部滚轮，桌面使用字段旁的列表。确认、取消和实际多选题录入已验证；短列表初始位置及少量叠层渲染差异仍在核对，详见MIGRATION_STATUS.md。

滚轮现已支持连续拖动、惯性和回弹；学科选择器已用相同真实触屏轨迹对照原版，停靠位置和最终选项一致。滚动计算模块的来源及许可证保存在frontend/src/platform/vendor/。

## 实际模型和语音检查

以下命令会实际请求所配置的服务，不属于默认测试；只发送合成样例，不使用学生资料。模型探测默认最多1个条目，报告不会输出凭据：

```bash
.venv/bin/python scripts/live_provider_smoke.py --pool-path /你的配置/api_pool.json --env-file .env --voice
```

语音识别首次使用需要Whisper small模型缓存，默认位于本目录.models/faster-whisper。本次已复制已有缓存并在离线模式下成功加载，缓存不提交Git。要检查网页代理、后端、算法服务、MySQL和原音下载整条链路，可以显式运行：

```bash
SCZX_RUN_LIVE_VOICE=1 .venv/bin/python scripts/integration_smoke.py
```

已验证的一句语音存在“已知”被识别为“一支”的误差，结果可编辑；这些检查证明链路能用，不代表所有录音都能准确识别。

真实图片识别和诊断也可以单独检查。下面会使用指定模型池处理一张程序绘制的方程题；开启网页模式后，会在手机尺寸网页上填写步骤、确认并分析，再检查刷新恢复。它不能与受控浏览器验收SCZX_RUN_E2E=1混用：

```bash
SCZX_LIVE_MODEL_POOL=/你的配置/api_pool.json SCZX_LIVE_MODEL_ENV=/你的环境文件/.env SCZX_LIVE_MODEL_BROWSER=1 .venv/bin/python scripts/integration_smoke.py
```

已实际通过这一流程：识别2x+3=11，核验正确答案x=4，并指出输入的第一步2x=14有误。原始图片完整保留，识别结果需要用户确认，浏览器没有伪造接口或模型结果。

逐项查看接口测试覆盖，可以运行：

```bash
.venv/bin/python scripts/audit_api_coverage.py
```

它会使用隔离MySQL运行后端测试，生成每个原接口对应的成功用例和已检查状态码；不会保存请求内容或凭据。报告位于.runtime/api-audit/。原版网页没有麦克风录音入口，迁移保留的是已有语音后端接口。

最新一轮已完整通过99项后端测试和72项浏览器验收。83条原接口的102种方法都有成功请求证据，具体用例和已检查状态码可在api_parity_inventory.json中查看；清单里的历史阶段说明已更新。页面显示差异仍在核对。

原版未启用随系统切换的深色主题，网页版也保留相同表现。已修复系统深色偏好下弹窗背景透明的问题，并在浅色/深色环境各检查8组弹窗和选择器状态。

检查是否还依赖旧项目代码或依赖目录，可以运行：

```bash
.venv/bin/python scripts/audit_standalone.py
```

它会在隔离进程中禁止读取旧项目和reference，检查服务导入、本地数学计算及Python/前端依赖的位置和版本。已通过90项Python、190项已安装前端依赖检查；另外60项属于其他平台的可选包。这个检查不连接数据库或外部模型，完整启动仍按上面的MySQL配置和联调步骤执行。

已修正提示文字与选择器叠放时的绘制层级：知识框架普通页和选择器状态的4张重点截图均与原版逐像素一致；登录及离线失败后保留输入的3项实际浏览器流程通过。

已恢复与原版一致的页面背景层，并检查缓存页不会占空白区域、未知路由提示仍在首屏。当前版本完整72项浏览器验收再次通过；最新98对截图90对完全一致，剩余7对微小像素差异和1对短列表差异继续记录。

截图工具另有原版自对照模式：SCZX_COMPARE_SELF_ORIGINAL=1。报告会标记original-self-repeat，正常迁移对照标记original-versus-vue；自对照结果不能算作迁移通过。相同原版重复渲染也出现过少量像素波动，迁移版剩余差异仍单独保留，未因此忽略。
