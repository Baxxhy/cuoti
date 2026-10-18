# 错题帮仓颉版（开发中）

独立于原 `backend/` Python 版的新实现。目标是仓颉承担 HTTP API、鉴权、业务逻辑和 MySQL 读写；Python 提供模型池、结构化校验和专业算法服务。原 Python 版保持可用。

当前完成账户、题目管理、图片识别、分析诊断、教学主流程、复习、学习统计、知识卡、组卷、系统状态、管理员与语音流程。精简后的 94 条业务 API 已全部通过真实 HTTP 与 MySQL 回归，原 Python 业务版本保留。外部模型、检索和语音上游使用隔离模拟验证协议；真实模型效果及更大产品计划继续单独验收。`/livez` 只检查进程，`/readyz` 检查实际 MySQL 与表版本；其历史 `ai: not_connected` 字段尚未更新为算法服务探测，不能据此判断模型可用性。

## 安装与验证

当前验证平台：Linux x86_64。工具链固定为官方仓颉 1.0.5 LTS、stdx 1.0.5.1。SDK 安装脚本校验官网 SHA-256；stdx 从官方发布地址下载。下载内容放在 Git 忽略的 `.runtime/` 中，不提交编译器。

```bash
bash scripts/install_cangjie.sh
bash scripts/install_cangjie_mysql.sh
bash scripts/cangjie.sh build
make verify-cangjie
bash scripts/cangjie.sh run
```

默认仅监听 `127.0.0.1:8002`，可通过 `CANGJIE_BACKEND_PORT` 设置。开发环境需要 OpenSSL 3；可以设置 `CANGJIE_OPENSSL_LIB_DIR`，启动器也会尝试使用已有 Conda 基础环境的库。仓颉测试运行器需要本机 socket 权限。

自带工具链可分别通过 `CANGJIE_SDK_DIR`、`CANGJIE_STDX_PATH` 指定 SDK 目录和 stdx 的 `dynamic/stdx` 目录。

## MySQL

仓颉通过一个薄 C ABI 适配器调用 MySQL 官方客户端，SQL、参数绑定、事务边界、数据读取都由仓颉负责，无 Python 数据库代理。当前本机使用 Ubuntu 20.04 的 libmysqlclient 8.0.42（发行版包）；安装脚本仅下载、解压到 `.runtime/mysql-client/`。其他环境可通过 `CANGJIE_MYSQL_CLIENT_ROOT` 指向客户端安装前缀（须包含 include/mysql 和 lib/x86_64-linux-gnu）。

配置使用 `CANGJIE_DB_HOST`、`CANGJIE_DB_PORT`、`CANGJIE_DB_USER`、`CANGJIE_DB_PASSWORD`、`CANGJIE_DB_NAME`，不读取原版 `.env`。库名必须以 `zhiwei_cangjie` 开头。业务启动默认连接 127.0.0.1:3307、zhiwei_cangjie 库与同名账号；密码必须自行配置，账号权限应仅覆盖新库。

创建独立空库与对应用户后，运行 `bash scripts/cangjie.sh init-db`。当前初始化拒绝非空库，不自动删表、导入原用户数据或修改原 Alembic 历史。DDL 中途失败会保留已建表并报错，需要另建空库重试；已有独立仓颉库运行 `bash scripts/cangjie.sh upgrade-db` 应用 `002_work_precision`、`003_diagnosis_precision`、`004_tutor_precision` 和 `005_practice_precision`；升级保留数据、支持重复执行，将作答、诊断、教学消息和推荐时间提升为微秒精度以可靠读取连续保存的新版本。新库自动应用，`/readyz` 当前要求 `009_task_sources`（包含006任务、007自检、008手写与009来源迁移）。初始建表中断恢复与后续版本升级需按各自迁移处理。

`make verify-cangjie` 通过本机 MySQL socket 的 root 账号创建随机测试库和仅有该库权限的随机测试账号，执行初始化、原生测试和 HTTP 冒烟，然后自动清理。可通过 `CANGJIE_TEST_MYSQL_SOCKET`、`CANGJIE_TEST_MYSQL_PORT` 指定测试实例。原生数据库测试使用临时表，还会拒绝非 `zhiwei_cangjie_test` 前缀的库。

