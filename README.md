# 错题帮

当前目标是整个系统能启动、主要功能能实际使用，页面简单清楚；不开发备份恢复。使用、功能与支持边界见[系统运行与使用说明](docs/final/SYSTEM_DELIVERY.md)。

当前主线为 **uni-app 前端 → 仓颉业务后端/MySQL → Python 内部算法**。最终产品需求见 [新版总方案](docs/final/README.md)，实际实现与待验收项见 [实施进度](docs/final/IMPLEMENTATION_STATUS.md)。

理解项目先看[当前项目与智能体架构](docs/ARCHITECTURE.md)：模块职责、错题学习闭环、持久任务时序和证据边界。当前收尾状态见[最终版续作记录](docs/final/FINALIZATION_2026_10_18.md)。

最新AI内容与修复见[补充题型验收](docs/final/EXTENDED_AI_ACCEPTANCE_2026_10.md)；逐功能核对与原提交检查见[最终提交复核](docs/final/FINAL_SUBMISSION_AUDIT_2026_10.md)。历史批次的测试数量不代表当前版本。

首次安装请按[当前架构启动指南](docs/final/QUICK_START.md)：`make install-final`创建算法所需的`.venv`并安装两端依赖，再准备仓颉工具链和独立MySQL。已有环境直接`make dev-final`启动、`make check-final`核对。实际模型与当前页面证据见[运行完善记录](docs/final/ACTUAL_RUNTIME_IMPLEMENTATION.md)。

本地启动：复制 `.env.cangjie.example` 为 `.env.cangjie` 并配置独立 MySQL（首次建表按[仓颉说明](backend-cangjie/README.md)显式执行），运行 `make dev-final`；`make check-final` 只检查服务就绪，Ctrl+C 停止本次启动的三个服务。启动器不创建数据库、不导入演示成绩、不探测付费模型。

教师、家长和管理员使用专用本地账号：`bash scripts/local_user.sh --email 实际邮箱 --role guardian --name '家长姓名'`，密码交互输入；`--role`也支持`teacher/admin`。命令拒绝覆盖已有账号，详见[角色账号配置](docs/final/LOCAL_IDENTITIES.md)。

真实练习题库：按[仓颉题库准备说明](docs/final/QUESTION_BANK_IMPLEMENTATION.md)配置独立Qdrant集合，运行`make setup-question-bank-cangjie`；默认读取本地CMMU文件，仓颉负责MySQL，Python只清洗/映射和建立BGE索引。不调用下文保留的旧Python业务版导入命令向新库写数据。

手机资源：`npm --prefix frontend run build:app:local` 用于本地开发基座；正式资源必须设置实际 `VITE_API_BASE_URL=https://你的网关/api/v1` 后运行 `build:app`。资源构建之后仍须签名打包与真机安装，见[手机交付说明](docs/final/MOBILE_DELIVERY.md)。下文原 `make dev/backend/verify` 是保留的 Python 业务版入口。

> 2026-10-16 仓颉独立版：既有 94 条业务接口已迁移，保留原 Python 版。新版本启动、配置和验证见 [仓颉运行说明](backend-cangjie/README.md)，验收范围见 [仓颉迁移记录](docs/cangjie/MIGRATION.md)。

> 历史部署前验收：密码修改后的旧会话、首次安装迁移和师生复核反馈的阶段记录见 [部署前验收进度](docs/qa/部署前验收进度.md)。当前状态以最终提交复核与实施进度为准。

> 2026-10-13 界面整理：聚焦当前任务、清楚题目列表与正常控件尺寸，统一手机和平板、电脑布局。见 [界面整理说明](docs/ui/2026-10-13-界面整理说明.md)。

> 2026-10-13 参赛完善：新增手动录题与错题学习档案，修复识别恢复、多选/复习、题干修改后的旧分析、账户与资源隔离等问题。本轮范围与证据见 [参赛完善说明](docs/competition/2026-10-13-参赛完善说明.md)。历史审计中的测试数量和完成结论仅代表对应日期。

