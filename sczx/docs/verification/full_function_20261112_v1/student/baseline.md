# 学生可见界面全功能验收基线

日期：2026-11-12；只从 http://127.0.0.1:8103/ 正常登录和点击寻路。

记录22项学生功能的真实动作、网络与回读结果；缺陷和未测项分开记录，模型返回成功不代表内容正确。

## 问题与观察

- **STU-F01 / P1** 确认学习位置冲突会连带覆盖未比较的题目草稿：每条尚未确认的题答案须比较；确认一条位置不能代确认所有答案。
- **STU-F02 / P2** OCR确认按钮仍要求另填主提问框：人工确认题干非空、数学式非空，点击确认题目并获取指导却报请写下问题，未创建新AI请求；填主提问后才成功。
- **STU-F03 / P2-content** 真实AI例子混用原等式两边且仍显示核验标记：提示写把5和−2都减去−2，追问5−(−2)和5分别等于多少；同时列出的等式已核对。
- **STU-F04 / P2** 已发布考试解析出现字面换行符和候选题待审核文案：学生2第2题解析含字面\n\n分步解释及本题为待教师审核的候选题。
- **STU-O01 / observation** 课堂归档的进入任务落到空答案独立练习：学生2课堂原答x7在实时页保留，已提交列表课堂记录进入后仅有上次作答状态，输入框为空。未在该入口再答，不能断言数据丢失。 继续完成练习后结果页仍显示已交、原讲评与作答记录，故这是入口展示问题，未断言数据丢失。
- **STU-F05 / P2** 补充学习的教师后续反馈返回405，学生无法回看：学生完成补充并经教师确认1/1；教师点击发送后续反馈的POST /api/teaching/supplements/:id/students/:id/feedback返回405（教师代理真实网络复核）；学生刷新补充仍无后续反馈。

## 功能与入口记录

### S01 新会话登录、错误提示、退出重登和账号隔离

- 结果：已验证。空登录被原生required拦截；错误密码401显示账号或密码不正确；主学生正常200进入首页；学生3退出后回登录并重登，自己的两条合成错题原答与已复测状态保留。
- 第一反应：首页登录。可见路径：根URL→登录；学生3退出图标→正常重登
- 写入回读：仅真实UI操作；对应网络记录见该profile network.jsonl，截图与动作/DOM快照可互相对照。
- 异常恢复/未测：空/错误密码/正常/退出重登已做；锁号、会话自然过期未测。
- 位置：入口与当前业务目标对应。 重复建议：保留一个主入口；次入口保持相同目标和文案。
- 证据：[shots/S01-login-error.png](shots/S01-login-error.png), [student3/shots/S01-student3-relogin.png](student3/shots/S01-student3-relogin.png), [student3/shots/S12-relogin-retains-wrong-original-status.png](student3/shots/S12-relogin-retains-wrong-original-status.png)

| 账号profile | 方法/端点 | HTTP | 次数 | 首条原始证据 |
|---|---|---|---|---|
| main | GET /api/auth/me | 401 | 2 | network.jsonl:1 |
| main | POST /api/auth/login | 401 | 1 | network.jsonl:3 |
| main | POST /api/auth/login | 200 | 1 | network.jsonl:4 |
| main | GET /api/auth/me | 200 | 13 | network.jsonl:16 |

### S02 找到任务、继续已有进度、待完成/已提交筛选

- 结果：已验证。初始5个真实任务；已提交为正确空状态；新任务发布后出现；原等式课从学习中继续，任务状态与已提交卡片变化。
- 第一反应：首页开始学习/已提交。可见路径：学习→开始学习/进入任务；待完成↔已提交
- 写入回读：仅真实UI操作；对应网络记录见该profile network.jsonl，截图与动作/DOM快照可互相对照。
- 异常恢复/未测：刷新回读已做；服务端异常/强制超时/越权/过期撤回未注入。
- 位置：任务主入口易找；已反馈卡片的进入任务仍回学习页，反馈须另经更多操作→学习结果，可增加直接查看反馈。 重复建议：保留一个主入口；次入口保持相同目标和文案。
- 证据：[shots/S02-home.png](shots/S02-home.png), [shots/S02-filter-realclick.png](shots/S02-filter-realclick.png)

| 账号profile | 方法/端点 | HTTP | 次数 | 首条原始证据 |
|---|---|---|---|---|
| main | GET /api/platform | 200 | 30 | network.jsonl:5 |
| main | PUT /api/platform | 200 | 143 | network.jsonl:6 |
| main | GET /api/teaching/dashboard | 200 | 9 | network.jsonl:8 |

### S03 搜索页面/任务并阅读通知

- 结果：已验证。搜索缩至对应任务；消息标读未读数5→4，API200且重开保留。
- 第一反应：搜索页面与任务/消息铃铛。可见路径：全局搜索→输入等式性质；查看消息→标为已读
- 写入回读：仅真实UI操作；对应网络记录见该profile network.jsonl，截图与动作/DOM快照可互相对照。
- 异常恢复/未测：搜索实际命中、消息标读、刷新回读已做；消息撤回未测。
- 位置：入口与当前业务目标对应。 重复建议：保留一个主入口；次入口保持相同目标和文案。
- 证据：[shots/S03-search-lesson.png](shots/S03-search-lesson.png)

