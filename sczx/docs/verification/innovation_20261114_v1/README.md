# 第一轮创新链路证据

2026-11-14。合成工程夹具；不包含真实学生或名师课堂效果结论。

- [统一验收表与返修](../../planning/第一轮实施与验收报告.md)
- `controlled-chain.json`：真实MySQL/API，管理员案例审核发布、学生指导、独立尝试0调用、教师备课与确认、v2修订及旧任务保护。模型输出受控，不是实际AI效果。
- `real-guidance-chain.json`：学生实际Codex CLI gpt-6-luna/low调用1次，约26.9秒；同链教师生成明确为受控提供者。包括来源、匹配证据、最终输出与原始run。
- `browser-real.json`：独立三账号实际登录；5175网页连接隔离8104 API，管理员出处、教师依据、学生既有真实指导；成功项与脚本异常实际记录。
- `checks.json`：检查结果、有效证据范围、命令与构建信息。
- `admin-source.png`、`teacher-decision.png`、`student-guidance.png`：1440×1000真实桌面截图。
- `admin-source-before-fix.png`：旧steps字符串导致出处页渲染失败的修复前截图，不能当最终页面。

## 复现

所有数据库检查必须使用独立全新`sczx_test_*`库及独立SCZX_STORAGE_DIR。环境配置保存在私有临时文件，不能提交凭据；原有套件使用固定测试用户名，不在同一测试库第二次重建全部账号。

```bash
PYTHONPATH=backend-business SCZX_RUN_MYSQL_TESTS=1 .venv/bin/python -m unittest discover -s backend-business/tests -v
CHROME_PATH=/path/to/chromium npm --prefix frontend test
npm --prefix frontend run test:unit
npm --prefix frontend run audit:ui
.venv/bin/python deploy/build_frontend.py
```

新链路单独复现：在完成原有测试库初始化后，将`backend-business/tests`加入PYTHONPATH，运行`python -m unittest test_experience_mysql -v`。可设置SCZX_INNOVATION_EVIDENCE输出JSON、SCZX_INNOVATION_LOGIN_FILE输出仅本机使用的随机验收账号与业务ID。默认模型受控；显式设置SCZX_INNOVATION_REAL=1才执行真实Codex指导，应单独运行M01并把输出写到不同文件。

三端业务实走脚本为`backend-business/tests/accept_experience_browser.mjs`。需要先启动指向同一测试库的隔离API服务（本轮8104，无后台worker），允许5175跨域；设置SCZX_INNOVATION_PRIVATE为上一步私有账号文件，SCZX_INNOVATION_CHAIN为相应JSON。脚本只在测试库账号上创建修订草稿、切换课时位置，截图写到本目录。页面仍使用5175，不改变日常5175→8099代理或重启8099。运行前先确认配置是测试库。

本地源环境已提供Chromium与当前Codex登录配置；未读取备用API凭据。原始输出中的版本和用户均为本次随机验收夹具，不能复用于正式账号。