面向初一至高三学生的多模态错题诊断与 AI 教学系统。学生上传错题后，系统完成图片净化、OCR 识别、解题步骤诊断、针对性导学、相似题训练、综合迁移、掌握度更新和间隔复习。

本仓库包含前端、后端、MySQL 迁移、模型下载和题库导入脚本。外部 AI 的可用性取决于服务授权、配额和网络，评审前应实际验证。

## 1. 项目结构

```text
zhiwei/
├── frontend/                  UniApp + Vue 3 前端（H5 / App）
├── backend-cangjie/           仓颉业务、权限、MySQL 与迁移
├── backend-algorithms/        Python 内部算法计算
├── backend/app/               保留的 Python 兼容业务版及共用算法
├── backend/alembic/           旧 Python 业务版 MySQL 迁移
├── backend/config/api_pool.example.json  安全示例；实际 api_pool.json 仅本机保留
├── scripts/                   启动、模型、题库和验收脚本
├── data/                      本地数据目录（大文件不进入 Git）
├── uploads/                   用户上传文件（不进入 Git）
├── reports/                   导出与验收报告
├── .env.cangjie.example       当前三端架构配置模板
├── .env.example               旧 Python 业务版配置模板
└── Makefile                   常用命令入口
```

核心技术栈：

- 前端：UniApp、Vue 3、Vite、Pinia、KaTeX、Canvas/SVG、Vitest、Playwright。
- 业务与数据：仓颉、MySQL；算法：Python/FastAPI、Pydantic v2。
- Python 兼容业务版：SQLAlchemy 2、Alembic、asyncmy；不作为当前前端的静默回退。
- AI：Qwen、OpenCV、SymPy、LangGraph。
- 检索：BGE-M3、BGE-reranker-v2-m3、Qdrant。
- 导出：ReportLab、openpyxl；仓库保留 faster-whisper / edge-tts 后端能力，当前学生端无语音入口。

前端统一使用 pnpm 和 `frontend/pnpm-lock.yaml`。维护代码时运行 `pnpm --dir frontend run format:check`，需要整理格式时运行 `pnpm --dir frontend run format`；后端使用 Ruff 格式化。生成的组件类型声明不手工维护。

<details>
<summary>旧 Python 业务版安装与调试参考（点击展开）</summary>

## 2. 旧 Python 业务版参考

以下安装、数据库迁移、账号管理与`make dev/verify`命令属于保留的 Python 兼容业务版。当前仓颉业务/MySQL + Python内部算法版本使用[当前架构启动指南](docs/final/QUICK_START.md)和`make install-final/dev-final/check-final/verify-final`，两套业务库和启动命令分别使用。

### 运行环境

推荐使用 Ubuntu 22.04/24.04 或当前项目相同的 Linux 容器。Windows 用户建议使用 WSL2。项目不支持 SQLite。

最低建议配置：

- 核心功能：8 核 CPU、16 GB 内存、20 GB 可用磁盘。
- 完整真实题库：32 GB 内存、40 GB 以上可用磁盘。
- GPU 不是启动核心功能的必要条件；真实题库向量化在 NVIDIA GPU 上更快。

必须安装：

- Git、curl、make、基础编译工具。
- Miniconda 或 Anaconda。
- Node.js 20 以上、Corepack、pnpm 11。
- MySQL Server 与 MySQL Client。
- Docker（仅真实题库的 Qdrant 需要）。
- ffmpeg（语音转写需要）。

Ubuntu 可先安装系统依赖：

```bash
sudo apt update
sudo apt install -y git curl make build-essential mysql-server mysql-client ffmpeg libgl1 libglib2.0-0
```

启用 pnpm：

```bash
corepack enable
corepack prepare pnpm@11.20.0 --activate
```

确认环境：