| 账号profile | 方法/端点 | HTTP | 次数 | 首条原始证据 |
|---|---|---|---|---|
| main | GET /api/teaching/messages | 200 | 10 | network.jsonl:10 |
| main | POST /api/teaching/messages/:id/read | 200 | 1 | network.jsonl:12 |

### S04 课程目录、预览与进入正确课时

- 结果：已验证。课程初始5课目录；预览等式性质1/8；进入对应课时，课时题目/活动一致；新短课目录2块与发布内容一致。 学生3后加入双班仍未获历史任务，课程目录可预览新短课1/2，但无分配学习入口。
- 第一反应：课程→预览。可见路径：学习→课程→等式性质预览→关闭→进入学习
- 写入回读：仅真实UI操作；对应网络记录见该profile network.jsonl，截图与动作/DOM快照可互相对照。
- 异常恢复/未测：预览关闭/进入、课程正确内容已做；课程停用/版本回滚由管理员代理覆盖。
- 位置：入口与当前业务目标对应。 重复建议：预览仅阅读，进入学习保存进度；两者应维持清楚区别。
- 证据：[shots/S05-balance.png](shots/S05-balance.png), [shots/E02-feedback-and-supplement.png](shots/E02-feedback-and-supplement.png), [student3/shots/S04-student3-catalog.png](student3/shots/S04-student3-catalog.png), [student3/shots/S04-new-version-preview.png](student3/shots/S04-new-version-preview.png)

| 账号profile | 方法/端点 | HTTP | 次数 | 首条原始证据 |
|---|---|---|---|---|
| main | GET /api/curriculum/courses | 200 | 12 | network.jsonl:14 |
| main | GET /api/units/unit-equation/progress | 200 | 3 | network.jsonl:15 |
| main | GET /api/units/unit-8c1745431e5c43b8abad81db5f43f75d/progress | 200 | 5 | network.jsonl:350 |
| student3 | GET /api/curriculum/courses | 200 | 2 | student3/network.jsonl:200 |
| student3 | GET /api/units/unit-8c1745431e5c43b8abad81db5f43f75d/progress | 200 | 1 | student3/network.jsonl:240 |
| student3 | GET /api/units/unit-equation/progress | 200 | 1 | student3/network.jsonl:241 |

### S05 分步学习、天平活动、解释门槛、保存恢复

- 结果：已验证。空解释时下一步禁用；单边加1显示不等，重置与双边加1正确；填写观察后可前进；刷新保持第3步，显式保存提示已保存；中途学习结果指出5项待完成并返回缺项。
- 第一反应：进入学习→下一步。可见路径：等式性质1/8→天平2/8→双边互动+解释→3/8→更多操作保存→刷新
- 写入回读：仅真实UI操作；对应网络记录见该profile network.jsonl，截图与动作/DOM快照可互相对照。
- 异常恢复/未测：空解释、活动重置、刷新、保存和缺项路径已做；该种子8步课未提交，E02新短课完整提交。
- 位置：入口与当前业务目标对应。 重复建议：保留一个主入口；次入口保持相同目标和文案。
- 证据：[shots/S05-balance.png](shots/S05-balance.png), [shots/S05-missing-submit.png](shots/S05-missing-submit.png)

| 账号profile | 方法/端点 | HTTP | 次数 | 首条原始证据 |
|---|---|---|---|---|
| main | GET /api/platform | 200 | 30 | network.jsonl:5 |
| main | PUT /api/platform | 200 | 143 | network.jsonl:6 |
| main | POST /api/records/:id/attempts | 201 | 6 | network.jsonl:103 |
| main | POST /api/records/:id/submit | 200 | 2 | network.jsonl:169 |

### S06 真实AI指导、分步、策略、追问、停止

- 结果：功能已验证，内容风险待核。真实hint模型返回并可展开3步；追问成功纠正前例混用5与-2；举例请求可停止，job取消且输入恢复；OCR确认补主提示后真实example返回。内容质量有一条已上报风险。 补基础和换种讲法也得到本题真实模型返回；同除以2/除数非零说明可见，分步展开可读，完整原文保存于ai-observed-results.json。
- 第一反应：问一问。可见路径：等式性质第3步→问一问→给我提示→发送→一步步看→回答后继续；新一轮举例→停止；新短课当前题→补基础/换种讲法→发送→分步展开
- 写入回读：通过可见提问按钮发起真实模型请求；保留首次提示、回应纠正、停止与各策略完整结果和jobId。至少一次结果有语义错误，未用核验标记代替人工内容检查。
- 异常恢复/未测：空发送校验、真实结果、追问、新一轮、停止后再发成功已做；模型服务超时/503未注入。
- 位置：入口与当前业务目标对应。 重复建议：保留一个主入口；次入口保持相同目标和文案。
- 证据：[shots/S06-ai-real-return.png](shots/S06-ai-real-return.png), [shots/S06-stopped.png](shots/S06-stopped.png), [shots/S07-ocr-confirm-blocked.png](shots/S07-ocr-confirm-blocked.png), [shots/S06-foundation-return.png](shots/S06-foundation-return.png), [shots/S06-foundation-steps.png](shots/S06-foundation-steps.png), [shots/S06-rephrase-return.png](shots/S06-rephrase-return.png), [ai-observed-results.json](ai-observed-results.json)

