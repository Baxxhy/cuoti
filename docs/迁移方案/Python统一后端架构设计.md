# Python统一后端架构设计

审计日期 2026-11-16，版本 v1。源码基线 `8dd7630fe88a566345baa67c91879d8edefb73e6`。对象为本地 origin 指向 Baxxhy/cuoti 的工作副本。依据实际源码与只读 MySQL 元数据。方案中的新 Python 业务实现均待开发，未执行迁移或修改数据库。

目标为模块化单体，同一 Python 代码库承担业务 API、应用服务、SQLAlchemy 数据访问和已有计算/Agent 调用。后台 worker 可用相同镜像独立进程运行。BGE 推理和 Qdrant 仍作为外部能力服务，业务事务由 MySQL 管理。

| 层 | 职责 | 迁移来源 |
|---|---|---|
| API | FastAPI APIRouter、认证依赖、Pydantic v2 输入模型、统一异常及响应包装 | main.cj、account_api.cj、http_api.cj、request_fields.cj |
| 应用服务 | 用户、题目、识别任务、诊断、辅导、学习任务、练习、复习、统计、试卷、管理用例及事务 | 功能清单中所有业务函数 |
| 数据访问 | SQLAlchemy 2.x Engine/Session、表映射、显式仓储查询、锁与版本检查 | database.cj 和各模块 SQL |
| 算法 | 图片、数学、判分、诊断、生成、导出、语音等已有函数 | backend-algorithms |
| Agent | LangGraph 编排，接收确定的学习上下文、检查点和动作，返回结果 | learning_workflow.py、learning_task_compute.py |
| 基础设施 | 原密钥兼容、文件安全、模型 API 池、BGE 客户端、Qdrant 客户端 | auth.cj、media*.cj、api_pool.py、retrieval_compute.py |

推荐目录为 backend-python/app/api、application、repositories、models、schemas、infrastructure、workers，保持学习计算代码原模块导入路径至首轮兼容完成。不要复制出第二份算法实现。SQLAlchemy 与 Alembic 是目标新依赖，当前 backend-algorithms/pyproject.toml 尚未声明。

Session 在一次请求或 worker 的一个事务单元内创建，应用服务持有事务边界，仓储函数不自行提交。初期采用同步 SQLAlchemy 与 PyMySQL，数据库阻塞调用放在线程执行的同步业务函数，异步模型调用与阻塞查询的调度要明确。模型计算原则上在释放数据库锁后执行，提交前重新锁定并校验版本。原有跨模型调用事务逐个评估，改动锁边界时必须有并发回归证据。[SQLAlchemy 官方事务说明](https://docs.sqlalchemy.org/en/20/orm/session_transaction.html)

认证兼容旧两段令牌、原密钥及 credential 失效语义。API 路径与 JSON 保持兼容，包括不统一的历史日期格式、空值、布尔与数字。错误处理覆盖 ApiError、输入验证和数据库异常。[FastAPI 官方异常处理说明](https://fastapi.tiangolo.com/tutorial/handling-errors/)

Alembic 先记录现有结构基线，核对 61 张实存表与 51 张代码声明表的差异，历史额外表保持完整。未来授权实施时才创建 Alembic 版本表，当前不执行 stamp 或 DDL。[Alembic 官方方案](https://alembic.sqlalchemy.org/en/latest/cookbook.html)

## 算法与 Agent 的保留方式

learning_workflow.py 已有 StateGraph，eced → student_action → aemt → arpp，并有 confirm 分支。图在每次学生动作后结束，当前图没有业务数据库 checkpointer。Python 业务服务继续持有 learning_tasks 的检查点、lease_token、lease_until、version、active_request 与幂等动作记录。不得直接切换为另一套 LangGraph 持久化，造成双重状态源。

service.py 的 ComputeRequest 明确支持 33 种 operation。迁移前保留 /v1/compute 兼容适配器，逐步把调用改成同进程函数或明确的后台任务，保证 operation 校验、超时、请求大小和结果结构一致。ApiPoolProvider 继续管理 API 池配置，不输出凭据。

可以保留的计算包括 diagnosis_compute/diagnosis_alignment/inequality_compute、dialogue_compute、learning_task_compute/learning_workflow/learning_planner/mastery_tracker、adaptive_practice、practice_generation/practice_alignment、variant_compute、grounded_knowledge、knowledge_lesson_compute、learning_hint_compute、learning_memory_compute、task_visualization_compute、paper_export_compute、voice_compute，以及 learning_core 的数学、视觉、识别、判分、教学与可视化实现。直接复用表示计算逻辑保留，配置、生命周期、文件路径及服务调用适配仍须测试。

retrieval_compute.py 通过 BGERuntime 调用 /embed、/rerank，scripts/retrieval_inference_server.py 使用 BAAI/bge-m3 和 BAAI/bge-reranker-v2-m3。Qdrant 集合与数据库绑定，必须保留集合名称、向量维度、payload、过滤和索引来源。首次迁移不重建索引或改变模型。业务服务准备 MySQL 题库快照，检索层返回候选，再做权限和适用性核对。

## 部署依赖

当前 Makefile 的 backend 指向仓颉，scripts/cangjie.sh 构建 SDK 与 libzhiwei_mysql.so，scripts/final.sh 管理本地进程，frontend/vite.config.js 管理代理。deployment/competition/Dockerfile 使用预打包 payload，镜像启动引用 /opt/app/deployment/entry.py，本地该路径不存在，需核对打包阶段是否生成，不能宣称 Docker 已可复现。Compose 有 app 和 qdrant 两个服务，app 挂载 /data，容器公开端口 8080。替换镜像时同时迁移反向代理、健康检查、MySQL 数据卷、媒体和 API 池挂载。

旧 CANGJIE_* 环境变量首轮提供兼容读取，新变量具有明确优先级，避免端口、媒体根路径、数据库或 Qdrant 集合误切。/livez 仅判断进程，/readyz 保留数据库就绪检查，并补充单独的 AI/检索状态。现 /readyz 只检查 010_study_sessions，不能视为所有 013 结构均已核对。