```bash
conda --version
node --version
pnpm --version
mysql --version
```

## 3. 克隆与配置

```bash
git clone https://github.com/Baxxhy/zhiwei.git
cd zhiwei
cp .env.example .env
```

默认 `.env` 已适配本机运行：

```dotenv
DATABASE_URL=mysql+asyncmy://minddimension:minddimension@127.0.0.1:3307/minddimension
API_POOL_PATH=backend/config/api_pool.json
AI_LOGICAL_MODEL=Qwen
UPLOAD_DIR=uploads
AI_MODE=live
```

AI 池文件 [backend/config/api_pool.json](backend/config/api_pool.json) 已纳入 Git，其中保留了项目可直接调用的服务地址和凭据。后端只允许 CSU 提供商，并校验所有模型均为 `Qwen`。不要把模型名称改成其他模型，否则后端会拒绝启动。

首次面向真实用户安装按以下顺序执行。知识卡初始化与演示账号分开：

```bash
make install
make mysql
make migrate
make seed-knowledge
make install-retrieval
make download-retrieval-models
make retrieval
make setup-question-bank
make verify-adaptive-practice
make build
make dev
```

最后一条命令会同时启动 MySQL、Qdrant、BGE 推理服务、FastAPI 和 UniApp H5。下面各节解释每一步做了什么及故障处理方式。

创建教师、家长和管理员账号由运营人员在服务器终端执行，密码交互输入且不显示。脚本拒绝覆盖已有账号，不重置密码或学习记录：

```bash
conda run --no-capture-output -n minddimension python scripts/manage_accounts.py create --role teacher --email teacher@example.com --name 教师
conda run --no-capture-output -n minddimension python scripts/manage_accounts.py create --role guardian --email guardian@example.com --name 家长
conda run --no-capture-output -n minddimension python scripts/manage_accounts.py create --role admin --email admin@example.com --name 管理员
```

学生从注册页建立账号。教师从班级页面添加学生。家长关系由运营人员核对后建立，重复执行不会重复添加：

```bash
conda run --no-capture-output -n minddimension python scripts/manage_accounts.py link-guardian --guardian-email guardian@example.com --student-email student@example.com
```

自动化环境可使用 `--password-stdin` 从标准输入读取密码，不把密码写进命令参数。`make seed` 与 `make fresh-student` 仅用于独立演示环境，后者会清空指定演示学生的数据，不用于真实用户初始化。

部署地址确定后配置 HTTPS，并将 `/api/`、`/uploads/`、`/reports/` 同源代理到后端。上传图片和导出文件由后端校验签名，不直接用静态服务器绕过校验；MySQL、上传目录、导出目录和本地会话密钥需持久保存。当前 `make dev` 用于本机联调，具体发布服务配置随目标环境确定。

`make verify` 包含真实 MySQL 识别并发检查：同题去重、不同题并发、范围冲突与原图保护。检查只建立独立临时数据，完成后清理，不调用远程 AI；也可单独运行 `make verify-recognition-concurrency`。

## 4. 安装完整功能

安装 Python Conda 环境和前端依赖：

```bash
make install
```

该命令会创建 `minddimension` Conda 环境，安装 FastAPI、OpenCV、MySQL 驱动等后端依赖，并执行 `pnpm install`。

启动项目内 MySQL，执行迁移和初始化：

```bash
make mysql
make migrate
make seed-knowledge
```

说明：

- MySQL 使用 `127.0.0.1:3307`，数据保存在 `mysql-data/`。该目录已被 Git 忽略。
- 旧版 `.mysql-data/` 会在数据库停止后，由 `make mysql` 整体改名迁移为 `mysql-data/`；已有运行实例会继续复用。迁移保留所有表和日志，不删除 UNDO 文件。MySQL 8.0 的启动扫描会忽略隐藏目录，因此不要把数据目录改回以点开头的名称。
- `make seed` 创建知识卡、家长、教师、管理员和演示数据。
- `make fresh-student` 创建空白学生 `1@1.com / 123`；重复执行会清空这个学生已有的学习数据。
- `scripts/start_mysql.sh` 需要当前用户能够执行 `runuser`、`chown` 和 `mysqld`。普通 Linux 主机可使用 `sudo make mysql`，但后续后端不要使用 sudo 启动。