| 账号profile | 方法/端点 | HTTP | 次数 | 首条原始证据 |
|---|---|---|---|---|
| main | GET /api/ai/jobs | 200 | 7 | network.jsonl:37 |
| main | POST /api/ai/jobs | 201 | 7 | network.jsonl:41 |
| main | GET /api/ai/jobs/:id | 200 | 19 | network.jsonl:42 |
| main | GET /api/ai/jobs/:id/events | 200 | 7 | network.jsonl:43 |
| main | POST /api/ai/jobs/:id/stop | 200 | 1 | network.jsonl:65 |

### S07 上传题图、真实OCR、人工修订与确认

- 结果：缺陷：OCR确认依赖空主提示。真实OCR识别3x+5=20及原答x=6；修订确认文字非空但主提问框为空时按钮报请写下问题；填主提问后成功发真实指导。
- 第一反应：问一问→选择题图。可见路径：上传合成problem-1112.png→识别题图→编辑确认题目→确认获取指导
- 写入回读：仅真实UI操作；对应网络记录见该profile network.jsonl，截图与动作/DOM快照可互相对照。
- 异常恢复/未测：真实识别/人工修订/失败恢复已做；模糊图、多题图、OCR服务错误未测。
- 位置：入口与当前业务目标对应。 重复建议：保留一个主入口；次入口保持相同目标和文案。
- 证据：[shots/S07-ocr-confirm-revised.png](shots/S07-ocr-confirm-revised.png), [shots/S07-ocr-confirm-blocked.png](shots/S07-ocr-confirm-blocked.png)

| 账号profile | 方法/端点 | HTTP | 次数 | 首条原始证据 |
|---|---|---|---|---|
| main | GET /api/ai/jobs | 200 | 7 | network.jsonl:37 |
| main | POST /api/ai/jobs | 201 | 7 | network.jsonl:41 |
| main | GET /api/ai/jobs/:id | 200 | 19 | network.jsonl:42 |
| main | GET /api/ai/jobs/:id/events | 200 | 7 | network.jsonl:43 |
| main | POST /api/ai/jobs/:id/stop | 200 | 1 | network.jsonl:65 |
| main | POST /api/files | 201 | 1 | network.jsonl:68 |
| main | GET /api/files/:id | 200 | 1 | network.jsonl:75 |

### S08 方程变形、非法除数、解释保存恢复

- 结果：已验证。变形得到x=7；表达式、历史步骤与解释刷新恢复；除以0被拦截为乘数/除数必须非零。
- 第一反应：独立练习→试着变形。可见路径：x-2=5→两边同加2→执行→保存解释→刷新重开；同除0
- 写入回读：仅真实UI操作；对应网络记录见该profile network.jsonl，截图与动作/DOM快照可互相对照。
- 异常恢复/未测：非法0除数和刷新恢复已做；撤销/重置及乘法分支未测。
- 位置：入口与当前业务目标对应。 重复建议：保留一个主入口；次入口保持相同目标和文案。
- 证据：[shots/S08-transform-restored.png](shots/S08-transform-restored.png), [shots/S08-divide-zero.png](shots/S08-divide-zero.png)

| 账号profile | 方法/端点 | HTTP | 次数 | 首条原始证据 |
|---|---|---|---|---|
| main | GET /api/equation-tools/:id/1 | 200 | 2 | network.jsonl:154 |
| main | PUT /api/equation-tools/:id/1 | 200 | 2 | network.jsonl:155 |
| main | PUT /api/equation-tools/:id/1 | 422 | 1 | network.jsonl:162 |

### S09 随堂/独立作答、解释、核验、帮助按题隔离

- 结果：已验证。原答x7→帮助后x4与独立题x7均保存；随堂需答案和解释才可提交；新题不沿用提示/帮助标记，学生2分层第2题显示独立作答。
- 第一反应：新任务进入→提交作答。可见路径：E02第1题新错答x7→提示→订正x4→第2题独立x7；学生2分层第1题提示→第2题独立
- 写入回读：仅真实UI操作；对应网络记录见该profile network.jsonl，截图与动作/DOM快照可互相对照。
- 异常恢复/未测：空字段门槛、错答、帮助确认、订正、刷新、新题帮助重置已做。
- 位置：入口与当前业务目标对应。 重复建议：短课第2随堂题与独立练习用同一道题和已答内容；可标明同题复查，独立新题应另给新题。
- 证据：[shots/E02-original-wrong.png](shots/E02-original-wrong.png), [shots/E02-assisted-correction.png](shots/E02-assisted-correction.png), [student2-online/shots/S09-new-question-help-reset.png](student2-online/shots/S09-new-question-help-reset.png), [student2-online/shots/S09-question2-independent.png](student2-online/shots/S09-question2-independent.png)

| 账号profile | 方法/端点 | HTTP | 次数 | 首条原始证据 |
|---|---|---|---|---|
| main | GET /api/platform | 200 | 30 | network.jsonl:5 |
| main | PUT /api/platform | 200 | 143 | network.jsonl:6 |
| main | POST /api/curriculum/tasks/:id/questions/0/hint | 200 | 2 | network.jsonl:99 |
| main | POST /api/records/:id/attempts | 201 | 6 | network.jsonl:103 |
| student2-online | GET /api/platform | 200 | 12 | student2-online/network.jsonl:3 |
| student2-online | PUT /api/platform | 200 | 56 | student2-online/network.jsonl:4 |
| student2-online | POST /api/records/:id/attempts | 201 | 3 | student2-online/network.jsonl:14 |
| student2-online | POST /api/curriculum/tasks/:id/questions/0/hint | 200 | 1 | student2-online/network.jsonl:158 |

