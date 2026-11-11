# 运行回归

不新增测试依赖，使用Python标准库unittest。冻结夹具为4篇项目自编案例、14条查询及用户单人复核标签，保留B0—B3原分数和排序，不代表真实教学效果。

```bash
PYTHONPATH=backend-business python -m unittest discover -s backend-business/tests -v
```

MySQL/API集成测试默认跳过。先新建仅供测试的 `sczx_test_*` 库，再设置 `SCZX_DATABASE_URL` 和 `SCZX_RUN_MYSQL_TESTS=1` 运行同一命令。测试拒绝任何其他库名，会执行迁移并创建测试账号、案例和版本，不删除数据库。使用独立新库运行；不要指向正式sczx库。凭据通过环境配置，不写进测试文件。

同时显式设置 `SCZX_STORAGE_DIR` 为本轮新建的独立测试上传目录；不能继承正式服务的上传目录。数据库和文件存储必须一起隔离。第二十步当前完整162项，另有23项Chromium、4项JavaScript；历史段落中的数量按当时版本保留。

前端在Vite运行后执行 `CHROME_PATH=/path/to/chromium npm --prefix frontend test`。Node22以上，使用内置test、WebSocket和现有Chrome；SCZX_TEST_ORIGIN可改本地地址，默认5177。浏览器并发用例控制响应只验证状态竞争；真实模型联调另记验收结果。

第十步补充：生成期间发布新课时、旧来源预检查、草稿并发冲突、不可变历史/恢复、DOCX固定版本与权限、局部改写保留手写属性，以及表达式/方程/条件三态核验。MySQL完整25项；无MySQL时12通过、13跳过。

前端持久Chromium现有5项，另有 `npm --prefix frontend run test:unit` 无外部服务JS检查。GitHub基础工作流不连接业务数据库、不调用真实Codex。当前Office实机验收状态请读取第十步统一验收表，不用DOCX解析测试代替Word/WPS打开验证。

Word专项新增4项独立导出/文本规则测试与2项MySQL保护测试，当前完整31项（不接MySQL为16通过、15跳过）。检查字体的四种OOXML映射、所有样式/页眉页脚纯黑、A4、双模式去重、清理只作用副本、语言规则及一次修订上限。当前Office状态见最新专项验收表，旧段落的待验收状态属于历史记录。

第十一步当前完整42项：原31项，加10项班级/任务/消息MySQL场景及1项日期边界单元。新增并发补发与读取去重、加入/移出/重入、私人安排收件、截止时区、提交重试首时间、旧说明兼容。前端当前7项Chromium及1项JS。真实多用户浏览器种子使用`PYTHONPATH=backend-business python backend-business/tests/seed_teaching_acceptance.py --output /tmp/sczx-step11/browser-private.json`，必须另用全新sczx_test_*库；凭据只写临时私有文件。[验收与复现](../../docs/verification/teaching_20261110_v1/README.md)。

第十二步当前完整54项：原42项加10项指导MySQL场景和2项完成规则/上下文边界单元。覆盖移出重试及执行写回、父轮/题图隔离、旧客户端策略约束、幂等重放、数学错误/泄露阻断和真实作答门槛。前端10项Chromium及1项JS。[第十二步证据](../../docs/verification/tutoring_20261110_v1/README.md)区分受控提供者、真实Codex、实际故障/注入故障及单人评阅。

第十三步新增独立错题帮、实际变式判分、运算类型匹配、旧固定记录保护、原图/裁剪与OCR确认、教师核对及并发重放检查。完整65项；前端11项Chromium、2项JS及构建通过。旧结构升级与真实模型/浏览器证据独立保存在[第十三步验收](../../docs/verification/remediation_20261110_v1/README.md)。Python算法独立目录与make verify不属于当前工程，继续使用本文现有命令。

第十四步完整80项：新增学习状态固定情境、证据稳定ID、跨任务/跨教师隔离、修订审计与冲突、稍后恢复、前置关系、旧固定/未知处理、教师指定复习完成、旧帮助保护等。前端13项Chromium、4项JS与构建通过；固定14情境的B0/B1/B2比较另存，不作为教育效果结论。见[第十四步证据](../../docs/verification/memory_20261110_v1/README.md)。

第十五步完整103项：新增唯一学生/任务/发布题目口径、最近作答与同刻矛盾、时区区间、班级投影、五类干预及基线、问题状态/并发/旧回复保护、失败任务权限与失效来源。15项Chromium、3个JS文件检查及构建通过；真实三流程、管理来源修订、Codex重试、旧0012升级和正式原字段保护见[第十五步证据](../../docs/verification/insights_20261111_v1/README.md)。
