# Python统一后端架构设计

## 本轮校准依据

审计日期 2026-11-16，版本 v2。最终源码基线为远程 origin/main 的 `1e116f574a88bb009b618218df23f679adc7a5fe`，父提交为 `b7c684fa48a0c3df84eaacb9243e7138b05fcafa`。旧审计基线 `8dd7630fe88a566345baa67c91879d8edefb73e6` 与该主线分叉。本轮逐文件对比生产源码并复查改变的启动、部署、依赖和测试入口，校准证据见迁移审计校准报告。下文保留的源码摘录经字节对比后沿用。数据库实存 61 表属于上一轮本地环境的只读快照，远程初始化和升级代码定义 51 表，不能将本地快照视为每个部署的必备结构。

当前 main 仅保留两个 Python 测试文件，仓颉单元测试、前端测试目录和旧 smoke/verify 脚本已删除。下文涉及旧测试路径均为历史证据，应在隔离环境恢复或重建相应用例后再验收。迁移成功项仍为零。

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

当前 Makefile 的 backend 仍指向 scripts/cangjie.sh，dev 指向 scripts/final.sh，默认前端端口为 5175。make check 通过 scripts/health.py 检查存活与数据库就绪。main 已移除 make test、make verify、verify-final 等目标，第二阶段需要建立自己的有效测试入口。

部署链已核对为 deployment/competition/prepare_payload.py 把 competition 整个目录复制到 payload/app/deployment，Dockerfile 再 COPY payload/ 到 /opt，因此容器 ENTRYPOINT 的 /opt/app/deployment/entry.py 对应仓库 deployment/competition/entry.py。旧报告“本地入口不存在”的判断有误，本轮纠正。entry.py 初始化专用 MySQL、保留 /data/secrets.json、按 initialized 标记导入 demo.sql，再启动内部算法、仓颉、可选 BGE 与 gateway。gateway.py 转发 api/uploads/reports/livez/readyz 到 8002，静态 H5 来自 /opt/app/web。初始化失败与标记写入之间的重启恢复需单独验收，迁移不能沿用半初始化状态误判逻辑。

prepare_payload.py 同时收集仓颉二进制、SDK/stdx 动态库和 libzhiwei_mysql.so，第二阶段保留旧部署入口，最终阶段逐一去除这些打包依赖。Dockerfile.models 添加检索环境和模型，prepare_exports.py 处理演示导出资料，assemble_delivery.py 生成源码包与说明，迁移后须同步目录选择规则。compose.yaml 与 start.sh 是两套启动入口，start.sh 使用 cuoti-delivery-data/cuoti-delivery-index 卷，Compose 使用项目 data/index 卷，切换时须识别实际卷，禁止把新空卷误当原数据。check.sh 检查服务可达，smoke_delivery.py 会注册、录题和交卷，--ai 还会调用真实模型，只能在独立交付环境使用。

render_math_pdf.cjs 已使用 playwright 而非 @playwright/test，前端 package.json 确实声明 playwright。预览 scripts/serve_build_preview.mjs 使用 ZHIWEI_PREVIEW_PORT/CERT/KEY，并硬校验 service=zhiwei-cangjie，这个检查必须在最终切换阶段适配 Python 身份。

旧 CANGJIE_* 环境变量首轮提供兼容读取，新变量具有明确优先级，避免端口、媒体根路径、数据库或 Qdrant 集合误切。/livez 仅判断进程，/readyz 保留数据库就绪检查，并补充单独的 AI/检索状态。现 /readyz 只检查 010_study_sessions，不能视为所有 013 结构均已核对。