### S10 错题文字/原图/裁剪/OCR录入及搜索来源原答

- 结果：已验证。新增两条合成错题；文字原答x13和原过程保持；图OCR后修订题干保留x6。原图1000x460与裁剪1000x253分别显示；搜索、待订正/已复测筛选正确。学生2考试错题回看x8和原解释。
- 第一反应：错题与复习→录入错题。可见路径：文字录入2x+7=19、原答x13；另上传图→精确调整裁剪→保存→OCR→核对确认→保存；搜索待订正
- 写入回读：仅真实UI操作；对应网络记录见该profile network.jsonl，截图与动作/DOM快照可互相对照。
- 异常恢复/未测：空保存禁用、OCR未确认保存禁用、上传裁剪、人工确认、刷新/重登原答保持已做；非图片/过大文件未测。
- 位置：入口与当前业务目标对应。 重复建议：保留一个主入口；次入口保持相同目标和文案。
- 证据：[student3/shots/S10-wrong-original-text.png](student3/shots/S10-wrong-original-text.png), [student3/shots/S10-crop-ocr-confirmed.png](student3/shots/S10-crop-ocr-confirmed.png), [student3/shots/S10-raw-crop-preserved.png](student3/shots/S10-raw-crop-preserved.png), [student3/shots/S10-search-filter-original.png](student3/shots/S10-search-filter-original.png), [student2-online/shots/S10-exam-wrong-source.png](student2-online/shots/S10-exam-wrong-source.png)

| 账号profile | 方法/端点 | HTTP | 次数 | 首条原始证据 |
|---|---|---|---|---|
| student2-online | GET /api/wrongs/options | 200 | 2 | student2-online/network.jsonl:188 |
| student2-online | GET /api/wrongs | 200 | 1 | student2-online/network.jsonl:189 |
| student2-online | GET /api/wrongs/:id | 200 | 1 | student2-online/network.jsonl:192 |
| student3 | GET /api/wrongs | 200 | 7 | student3/network.jsonl:54 |
| student3 | GET /api/wrongs/options | 200 | 21 | student3/network.jsonl:55 |
| student3 | POST /api/wrongs | 201 | 2 | student3/network.jsonl:56 |
| student3 | GET /api/wrongs/:id | 200 | 14 | student3/network.jsonl:61 |
| student3 | POST /api/ai/jobs | 201 | 4 | student3/network.jsonl:62 |
| student3 | GET /api/ai/jobs/:id | 200 | 12 | student3/network.jsonl:63 |
| student3 | GET /api/ai/jobs/:id/events | 200 | 4 | student3/network.jsonl:64 |
| student3 | PUT /api/wrongs/:id | 200 | 7 | student3/network.jsonl:71 |
| student3 | POST /api/wrongs/:id/attempts | 201 | 2 | student3/network.jsonl:78 |
| student3 | POST /api/files | 201 | 2 | student3/network.jsonl:103 |
| student3 | GET /api/files/:id | 200 | 5 | student3/network.jsonl:104 |

### S11 真实错因分析、指导、人工确认分类

- 结果：已验证。真实分析定位符号处理错误，给同减7/同除2/代回三步；可见折叠区中选符号处理错误并勾确认、保存，刷新重登保持分类，原答x13不变。图题计算错误也从可见分类区保存。
- 第一反应：错题→分析这道题。可见路径：文字新错题→分析→开始订正→三步→原来的作答→打开错因分类→确认→保存
- 写入回读：仅真实UI操作；对应网络记录见该profile network.jsonl，截图与动作/DOM快照可互相对照。
- 异常恢复/未测：空订正回应按钮禁用、真实生成、分类确认回读已做；重新分析未执行。
- 位置：入口与当前业务目标对应。 重复建议：保留一个主入口；次入口保持相同目标和文案。
- 证据：[student3/shots/S11-cause-analysis-real.png](student3/shots/S11-cause-analysis-real.png), [student3/shots/S11-cause-visible-saved-reread.png](student3/shots/S11-cause-visible-saved-reread.png), [student3/shots/S12-relogin-retains-wrong-original-status.png](student3/shots/S12-relogin-retains-wrong-original-status.png)

| 账号profile | 方法/端点 | HTTP | 次数 | 首条原始证据 |
|---|---|---|---|---|
| student3 | GET /api/wrongs/options | 200 | 21 | student3/network.jsonl:55 |
| student3 | GET /api/wrongs/:id | 200 | 14 | student3/network.jsonl:61 |
| student3 | POST /api/ai/jobs | 201 | 4 | student3/network.jsonl:62 |
| student3 | GET /api/ai/jobs/:id | 200 | 12 | student3/network.jsonl:63 |
| student3 | GET /api/ai/jobs/:id/events | 200 | 4 | student3/network.jsonl:64 |
| student3 | PUT /api/wrongs/:id | 200 | 7 | student3/network.jsonl:71 |
| student3 | POST /api/wrongs/:id/attempts | 201 | 2 | student3/network.jsonl:78 |

### S12 真实变式及独立复测，保留原答

