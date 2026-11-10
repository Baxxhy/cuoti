# 第十二步证据与复现

日期2026-11-10，版本v1。

## 验收来源

mysql-tests.log/json是最终54项后端套件，数据库sczx_test_tutoring_*，返回码0。frontend-final.log为10项真实Chromium，frontend-unit.log为1项JS，build-final.log为Vite生产构建。执行时间见execution-times.json，模型精确耗时和时间见各ModelRun。

browser-flow.json保存19步真实师生流、9个模型任务详情。它保留机器检查曾通过的原记录，但其中确认图与原题混用的问题在复核发现；该分支的最终结果以ocr-focus.json为准：新上传→OCR→用户确认→正确图像对象的指导→刷新→教师回看与反馈→学生读取，记录为5个主要检查点。audit-issues.json不删除初验失败或将其改成通过。

faults.json包含受控中断注入与真实恢复函数、真实Codex手动重试、实际生成中移出后不写回、同请求重复返回同ID、禁止新建/重试及停止保留历史。注入故障不是外部服务自然超时。desktop.json包含真实断网保存失败、保留草稿、联网重试/刷新及求助焦点；15张桌面截图验证1440/1920/2560。

image-integrity.json证明原PNG与上传字节相同，OCR原文、人工修订、公式与原任务ID分别保留。question.png是项目自编图片，不是用户真实作业。

main-protection.json与main-smoke.json是正式sczx服务只读检查及原学习任务、作答、教案、文件、案例、班级的哈希保护，不使用正式库做测试夹具。无新迁移。

评测有25固定情境、100行真实比较、88次外部调用，原始请求、结果、模型、耗时和错误/修订都在evaluation/results.json。B0违规是离线按新版规则审查，不表示旧系统已拦截。B1/B2/B3各有5个程序自主检查点，不能冒充模型调用。用户单人复核仅覆盖B3 25项；原话及范围见evaluation/human-review.json。数据不代表真实课堂效果。

## 复现

依赖沿用backend-business/pyproject.toml与frontend/package-lock.json。先新建独立sczx_test_* MySQL库，用SCZX_DATABASE_URL指定，切勿指向正式sczx库。

```bash
PYTHONPATH=backend-business SCZX_RUN_MYSQL_TESTS=1 python -m unittest discover -s backend-business/tests -v
CHROME_PATH=/path/to/chrome npm --prefix frontend test
npm --prefix frontend run test:unit
npm --prefix frontend run build
```

fixture.py从空测试库生成2教师、3班、11学生、两课时/知识点及只读任务，凭据只存/tmp/sczx-step12/browser-private.json（0600），不提交。以同库运行FastAPI8001，SCZX_STORAGE_DIR指定/tmp/sczx-step12/uploads-final；以SCZX_API_PROXY=http://127.0.0.1:8001运行Vite5178。真实模型使用既有Codex CLI登录与gpt-6-luna/low，不接入备用凭据。

依次运行browser-flow.mjs、ocr-focus.mjs、faults.py、desktop.mjs；原脚本使用/tmp/sczx-step12输出，首次流程要求全新夹具。browser-flow.mjs保留初验完整路径供复现，但修订后图像目标已有服务端约束。evaluation/run.py运行25情境四方法比较，需同路径私有夹具，最多并行2个；会真实消费外部模型。重复验收不要误用旧数据假定“第一次发布/加入”。脚本工作目录为项目根，CDP模块用相对路径。

持久回归：backend-business/tests/test_tutoring_mysql.py、test_tutoring_policy.py、frontend/tests/tutoring-scope.test.mjs。受控提供者只用于程序边界测试，不作为真实模型效果证据。

## 截图

|页面|1440|1920|2560|
|---|---|---|---|
|学生学习|[图](student-learning-1440.png)|[图](student-learning-1920.png)|[图](student-learning-2560.png)|
|独立检查与题图指导|[图](student-check-1440.png)|[图](student-check-1920.png)|[图](student-check-2560.png)|
|学习结果|[图](student-result-1440.png)|[图](student-result-1920.png)|[图](student-result-2560.png)|
|教师学情|[图](teacher-insights-1440.png)|[图](teacher-insights-1920.png)|[图](teacher-insights-2560.png)|
|教师过程弹窗|[图](teacher-guidance-history-1440.png)|[图](teacher-guidance-history-1920.png)|[图](teacher-guidance-history-2560.png)|

sha256.json记录归档文件摘要。原始失败日志保留；坏输出不计入最终通过结果，未知数学不改成正确。

output-audit.json将直接答案检查同时应用到文本和结构化mathClaims，重审100条最终比较行，通过计数不变；不代表每次初始调用均无问题。修订前的调用和修订理由仍在evaluation/results.json的calls中。B0是旧单次指令/schema加统一公开字段的离线比较，不是对旧线上系统所有行为的复刻。