迁移范围与验收定义见 `docs/cangjie/MIGRATION.md`。原 Python 版的数据与运行入口保持不变。

## 已实现的业务接口

- `POST /api/v1/auth/register`、`POST /api/v1/auth/login`：账户和学生档案落入独立 MySQL，注册角色固定为学生。
- `POST /api/v1/auth/reset-password`：要求当前密码，事务中锁定账户更新密码；旧凭据签发的会话随即失效。
- `GET/PATCH /api/v1/auth/me`：按签名和当前密码摘要验证会话，仅允许更新当前账户姓名。
- `POST /api/v1/questions/manual`：学生可录入综合/单选/多选题，题目、作答、步骤在同一事务内保存，校验选项标记和数量、文字长度及角色，不触发模型调用。
- `DELETE /api/v1/questions/{question_id}`：验证所有权并锁定题目，同一事务内归档和取消待复习计划；保留作答与已完成复习，支持重复请求。
- `GET /api/v1/questions/{question_id}`：校验所有权后读取题目、资源分组、OCR、分析与参考步骤、诊断与证据、作答步骤、批注和识别任务；返回保留类型的 JSON。返回的资源签名链接可访问独立文件目录中的文件。
- `GET /api/v1/questions`：当前账户未归档题目，支持学科筛选、题干/标签/知识点/诊断搜索、中文错因名称映射、重复题合并，返回诊断、掌握度、复习、缩略图签名和最新任务摘要。
- `PATCH /api/v1/questions/{question_id}`：只更新白名单字段；修改题干、作答等学习内容时，在锁定题目的事务中清除旧分析/诊断/推荐并标记历史学习记录过期，保留原图、作答和对话。标题/收藏/标签修改不清除学习结果，相同内容不触发失效。输入上限 8 MiB；已归档题目返回 409，避免编辑使其重新激活。与原版一致，此接口校验 student_steps/teacher_marks 但不更新这些记录，需使用专门接口（尚待迁移）。
- `GET /api/v1/jobs/{job_id}`：按关联题目的所有权读取任务状态、进度和错误；未登录 401，跨账号及不存在任务 404。上传识别已接入任务创建、执行和重试。

- `POST /api/v1/questions/ingest`：接收 multipart 图片，保存独立原图；延迟处理返回 awaiting_crop，否则创建异步识别任务。识别结果经 Python 计算服务校验后由仓颉事务落库；失败保留原图，编辑/归档取消过期结果，重启标记中断任务。

- `POST /api/v1/jobs/{job_id}/retry`：仅重试本人未归档题目的失败识别任务；复用已有活跃任务，并发重试只启动一次。优先裁剪图，仅上传识别可回退原图，缺少图片返回 422。

- `POST /api/v1/questions/{question_id}/ocr`：必须已有裁剪图，同步完成识别并返回任务与题目；已有活跃任务则直接复用。
- `POST /api/v1/questions/{question_id}/reprocess`：基于裁剪图异步重新识别，返回任务 ID；并发请求复用同一活跃任务。裁剪接口已接入。

- `POST /api/v1/questions/{question_id}/crop`：校验归一化范围、保存独立裁剪图并启动识别；相同范围的活跃任务复用，不同范围返回 409。重新框选和数据库失败均保留原图；旧裁剪文件暂保留，尚未实现过期资源回收。

- `POST /api/v1/questions/{question_id}/draft`、`/confirm`：保存人工核对内容与新的作答版本，保留历史步骤；内容变化清除过期学习结果，核对操作取消旧识别任务，确认要求非空题干。支持空请求体，归档题目拒绝修改。

- `POST /api/v1/questions/{question_id}/analyze`：要求本人已确认的非空题目，使用最新作答和裁剪/原题图片计算；事务保存分析、参考步骤及知识点关联，内容变化或归档时拒绝旧结果，失败保留先前分析。

- `POST /api/v1/questions/{question_id}/student-work`：保存新的答案、说明和步骤版本，保留历史；事务内清除过期学习结果、取消旧识别与待复习任务。人工步骤标记为用户来源，归档题目拒绝提交。