- 结果：已验证。变式正确后仍需独立复测；独立题正确后状态已复测；刷新和重登仍已复测；原错题x13未改。
- 第一反应：订正完成→练一道类似的题。可见路径：写订正说明→真实生成3x+5=20→答x5→独立再试一题4x+6=22→答x4
- 写入回读：仅真实UI操作；对应网络记录见该profile network.jsonl，截图与动作/DOM快照可互相对照。
- 异常恢复/未测：空答案禁用、两次实际提交、刷新重开已做；复测求助后重新独立题分支未测。
- 位置：入口与当前业务目标对应。 重复建议：保留一个主入口；次入口保持相同目标和文案。
- 证据：[student3/shots/E03-independent-retest.png](student3/shots/E03-independent-retest.png), [student3/shots/S12-relogin-retains-wrong-original-status.png](student3/shots/S12-relogin-retains-wrong-original-status.png)

| 账号profile | 方法/端点 | HTTP | 次数 | 首条原始证据 |
|---|---|---|---|---|
| student3 | GET /api/wrongs/options | 200 | 21 | student3/network.jsonl:55 |
| student3 | GET /api/wrongs/:id | 200 | 14 | student3/network.jsonl:61 |
| student3 | POST /api/ai/jobs | 201 | 4 | student3/network.jsonl:62 |
| student3 | GET /api/ai/jobs/:id | 200 | 12 | student3/network.jsonl:63 |
| student3 | GET /api/ai/jobs/:id/events | 200 | 4 | student3/network.jsonl:64 |
| student3 | PUT /api/wrongs/:id | 200 | 7 | student3/network.jsonl:71 |
| student3 | POST /api/wrongs/:id/attempts | 201 | 2 | student3/network.jsonl:78 |

### S13 学习记忆知识点证据、复习与纠正

- 结果：已验证。待复习建议、关联知识点和未关联证据都可看；证据显示原答/过程/待确认错因；理由为空保存禁用，填理由后保存出现修订记录并刷新保留。
- 第一反应：错题与复习→复习建议。可见路径：复习建议→简单方程→展开证据3x+5=20→提出纠正→理由→确认保存
- 写入回读：仅真实UI操作；对应网络记录见该profile network.jsonl，截图与动作/DOM快照可互相对照。
- 异常恢复/未测：证据展开、空理由禁用、保存修订、刷新已做；稍后延迟/完整复习队列未测。
- 位置：入口与当前业务目标对应。 重复建议：保留一个主入口；次入口保持相同目标和文案。
- 证据：[student3/shots/S13-memory-evidence.png](student3/shots/S13-memory-evidence.png)

| 账号profile | 方法/端点 | HTTP | 次数 | 首条原始证据 |
|---|---|---|---|---|
| student3 | GET /api/memory | 200 | 13 | student3/network.jsonl:8 |
| student3 | POST /api/memory/changes | 201 | 1 | student3/network.jsonl:125 |

### S14 学习记录查看原答/多次作答并导出

- 结果：已验证。显示x7需订正、x4正确、x7正确三条原始作答；docx实际下载35965字节，ZIP结构有效，document.xml含新任务、原错答与订正答案。
- 第一反应：学习记录→展开任务。可见路径：学习记录→点击新短课标题→三次作答→导出记录
- 写入回读：仅真实UI操作；对应网络记录见该profile network.jsonl，截图与动作/DOM快照可互相对照。
- 异常恢复/未测：实际导出内容和刷新记录已做；导出失败/超大记录未测。
- 位置：入口与当前业务目标对应。 重复建议：保留一个主入口；次入口保持相同目标和文案。
- 证据：[shots/S14-records-original-history.png](shots/S14-records-original-history.png), [downloads/learning-records.docx](downloads/learning-records.docx)

| 账号profile | 方法/端点 | HTTP | 次数 | 首条原始证据 |
|---|---|---|---|---|
| main | GET /api/platform | 200 | 30 | network.jsonl:5 |
| main | PUT /api/platform | 200 | 143 | network.jsonl:6 |

### S15 邀请码加入、双班切换与固定分配隔离

- 结果：已验证。非法码明确无效，空码按钮禁用；两班加入刷新保持；两个班筛选标签/路由由点击生成且可返回全部；后来加入一班未自动得到既有固定任务/考试。
- 第一反应：班级→输入邀请码。可见路径：学生3空码/非法码→隔离班有效码→一班有效码→各班查看学习任务→全部班级
- 写入回读：仅真实UI操作；对应网络记录见该profile network.jsonl，截图与动作/DOM快照可互相对照。
- 异常恢复/未测：空/非法/有效、刷新/重登、班级切换和隔离已做；邀请码过期/重复加入未测。
- 位置：入口与当前业务目标对应。 重复建议：保留一个主入口；次入口保持相同目标和文案。
- 证据：[student3/shots/S15-class-joined.png](student3/shots/S15-class-joined.png), [student3/shots/S15-class-one-filter-no-old-task.png](student3/shots/S15-class-one-filter-no-old-task.png), [student3/shots/S15-class-two-filter.png](student3/shots/S15-class-two-filter.png), [student3/shots/S15-student3-no-old-exam.png](student3/shots/S15-student3-no-old-exam.png)

| 账号profile | 方法/端点 | HTTP | 次数 | 首条原始证据 |
|---|---|---|---|---|
| student3 | GET /api/teaching/dashboard | 200 | 9 | student3/network.jsonl:5 |
| student3 | GET /api/teaching/classes | 200 | 9 | student3/network.jsonl:10 |
| student3 | POST /api/teaching/join | 422 | 1 | student3/network.jsonl:11 |
| student3 | POST /api/teaching/join | 200 | 2 | student3/network.jsonl:12 |
| student3 | GET /api/exams | 200 | 1 | student3/network.jsonl:197 |

