# 本地维护账号

2026-10-22起仅支持学生个人使用；老师、家长账号创建及关联已删除。学生使用注册页建立账号，维护管理员只用于本地系统检查。

```bash
bash scripts/local_user.sh --email admin@example.com --role admin --check
bash scripts/local_user.sh --email admin@example.com --role admin --name '本地维护'
```

密码交互输入且不回显；邮箱已存在时不会覆盖角色、密码或学生记录。命令只支持 `admin`，注册页面只创建 `student`。旧老师、家长账号即使有未过期令牌，也无法登录或恢复会话。没有开放跨学生报告、班级、作业、复核和授权接口。

旧数据库中的历史表没有自动删除；新建库不再创建协作表。这避免不可逆删除历史记录，运行代码不会查询或写入这些废弃表。
