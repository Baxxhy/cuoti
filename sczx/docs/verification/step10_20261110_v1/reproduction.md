# 复现与数据说明

日期 2026-11-10　版本 v1

## 自动化

项目根目录安装backend-business既有Python依赖及frontend锁定依赖。无外部模型、无MySQL的基础检查：

```bash
PYTHONPATH=backend-business python -m unittest discover -s backend-business/tests -v
python -m compileall -q backend-business/sczx_business
PYTHONPATH=backend-business python -c 'import sczx_business.main'
npm --prefix frontend run test:unit
npm --prefix frontend run build
git diff --check
```

核心测试会明确跳过MySQL集成部分，不能将跳过计为通过。MySQL完整测试先新建独立sczx_test_*数据库，以环境变量设置SCZX_DATABASE_URL及SCZX_RUN_MYSQL_TESTS=1，再执行同一unittest命令。测试拒绝业务库名，不自动删除测试库。实际数据库、完整起止时间和返回码见mysql-tests.json。

启动Vite到5177后：

```bash
CHROME_PATH=/path/to/existing/chromium npm --prefix frontend test
```

Node22以上。该命令含受控延迟/SSE/助手/历史切换/保存响应测试，不消耗外部模型，不可描述为真实Codex请求。

## 实际浏览器数据与操作

使用现有演示教师和学生账号，账号密码留在本地忽略配置，本归档不包含凭据。素材为4篇自编案例、等式性质课时、另一乘除应用课时和既有自编验收班级。

1. 教师打开等式性质备课，修改目标/学生基础/重点；案例与版本中查“等式性质”，阅读来源，选择主案例v6、辅助v2，保存并刷新。
2. 三类真实任务输入见real-jobs.json；原始完整结果按agent-*.json保存。浏览器对activity保存手写首块，再局部生成eq-balance，展开差异并不采用；随后明确采用全量建议和另一个局部建议。
3. 点击另一课时历史，核对URL/任务/引用并刷新；旧v4来源与当前v5冲突被阻止。教师在备课页明确采用当前发布课时后，再通过UI生成并确认，完整记录agent-foundation-current.json。
4. 版本界面恢复已保留的v8生成教案，再恢复原始历史并恢复生成版；最终当前v12。已保存的旧版本不变。
5. 三桌面宽度检查教案/Agent滚动、长文与差异；真实截图在docs/design/screenshots_20261110_v2。
6. 预览后选择既有验收班并主动发布，task-fa4796a71a3835e71d9a02e72f233bab。学生两道随堂练习、天平解释与进度、提示后检查、换新题独立尝试、提交；教师反馈后学生回看。
7. 原有任务另外完成实际题图OCR、修改确认文本、真实文字指导、刷新和教师过程回看，具体jobId见stage8-browser.json。

运行取消使用单独任务，观察generate节点running后取消，保留前三成功节点，完整before/after和模型运行在cancel-running.json。模型运行中管理员发布V2的精确场景由持久隔离API测试完成，provider被人工门闩控制；不是另一条真实模型证据。

## DOCX

教案导出样例为选定v12，含8活动、6题、主辅案例和实际来源。python-docx打开/逐项比对/编辑副本保存再打开通过，样例本身未加入验证段落。Office程序启动失败保留三个日志；用户未复核，因此Office实机一项阻塞。没有PDF样例，不宣称已渲染成功。

## 证据口径

environment.json记录环境、实际命令、日志完成时间和哈希；source-manifest.json冻结业务源码哈希。JSON中的UTC任务时间按+8换算北京时间。mysql-tests*.log保留两轮有效回归，frontend-initial.log、build-initial.log和两个初验JSON保留失败。最终报告仅依据最终对应证据，不抹去初验停点。
