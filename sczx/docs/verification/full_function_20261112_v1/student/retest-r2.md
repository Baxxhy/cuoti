# 学生 R2 定点复测

三份全新profile，收到受控中断恢复完成通知后开始；实际主JS为 index-8bNtgQgl.js。

同一原E04第2题的旧解析格式修复通过，原答和成绩保持只读。教师指定复习说明与绑定课堂证据已回看并返回，实际入口限制单独记录。

## R2-S16 同一原E04第2题旧解析实际分行、隐藏流程尾注且保留原答和成绩

修复通过。旧解析已显示真实换行，提示、分步解释1/2/3分行，计算样式white-space:pre-wrap；页面无字面反斜杠n、无“待教师审核的候选题”尾注。总分18/30、第2题0/10、原答x8及原始解释完整保留。input/textarea readOnly=true；真实点击答案并按Backspace后仍x8，无写请求；刷新后相同。

第一反应：班级→考试。
可见路径：学生2全新profile正常登录→班级→考试→原E04已发布卷→下一题→第2题；刷新再点击第2题
回读：只做原考试GET读取、键盘只读检查和刷新；没有提交、保存或修改任何旧答案。
边界：本轮以同一旧数据验证展示层修复，未重跑考试创建/批阅/故障注入。

证据：[r2-student2/shots/r2-original-exam-format-fixed.png](r2-student2/shots/r2-original-exam-format-fixed.png), [r2-student2/shots/r2-original-answer-readonly-unchanged.png](r2-student2/shots/r2-original-answer-readonly-unchanged.png), [r2-student2/r2-snapshots.jsonl](r2-student2/r2-snapshots.jsonl)

## R2-S13 找到已有教师指定复习说明，回看绑定课堂证据并返回学习记忆

内容和原证据往返完成；指定条直达入口未验证。找到完整“R1复习内容1112：请回看课堂记录，比较x4与移项符号误答，说明两边同时做相同运算。”。同页11:00原课堂证据展开显示x4及两边同减3/同除2说明；查看原任务进入正确“课堂记录 · 合成工程验收 E01 等式平衡短课”，讲评说明同减3不能仍加3、同除2、代入检验；学习记录展开为1次作答2*x+3=11→x4。经可见导航返回复习建议并重读指定说明。

第一反应：错题与复习→复习建议。
可见路径：主学生全新profile正常登录→错题与复习→复习建议→尚未关联知识点下11:00独立答对2*x+3=11→展开原答→修订记录→教师指定复习说明→同页查看原任务→课堂学习结果/讲评→1作答记录→展开课堂记录→错题与复习→复习建议→重开修订记录
回读：GET memory/platform重读教师现有安排与原答，没有添加、纠正或替换学习证据。
边界：顶部当前复习卡仍为较早的等式性质继续订正；没有推进既有复习队列。教师指定复习在底部修订记录内仅显示文字，没有独立直达按钮。本次通过其绑定证据进入，不把未走到的指定条开始复习记通过。

证据：[r2-main/shots/r2-memory-review-entry.png](r2-main/shots/r2-memory-review-entry.png), [r2-main/shots/r2-teacher-review-audit-entry.png](r2-main/shots/r2-teacher-review-audit-entry.png), [r2-main/shots/r2-memory-to-original-class-record.png](r2-main/shots/r2-memory-to-original-class-record.png), [r2-main/shots/r2-class-original-answer-and-review.png](r2-main/shots/r2-class-original-answer-and-review.png), [r2-main/shots/r2-return-to-memory-teacher-review.png](r2-main/shots/r2-return-to-memory-teacher-review.png)

## R2-S05 单元进度统计、后续课时定位与返回

统计查看及02课定位往返通过。一元一次方程显示0/5课已提交，01等式性质学习中，02–05待开始。没有单独名为下一课的按钮，本次按可见顺序选择02行的进入学习，真实进入“解简单的一元一次方程”第1/7步“确定未知量与运算顺序”，课内例题2x+3=11；未点击下一步、未作答。返回课程后重开单元进度，0/5与原状态一致。E01单元显示1/2课已提交：E01已反馈，R1教研改编目标尚未分配且无进入按钮。

第一反应：学习→课程→单元进度。
可见路径：新profile正常登录→课程→展开一元一次方程的单元进度→第02行进入学习→对应课时1/7→我的学习→课程→重开单元进度；再展开E01单元统计
回读：通过课程/单元进度GET与已分配课时跳转读取，没有提交答案、推进步骤或发AI。
边界：只验证现有数据统计及跳转，不扩张为完成五课后的下一课自动推荐/统计增量已通过；未分配课无学习按钮。

证据：[r2-unit/shots/r2-unit-progress-assigned-status.png](r2-unit/shots/r2-unit-progress-assigned-status.png), [r2-unit/shots/r2-unit-next-lesson-correct-target.png](r2-unit/shots/r2-unit-next-lesson-correct-target.png), [r2-unit/shots/r2-unit-return-retains-status.png](r2-unit/shots/r2-unit-return-retains-status.png), [r2-unit/shots/r2-unit-completed-assigned-scope.png](r2-unit/shots/r2-unit-completed-assigned-scope.png)

## 验收边界

- 本轮仅这三项定点复测；无新AI、E06重做、语音验证或全平台视觉重跑。
- ASR/TTS设备限制与未覆盖故障边界沿用基准及主代理技术补测，不扩大本轮结论。