- `POST /api/v1/questions/{question_id}/diagnose`：自动补齐缺失分析，计算诊断和反事实验证后事务保存证据、历史与知识点关系；输入变化时拒绝过期结果。
- `GET /api/v1/questions/{question_id}/diagnosis`：按所有权读取最新诊断、步骤证据和反事实结果，无诊断返回 null。

- `PATCH /api/v1/questions/{question_id}/diagnosis`：只修正本人最新诊断的白名单字段，校验步号、置信度及文字，标记人工确认并记录本次修正；保留历史诊断和原计算证据。归档题目拒绝修改，正在计算的旧诊断不能覆盖人工修正。

- `POST /api/v1/questions/{question_id}/diagnosis/counterfactual`：复用已有结果，缺失时计算并事务保存；并发计算只保存一份记录，保留步骤证据，内容或诊断变化后拒绝旧结果。

## 内部算法边界

`src/algorithm_client.cj` 通过带独立密钥的回环 HTTP 调用 `backend-algorithms/`，支持图像处理、Qwen 结构化识别、题目分析、诊断/反事实计算和 SymPy 计算，不把业务数据库交互交还 Python。配置和操作协议见 `backend-algorithms/README.md`。目前已接入上传识别：仓颉负责任务、原图与派生资源保存、结果事务落库及中断恢复。模型可用性尚未纳入 `/readyz`。

原生测试现在还需要独立算法服务环境；优先运行 `make verify-cangjie`，它自动配置、启动并清理测试服务，原生测试使用缺失的测试模型池，HTTP 上传测试随后接入临时本地模拟模型池，避免调用真实远程模型。

`schema/column_types.json` 是开发时从原模型提取的字段类型快照，`schema/error_taxonomy.json` 保存原版错因编码与中文名称，仓颉运行时直接读取，不启动 Python。开发环境可用 `.venv/bin/python scripts/snapshot_cangjie_contract.py` 同步这两个快照和测试默认值；模型变更时需同时审查 SQL schema 版本，快照生成不会修改数据库。

会话密钥优先使用 `CANGJIE_AUTH_SECRET`（至少 32 字符）；未设置时启动器在 `.runtime/cangjie-auth-secret` 创建独立持久密钥，文件权限 0600、加锁初始化，重启复用。它与原 Python 版密钥独立。只有明确使用相同密钥和对应账户凭据时，两版令牌格式才可互认；默认不会共享登录。

密码采用原版 PBKDF2-HMAC-SHA256、210000 次迭代和随机 16 字节盐；令牌使用 HMAC-SHA256 并绑定当前密码摘要。OpenSSL 只提供密码学原语，账号策略、令牌解析、权限与数据库操作由仓颉实现。

## 独立资源目录

`GET/HEAD /uploads/*` 和 `/reports/*` 使用四小时 HMAC 签名链接。默认根目录为 `backend-cangjie/media/`（启动器切换到仓颉目录），分别读取其中 `uploads/`、`reports/`；可用 `CANGJIE_MEDIA_ROOT` 指定独立目录，建议绝对路径。不会自动读取或复制原 Python 版上传文件。上传及报告生成由对应仓颉接口完成，原始上传不会被清洁图覆盖。

文件采用 64 KiB 分块发送，不将大文件整体读入内存；支持 HEAD、单段 Range、If-Range 和 ETag/If-None-Match。多个 Range 段回退到完整 200 响应；不提供目录索引。每个请求先验证签名，再逐级 openat 打开路径，拒绝 `..`、符号链接、目录和非普通文件。原生 C 适配层只负责 POSIX 文件操作，签名和 HTTP 行为由仓颉实现。

验证脚本使用自动清理的临时目录，检查大文件内容、中文路径、链接过期与篡改、越界路径、符号链接、FIFO、缓存校验和中途断开后的文件句柄释放。静态资源挂载不属于 103 条 API 清单，单独记录于 `docs/cangjie/resource_routes.json`。

题目分析已接入仓颉权限、事务落库、参考步骤验证标记和已有知识点关联；当前业务路由完成数为 94/94，教学及练习主流程已接入。

诊断生成与读取已接入仓颉证据落库和知识点关联更新；人工修正及独立反事实触发也已接入。

