# 错题帮

## 迁移状态（2026-11-16）

已确定目标路线为 **uni-app + Vue 3 + TypeScript → Python + FastAPI → SQLAlchemy 2.x + MySQL**，使用 Alembic 管理数据库迁移，复用 backend-algorithms，使用 LangGraph 编排教学 Agent，使用 BGE + Qdrant 检索。

目前已完成迁移审计、校准、Python骨架与账号认证迁移。Python服务已支持账号认证、个人资料、学习偏好、错题录入管理、图片上传裁剪、识别任务及原算法计算入口，学习任务等业务继续分阶段迁移。下文介绍的是仍在使用的仓颉运行实现及其启动方法。迁移期间旧代码作为兼容参照，后续停止新增仓颉业务功能，最终移除全部仓颉运行依赖。

骨架范围见 [第二阶段实施指令](docs/迁移方案/第二阶段实施指令.md)，审计差异见 [迁移审计校准报告](docs/迁移方案/迁移审计校准报告.md)。

面向中学生的个人错题学习系统：uni-app 学生界面，仓颉业务服务与 MySQL，Python 内部算法服务。Python 算法不读写业务数据库。

## 本次提交

在远程精简交付版 f3fdec2 的基础上补齐已在评审程序包中验证的运行改动：

- 支持 xiaojing 的模型配置与 XIAOJING_API_KEY 环境变量读取，实际模型为 gpt-6-luna。
- 服务元信息返回配置中的实际模型名称。
- Excel 导出与前端保持相同的分数公式控制字符修复规则；其他非法控制字符作为输入错误处理。
- 补充对应回归测试及公开部署脚本、依赖清单和部署说明。

评审镜像的源码构建基线为 899b0f60705aafac8ed415ee72278ff1e1559b77；本仓库保留精简版构建与开发入口，不恢复历史文档、视频和测试素材。文档中的 d01d742 为此前文档核对基线；上述改动是后续运行修复。

## 运行方式

已领取评审程序包时，按包内《部署说明.docx》运行 start.sh。运行镜像和模型文件通过评审渠道提供，不存放于此仓库。公开部署资料见 [deployment/competition](deployment/competition/README.md)。

从源码启动时，使用根目录 Makefile 中的 install-cangjie、install、install-browser、mysql、setup-local、dev 与 check 入口。复制 config/api_pool.example.json 为本机 config/api_pool.json，并在运行环境中设置 XIAOJING_API_KEY；也可以写入仅保存在本机的 .env.cangjie。数据库与内部服务配置参照 .env.cangjie.example。默认前端端口为 5175。

AI 请求需要有效密钥、额度和网络；此仓库不提供真实密钥或学生数据。不要将含密钥的评审程序包、.env 或实际 api_pool.json 提交到 Git。

## 本次回归测试

安装算法开发依赖后执行：

```bash
PYTHONPATH=backend-algorithms python -m pytest backend-algorithms/tests -q
```

本目录当前测试覆盖模型配置、环境变量凭据读取和 Excel 控制字符处理；测试通过不代表任意新题均可正确诊断。

## Python 后端骨架

骨架默认监听127.0.0.1:8003，原业务服务继续使用原入口。安装、启动和测试命令见 [第二阶段完成与验证记录](docs/迁移方案/第二阶段完成与验证记录.md)。默认读取项目根目录 .env.cangjie，可通过 CUOTI_ENV_FILE 指定已有本地开发配置；CUOTI_DB_* 环境变量优先。暂无数据库时 /livez 可用，/readyz 返回503，仍可运行模拟测试。

## Python 账号认证迁移

新服务继续独立监听8003，支持原 `/api/v1/auth/*` 和 `/api/v1/student-preferences` 路径，沿用现有MySQL表、密码哈希与令牌格式。默认读取.env.cangjie以及同目录.runtime中的原认证/算法密钥文件，CUOTI_AUTH_SECRET和CUOTI_ALGORITHM_SECRET可以显式覆盖。切换环境时应使用原密钥以保持令牌兼容。

```bash
CUOTI_ENV_FILE=/绝对路径/.env.cangjie .venv/bin/python -m cuoti_backend
CUOTI_ENV_FILE=/绝对路径/.env.cangjie .venv/bin/python -m cuoti_backend.manage_user --email admin@example.test --check
```

移除管理员命令中的--check后交互输入密码可创建专用管理员，命令不会改动已有账号。原算法处理器在同一Python进程提供 `/v1/compute`，继续要求独立算法Bearer密钥。

测试和备份记录、接口范围与后续安排见 [账号认证迁移完成与验收记录](docs/迁移方案/账号认证迁移完成与验收记录.md)。

## Python 错题录入与识别迁移

