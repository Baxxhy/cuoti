# 仓颉题库准备与实际练习

## 本批实施计划

目标是让当前独立仓颉库具备可用练习内容，复用现有BGE/Qdrant与公开题源，不依赖旧Python业务库。

1. 增加本地仓颉题库命令：参数化写入题源和题目，分批事务、重复导入保留ID、不删学生记录；只向本地准备工具导出题目快照和知识卡。
2. Python复用现有文件解析、图片检查、质量规则和知识映射，只负责文件计算与索引；数据库读写全部通过仓颉命令。默认使用本地CMMU文件，不自动下载或调用LLM。
3. 建独立Qdrant集合，按仓颉返回的真实题目ID建立BGE索引；重复执行核对内容指纹，不以旧索引ID代替新库记录。
4. 用隔离MySQL检查导入、重复导入、无效输入、批次回滚与导出，再在实际环境完成导入、索引及推荐/作答核验。外部服务错误不能变成伪造题目。
5. 更新启动与数据准备说明，记录实际数量、学科、未覆盖范围和验证结果；当前完整回归成功后提交。

题源原有元数据与许可信息随导入保存；不把公开评测题称为本项目原创题或已经验证的教学质量。质量规则中的“答案可判”不等于答案经过人工或数学证明。手机发行、备份不在本批范围。

## 本地准备命令

在可信本地`.env.cangjie`中为当前库设置独立集合，例如库名是`zhiwei_cangjie_local`时，设置`CANGJIE_QDRANT_COLLECTION=zhiwei_cangjie_local_questions_v1`。仓颉启动器会将同一配置传给Python算法，更新配置后需重启。不得混用旧业务库的题目ID或索引。

先按现有检索环境说明启动BGE与Qdrant，再运行：

```sh
make setup-question-bank-cangjie
```

默认使用本地`data/question_bank_sources/cmmu/*.jsonl`和`data/question_bank_assets/cmmu`，不下载题源、不调用LLM。清洗和质量检查复用现有实现；缺图或缺答案的题目保留来源记录，但不导出给练习索引。知识映射保留规则估计的置信度与方法，不能作为学生掌握证据。

```sh
# 已完成入库时，仅继续建立/核对索引
bash scripts/question_bank_cangjie.sh --index-only
# 只准备MySQL，不建立索引
bash scripts/question_bank_cangjie.sh --skip-index
# 本地已有CMM-Math文件时使用同一流程
bash scripts/question_bank_cangjie.sh --source cmm-math
```

每50题一个事务；成功批次保留，失败批次不提交。重复导入按题源/源题号更新，保留题目ID和已有学生尝试。不会删除源文件、学生记录、旧数据库或已有Qdrant集合。索引按ID与文本/内容指纹补齐或更新，恢复执行不会每次重新计算全部向量。

本地仓颉`--question-bank`通过标准输入接受准备操作，无HTTP路由；仅本机管理者可导出含答案的题库快照。普通学生接口仍在提交后才提供答案。

## 验证记录

- 隔离MySQL专项已退出0：86项算法、31组仓颉原生，原生导入/导出、重复ID、更新答案、无效标记、错误指纹/路径、整批回滚、空库名及不修改用户均通过。随后补充未变内容不刷新`updated_at`的保护及断言，`/tmp/zhiwei-bank-version-focused.log`专项也已退出0。早先中断的完整回归不计成功；加入界面修复后的最终回归另记。
- 实际CMMU已通过仓颉导入1675题，现有质量规则判定1381题可练、294题只适合人工判定。可练题分布：数学212、物理220、化学214、生物220、地理220、历史145、思想政治150。该规则分类不代表正确性或教学质量评审。
- BGE CPU真实索引已完整完成，独立集合1381条；重复`--index-only`退出0，indexed=0、skipped=1381、集合仍1381条。日志`/tmp/zhiwei-bank-actual-prepare.log`和`/tmp/zhiwei-bank-actual-resume.log`。没有以部分索引当作完成。
- 实际三端已加载独立集合，`make check-final`四项就绪通过；`scripts/check_live_practice.py`退出0，真实BGE/Qdrant推荐、MySQL源题对应、提交前不泄露答案、配图签名下载、正确作答和重复提交409均通过。固定来源错题为一元一次方程，不扩大为所有学科的推荐质量证明。报告保存在Git忽略的`.runtime/live-practice-check.json`，不提交账号或令牌。

实际核验复现：先按[实际运行记录](ACTUAL_RUNTIME_IMPLEMENTATION.md)准备专用核验账号，加载`.env.cangjie`后运行`.venv/bin/python scripts/check_live_practice.py`。命令会新增一条专用错题和练习尝试，判题必要时使用现有Qwen池，不修改普通学生题目。

实际390宽度浏览器已成功打开后续推荐，题目与配图来自真实服务，无横向溢出、无对象占位输出。目视检查曾发现题型和公式排版问题，本批已修复：CMMU的`multiple-choice`按单选呈现、`multiple-response`按多选呈现，题型显示中文；练习题干/选项启用行内公式，填空占位不再裸露LaTeX间距命令，正文和选项改善字号与触摸高度。更新后的[真实练习截图](screenshots/practice-actual.png)已目视检查，同一道真实题的单选控件、中文标签、连续公式及390宽度均通过。没有修改数据库题干或原始图片。

前端122项/33文件和类型检查通过；新增浏览器专项退出0，单选A→C仅提交C，多选C→A提交A、C，并检查短公式没有块级分拆。此控件场景使用受控接口响应，不能冒充真实题库推荐证据；真实服务证据见前述独立核验。主提交按钮补可访问角色和禁用状态。最终`CANGJIE_VERIFY_FOCUS= make verify-final`已退出0：122项前端/33文件、类型、H5与App本地资源构建、86项算法、31组仓颉原生、完整HTTP/MySQL与重启恢复、31项浏览器通过，0跳过。日志`/tmp/zhiwei-bank-ui-final.log`，包含新增题库命令专项与控件场景；结束后`make check-final`四项通过，实际服务保持运行。


## 知识点准入补充

支持可选 `--contains` 对来源题干与解析作文字筛选，默认导入行为不变。实际CMM-Math筛选“一元一次方程”导入95题，其中可自动判题61题、无答案5题、人工判定29题；61条真实BGE索引完成后总集合1442条，总题库1770题。筛选词保留在来源元数据，不能凭筛选词认定推荐相关。

新推荐、旧缓存和作答均经过独立匹配校验，并绑定源题/分析/诊断、目标卡与题库版本；旧错配几何题提交已确认409且无学习写入，实际方程题正向判题/认知归属通过。详见[练习相关性实现](PRACTICE_ALIGNMENT_IMPLEMENTATION.md)。