教学活动基础逻辑位于 `src/tutor_policy.cj` 和 `src/tutor_activities.cj`：仓颉决定教学模式、生成理解计划并过滤公开进度/活动字段。固定文案存于 `schema/teaching_templates.json`，开发时使用 `.venv/bin/python scripts/snapshot_cangjie_teaching.py` 更新文案快照与原版对照测试；运行时不依赖此脚本。教学会话创建、读取恢复和后续活动已接入。

`POST /api/v1/tutor/sessions` 已接入：仓颉保存教学会话、开场消息与工具记录，返回完整或简短模式开场活动。要求本人未归档且已有有效分析答案的题目，内部判题计划不返回前端。

`GET /api/v1/tutor/sessions/{session_id}` 支持恢复当前会话、活动与消息；近/远迁移缺少练习时自动生成并保存；参考题使用 BGE/Qdrant/reranker，复用旧练习前重新校验数学结论与知识点一致性。

`POST /api/v1/tutor/sessions/{session_id}/variant` 支持生成和复用当前阶段练习，答案和解法只保存在服务端。与读取接口共用检索与重新校验逻辑，检索不可用状态如实记录。

`POST /api/v1/tutor/sessions/{session_id}/advance` 与 `/rewind` 已接入：通过理解检查后进入复述，以及按完整/简短模式返回前一阶段。理解、复述、练习提交和学习总结均已接入。

`POST /api/v1/tutor/sessions/{session_id}/activity/answer` 已接入理解与复述分支，支持提示、辅助确认和进入相似题；已接入相似题、迁移题作答、不会写提示及学习总结，完成后保存掌握度、认知变化与复习计划。已支持教学手写作答图片与识别结果关联，清单标为 verified。

`POST /api/v1/answers/handwriting` 已接入 tutor、review、assignment、practice 场景：上传原图、Qwen 转写、用户与活动校验、签名图片链接；practice 还校验已推荐记录与原题版本。

复习接口已接入：今日列表、提交答案、反馈和历史记录。支持文字/手写答案关联、按原版规则安排下一次复习、查看结果与图片；不可确定的判题结果不能用于更新复习计划。

## 学习档案、知识卡与首页

现有 `GET /api/v1/dashboard`、`GET /api/v1/analytics/overview`、`GET /api/v1/analytics/cognition-graph` 和知识卡列表/详情，共 5 个接口；无调用的统计别名已删除。

- 学习统计读取当前用户的最新掌握度、合并后的错因和 UTC 滚动窗口内的掌握证据趋势，overview 统一返回掌握度、错因和趋势。
- 图谱提供知识点、错题、错因与学习策略及关联，支持学科/时间筛选、个人知识映射和先修关系。已归档题不出现在题目节点或证据连线中。
- 知识卡维持公开读取，支持文字、学科、年级和误解筛选；详情返回先修与后续知识卡，支持中文编码。
- 首页返回待复习、继续学习、学习天数、掌握状态、教师任务数量及未撤销反馈；复习截止和连续学习按北京时间计算。

具体语言能力与验证边界见 `docs/cangjie/CANGJIE_DESIGN.md`。这批只读业务不改写 Python 算法，未做额外并发或性能专项。

## 教师班级与家长报告

已接入班级创建/列表/详情、添加和移除学生、教师首页、学生复习计划查询/调整、教师审计，以及家长关联学生列表、家长概览与教师学生报告，共 12 条 API。教师响应保留原版的直接 JSON 或 envelope 格式，兼容现有前端。

`TeacherScope` 从实际登录账号建立，只允许教师访问本人班级和班内学生；家长读取限定关联学生。班级/成员/计划修改和审计在同一 MySQL 事务完成。计划调整要求填写原因；截止时间由仓颉 `std.time.DateTime` 校验并规范为 UTC，兼容带时区和浏览器 datetime-local 输入。成员移除保留既有任务和审计，教师查看学生报告/计划的权限随班级关联撤销。

教师题库、任务下发、学生作答和人工复核已接入。既有管理员、练习推荐等接口已迁移，验收范围见 `docs/cangjie/FINAL_ACCEPTANCE.md`。

## 接口精简（2026-10-16）

