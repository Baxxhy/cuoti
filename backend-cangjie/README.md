# 仓颉业务服务

这是唯一业务后端，负责学生账号、MySQL、错题与原图、异步识别、订正任务、学习记录、题库与练习、复习、知识关系、统计和组卷导出。Python只提供内部算法计算。

项目根目录执行 `make install-cangjie` 安装SDK与MySQL桥接依赖。使用 `.env.cangjie` 配置，`make dev` 启动应用；单独运行可用 `make backend`。数据库只允许MySQL，初始化只接受空库，旧库通过 `bash scripts/cangjie.sh upgrade-db` 升级，不自动清空数据。

`schema/` 是实际建表、迁移和知识内容；`src/` 包含业务实现与原生测试；`tests/` 是原生/接口验收使用的固定数据。不得按“非源码”删除这些必需资源。

验证：`make verify-cangjie`；包含浏览器的完整学生验收用 `make verify`。隔离测试会创建和清理独立临时MySQL库，不修改实际学生数据库。
