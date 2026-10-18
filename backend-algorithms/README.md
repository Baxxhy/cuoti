# 仓颉版内部算法服务

该服务保留 Python 专业计算能力，复用原版 `backend/app/services` 与 `ApiPoolProvider`，不修改原版源码，不导入 `app.db`、`app.models`、`app.main`、`app.config`，没有账户、业务路由或数据库写入。仓颉负责后续业务编排和结果落库，不能把本服务当作旧 FastAPI 业务代理。

## 启动

使用项目现有 `.venv` 依赖。仓颉与算法服务需要设置相同的 `CANGJIE_ALGORITHM_SECRET`（至少 32 个字符，与用户登录密钥独立），然后运行 `make algorithms-cangjie`。

- 默认仅监听 `127.0.0.1:8012`，可通过 `CANGJIE_ALGORITHM_PORT` 修改。
- 仓颉端 `CANGJIE_ALGORITHM_URL` 默认 `http://127.0.0.1:8012`，仅接受此形式的回环地址，不使用代理。
- `CANGJIE_API_POOL_PATH` 默认指向项目 `backend/config/api_pool.json`。启动不会探测或调用模型；首次识别请求才加载池，逻辑模型固定 Qwen，调用经过 ApiPoolProvider 轮询。
- 不加载原版 `.env`，不读写业务数据库，不接受客户端文件路径；图像计算使用每次请求独立的临时目录并自动清理。

## 内部接口

`GET /livez` 仅报告服务存活，不代表模型池或整个应用就绪。`POST /v1/compute` 要求 `Authorization: Bearer <内部密钥>`，JSON 请求体最多 22 MiB；原始图片上限仍为 15 MiB、2500 万像素。

| operation | 输入 | 结果 |
| --- | --- | --- |
| normalize | image_base64 | 规范化 JPEG、SHA-256 |
| crop | image_base64、box `[x,y,width,height]` | 裁剪 JPEG、SHA-256、实际几何尺寸 |
| preprocess | image_base64 | 清洁图、红色掩膜、覆盖图及指标 |
| recognize | image_base64（仓颉选定的原图或裁剪图） | 经 Pydantic 校验及红色证据过滤的结构化识别结果、区域图片和耗时 |
| math_compare | left、right | equivalent、verified |
| math_solve | text | answer、verified |
| analyze | text、subject、grade、question_type、student_answer、student_steps、options、images_base64 | Pydantic 校验的 analysis、逐参考步骤 reference_math_valid、logical_model |
| diagnose | text、subject、question_type、student_answer、options、reference_steps、student_records、images_base64 | diagnosis、alignment、counterfactual、logical_model |
| counterfactual | text、subject、reference_steps、student_records | alignment、counterfactual、logical_model |

识别服务不会代替仓颉检查题目所有权或选择裁剪图；这些约束必须在仓颉任务编排中落实。所有图片通过 base64 传递，结果不包含临时绝对路径。异常响应使用固定文本，不回传上游错误或池内凭据。

## 验证与当前范围

`make verify-cangjie` 启动专用算法进程、创建隔离 MySQL 测试库并在结束时清理。仓颉原生测试真实调用该进程执行图像裁剪、数学计算及错误映射；使用不存在的测试模型池确保不触发真实模型费用。Python 测试以模拟双节点上游验证 ApiPoolProvider 故障切换及结构化输出失败后的重试，并检查输入边界和错误脱敏。

已接入仓颉上传、识别结果落库与中断任务恢复；HTTP 集成以临时本地模拟 Qwen 验证完整识别流程。仓颉已接入失败任务重试；真实模型端到端验收仍待完成。原 Python 完整版继续保留。

## 题目分析计算

`analyze` 接受题干、作答、选项和仓颉选定的裁剪图/原题题图（base64，最多 32 张，总请求仍限 22 MiB）；不接受文件路径，不读取数据库。图片规范化到临时目录，请求结束后清理。

通过 ApiPoolProvider 的 Qwen 结构化/多模态接口生成 AnalysisOutput。数学非选择题沿用 SymPy 求解结果纠正最终答案并设置 answer_verified；逐参考步骤使用原版 equation_equivalent(require_symbolic=True) 验证。模型不可用时仅在符号求解已验证的情况下使用原版规则结果，否则返回 503；空题干或非法图片返回 422，错误不包含上游凭据。

当前已接入仓颉分析业务接口，权限、并发输入校验、结果落库与知识点关联均由仓颉承担。测试使用实际 ApiPoolProvider 加本地模拟上游，未调用真实远程模型。

## 诊断与反事实计算

`reference_steps` 与 `student_records` 是最多 100 项的 `{id, text}` 记录（ID 最长 36 字符、文字最长 12000 字符）。由仓颉查询并验证所属题目后传入，Python 不读取数据库，也不接收客户端文件路径或现成的“已验证”对齐结论。

