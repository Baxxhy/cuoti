# 本地角色账号配置

适用仓颉业务后端＋MySQL。学生使用注册页面；本地管理者通过此命令创建专用教师、家长、管理员账号。浏览器注册和修改资料都不提供身份切换。

## 创建

先按[仓颉运行说明](../../backend-cangjie/README.md)准备独立MySQL库、初始化或升级到当前版本，并配置本地`.env.cangjie`。本命令读取与`final.sh`相同的可信本地配置，不初始化数据库、不导入示例学生或成绩。

```bash
# 预检邮箱与数据库：不需要密码，不写业务数据。
bash scripts/local_user.sh --email parent@example.com --role guardian --check

# 输入两次密码，不回显；创建家长账号。
bash scripts/local_user.sh --email parent@example.com --role guardian --name '家长姓名'

# 教师、管理员使用各自专用邮箱，操作相同。
bash scripts/local_user.sh --email teacher@example.com --role teacher --name '教师姓名'
bash scripts/local_user.sh --email admin@example.com --role admin --name '本地管理员'
```

示例邮箱须替换为实际账号邮箱，不会发邮件或向他人发送消息。密码为12—256个字符的单行文字。账号创建后，通过正常登录页面登录，系统按数据库身份进入对应工作台。创建家长账号不会自动获取任何学生权限；仍须由学生在“我的 → 家长查看权限”确认授权。

自动化可显式加`--password-stdin`，从标准输入读一行密码。不要将密码作为命令参数或环境变量；此命令没有`--password`参数。输出只含数据库名、账号邮箱、身份、创建状态和账号ID，不含密码、哈希或令牌。`--check`可返回已存在账号的身份，但不会修改它。若提交期间进程中断，先用`--check`核对结果，再决定是否重试。

## 对已有账号的处理

邮箱大小写归一化后已存在，创建操作报冲突。原身份、密码、学习记录、会话和关联全部保留，不会把已有学生升级成管理员。并发创建同一邮箱由MySQL唯一约束保证只有一个成功。

本命令只创建新账号，不承担已有账号角色转换、删除或强制重置密码。角色转换会影响学生数据与教师责任，需要单独迁移方案；当前交付方式是使用专用新账号。已知当前密码时，可使用现有登录页“修改密码”，旧会话随密码变更失效。

## 实现边界

- `scripts/local_user.sh`读取可信本地`.env.cangjie`并启动Python输入收集器。该配置使用Bash语法，与现有启动器一致；环境文件不进入Git。
- `scripts/local_user.py`只负责命令参数、无回显输入、预检和调用，不连接MySQL，不计算密码哈希，不引入Python业务后端。
- 仓颉`local_users.cj`校验身份/邮箱/密码、复用PBKDF2密码派生、参数化事务写入。底层`--create-local-user`从标准输入接收单行JSON，未注册成HTTP接口。
- 显式要求`CANGJIE_DB_NAME`，沿用独立库名前缀保护，并检查已有009迁移；缺库、版本不符或数据库异常均不自动建表/升级。新增角色没有学生档案，不伪造学习数据。
- 读取使用仓颉`getStdIn().readln()`，接口参考[官方env标准输入示例](https://docs.cangjie-lang.cn/docs/1.0.0/libs/std/env/env_samples/env_sample.html)，本项目在固定1.0.5工具链实际编译验证。

## 验证

`scripts/smoke_cangjie_local_users.py`在随机隔离库验证三种角色创建/登录/权限、预检无写入、已有学生与题目不变、重复/并发邮箱、无效配置、输出脱敏以及真实`--password-stdin`输入收集器。

专项：`CANGJIE_VERIFY_FOCUS=local-users make verify-cangjie`。完整`make verify-cangjie`和`make verify-cangjie-browser`也接入该专项；聚焦检查不能替代完整浏览器门槛。最新实际结果见[实施进度](IMPLEMENTATION_STATUS.md)。

本批实际专项已通过：算法86项、仓颉原生31组、真实CLI/MySQL/HTTP身份检查；日志`/tmp/zhiwei-local-users-verify.log`。本批前端未改动，沿用家长权限阶段114项前端与28项浏览器零跳过证据，不把本专项记作完整浏览器重跑。