### S16 考试开始、草稿恢复、原生确认交卷、成绩讲评

- 结果：业务完成，解析展示缺陷。主学生取消空答交卷确认后继续；两人保存并实际交卷，原生提示提交后只读；成绩发布后主30/30、学生2 18/30，分题讲评和自己的原答只读。存在解析字面\n及候选题文案问题。
- 第一反应：班级→考试。可见路径：两学生进入本轮新考试→开始→保存草稿→主刷新→原生确认→等待→成绩发布后回看
- 写入回读：仅真实UI操作；对应网络记录见该profile network.jsonl，截图与动作/DOM快照可互相对照。
- 异常恢复/未测：草稿刷新、交卷取消/确认、只读、发布后回看已做；自然超时自动交卷/并发交卷/考试撤回未测。
- 位置：入口与当前业务目标对应。 重复建议：保留一个主入口；次入口保持相同目标和文案。
- 证据：[shots/E04-draft-restored.png](shots/E04-draft-restored.png), [shots/E04-main-submitted.png](shots/E04-main-submitted.png), [shots/E04-main-score30.png](shots/E04-main-score30.png), [student2-online/shots/E04-student2-score.png](student2-online/shots/E04-student2-score.png), [student2-online/shots/E04-student2-wrong-comment.png](student2-online/shots/E04-student2-wrong-comment.png), [dialogs.jsonl](dialogs.jsonl)

| 账号profile | 方法/端点 | HTTP | 次数 | 首条原始证据 |
|---|---|---|---|---|
| main | GET /api/exams | 200 | 6 | network.jsonl:180 |
| main | GET /api/exams/:id | 200 | 4 | network.jsonl:188 |
| main | POST /api/exams/:id/start | 200 | 1 | network.jsonl:189 |
| main | PUT /api/exams/:id/answers | 200 | 3 | network.jsonl:190 |
| main | POST /api/exams/:id/submit | 200 | 1 | network.jsonl:202 |
| student2-online | GET /api/exams | 200 | 5 | student2-online/network.jsonl:28 |
| student2-online | GET /api/exams/:id | 200 | 3 | student2-online/network.jsonl:37 |
| student2-online | POST /api/exams/:id/start | 200 | 1 | student2-online/network.jsonl:38 |
| student2-online | PUT /api/exams/:id/answers | 200 | 3 | student2-online/network.jsonl:39 |
| student2-online | POST /api/exams/:id/submit | 200 | 1 | student2-online/network.jsonl:42 |

### S17 实时课堂双学生加入、回答、讲评

- 结果：已验证。两人实际加入，主x4正确/学生2x7错误，提交后原答只读；双方收到讲评且刷新保留。教师UI反馈2参加2提交1对1错。归档入口出现空编辑框，另列观察。 从归档空框继续“完成练习”后可回到已交结果、原讲评和作答记录，因此不判为原答丢失。
- 第一反应：班级→课堂。可见路径：本轮课堂→进入→加入→当前题→主草稿刷新→两人提交→教师讲评
- 写入回读：仅真实UI操作；对应网络记录见该profile network.jsonl，截图与动作/DOM快照可互相对照。
- 异常恢复/未测：未加入无提交按钮、空答禁用、保存刷新、提交后只读、讲评轮询已做；断线重连/撤题未测。
- 位置：入口与当前业务目标对应。 重复建议：保留一个主入口；次入口保持相同目标和文案。
- 证据：[shots/E05-main-draft-restored.png](shots/E05-main-draft-restored.png), [shots/E05-main-submitted.png](shots/E05-main-submitted.png), [shots/E05-main-comment-persisted.png](shots/E05-main-comment-persisted.png), [student2-online/shots/E05-student2-submitted.png](student2-online/shots/E05-student2-submitted.png), [student2-online/shots/E05-student2-comment.png](student2-online/shots/E05-student2-comment.png), [student2-online/shots/E05-student2-archive.png](student2-online/shots/E05-student2-archive.png), [student2-online/shots/E05-archive-result-feedback.png](student2-online/shots/E05-archive-result-feedback.png)

| 账号profile | 方法/端点 | HTTP | 次数 | 首条原始证据 |
|---|---|---|---|---|
| main | GET /api/live | 200 | 7 | network.jsonl:213 |
| main | GET /api/live/:id | 200 | 79 | network.jsonl:224 |
| main | POST /api/live/:id/join | 200 | 1 | network.jsonl:229 |
| main | PUT /api/live/:id/activities/:id/answer | 200 | 2 | network.jsonl:240 |
| student2-online | GET /api/live | 200 | 7 | student2-online/network.jsonl:53 |
| student2-online | GET /api/live/:id | 200 | 78 | student2-online/network.jsonl:64 |
| student2-online | POST /api/live/:id/join | 200 | 1 | student2-online/network.jsonl:69 |
| student2-online | PUT /api/live/:id/activities/:id/answer | 200 | 1 | student2-online/network.jsonl:81 |

### S18 学生反馈创建、回复、追加、状态、失败重试