计算复用原版步骤对齐、错误分类、Qwen/Pydantic 诊断与反事实提案，并以本地等价性检查验证修复路径。提案不可用时保留原版参考路径回退，并明确 verification_method；模型诊断失败返回 503，非法输入返回 422。只有答案没有步骤时，不生成具体错误步号或反事实根因结论；完全匹配的步骤也不保留模型虚构的错误步号。

仓颉已接入诊断生成、读取和证据事务，内部计算服务不承担业务数据库操作；人工修正和独立反事实触发业务接口也已由仓颉接入。测试使用真实 ApiPoolProvider 配合模拟上游，覆盖图文输入、对齐 IDs、传播标记、错误修复拒绝、回退、无步骤/正确路径及敏感错误隐藏。

## 教学简报计算

内部 `teaching_brief` 操作接收非空 `text`、非空 `correct_answer`，以及 `question_type`、`student_answer`、`student_steps`、`options`、`knowledge_points`、`diagnosis`；返回 `brief` 和 `logical_model: Qwen`。仓颉先验证题目与分析，再提供这些数据；计算服务不查询题目、不创建教学会话、不推进学习阶段。

复用原版 ApiPoolProvider/Pydantic 简报生成与本地回退：已分析答案覆盖模型自行生成的答案，规范化检查选项及答案映射，含糊提问替换为规则检查题。已配置模型池但上游失败或结构化输出无效时使用原版回退；模型池缺失返回 503，题干/答案为空或输入结构非法返回 422。测试使用模拟上游，未进行真实模型质量验收。

## 迁移练习生成

`generate_variant` 接收题目上下文 `text`、`subject`、`question_type`、`knowledge_points`、`transfer_type`（near/far）及可选的 `variant_references`，返回 `variant`、`verified`、`generation` 和 `logical_model`。参考题由仓颉查询后传入，每项包含 id、question_text、answer，以及可选 solution、question_type、knowledge_points、score；本服务不访问题库数据库。

`variant_compute.py` 从保留的 Python 版练习算法提取，移除了依赖业务配置、模型表和数据库的检索模块导入。保留 Qwen 结构化生成、数学答案验证、知识点对齐与生成失败回退，明确记录生成来源和回退原因。此处 verified 沿用原算法的格式/答案/对齐检查含义，并不代表所有学科答案都经过符号证明。

## 作答判定

`grade_answer` 接收 `text`、`answer`、`expected`、`subject`、`question_type`、`options` 和 `reference_solution`，返回原版统一判题结果，包括 correct、feedback、verdict、can_update_learning 和依据。答案支持 JSON 字符串或选择项列表；标准答案由仓颉从服务端活动/练习读取，不能使用前端提交的标准答案。

复用原 Python 版纯判题算法。选择项精确比较、数学等价性及可靠规则可在没有模型池时运行；需要过程复核时通过 ApiPoolProvider/Qwen。模型失败、证据不足或模型与规则冲突时保留需复核结果，仓颉应仅在 can_update_learning=true 时使用判定推进掌握度。

`recognize_handwriting` 接收原始作答图片的 `image_base64`、当前题目 `text` 和 `subject`，经 ApiPoolProvider 调用 Qwen，仅转写可见内容，返回 Pydantic 校验的 `recognition`（最终答案、步骤、完整转写、置信度、不确定标记）。`validate_handwriting` 对提交的 `recognition` 做相同结构校验，不调用模型。图片所属用户、学习上下文、原图保存及作答关联由仓颉处理。

`cognition_update` 接收 mastery_values、misconception_values、learning_evidence 和 misconception_label，返回原 Python 认知算法的新数值。它不接收数据库凭据、不读取或写入业务表。仓颉负责读取快照及将结果连同证据保存。纯计算共用 `app.services.cognition_rules`，以原实现生成的 54 组结果向量验证一致性。

`evaluate_teach_back` 接收复述文本 `text`、`subject`、`question_type`、`teach_back_points` 和 `reference_solution`，复用原 Python `evaluate_teach_back` 返回通过结果、反馈及概念匹配信息。无需模型池；仓颉负责尝试次数、辅助推进、练习生成与消息保存。

`visualization_config` 接收 `subject`、`question_type`、`teach_back_points` 与 `visualization_values`，复用原推荐规则和配置，返回演示类型目录、匹配类型和参数覆盖后的 `VisualizationPayload`。不调用模型，不保存交互记录；仓颉负责会话权限、演示和观察证据落库。

`render_paper` 接收 paper_title、paper_kind（question/answer/excel）和 paper_questions，复用原 PDF/Excel 生成函数，返回文件 Base64 与 SHA-256。题目、分数、答案、解析和显式题图由仓颉查询并传入；图像在临时目录中供文件生成函数使用，计算服务不读写业务库或持久导出目录。仓颉校验摘要后保存文件并记录下载信息。

`system_state` 返回当前 ApiPoolProvider 与 VoiceProvider 状态；probe_provider=true 时显式调用原池探测，普通查询只读取状态。池不存在时返回 unavailable 和零条目；探测不可用时返回 503。状态不包含凭据。