已逐项审计原 103 条路由，移除 9 个未使用的空操作、重复别名与废弃入口，保留 94 条。完整用途见 `docs/cangjie/ROUTE_USAGE.md`，已删除项单列在 `routes_retired.json`，不再计入迁移分母。仓颉当前 94/94 verified，当前证据与范围见 `docs/cangjie/FINAL_ACCEPTANCE.md`。

学生页面使用 `/analytics/overview`；注册、登录、改密和本地退出保留。学生作业所需题库、下发、作答、手写、判题和教师反馈接口保留。本轮不做运维或部署，也不新增页面凑接口调用。

## 作业闭环（2026-10-16）

已接入教师题库列表/录题、作业列表/下发、学生作业列表/提交、教师复核队列/详情/决定及学生反馈历史，共 10 个接口。仓颉负责权限、MySQL 读写、作业状态和审计，Python 仍执行原版判题与认知更新算法。

支持按班级/学生下发、自动批改开关、要求手写、允许重做、教师强制复核、是否计入掌握度，以及正确/错误/部分正确/重交/题目有误五种教师结论。需要复核的结果不会提前写入掌握证据。审核旧作答只更新该作答，不完成学生的新提交；业务变更与审计失败一并回滚。

认知公式已整理到 `backend/app/services/cognition_rules.py`，原 Python ORM 入口继续复用同一算法。仓颉教学完成与作业复核都通过内部 cognition_update 计算，再由仓颉保存结果。旧算法的 54 组固定结果及原 Python 后端 296 项测试通过。

本节记录作业迁移阶段的 HTTP/MySQL 主流程证据；教师撤销、重判与转交均已接入。最新整体接口状态及浏览器证据见 FINAL_ACCEPTANCE.md。

## 错题学习历程（2026-10-16）

`GET /api/v1/questions/{question_id}/journey` 已由仓颉直接读取 MySQL，汇总当前题目的五阶段进度、下一步入口、练习与复习计数及最近事件。`JourneyAction` 枚举集中定义导航分支；数据库先按用户和题目筛选，各类历史最多读取 50 条、最多返回 30 个事件。

题目变更后的旧记录不作为当前证据；待核对结果不作为有效练习或复习；辅助完成不算独立迁移。到期复习按北京时间的当天边界计算。28 组原 Python 固定输出、真实 MySQL/HTTP 的权限与历史上限检查和原接口对照通过。这个接口仅投影持久记录，没有改动 Python 算法。

## 教师复核纠正（2026-10-16）

复核撤销、重新判定和转交三个接口已迁移。`ReviewChange` 枚举集中约束操作分派和审计动作，仓颉完成权限、版本检查及 MySQL 事务。重新判定仍调用原 Python grade_answer，保留原作答和原批改证据；纠正文本和参考答案只作用于本次重判，不改题库标准答案，不提前更新学习。

撤销采用原有条件恢复规则：仅在当前分数/错因概率仍等于该次复核快照时恢复对应数值和计数，后续学习改变该值时保留当前记录；撤销旧作答也不覆盖最新提交。单管理员班级的转交仍只允许当前管理员。三条接口的完整响应（忽略自动更新时间）与原 Python 路由对照通过，权限、版本拒绝、审计失败回滚及学习状态通过真实 HTTP/MySQL 验证。

## 教学收尾与互动演示（2026-10-16）

已接入独立 teach-back、finish 和四个互动演示接口。复述评估复用原 Python 算法；仓颉保存会话进度、消息、工具证据、掌握度与复习计划，重复完成返回已有结果。现有互动演示页面可以读取推荐 JSON 配置、保存参数与观察记录，并重新读取已保存演示。

本批通过 `make verify-cangjie`：15 项算法、25 组仓颉原生和完整 HTTP/MySQL 回归。新增接口与原 Python 结果对照通过；未进行完整浏览器或真实模型质量验收。

## 独立练习作答与组卷（2026-10-16）

已接入 variants/{variant_id}/attempt 及组卷的候选、创建、列表、详情、编辑、删除、导出与下载，共 9 个接口。组卷支持保存题序和分数，导出题目 PDF、答案 PDF 与 Excel。仓颉负责用户权限、筛选、MySQL 与持久文件；Python 复用原判题和文档生成函数。