- 结果：已验证。系统反馈创建201并刷新保留；两次学生追加和管理员回复/关闭完整保留；已回复与已关闭筛选正常；断网刷新显示连接失败+重新读取，联网重读恢复。
- 第一反应：帮助与反馈。可见路径：提交问题→无任务学习疑问被拦→改系统问题→新增→追加→管理员回复→学生回看追加→管理员关闭
- 写入回读：仅真实UI操作；对应网络记录见该profile network.jsonl，截图与动作/DOM快照可互相对照。
- 异常恢复/未测：空文本禁用、无任务422校验、创建/追加/状态/断网恢复/重登已做；服务端500/提交超时未测。
- 位置：入口与当前业务目标对应。 重复建议：保留一个主入口；次入口保持相同目标和文案。
- 证据：[student3/shots/S18-feedback-added.png](student3/shots/S18-feedback-added.png), [student3/shots/S18-feedback-offline-error.png](student3/shots/S18-feedback-offline-error.png), [student3/shots/S18-admin-reply-read.png](student3/shots/S18-admin-reply-read.png), [student3/shots/S18-feedback-closed.png](student3/shots/S18-feedback-closed.png), [student3/shots/S18-closed-history.png](student3/shots/S18-closed-history.png)

| 账号profile | 方法/端点 | HTTP | 次数 | 首条原始证据 |
|---|---|---|---|---|
| student3 | GET /api/support | 200 | 14 | student3/network.jsonl:26 |
| student3 | GET /api/ai/failures | 200 | 8 | student3/network.jsonl:27 |
| student3 | POST /api/support | 422 | 1 | student3/network.jsonl:28 |
| student3 | POST /api/support | 201 | 1 | student3/network.jsonl:35 |
| student3 | POST /api/support/:id/events | 200 | 2 | student3/network.jsonl:43 |
| student3 | GET /api/support | net::ERR_INTERNET_DISCONNECTED | 1 | student3/network.jsonl:51 |

### S19 教师补充、分层任务与提交/学情回看

- 结果：分层与补充提交已验证；后续反馈失败。两账号只显示各自组任务，均两题真实提交并已交老师；教师刷新确认两组各1/1已交。主补充文本提交且刷新保留，教师确认1/1完成及完整文字。教师后续反馈按钮请求405，学生刷新仍无该反馈；该子功能失败。学生2未看到主学生的定向补充；两人均看到新增取消安排的已取消状态且无处理按钮。
- 第一反应：学习任务/本课资料与进度。可见路径：主巩固/学生2证据不足→分别两题→完成→交老师确认；原短课结果→资料→补充→开始处理→提交说明
- 写入回读：仅真实UI操作；对应网络记录见该profile network.jsonl，截图与动作/DOM快照可互相对照。
- 异常恢复/未测：分组/定向隔离、空说明禁用、提交、刷新、撤销后只读已做；教师后续反馈405由教师真实按钮与网络复核，学生端无反馈可读。
- 位置：分层新任务在首页易找；补充藏在结果页资料抽屉，首页提醒可提供直接到待处理补充。 重复建议：保留一个主入口；次入口保持相同目标和文案。
- 证据：[shots/S19-main-groups-isolated.png](shots/S19-main-groups-isolated.png), [shots/S19-main-group-submitted.png](shots/S19-main-group-submitted.png), [shots/S19-supplement-persisted.png](shots/S19-supplement-persisted.png), [student2-online/shots/S19-student2-groups-isolated.png](student2-online/shots/S19-student2-groups-isolated.png), [student2-online/shots/S19-student2-group-submitted.png](student2-online/shots/S19-student2-group-submitted.png), [shots/S19-followup-feedback-read.png](shots/S19-followup-feedback-read.png), [student2-online/shots/S19-student2-no-targeted-supplement.png](student2-online/shots/S19-student2-no-targeted-supplement.png)

| 账号profile | 方法/端点 | HTTP | 次数 | 首条原始证据 |
|---|---|---|---|---|
| main | GET /api/teaching/dashboard | 200 | 9 | network.jsonl:8 |
| main | GET /api/teaching/tasks/:id/supplements | 200 | 8 | network.jsonl:89 |
| main | POST /api/records/:id/attempts | 201 | 6 | network.jsonl:103 |
| main | POST /api/records/:id/submit | 200 | 2 | network.jsonl:169 |
| main | POST /api/teaching/supplements/:id/start | 200 | 1 | network.jsonl:354 |
| main | POST /api/teaching/supplements/:id/submit | 200 | 1 | network.jsonl:356 |
| student2-online | GET /api/teaching/dashboard | 200 | 7 | student2-online/network.jsonl:5 |
| student2-online | POST /api/records/:id/attempts | 201 | 3 | student2-online/network.jsonl:14 |
| student2-online | POST /api/records/:id/submit | 200 | 1 | student2-online/network.jsonl:172 |
| student2-online | GET /api/teaching/tasks/:id/supplements | 200 | 1 | student2-online/network.jsonl:210 |

### S20 实际离线下载、加密、断网草稿、关闭重开、冲突同步、导出删除锁定