`voice_transcribe` 接收 audio_base64、audio_suffix，在临时目录调用原 VoiceProvider.transcribe，返回文本及元数据；`voice_synthesize` 接收 text、voice，调用原合成方法，返回音频 Base64、SHA-256 和元数据。专业计算失败返回不含底层细节的 502；原音频保存、归属校验、作答更新和失败记录均由仓颉完成。

`tutor_dialogue_prepare` 使用 dialogue_context 和仓颉提供的 dialogue_memory_rows，执行原 LangGraph 分支和公开行动规划，返回记忆、规划、图状态与知识卡查询词。`tutor_dialogue_finish` 接收准备结果、仓颉查询出的 dialogue_cards 及题目图字节，执行原工具规则、决策核验、图文引导与重复回复规避，返回受长度约束的回复和可审计结果。计算模块不导入 ORM、业务配置或读取 MySQL；原版 agent_runtime 的无数据库算法已提取，并由独立进程对照验证。


`retrieval_prepare` 从仓颉提供的题目、分析、诊断及知识卡快照计算检索词和排序目标；`retrieval_search` 执行原 BGE-M3 + Qdrant 稠密/稀疏 RRF 查询，只返回索引命中和名次；`retrieval_rank` 接收仓颉从 MySQL 加载的候选快照，执行原重复题过滤、结构相似度及模式重排，返回排序和迁移参考。索引不是业务事实源，最终可用性、权限和保存由仓颉校验。

`validate_variant` 复用原 SymPy 和知识点一致性规则校验旧迁移题；`normalize_options` 复用原题库选项规范化。两者均无数据库访问或模型调用。检索配置见仓颉版 README；默认端口沿用原检索服务，测试夹具只在验证命令中启用。

## 持久学习任务计算

内部`learning_task` operation消费TaskContext/Checkpoint/TaskAction，返回经Pydantic校验的TaskResult，包含受控StudentView、只读工具轨迹与作用域。没有身份、业务SQL或数据库写入权限。来源/预算/租约/版本与学习证据提交由仓颉再次校验。当前规则与数学能力边界见 [任务实现记录](../docs/final/LEARNING_TASK_IMPLEMENTATION.md)。

学习任务的recognize_handwriting动作复用现有手写转写器和ApiPoolProvider，原图仅由仓颉保存。Python在临时目录规范化识别副本、返回Pydantic转写和待本人核对的视图，不直接判题或写掌握分；确认后的文字仍使用统一grade_answer，use_text可退出照片重试。


`practice_alignment` 接收仓颉提供的 `retrieval_source`、`retrieval_target` 和最多10个 `retrieval_candidates`，独立核验推荐目标。直接方程用SymPy判定，其余经ApiPoolProvider/Qwen和Pydantic校验，并检查逐字证据；无法确认时返回不准入。返回匹配方法，不返回标准答案，不写MySQL。仓颉负责版本凭据、缓存及作答时的再次检查，见[相关性实现](../docs/final/PRACTICE_ALIGNMENT_IMPLEMENTATION.md)。


诊断新增 `diagnosis_alignment.py`：明确求解的独立一元多项式（1至4次、有限非空实数解）可按原方程解集核对短推导、分支与最终答案，避免将参考说明行当作必需步骤。反事实修复须保留原正确前缀并补全原方程所有实数解。结果明确记录 verification_scope/validation_scope；超范围沿用既有流程，不冒充符号证明。详情与真实样本见[诊断对齐记录](../docs/final/DIAGNOSIS_ALIGNMENT_IMPLEMENTATION.md)。


持久任务的几何照片采用严格的FigureHandwritingRecognition输出，保留普通手写兼容；inspect_figure核对明确原题与候选标注，结果保留model_observation分类。度数单位兼容与单个角度判题在内部适配层处理，原始作答/角标保留；不支持的标注不当作条件。工具反馈标记辅助，具体范围见[图形核对记录](../docs/final/FIGURE_REVIEW_IMPLEMENTATION.md)。


独立、无选项的一元有理系数多项式不等式已接入有界实数解集核验：分析可修正模型标准答案，诊断保留正确变形/边界零点/必要条件，反事实保留原正确前缀，统一判题比较完整解集与端点。未知过程、参考冲突及未支持的定义域保持复核路径；细节见[不等式合同](../docs/final/INEQUALITY_IMPLEMENTATION.md)。


语音运行依赖固定edge-tts7.3.1（包含新握手及日期解析修复）。仓颉实际检查使用`python scripts/check_voice_cangjie.py --token-stdin`，从项目根目录执行；该命令实际合成/转写并产生本人语音记录。实际结果、环境与准确性边界见[语音运行记录](../docs/final/VOICE_RUNTIME_IMPLEMENTATION.md)。学生界面仍遵守既有无语音入口设计。