本批 make verify-cangjie 全部通过：17 项算法、25 组仓颉原生及 HTTP/MySQL 回归。实际生成并下载三种文件，验证 Excel 文本格式、编辑回滚和其他账号拒绝；未新增并发或性能专项。该阶段结束时仍有 3 个 partial 与 13 个 pending，未完成全部接口。

## 系统、管理员与语音（2026-10-16）

已接入系统健康、模型池状态与显式探测、语音状态、管理员工作台/学生/会话，以及语音转写/合成，共 9 个接口。系统状态来自实际数据库和计算服务；管理员接口限制 admin 角色，过滤私有提示、推理和凭据字段。语音复用原 Python VoiceProvider，仓颉处理权限、原音频保存、作答说明、语音记录和签名链接。

本批 make verify-cangjie 全部通过：19 项算法、25 组仓颉原生和完整 HTTP/MySQL 回归。管理员响应与原 Python 同库对照通过；语音采用模拟引擎及内部传输验证流程，没有下载模型或调用外部语音服务，不表示真实语音质量验收完成。该阶段结束时仍有 3 个 partial 与 4 个 pending，继续迁移练习推荐和教学对话等剩余接口。

## 教学自由对话（2026-10-16）

已接入 POST /api/v1/tutor/sessions/{session_id}/turns，沿用原 LangGraph 分支、公开规划、六类教学工具、长期记忆和图文引导。仓颉提供授权后的原题与学习快照、查询知识卡、检查结果是否过期，并原子保存对话和工具轨迹。普通聊天不会推进显式学习阶段或直接记录掌握。

make verify-cangjie 全部通过：21 项算法、25 组仓颉原生及完整 HTTP/MySQL 回归。计算规则与原 Python 独立进程对照通过；实际接口验证模型规划、原图、知识卡、消息恢复、答案工具限制、身份隔离和回滚。该阶段结束时，题库推荐、练习作答/图片、practice 手写与两条检索部分项共 6 条待补齐。


### 练习图片、手写与作答

练习题图片通过 GET/HEAD `/api/v1/practice/questions/{question_id}/images/{image_index}` 读取，使用四小时签名，并复用范围读取与缓存语义。默认只读取项目下 `data/question_bank_assets/`，可通过 `CANGJIE_QUESTION_BANK_ROOT` 指定绝对根目录；数据库里的相对图片路径按项目根目录解释。拒绝越界路径和符号链接，不复制或修改题库原图。

`answers/handwriting` 补齐 practice 上下文，校验错题归属、已推荐题目和原题指纹，选择题要求直接选项作答。原题及学生作答版本的指纹与保留的 Python 版一致。`practice/attempt` 由仓颉校验推荐和重复提交，Python 复用原判题与认知计算；只有确认的答案才写入练习记录和认知证据，使用推荐的目标知识点。字符串和多选数组答案以 JSON 原类型保存，记录与认知更新同事务提交。

新增场景已通过真实 HTTP/MySQL 专项验证，完整回归结果见迁移记录。本阶段结束时 91/94，剩余练习推荐及两条教学迁移题的检索/重新校验部分项；保留原 Python 入口，不新增并发或性能专项。


### 题库推荐与迁移题检索

练习推荐、教学迁移题共用原 BGE-M3 编码、Qdrant 稠密/稀疏融合和 BGE reranker 算法。Python 只访问算法索引；候选题、标准答案、知识关联、已做/已推荐排除和最终保存由仓颉从 MySQL 完成。练习推荐在网络计算前后检查原题版本，只有保存结果时短暂锁定原题；连续换题以微秒时间排序，缓存指向最新推荐。

算法服务配置（启动时读取，不加载旧 `.env`）：

- `CANGJIE_RETRIEVAL_INFERENCE_URL`：默认 `http://127.0.0.1:8011`，提供原 `/embed` 和 `/rerank` 协议。
- `CANGJIE_QDRANT_URL`：默认 `http://127.0.0.1:6333`。
- `CANGJIE_QDRANT_COLLECTION`：代码兼容默认仍为 `minddimension_questions_v1`；新独立库应显式使用以库名加下划线开头的独立集合，当前环境模板与一次性准备工具已配置。索引的 question_id 必须对应仓颉独立 MySQL 中的题库记录；初始化只建表，不自动复制旧题库或用户记录。

