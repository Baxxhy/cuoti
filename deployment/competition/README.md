# Python 竞赛运行包

日期：2026-11-17；版本：v2.0。

部署入口已改为 Python + FastAPI，复用现有算法和 MySQL 结构，不打包仓颉可执行文件、SDK、运行库或原生桥接。前端仍是原 uni-app H5 构建。`gateway.py` 仅提供静态页面并转发请求，业务和数据库访问都在统一 Python 后端。

运行用户按《部署说明.md》或同名 Word 文档操作。新镜像标签为 `cuoti-python:20261117`，Qdrant 镜像沿用已有公开索引服务。没有模型凭据时可启动基础页面并保存手动错题，AI 请求需要有效配置。

## 构建

以下收集工具面向已有依赖的 Linux x86_64 构建主机，不是评委安装脚本。使用项目 Python 3.13 环境运行，提前完成 `make install install-browser build`；MySQL 服务和客户端工具也需安装。

```bash
.venv/bin/python deployment/competition/prepare_payload.py
# 上下文必须为空；可用 --context 指定新的目录，不覆盖旧程序包。
docker build --pull=false --network=none -t cuoti-python:core-20261117 .runtime/python-delivery/context
.venv/bin/python deployment/competition/prepare_exports.py --check-image cuoti-python:core-20261117
.venv/bin/python deployment/competition/prepare_models.py --source-image 已有公共模型镜像
docker build --pull=false --network=none -t cuoti-python:20261117 .runtime/python-delivery/models-context
```

核心资源来自当前 Python 环境、MySQL 安装和真实 Node/Chromium 排版环境，包含 Python 后端自己的 SQL 与知识卡资源。收集工具解析动态库；构建后的 `--check-image` 会在镜像内实际生成数学 PDF；不会读取 `.env`、真实模型池配置或学生数据。

模型收集工具只从已有镜像复制 `/opt/retrieval`、`/opt/app/.models/bge` 和 `/opt/app/.models/faster-whisper`，不启动原业务程序，也不复制原业务代码、数据库、密钥和仓颉运行库。首次迁移可以复用原交付镜像中的这些公共组件；以后可以直接使用已验收的 Python 模型镜像作为缓存来源。模型来源镜像 ID 会记录在构建上下文中，不把复用模型描述为自行训练或重新实现算法。

`prepare_exports.py` 为核心上下文收集原公式渲染代码、前端依赖、Chromium 和中文字体；无需另外构建旧版的导出补丁镜像。核心镜像也可配置外部 BGE HTTP 服务；完整镜像同时附带原 CPU BGE 环境和语音模型缓存。

## 交付组装

Word 文档构建需要 `python-docx`：可在构建环境安装 `./backend-python[delivery]`，或使用已安装该库的 Python。该额外依赖不要求在业务运行环境安装。

```bash
.venv/bin/python deployment/competition/assemble_delivery.py
docker save cuoti-python:20261117 cuoti-qdrant:20261023 | gzip > .runtime/python-delivery/bundle/错题帮_Python可运行程序包/images.tar.gz
```

组装工具生成中文部署文档和公开源码 ZIP，源码包含 `backend-python`，不包含仓颉源目录、安装脚本、真实配置及数据卷。仅从 Git 已跟踪文件组装源码，应在阶段提交完成后运行。镜像和离线模型不推送 Git。

`start.sh` 使用原数据卷及持久密钥；更新已有容器前先停止服务并对整个卷做冷备份，失败时保留并恢复旧容器。缺少历史升级时默认拒绝修改结构，显式开启 `CUOTI_UPGRADE_DB=true` 后由 Python 升级命令先做 SQL 备份再执行。不会重新初始化非空数据库。

实际验收以迁移报告为准。`smoke_delivery.py` 只应指向自己的独立验收容器，会注册临时用户并录入测试数据；`--ai` 会调用真实模型。健康响应不代表模型加载完成或输出质量通过。