## 5. 模型说明与下载

当前功能使用以下模型与服务：

| 模型/服务 | 使用方式 | 对应功能 |
|---|---|---|
| `Qwen` | CSU API 池远程调用 | 拍题结构化识别、分析、诊断和教学 |
| `BAAI/bge-m3` | 本地下载 | 真实题库向量检索 |
| `BAAI/bge-reranker-v2-m3` | 本地下载 | 对候选相似题重新排序 |
| `faster-whisper small` | 可选，本地下载 | 保留的后端语音转写，当前学生端无入口 |
| edge-tts | 可选，联网调用 | 保留的后端讲解语音，当前学生端无入口 |

### 5.1 保留的语音能力（可选）

```bash
make download-voice
```

当前学生主流程无需此步骤。该命令供维护保留的后端语音接口时使用，会下载 `faster-whisper small`，保存在 `.models/faster-whisper/`。文字转语音使用 edge-tts，需要网络。

### 5.2 真实题库检索（必须）

```bash
make install-retrieval
make download-retrieval-models
```

这会安装独立的 `minddimension-retrieval` 环境并下载 BGE-M3 和 BGE reranker。完整系统需要它们为 CMM-Math、M3KE、CMMU 题库提供真实相似题推荐。

## 6. 启动完整系统

`make dev` 会固定启动 Qdrant 与 BGE 推理服务。首次部署可先单独运行下面命令确认检索服务就绪：

```bash
make retrieval
```

在项目根目录运行：

```bash
make dev
```

它会启动：

- MySQL：`127.0.0.1:3307`
- FastAPI：`http://127.0.0.1:8000`
- UniApp H5：`http://127.0.0.1:5173`

上面是默认端口。当前工作区的 `8000` / `5173` 已由其他项目使用，因此本项目 `.env` 已配置 `ZHIWEI_BACKEND_PORT=8001`、`ZHIWEI_FRONTEND_PORT=5174`。`make dev`、后台启动器和 `make verify` 会读取这两个设置，前端代理同时指向对应后端；端口被占用时会明确失败。

本机当前访问地址：

- 前端：http://127.0.0.1:5174
- 后端健康状态：http://127.0.0.1:8001/api/v1/system/health
- API 文档：http://127.0.0.1:8001/docs

新部署可在 `.env.example` 对应的两项中选择空闲端口。启动器只复用标题确认为“错题帮”的服务，避免把其他项目误判为已启动。

如果希望分别启动，打开两个终端：

```bash
make backend
```

```bash
make frontend
```

## 7. 登录账号

下表为演示种子账号说明，不保证仓颉独立库已初始化全部账号。2026-10-17当前仓颉本地库已核验学生 `1@1.com` / `123` 可登录，该账号已有使用记录，不再称为空白账号；`e2e@minddimension.local` 在当前独立库未通过登录核验。新用户可直接注册；教师、家长和管理员按上文专用命令创建。不要把旧Python业务库的登录状态当作仓颉登录状态。

| 身份 | 账号 | 密码 |
|---|---|---|
| 本地学生 | `1@1.com` | `123` |
| 演示学生 | `e2e@minddimension.local` | `123456` |
| 家长 | `guardian@minddimension.local` | `123456` |
| 教师 | `teacher@minddimension.local` | `123456` |
| 管理员 | `admin@minddimension.local` | `123456` |

身份由登录账号在 MySQL 中的角色决定，个人中心不能随意切换身份。

## 8. 导入 20,839 道真实题库