本地真实题源准备入口为`make setup-question-bank-cangjie`，详细操作与实际证据见[仓颉题库说明](../docs/final/QUESTION_BANK_IMPLEMENTATION.md)。新增`--question-bank`仅供本地准备工具通过标准输入执行导入、知识卡快照和题库分页导出，不增加公开HTTP接口。Python不读取或写入业务MySQL；重复导入保留题目ID，相同内容不刷新题目版本，失败批次整体回滚。

检索服务不可用时，练习推荐返回 503，没有合适候选返回 404；教学迁移题沿用原生成降级，并如实记录 retrieval_status。复用迁移题前重新执行数学与知识点校验，失效旧题保留审计记录并生成新题。

`make verify-cangjie` 验证算法、原生行为与全部业务 HTTP/MySQL；`make verify-cangjie-browser` 追加现有前端浏览器流程，使用独立端口和测试数据库连接仓颉，不依赖旧 Python 业务服务。测试中的 BGE/Qdrant HTTP 服务只由验证脚本启动，不参与正常运行。原 `make backend`、`make dev`、`make verify` 继续服务保留的 Python 版。


正常运行时，先按上文配置独立 MySQL 和两个后端共享的内部密钥，分别启动 `make algorithms-cangjie` 与 `make backend-cangjie`。前端可在另一个终端运行 `ZHIWEI_BACKEND_URL=http://127.0.0.1:8002 pnpm --dir frontend run dev:h5 --port 5174`，与旧版默认 5173/8000 端口同时使用。初始化后运行 `make seed-knowledge-cangjie`，由仓颉写入原版公开的 250 张基础知识卡与 65 条前置关系，重复执行保留既有记录 ID，不生成学生学习记录。题库记录和算法索引需准备到对应独立环境；空库不会自动引入演示成绩或旧用户数据。

## 最终版学习任务（006）

新增独立持久任务API与两个有界worker，仓颉负责MySQL、所有权、题目/步号版本、幂等、取消、租约和事务；Python负责有类型的计划、工具、数学验证与统一判题。局部订正不更新整题掌握；独立且未曝光的对照证据只提交一次。具体接口、边界与证据见 [任务实现记录](../docs/final/LEARNING_TASK_IMPLEMENTATION.md)。

新库初始化自动包含`006_learning_tasks`；已有独立仓颉库备份后显式运行`bash scripts/cangjie.sh upgrade-db`。`/readyz`当前要求009，未升级时不会误报就绪。旧94条接口仍保留，这5条新任务方法不计入原迁移分母。

自检与任务档案（007）：`GET /learning-tasks/{id}/history`返回本人最近50次学生可见动作；`GET/PATCH/DELETE /learning-tasks/{id}/self-check`保存、编辑或删除学生确认的一句要点。PATCH要求confirmed=true、version、input_fingerprint与最多300字text；DELETE只接受version。要点和save_self_check审计一起提交，不写掌握分。源题变化后的要点只读、可删除；`journey`新增任务及要点投影，保持旧完整迁移和教回要求。新库自动应用007，已有独立库备份后显式upgrade-db。

008任务手写：`POST /api/v1/learning-tasks/{id}/handwriting`接收file及request_id/version/step_id/input_fingerprint，202保存原始字节并排队转写，不在上传事务调用模型。recognize_handwriting使用既有Qwen轮询与Pydantic；学生确认文字后actions提交handwriting_id/handwriting_confirmed=true，识别由服务器读取。失败可resume同一原图或use_text；旧版本/步骤/其他任务照片拒绝混用。任务历史可按需查看签名原图；升级后readyz要求008。

## 本地角色账号

教师、家长、管理员通过`bash scripts/local_user.sh --email 实际邮箱 --role guardian --name 家长姓名`创建，密码无回显输入；teacher/admin分别用于教师和管理员。先配置`.env.cangjie`并显式初始化/升级独立数据库，命令不会自动建库或改变已有账号。`--check`仅预检；Python仅收集输入，仓颉负责校验、密码哈希及MySQL写入。具体边界、自动化和验证见[本地身份配置](../docs/final/LOCAL_IDENTITIES.md)。