已接入原错题列表、详情、手动录题、编辑归档、上传、裁剪、OCR、人工核对和任务查询重试接口。列表保持原数组格式与去重规则，支持page/page_size、subject、grade、question_type、knowledge_point、search及sort（created_at、updated_at、oldest），分页后批量查询附属信息，避免逐题重复查库。

手动录题、编辑及人工核对支持可选correct_answer、explanation、source_info，保存为未核验的人工参考资料。POST /api/v1/questions/{id}/images支持为已有题目补图，replace=true可替换识别主图，defer_processing=true可先裁剪再识别；原始字节与旧文件均保留。正文或参考资料修改时保留历史分析、诊断与步骤快照，不清除学习会话和复习记录。

图片继续使用现有uploads/reports目录与签名规则。CUOTI_MEDIA_ROOT可指定存储目录，默认定位到配置文件所在项目的backend-cangjie/media。迁移验证复用了现有数据库，前端仍连接原服务。启动命令继续使用python -m cuoti_backend，当前采用单进程、两个识别线程。

CUOTI_COMPUTE_TIMEOUT控制单次内部算法调用超时，默认200秒。媒体沿用有效签名链接访问；携带Bearer时额外校验所有权，匿名有效签名链接仍可访问，以兼容现有图片标签。

完整功能对照见 [第三阶段全面迁移对照清单](docs/迁移方案/第三阶段全面迁移对照清单.md)，最新验证见 [第三阶段全面迁移验收报告](docs/迁移方案/第三阶段全面迁移验收报告.md)。真实手写根式存在识别错误，已验证人工纠正和确认保存；不能把流程跑通视为识别质量已达标。上一轮记录保留在 [第三阶段迁移完成与验收报告](docs/迁移方案/第三阶段迁移完成与验收报告.md)。

## Python诊断迁移进度

已接入analyze、diagnose、diagnosis读取和diagnosis/history，复用现有算法并保存分析与证据。一个真实模型业务闭环通过；完整第四阶段尚未验收，识别质量检查、知识关联、反事实独立入口及评测仍待补齐。详见[第四阶段诊断业务接入进度](docs/迁移方案/第四阶段诊断业务接入进度.md)。

2026-11-17补充：已迁移学生作答提交、诊断人工修订、独立反事实入口和知识关联同步。范围及实际测试见[诊断与作答迁移补全记录](docs/迁移方案/诊断与作答迁移补全记录.md)。全量业务及部署迁移仍在进行。

知识库列表/详情、个人知识框架、首页概览及统计overview已迁移，保持原数据契约；新旧服务内容对照和范围见[知识库与学习概览迁移记录](docs/迁移方案/知识库与学习概览迁移记录.md)。

知识卡AI讲解与历史已接入Python，保留来源版本校验、请求幂等及用户隔离；已完成真实模型生成保存查询和旧服务重放验证，见[知识讲解业务迁移记录](docs/迁移方案/知识讲解业务迁移记录.md)。

教学会话创建、读取及阶段前进/返回已开始接入Python，并补齐诊断知识卡上下文；答题、对话、迁移练习和教学完成仍待迁移，具体限制见[教学会话迁移记录](docs/迁移方案/教学会话创建读取与阶段迁移记录.md)。

近/远迁移练习的生成、复验与历史保留，以及讲清评估入口已接入Python；包含原检索适配和不可用回退，见[迁移练习接入记录](docs/迁移方案/迁移练习生成与讲清评估接入记录.md)。完整答题评分、认知写回和教学对话仍待迁移。

教学活动答题、近/远迁移评分、认知与复习计划写回、重复完成幂等已接入Python，来源指纹完成旧服务对照修复。范围与测试见[教学答题及完成迁移记录](docs/迁移方案/教学答题认知与完成业务迁移记录.md)。教学对话和学习任务等迁移继续进行。

教学对话与来源校验的学习记忆已接入Python，真实Agent对话单例通过。范围及限制见[教学对话与学习记忆迁移记录](docs/迁移方案/教学对话与学习记忆迁移记录.md)。

学习任务掌握度证据及复习写回已实现，尚待整合至完整任务提交事务与后台执行循环。见[本次迁移记录](docs/迁移方案/学习任务掌握度与复习写回迁移记录.md)。

学习任务结果保存已整合为调用方控制的事务，包含照片确认步骤与失败回滚；后台执行循环和任务 API 尚待接通。见[结果事务迁移记录](docs/迁移方案/学习任务结果事务迁移记录.md)。

学习任务单次执行流程已连接租约、原算法调用、来源复核和结果事务；持续轮询与公开任务 API 继续迁移。见[执行流程记录](docs/迁移方案/学习任务单次执行流程迁移记录.md)。