真实题库训练是当前上线功能。每台新机器都必须完成本节，不能用 Mock 数据代替。

### 8.1 检索环境与模型

```bash
make install-retrieval
```

脚本会创建 Python 3.11 Conda 环境 `minddimension-retrieval`：

- 有 NVIDIA GPU 时自动安装 CUDA 12.8 PyTorch。
- 没有 GPU 时自动安装 CPU PyTorch。
- 如需强制 CPU：`RETRIEVAL_TORCH_FLAVOR=cpu make install-retrieval`。

`make retrieval` 读取 `.env` 的 `RETRIEVAL_CONDA_ENV`。本机原独立检索环境有缺失文件，已复用依赖完整的 `minddimension` 环境；原环境、模型缓存和 Qdrant 索引均保留。主环境的 Transformers 5 与 FlagEmbedding 1.4 不兼容，因此仅检索子进程通过 `RETRIEVAL_PYTHONPATH=.runtime/retrieval-packages` 使用项目内的 Transformers 4.57.6、HuggingFace Hub 0.36.2；复用的 Tokenizers 0.22.2 满足版本约束，主环境包没有被替换。启动器会检查服务依赖，不会在环境损坏时宣称检索可用。正式新部署仍建议使用上面的独立环境安装入口。

下载模型：

```bash
make download-retrieval-models
```

会下载：

- `BAAI/bge-m3`
- `BAAI/bge-reranker-v2-m3`

模型保存在 `.models/bge/`，合计需要数 GB 磁盘。下载需要访问 Hugging Face。

设备会自动选择：

- 双 GPU：embedding 使用 `cuda:0`，reranker 使用 `cuda:1`。
- 单 GPU：二者共用 `cuda:0`。
- 无 GPU：二者都使用 CPU，功能可用但导入和检索会明显更慢。

也可在 `.env` 手动配置：

```dotenv
RETRIEVAL_EMBEDDING_DEVICE=cuda:0
RETRIEVAL_RERANKER_DEVICE=cuda:0
RETRIEVAL_BATCH_SIZE=8
```

### 8.2 启动 Qdrant 和推理服务

运行：

```bash
make retrieval
```

服务地址：

- Qdrant：`http://127.0.0.1:6333`
- BGE 推理服务：`http://127.0.0.1:8011/health`

### 8.3 下载并导入公开题库

```bash
make import-question-bank
make map-question-bank
make index-question-bank
```

也可以合并执行：

```bash
make setup-question-bank
```

脚本会自动下载：

- CMM-Math：14,856 道。
- M3KE：4,308 道。
- CMMU：1,675 道。
- 合计：20,839 道。

原始数据和图片保存在 `data/question_bank_sources/`、`data/question_bank_assets/`，不会提交到 Git；Qdrant 索引保存在 `data/qdrant_storage/`。这些内容必须由每位队友在本机下载和构建。

完成后验证：

```bash
make verify-adaptive-practice
```

## 9. 常用开发命令

```bash
make backend          # 只启动后端，支持热更新
make frontend         # 只启动 H5 前端
make test-backend     # 后端测试
make test-frontend    # 前端 Vitest
make build            # 构建 H5
make test-e2e         # Playwright 端到端测试
make audit            # 项目配置审计
make verify           # 常规完整检查
```

前端 App 构建：

```bash
pnpm --dir frontend run build:app
```

该命令生成 UniApp App 构建产物；要生成最终 Android APK，仍需使用 HBuilderX 云打包或配置本地 Android 原生打包环境。

## 10. 手机访问

开发机和手机在同一局域网时，前端用 `--host 0.0.0.0` 启动后，查看终端中的 Network 地址，例如：

```text
http://192.168.1.20:5173
```

云服务器开发时，需要在云防火墙中开放前端端口，或使用 SSH 端口转发：

```bash
ssh -L 5173:127.0.0.1:5173 -L 8000:127.0.0.1:8000 user@服务器地址
```

