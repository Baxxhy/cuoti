# 第十一步证据与复现

日期 2026-11-10　版本 v1

- mysql-tests.log/json：最终42项后端套件全部通过，隔离库sczx_test_teaching_3a7c918e；原31项加10项新增MySQL场景和1项日期边界单元。
- frontend-tests.log：7项真实Chromium回归，包括班级延迟响应、无学生记录、离页首页旧响应。
- frontend-unit.log：1项JavaScript单元通过。build.log：Vite生产构建成功，只有既有大chunk提示。
- browser-flow.json：完整师生操作，共16个记录步骤，包含新增发布任务ID，无脚本异常。
- browser-edge.json：6个补充场景：消息跳转、重登已读、错题补救刷新、班级刷新、网页移出及历史只读。
- desktop.json：教师班级/首页/学情，学生首页/结果/学习，6页×3宽；errors为空，横向滚动宽度没有超出视口。
- fixtures.json：2教师、3班、9名班内学生、跨班/晚加入关系与6原任务；隔离浏览器库sczx_test_teaching_browser_ce1977。
- migration.json：在单独测试库重建0009结构，再升级0010两次，旧数据摘要一致，旧补充文本保持note。
- business-migration.json：sczx业务库增量升级，原班级、成员、任务、学生记录、教案、案例、文件和补充说明的数量及哈希均未变。
- main-smoke.json：升级主服务后，原教师/学生账号的8个只读接口均200。
- PNG为实际截图，历史只读额外1张；sha256.json为原始证据文件校验值。

## 可重复执行

需要已有MySQL、backend-business依赖、Node依赖和Chromium。本仓库没有Makefile或backend-algorithms，按当前工程的真实入口验证。业务源码为Vue/JavaScript与FastAPI，不按旧项目说明重建其他后端。

先创建全新的独立sczx_test_*库，并通过SCZX_DATABASE_URL指定。禁止把下面的测试和种子命令指向sczx业务库。

```bash
PYTHONPATH=backend-business SCZX_RUN_MYSQL_TESTS=1 python -m unittest discover -s backend-business/tests -v
CHROME_PATH=/path/to/chrome npm --prefix frontend test
npm --prefix frontend run test:unit
npm --prefix frontend run build
```

真实网页流程要另建空的sczx_test_*库，再执行：

```bash
PYTHONPATH=backend-business python backend-business/tests/seed_teaching_acceptance.py --output /tmp/sczx-step11/browser-private.json
```

种子包含测试密码，仅写入权限0600的临时文件，不提交。用同一数据库启动验收FastAPI8001；以SCZX_API_PROXY=http://127.0.0.1:8001启动Vite5178。随后依次运行本目录browser-flow.mjs、browser-edge.mjs、desktop-capture.mjs，设置CHROME_PATH。本轮原始脚本使用/tmp/sczx-step11输出，完整流程要求新种子：不要在已跑完的班级数据上再次假定“首次加入”。学校班级名与账号均是自编样例。

持久浏览器测试文件位于frontend/tests/teaching-class.test.mjs。API测试位于backend-business/tests/test_teaching_mysql.py。完整流程真实点击Reka选择器需指针事件；普通DOM click不能代表该组件的实际鼠标交互。

## 桌面截图

|页面|1440|1920|2560|
|---|---|---|---|
|教师班级|[图](teacher-class-1440.png)|[图](teacher-class-1920.png)|[图](teacher-class-2560.png)|
|教师首页|[图](teacher-home-1440.png)|[图](teacher-home-1920.png)|[图](teacher-home-2560.png)|
|教师学情|[图](teacher-insights-1440.png)|[图](teacher-insights-1920.png)|[图](teacher-insights-2560.png)|
|学生首页|[图](student-home-1440.png)|[图](student-home-1920.png)|[图](student-home-2560.png)|
|学生结果|[图](student-result-1440.png)|[图](student-result-1920.png)|[图](student-result-2560.png)|
|学生学习|[图](student-learning-1440.png)|[图](student-learning-1920.png)|[图](student-learning-2560.png)|

自审检查层级、文字对比、导航密度、控件宽度、主操作、三栏/两栏分配和横向溢出。教师学情8格统计在1440仍可读；宽屏右栏用于真实消息和班级入口，没有填充口号。
