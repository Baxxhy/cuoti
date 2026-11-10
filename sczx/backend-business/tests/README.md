# 运行回归

不新增测试依赖，使用Python标准库unittest。冻结夹具为4篇项目自编案例、14条查询及用户单人复核标签，保留B0—B3原分数和排序，不代表真实教学效果。

```bash
PYTHONPATH=backend-business python -m unittest discover -s backend-business/tests -v
```

MySQL/API集成测试默认跳过。先新建仅供测试的 `sczx_test_*` 库，再设置 `SCZX_DATABASE_URL` 和 `SCZX_RUN_MYSQL_TESTS=1` 运行同一命令。测试拒绝任何其他库名，会执行迁移并创建测试账号、案例和版本，不删除数据库。使用独立新库运行；不要指向正式sczx库。凭据通过环境配置，不写进测试文件。

前端在Vite运行后执行 `CHROME_PATH=/path/to/chromium npm --prefix frontend test`。Node22以上，使用内置test、WebSocket和现有Chrome；SCZX_TEST_ORIGIN可改本地地址，默认5177。浏览器并发用例控制响应只验证状态竞争；真实模型联调另记验收结果。

第十步补充：生成期间发布新课时、旧来源预检查、草稿并发冲突、不可变历史/恢复、DOCX固定版本与权限、局部改写保留手写属性，以及表达式/方程/条件三态核验。MySQL完整25项；无MySQL时12通过、13跳过。

前端持久Chromium现有5项，另有 `npm --prefix frontend run test:unit` 无外部服务JS检查。GitHub基础工作流不连接业务数据库、不调用真实Codex。当前Office实机验收状态请读取第十步统一验收表，不用DOCX解析测试代替Word/WPS打开验证。
