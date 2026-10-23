# 错题帮

面向初一至高三学生的个人错题学习应用。当前只保留一条运行主线：**uni-app + Vue 3 前端 → 仓颉业务服务/MySQL → Python内部算法服务**。旧Python业务后端及其备份入口已删除。

## 功能

- 拍照、选图或手动录题，框选、OCR核对，保留原图、选项及作答步骤。
- AI分析、首错定位、错因回放、分步订正、提示和独立重做。
- 根据错题匹配类似题，缺少合格候选时生成并核验，支持连续练习及结果恢复。
- 题库练习、模拟考试、到期复习、知识卡、个人知识关系与易错地图。
- 学习记录、学习报告、个人资料，以及错题组卷、PDF/答案卷/Excel导出。

不提供老师、家长关联或班级作业。AI请求使用xiaojing提供的gpt-6-luna并经过API池轮询；模型不可用或题目无法核验时明确提示，不伪造结果。

## 目录

| 目录 | 用途 |
| --- | --- |
| `frontend/` | 学生页面、公共组件、公式渲染与浏览器测试 |
| `backend-cangjie/` | 唯一业务后端、MySQL结构、知识内容及原生测试 |
| `backend-algorithms/` | 独立Python算法服务及测试；共用模块在`learning_core/` |
| `config/` | API池示例；实际`api_pool.json`不提交Git |
| `scripts/` | 当前安装、启动、导入、检索和验收脚本 |
| `docs/final/` | 当前架构、运行方法和清理验收记录 |

数据库、学生原图、导出文件、题库图片、模型和已安装依赖是本地运行资料，不是废弃源代码。清理不会删除这些资料，也不会丢弃其他Git工作树的工作。

## 安装与启动

需要Linux、Python 3.11+、Node.js、pnpm、MySQL 8、C/C++工具链和仓颉SDK。项目根目录执行：

```bash
make install
make install-cangjie
make mysql
```

全新环境且没有`.env.cangjie`时，可用`make setup-local`安全创建独立数据库、配置和知识内容；它拒绝覆盖已有配置或数据库。已有环境沿用现有`.env.cangjie`，不要重复初始化。

把实际API池保存到`config/api_pool.json`，结构参考`config/api_pool.example.json`；也可设置`CANGJIE_API_POOL_PATH`。配置内容仅供算法服务使用，不放进前端。

```bash
make dev
make check
```

默认前端`http://127.0.0.1:5174`，仓颉8002、内部算法8012；以`.env.cangjie`实际配置为准。学生通过页面注册账号。安装资源后的App构建不等于已完成手机签名发布。

## 题库与检索

已有MySQL题库及`data/question_bank_assets/`直接使用。补充本地题库文件后，运行`make setup-question-bank-cangjie`；只通过仓颉写入数据，不启动Python业务后端。导入与格式审计工具保留在`scripts/`。

启用BGE检索时使用`make install-retrieval`、`make download-retrieval-models`、`make retrieval`，需要Docker中的Qdrant和独立检索环境。语音模型可用`make download-voice`准备。已下载的模型与索引应保留。

## 构建与验收

```bash
make test
make build
make verify
```

`make verify`与`make verify-final`为同一完整入口，包含前端测试/类型检查/H5与App资源构建、算法、仓颉原生测试，以及隔离MySQL的接口和真实浏览器验收。默认不调用真实模型，不修改实际学生数据库。需要可连接的本地MySQL管理socket，默认`.mysql-run/mysqld.sock`。

当前实现与验证范围见[交付记录](docs/final/IMPLEMENTATION_STATUS.md)。

模型密钥通过算法服务进程的 `XIAOJING_API_KEY` 环境变量提供；API池使用 `api_key_env` 引用，不在示例配置中保存密钥。修改模型配置后需重启算法服务。