之后本机访问 `http://127.0.0.1:5173`。

## 11. 常见问题

### `mysqld`、`mysqladmin` 或 `runuser` 不存在

说明系统没有安装完整 MySQL Server/Client，或当前不是 Linux 环境。安装 MySQL 后重新执行 `make mysql`。

### 端口被占用

检查 `3307`、`6333`、`8011`、`8000`、`5173`：

```bash
ss -lntp | grep -E '3307|6333|8011|8000|5173'
```

### BGE 显存不足

将 `.env` 中的批量大小改小：

```dotenv
RETRIEVAL_BATCH_SIZE=4
```

也可以把 reranker 放到 CPU：

```dotenv
RETRIEVAL_RERANKER_DEVICE=cpu
```

### Hugging Face 下载失败

确认服务器能访问 Hugging Face，或在运行下载命令前设置可用的镜像地址：

```bash
export HF_ENDPOINT=https://hf-mirror.com
make download-voice
make download-retrieval-models
```

### AI 调用不可用

登录后进入系统状态页检查模型与服务状态；对应 `/api/v1/system/providers` 接口需要登录凭据。逻辑模型应为 `Qwen`，`text_entries`、`vision_entries` 应大于 0。条目数量只说明配置已加载，实际可用性应以 `make verify-live-ai` 的真实调用为准。

## 12. 不进入 Git 的内容

以下内容体积大或属于运行时数据，克隆后由脚本生成：

- `.env`
- Conda 环境与 `frontend/node_modules/`
- Whisper、BGE 模型文件
- MySQL 数据目录
- Qdrant 数据目录
- CMM-Math、M3KE、CMMU 原始数据和图片
- 用户上传图片
- PDF、Excel 等运行时导出文件

项目运行所需的源代码、数据库迁移、`.env.example`、API 池副本和下载/初始化脚本均会提交到远程仓库。

## 13. 进一步了解

- 系统架构：[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- 本轮完善与验证：[参赛完善说明](docs/competition/2026-10-13-参赛完善说明.md)
- 历史功能审计：[docs/CURRENT_AUDIT.md](docs/CURRENT_AUDIT.md)
- 页面审计：[docs/PAGE_AUDIT.md](docs/PAGE_AUDIT.md)
- 数据库使用审计：[docs/DATABASE_USAGE_AUDIT.md](docs/DATABASE_USAGE_AUDIT.md)


## 当前参赛版验证入口

```bash
make mysql
make migrate
make verify
```

`make verify` 包含后端回归、前端行为测试、代码检查、H5 构建、浏览器流程和真实 MySQL 本地冒烟；不调用外部 AI。浏览器测试会复用已有服务或启动前后端。运行环境限制网络接口检测时可设置 `CI=1` 跳过构建工具的更新检查。

`make verify-retrieval` 使用独立验收学生和手工错题验证真实 BGE/Qdrant 推荐、MySQL 题干与检索记录及答案不提前泄露，要求本地模型已加载和题库已索引；结果写入 `reports/retrieval-smoke-*.json`，不下载模型、不调用远程 AI。

完整 AI 链路单独运行：

```bash
make verify-live-ai
```

需要后端、MySQL 与池内真实模型服务可用。请在交互终端运行，按显示的公开题干独立输入学习任务答案；脚本不读取隐藏评分答案来模拟掌握。验收会新增一名独立学生，并在 `reports/live-smoke-*.json` 保存不含凭据的实际学习证据。一次成功只证明该用例通过，不代表所有学科、图像和答案均正确。额外的向量题库练习依赖 Qdrant、BGE 服务与已导入题库；不要用未运行的历史报告替代当次结果。

新增入口：拍照录入页的“没有图片？手动录入”；错题详情页的“学习档案”。手工题在保存后即可查看和组卷，AI 诊断在用户进入诊断步骤时运行。档案读取已有学习记录，不额外调用模型。

</details>
