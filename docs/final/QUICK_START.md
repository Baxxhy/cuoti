# 当前架构启动指南

适用仓颉业务/MySQL、Python内部算法、uni-app前端。已有可用环境直接从第3步启动；首次安装按第1、2步准备。旧Python业务版的`make install/migrate/dev`不是本指南的安装入口。

## 1. 首次安装依赖

当前仓颉工具链支持Linux x86_64。准备Git、make、C编译工具、curl、unzip、OpenSSL 3、MySQL Server/Client，以及Python 3.11以上（含venv/pip）、Node.js和项目固定的pnpm 11.20.0。仓颉SDK与stdx由已有安装脚本准备。

本次运行环境为Python 3.13.9、Node.js 24.15.0、pnpm 11.20.0；仓颉安装脚本固定SDK 1.0.5与stdx 1.0.5.1。

在项目根目录运行：

```bash
make install-final
bash scripts/install_cangjie.sh
bash scripts/install_cangjie_mysql.sh
```

`install-final`只负责`.venv`中的Python依赖和锁定的前端依赖；已有`.venv/bin/python`会复用，不改数据库或私有配置。需要指定Python时可用`make install-final FINAL_PYTHON=python3.13`。下载依赖和仓颉工具链需要网络；不要将本轮环境验证理解为已在所有Linux发行版上完成安装测试。

## 2. 准备独立MySQL与配置

先启动自己安装的MySQL。应用只使用独立的`zhiwei_cangjie`前缀数据库，不使用SQLite。

已有本项目本地MySQL实例、root无密码socket管理连接，且还没有`.env.cangjie`和独立库时，可以运行：

```bash
.venv/bin/python scripts/setup_cangjie_local.py
```

该入口默认连接`.mysql-run/mysqld.sock`和3307端口；可通过`CANGJIE_TEST_MYSQL_SOCKET`、`CANGJIE_TEST_MYSQL_PORT`指定实际实例。它建立全新独立库、专用账号、0600私有配置和知识卡；拒绝覆盖已有配置、库或账号。它不负责安装或启动MySQL。

其他MySQL安装方式：手工建立独立空库和仅有该库权限的账号，复制`.env.cangjie.example`为`.env.cangjie`，填写自己的数据库地址、端口、账号和密码，然后在项目根目录执行：

```bash
set -a
source .env.cangjie
set +a
bash scripts/cangjie.sh init-db
bash scripts/cangjie.sh seed-knowledge
```

已有仓颉库使用`bash scripts/cangjie.sh upgrade-db`，不重复初始化非空库。当前就绪表版本为`009_task_sources`。变量和工具链细节见[仓颉说明](../../backend-cangjie/README.md)。

## 3. 启动并使用

```bash
make dev-final
```

打开终端输出的H5地址；端口由`.env.cangjie`决定，不固定照抄旧版5173地址。另一个终端运行：

```bash
make check-final
```

仓颉业务、MySQL/表版本、Python算法、前端四项均通过后，注册学生账号，从“今日 / 错题 / 学习 / 我的”使用。Ctrl+C停止本次启动的三端服务，MySQL独立管理。

- 先手动录入一道题，核对题目与当时作答；有模型配置时分析诊断并进入本题学习，进度由后端保存。
- 在学习页进入练习、复习、知识和组卷；报告依据真实作答记录形成，初始空记录属于正常状态。
- 教师、家长和管理员使用[专用账号入口](LOCAL_IDENTITIES.md)。家长查看学生报告需要学生明确授权。

模型逻辑名称固定`Qwen`，请求通过项目配置的`ApiPoolProvider`轮询。OCR、分析诊断与智能教学需要有效池配置；手动保存题目不需要调用模型。`check-final`不消费模型探测，因此四项就绪不等于外部模型或检索已经可用。

提交包只包含安全示例`backend/config/api_pool.example.json`，不包含实际凭据。首次配置且没有私有池文件时，复制示例为`backend/config/api_pool.json`，填写自己的服务地址和凭据，保持`model`为`Qwen`，并把已配置条目的`disabled`改为`false`；可添加多个条目，由ApiPoolProvider统一轮询。不要覆盖本机已经可用的池文件。实际文件已被Git忽略，只保留在后端，不发给前端或随提交包分发。示例默认禁用且凭据为空，不能直接调用模型。

真实题库/BGE/Qdrant按[题库准备说明](QUESTION_BANK_IMPLEMENTATION.md)另行准备；内部语音按[语音记录](VOICE_RUNTIME_IMPLEMENTATION.md)按需核验，不是学生界面的必要入口。

## 4. 检查与恢复

完整软件验收使用`make verify-final`，会创建并清理随机独立测试库，需要相应MySQL管理连接和浏览器运行环境。已有验证与未覆盖边界见[系统运行说明](SYSTEM_DELIVERY.md)和[验收矩阵](ACCEPTANCE_MATRIX.md)。

首次运行浏览器验收前安装对应Chromium及其Linux运行库：`pnpm --dir frontend exec playwright install --with-deps chromium`。该步骤需要网络和系统依赖安装权限，仅用于开发验收，不是学生打开H5页面的前置要求。

| 遇到的问题 | 处理方式 |
| --- | --- |
| 找不到`.venv/bin/python`或依赖 | 回到第1步运行`make install-final`；不要改用旧业务版启动命令 |
| MySQL/表版本未就绪 | 检查实际数据库连接；新空库显式初始化，已有仓颉库显式升级 |
| 端口已占用 | 停止自己确认的旧服务，或在私有配置中调整对应端口后重新启动 |
| OCR/模型/题库不可用 | 检查对应真实资源配置；不以演示内容冒充成功 |
| 学习或复习提交失败 | 保留当前作答，按页面提示核对任务/历史状态后重试 |

本指南交付H5运行系统；手机签名安装按用户要求后置，App资源编译不代表已生成安装包。备份恢复不在本次范围。
