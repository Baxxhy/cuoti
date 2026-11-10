# 第十六步证据索引

2026-11-11，v1。数据均为自编隔离验收；正式库仅保存内容映射与不变性摘要，不包含私有SQL、Cookie、凭据或真实学生原文。

- 内容：human-review.json、content-inventory.json、content-reference-checks.json、content-quality.json、content-main-installed.json、main-protection.json、main-smoke.json。
- 自动检查：tests-final.log（114）、frontend-final.log（17）、frontend-unit-final.log（4个文件）、build-final.log。初始失败与中间轮日志另保留，终验不改写原失败。
- 教师：agent-initial.json、teacher-browser.json、tasks.json。
- 学生：student-browser.log/first-failure.json与student-browser.json（保留第一课后resume），model-unit.json（35流程、30实际模型）、question-images.json及五张题图。
- 三题补救：repair-unit.json（含证据拒绝）及repair-retry.json（仅补第一次失败的乘法题）；初次失败没有保存被拒绝的原始模型候选正文，保留错误原因/任务及后续成功原文，不伪称失败输出已完整留存。
- 干预/反馈：feedback-flow.json、search-intervention.json、final-browser.json；最后一份含浏览器实际编辑、重登和三宽度截图。初次浏览器脚本未等待表单同步的失败保留于final-browser.log/failure.json，不当作成功证据。
- 冷加载：cold-load.json为全新浏览器禁用缓存的生产登录页面；final-browser的导航含重登缓存，不当冷加载。
- 部署：restart-recovery.json、release-smoke.json、runtime-check.json、backup-restore.json（最终全部表及7文件一致），backup-restore-initial.json为更早一次真实恢复；所有SQL/tar/config留本机不上传。
- 文档：export-metrics.json、docx-render.json及四页PNG；DOCX/PDF在../../exports/20261111_v1。系统旧Office失败日志与可运行25.2渲染日志分开保存。
- 视觉：unit-catalog-final、teacher-unit-insights-final、student-unit-result-final各1440/1920/2560。unit-catalog-1920.png为修复前竖排缺陷，不能拿它代表最终效果。
- source-sha256.json是本轮源码摘要；evidence-sha256.json为归档文件摘要。scripts仅含自编验收脚本，读取本机Git外私有fixture/config后才可运行，不能直接对正式库执行seed-preview或回放验收。

[35项验收](../../planning/第十六步统一验收表_20261111_v1.md) · [真实流程/指标](../../planning/第十六步完整业务与评测报告_20261111_v1.md)。仅本机预发布，不宣称公网正式上线或真实教学效果。