- 结果：缺陷：同任务其他草稿绕过比较。下载和断网学习真实完成；重复保存同题仍2条待同步（位置+答案）；断网重开恢复x4和解释；并发在线x5导致409，但仅比较位置的确认随后自动把答案x4写掉x5，未逐题比较，属于缺陷；再次同步0条未重复写。副本591字节含x4；本机下载删除/锁定退出原生后果确认均已实际执行，仅自己新档案。
- 第一反应：离线学习。可见路径：学生2首次设口令→下载本轮课→真断网→阅读/草稿→关浏览器→断网重开→解锁恢复→另一profile在线新编辑→联网同步→冲突确认→导出副本→删除下载→锁定退出
- 写入回读：仅真实UI操作；对应网络记录见该profile network.jsonl，截图与动作/DOM快照可互相对照。
- 异常恢复/未测：实际断网/关闭重开/并发/409/本机确认/重复同步/导出/删除/锁定退出已做；坏口令/本机空间不足未测。
- 位置：离线学习独立入口清楚；冲突列表默认折叠、位置比较无内容，必须提升可见性并逐草稿比较。 重复建议：保留一个主入口；次入口保持相同目标和文案。
- 证据：[student2/shots/E06-downloaded.png](student2/shots/E06-downloaded.png), [student2/shots/E06-offline-draft.png](student2/shots/E06-offline-draft.png), [student2/shots/E06-reopened-offline-restored.png](student2/shots/E06-reopened-offline-restored.png), [student2/shots/E06-conflict-compare.png](student2/shots/E06-conflict-compare.png), [student2/shots/E06-conflict-after-progress.png](student2/shots/E06-conflict-after-progress.png), [student2-online/shots/E06-online-newer.png](student2-online/shots/E06-online-newer.png), [student2-online/shots/E06-online-after-uncompared-answer.png](student2-online/shots/E06-online-after-uncompared-answer.png), [student2/shots/E06-download-deleted.png](student2/shots/E06-download-deleted.png), [student2/shots/E06-locked-exited.png](student2/shots/E06-locked-exited.png), [student2/dialogs.jsonl](student2/dialogs.jsonl)

| 账号profile | 方法/端点 | HTTP | 次数 | 首条原始证据 |
|---|---|---|---|---|
| student2 | GET /api/offline/tasks | 200 | 5 | student2/network.jsonl:70 |
| student2 | GET /api/offline/packages/:id | 200 | 1 | student2/network.jsonl:91 |
| student2 | POST /api/offline/sync | 409 | 1 | student2/network.jsonl:100 |
| student2 | POST /api/offline/sync | 200 | 2 | student2/network.jsonl:104 |
| student2 | GET /api/offline/tasks | 401 | 1 | student2/network.jsonl:110 |

### S21 原生语音输入/朗读及文字回退

- 结果：环境限制，语音未通过。ASR实际报未获得麦克风权限，请继续文字输入；TTS准备后报设备没有可用中文朗读声音，请继续阅读文字。文字输入和后续业务可继续，语音本身未通过。
- 第一反应：语音输入/朗读。可见路径：学习助手语音输入；考试成绩朗读
- 写入回读：仅真实UI操作；对应网络记录见该profile network.jsonl，截图与动作/DOM快照可互相对照。
- 异常恢复/未测：真实设备/权限失败提示与文字回退已做；没有伪造设备或成功转写。
- 位置：入口与当前业务目标对应。 重复建议：保留一个主入口；次入口保持相同目标和文案。
- 证据：[shots/S21-asr-observed.png](shots/S21-asr-observed.png), [student2-online/shots/S21-tts-after.png](student2-online/shots/S21-tts-after.png)

### S22 新学习问题绑定当前任务并回看教师回复

- 结果：已验证。新问题实际POST 201，绑定本轮新短课；教师真实回复后刷新显示已回复，打开看见两边同减3保持差为0、同除非零2得到x=4及代入检验的完整文字，历史问题未修改。
- 第一反应：帮助与反馈→提交问题。可见路径：提交问题→学习疑问→可见任务选择新短课→填写新合成问题→提交→刷新→已回复问题→对话记录
- 写入回读：创建后刷新重读；教师回复后再次刷新并打开原问题读取完整回复，状态为已回复。
- 异常恢复/未测：无任务学习疑问422已在S18验证；新问题创建/回复回读完成；本问题追加和关闭未重复测试，系统问题的追加/关闭见S18。
- 位置：学习疑问需要在通用帮助页重新选任务；课内直接携带任务上下文会更清楚。 重复建议：问题与回复保留统一入口，课内求助可复用并预选当前任务。
- 证据：[shots/S18-new-learning-issue-for-teacher.png](shots/S18-new-learning-issue-for-teacher.png), [shots/S22-learning-issue-current.png](shots/S22-learning-issue-current.png), [shots/S22-learning-issue-teacher-reply.png](shots/S22-learning-issue-teacher-reply.png)

| 账号profile | 方法/端点 | HTTP | 次数 | 首条原始证据 |
|---|---|---|---|---|
| main | GET /api/support | 200 | 6 | network.jsonl:415 |
| main | POST /api/support | 201 | 1 | network.jsonl:416 |

## 验收边界

- 未全组合覆盖每个写操作的500、超时、权限过期/撤回和并发；已测异常逐项列出，不把未测记通过。
- 旧种子等式课只保存学习进度/新增作答，完整提交E02使用教师本轮新发布课。
- 初期helper曾把折叠details子元素列入DOM；相关无效动作剔除，错因确认通过实际打开折叠区重新完成。原始动作保留供审计。
- ASR/TTS仅失败回退通过，音频采集/播放质量未通过。
- 本轮停止新增AI长请求；未将同一份接口成功返回、页面正常或主观评分当作全功能通过。无业务源码/API脚本读取和写入。

## 待收尾

- R1新profile复测已上报缺陷及E06两profile逐条冲突；补充后续反馈405需教师端修复后重发、学生回看。
