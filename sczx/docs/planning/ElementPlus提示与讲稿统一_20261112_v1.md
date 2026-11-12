# Element Plus提示与讲稿统一

2026-11-12 / v1

本轮补齐此前遗漏的原生确认框、自定义提示条、教案折叠和流程展示。沿用Vue 3与JavaScript，不引入其他组件库。

## 替换结果

| 原实现 | 当前实现 |
| --- | --- |
| 23处浏览器原生confirm调用 | ElMessageBox.confirm，确认与取消分别返回明确结果；保留删除、停用、交卷、发布和丢弃草稿的后果说明 |
| 错误、保存结果、识别疑问与运行提示 | ElAlert；正确为success、待评阅为warning、错误为error、普通信息为info |
| 作答结果自绘色块 | ElAlert与ElTag，不再单独绘制背景、边框和左侧装饰线 |
| 75处details及1处动态details | ElCollapse/ElCollapseItem；保留展开状态、筛选恢复和旧教案学生正文的初始化 |
| AI备课手绘步骤 | ElSteps/ElStep；成功使用success，失败使用error，运行中使用process；尚未采用的建议保留“待确认”，不标成已确认 |
| 分步讲解和教案输出卡片 | ElCard；分析过程使用ElTimeline，普通学习内容仍保留语义段落 |
| 19处加载占位 | ElSkeleton，保留可访问名称 |
| 旧提示、折叠和进度皮肤 | 清理旧规则及重复图标；仅保留布局、间距与业务内容排版 |

原AppAlert、AppDialog等调用名是官方控件的薄适配；新增AppDisclosure内部仅组合ElCollapse和ElCollapseItem，处理展开状态及change事件，不自行实现折叠行为、图标或视觉皮肤。统一确认方法也直接调用ElMessageBox，不覆盖window.confirm。

## 修复与验证

迁移中发现，确认服务先于Vue入口加载Element Plus时，开发预构建中的图标模块可能在Vue初始化前调用defineComponent。确认服务显式先初始化Vue后，入口恢复；浏览器冷启动及完整回归通过。没有通过屏蔽运行错误或自动接受确认绕过问题。

- 45项浏览器回归通过，包含实际点击官方确认/取消、四种提示色、折叠展开、旧稿正文恢复、未保存建议的离开拦截与返回。
- 17项JavaScript检查通过，Vite构建通过。
- 使用隔离账号实际走查学生、教师、管理员，1440/1920页面无横向溢出、未捕获脚本异常。
- 学生已有正确作答显示success，写作待评阅显示warning；教师打开提问与调整、取消恢复原稿后讲稿保持；AI备课使用官方步骤；管理员发布课时配置可折叠查看。
- 本轮修改前端控件，不改业务后端、数据库结构或模型配置。

[截图和日志](../verification/element_feedback_20261112_v1/README.md)。本地入口保持http://127.0.0.1:8099，qmx账号继续使用。
