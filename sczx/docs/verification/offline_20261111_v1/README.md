# 第十九步证据

2026-11-11，独立合成数据MySQL＋8093生产构建。

- five-flows.json：五条流程最终汇总；offline-browser.json是真实关闭/重开、图片、同步与正式提交。
- conflict-browser.json保留中途失败及已完成冲突/撤回/容量验证；isolation-browser.json补齐同浏览器账号与退出最终通过，server-final-facts.json重新读取数据库交叉核对。
- visual-browser.json：23页三宽度；visual-extra.json：案例审核/模型任务/弹窗和保存/导出/撤回操作。
- migration-check.json：51旧表全行不变，0016新增空表；正式数据库未迁移。
- tests-delivery.log为151项全量通过，tests-focused-delivery.log为后续15项当前读复验；frontend-verified.log为最终23项，无跳过；JS与构建日志齐全。
- docx-check.json和回归教案.docx为新导出及字体颜色检查，导出实现与历史人工Office验收未改。
- 初验/中间失败日志与failure.png保留，不作为最终通过截图；受控失败注入见流程说明，不伪造成功写入。
- ci-receipt.json与ci-mysql.log：2ab3a1e，运行42988746401，双Job成功，151项MySQL无跳过。私有配置、口令、浏览器配置目录、SQL、上传备份及私人清单不入库。

脚本读取/tmp/sczx-step19/private.json，仅可用于专用合成验收环境；不能对正式库执行。日志归档只去除行尾空格，原日志在/tmp保留。
