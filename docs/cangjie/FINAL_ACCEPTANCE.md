# 仓颉既有接口迁移验收

日期：2026-10-16。范围：保留原 Python 版本，将既有业务接口、权限、MySQL 读写及教学流程迁移到独立仓颉后端，Python 承担模型和专业计算。

当前状态：94/94 条有效业务接口已实现并通过 HTTP/MySQL 回归；仓颉模式浏览器联调18项通过、4项按原配置跳过。

## 接口范围与证据

原始清单 103 条，经用途审计移除 9 条未使用入口，保留 94 条。全部条目为 verified；逐条方法、路径、仓颉实现和验证脚本见 [routes.json](routes.json)，原清单的页面/脚本/资源用途见 [ROUTE_USAGE.md](ROUTE_USAGE.md)。本轮重新核对了全部 94 条的原生注册路径及实现、验证文件。

| 接口路径分组 | 数量 |
| --- | ---: |
| admin | 3 |
| analytics | 2 |
| answers | 1 |
| auth | 5 |
| dashboard | 1 |
| guardians | 2 |
| jobs | 2 |
| knowledge | 2 |
| papers | 8 |
| practice | 3 |
| questions | 18 |
| reviews | 4 |
| students | 3 |
| system | 4 |
| teachers | 20 |
| tutor | 11 |
| variants | 1 |
| visualizations | 2 |
| voice | 2 |

## 验收记录

| 要求 | 当前证据 |
| --- | --- |
| 仓颉执行全部业务接口及权限 | 原生注册路径核对；完整 HTTP/MySQL 回归覆盖学生、教师、家长、管理员和跨账号拒绝 |
| 仓颉读写业务 MySQL | 参数化原生驱动、48 表及升级版本 005；各业务真实落库、回滚、旧结果拒绝与重启恢复 |
| Python 只做专业计算 | 算法测试检查未加载旧 ORM、数据库、业务入口或配置；原算法独立参考进程对照；运行时只提供内部 compute 协议 |
| 保留原 Python 版 | 原业务源码和启动命令保留；make verify 通过：297 项后端、76 项前端，类型检查、H5 构建及原有浏览器（18通过、4跳过）/本地流程通过 |
| 模型、数学与资源约束 | ApiPoolProvider/Qwen、Pydantic、SymPy 原规则；原图保留、签名及路径限制；可视化消费 JSON；凭据脱敏检查 |
| 最后练习与检索接口 | BGE/Qdrant/reranker 实际 HTTP 协议；原算法排序对照；推荐缓存/排除/判题、失效迁移题重建、服务不可用和写入失败回滚 |
| 仓颉完整回归 | make verify-cangjie 通过：23 项算法、27 项仓颉原生及完整 HTTP/MySQL，重启与无数据库配置检查通过；最终候选再校验回归见下述日志 |
| 现有页面连接仓颉 | make verify-cangjie-browser 通过：18项浏览器场景通过、4项角色专项按原配置跳过；角色业务另有完整 HTTP/MySQL 回归。使用独立数据库、原生后端、公开知识卡与随机前端端口 |
| 路由与静态检查 | 用途审计生成和 --check、Ruff、diff 检查通过 |
| Git 交付 | 分阶段提交，最终工作区干净；提交版本见 git log，交付时以 git status --short 复核 |

日志：`/tmp/zhiwei-cangjie-candidate-final.log` 为最终候选年级/答案可用性再校验回归，`/tmp/zhiwei-cangjie-retrieval-final.log` 为接口回归，`/tmp/zhiwei-original-verify-20261016.log` 为保留版本检查，`/tmp/zhiwei-cangjie-complete.log` 为仓颉浏览器联调。临时日志不提交，运行命令可重复产生证据。

## 运行与验证

- 原 Python：make backend / make dev / make verify。
- 仓颉：make algorithms-cangjie、make backend-cangjie；先配置独立 MySQL 和内部密钥，详情见 [运行说明](../../backend-cangjie/README.md)。
- 仓颉接口验证：make verify-cangjie。
- 仓颉接口与现有前端联调：make verify-cangjie-browser。

## 验收边界

外部模型、BGE/Qdrant 与语音引擎使用隔离上游验证协议；真实模型效果、真实检索质量和语音质量仍需按实际部署资源验证。新独立库只初始化表结构；公开知识卡可通过 make seed-knowledge-cangjie 初始化；题库、资源文件及索引需要对应准备，不自动复制旧用户数据。检索缺失时明确返回不可用或无候选，教学保留原降级语义。

[最终产品方案](../final/README.md) 中的新增订正、自检和学生试用等继续按其范围验收。本页记录既有接口迁移的结果。未新增并发、性能或部署专项。
