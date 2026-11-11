# 第十七步证据索引

2026-11-11，v1。原生语音V01/V03阻塞；CI在推送后读取结论。不能声明本步全部完成。所有学生活动均为工程自编验收数据，不含正式SQL、配置、Cookie、密码或真实学生资料。

- 最终回归：tests-delivery.log（128）、frontend-delivery.log（21）、frontend-unit.log（4JS文件）、build-frozen.log。初验及中间失败日志保留，最终证据不覆盖失败。
- 教师真实UI：teacher-browser.json，录题→约束组卷→手改→预览→审核→发布；candidate-check.json为真实Codex任务采用待审核草稿；flow-fixture保存实际准备题。
- 学生真实UI：student-browser-initial.json/截图为初次恢复故障，student-browser.json及retry.log为修复后原记录继续；other-submissions为另外三人实际API提交。
- 批阅/结果：grading-browser.json四份实际审计与总分，results-browser.json学生重登、错题来源和教师记忆，final-pages.json保存试卷重开及宽度；三宽截图分别为teacher-grading/student-result/exam-bank/exam-papers等。
- 补救：exam-repair.json四次实际Codex任务，实际返回方程及答案、独立复测、学生和教师记忆；工程计算答案不是人类学习效果。equation-browser.json为方程教具实际操作/恢复/拒绝/撤销/重置。
- 导出：export-check.json、docx-render-check.json和实际渲染log；六份DOCX/PDF在../../exports/20261111_v2。正文全黑，宋体/TNR，A4及边界检查。没有伪称新版Word/WPS人工验收。
- 迁移：migration-check.json为真实正式备份的独立空库恢复及0014验证，全旧行不变；正式库本轮未执行升级。main-protect-before初次失败是旧8000端口未运行，第二次完成私有备份。
- 语音：native-audio-permission-initial.json默认权限失败；native-audio.json及native-audio-granted.log为授予临时麦克风权限后真实流可打开、仍未识别及无中文声音。没有假设备或音频文件注入。模拟引擎控制检查仅在frontend-delivery.log中，不能代替实机。
- CI：ci-receipt.json在推送后记录远端运行；原修复e9b6159对应运行42943733716已通过。新增MySQL Job的结果单独核对。
- 日志归档仅规范化行尾空白以遵守CI，不删错误正文；原始日志仍保留在/tmp/sczx-step17。scripts为本次验收复现脚本，依赖本机Git外私有配置，不能直接对正式库回放。

[38项验收](../../planning/第十七步统一验收表_20261111_v1.md) · [限制与审批阻塞](../../planning/第十七步遗留问题_20261111_v1.md)。
