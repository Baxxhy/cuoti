# 全界面重构验收证据

2026-11-11—12，基线746a2a1。源码、数据和当前运行结果共同核对。

- pages.json：8099当前新版33个角色页面×三种桌面宽度，实际标题、可见操作、横向溢出和运行异常。
- screens/：99张主要页面截图，另含登录、原文、未知路由、五课正文与编辑/批阅状态。
- before/：相同账号和桌面宽度的旧版参考。
- teacher-interactions.json、operations-interactions.json、student-shell.json、student-details.json：真实鼠标/键盘交互。
- frontend-tests-final.log：27项浏览器回归。unit-tests-final.log：4项JS单元检查。
- backend-tests.log：168项独立MySQL测试，无跳过。
- student-reading-and-routes.json：qmx登录、五课学生正文、原文与未知路由。
- local-update.json：原21个任务快照未改，数据库未重启。
- contrast.json：四个关键页面工作区实际颜色与背景检查。
- fresh/：从零实例F01—F12、五课新版本、离线关闭重开/同步、备份与恢复证据；report.json有逐项关联ID和实际结果。
- manifest.json：公开文件摘要，manifest自身不计入。

8102是隔离的工程验收实例，使用合成学习者、工程输入和程序核验，不声称真人教学效果。语音保留V01/V03设备限制。

账号密码、SQL备份、原始材料、浏览器配置与私有状态均留在本机忽略目录，未放入此证据目录。历史视频和旧手册仍是历史版本；当前界面以本目录和web_20261112_v1手册为准。

- export/：本轮新实例真实教案DOCX及LibreOffice渲染PDF，字体/颜色/A4与页内文字检查。
- ci.json：本轮源码提交对应的远端双CI结果。
