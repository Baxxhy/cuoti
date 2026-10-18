# 设计参考与证据记录

检索/阅读日期：2026-10-16。只使用公开官方产品介绍、官方技术文档、论文和本地技能；未登录竞品、未实测其付费能力、未开展学生访谈。官网营销表达不视为学习效果证据，也不推断为产品当前每个页面的真实样式。

## 1. 产品参考：观察 → 借鉴 → 本项目决策

| 产品与来源 | 实际观察 | 借鉴 | 不照搬 |
| --- | --- | --- | --- |
| [Duolingo官方首页设计说明](https://blog.duolingo.com/new-duolingo-home-screen-design/) | 官方2022年设计文解释引导路径、单元和复习组织；已查看公开前后对照图 | 减少“我现在该干什么”的选择负担，显示当前一步 | 不是2026最新版全界面实测；不照搬路径长卷、积分/宝石、角色动画 |
| [Photomath官方使用说明](https://www.photomath.com/articles/photomath-101-get-math-with-photomath/) | 扫描、可改识别内容、解题步骤主动展开 | 题目为中心、先核对再展开解释 | 不以扫描后立即给完整答案作为默认独立学习体验 |
| [Quizlet Learn](https://quizlet.com/features/learn) | 官方功能页描述多题型和针对性练习 | 学习模式以任务命名，练习入口与题集关联 | 不复制会员结构或营销正确率；不能据官网断言学习收益 |
| [Khanmigo learners](https://www.khanmigo.ai/learners) | 官方定位强调引导学生推理与逐步帮助 | 一次一个问题、给予必要提示 | 不把所有学习步骤做成长聊天，也不推断完全不展示答案 |
| [小精龙官网](https://mate.tal.com/) | 错题轻课、学情地图等；官网要求平板体验，已查看举一反三公开图 | 把错题转成短学习任务，强调知识关联 | 图中长题干/讲解/视频窗是平板呈现，不直接缩到手机；不增加多学伴入口 |

公开展示图链接：[Duolingo](https://storage.ghost.io/c/7a/33/7a33d0f4-927d-4fe8-a6bf-96131b5e76d4/content/images/2022/05/NEWV2Blog-Tree-Homescreen--2-.png)、[小精龙](https://mate.tal.com/_nuxt/main-pic.q8o6jmBP.png)。仅用于设计观察；最终页面稿自行绘制，不复制品牌资产。公开图片可能随官网更新失效，以对应产品页为定位入口。

这里的借鉴是针对本产品任务作出的设计判断；不能以竞品存在某功能证明本方案创新或有效。

## 2. 本地技能的实际使用

- `ui-ux-pro-max`：系统方向检索 `education mobile calm minimal`，一次重试 `education application`。返回包含营销Hero/Testimonials、外文字体和滚动动画，与学生App不匹配，未持久化或采用该布局。保留低密度/少动效方向，颜色沿用仓库。
- 同技能检索 `touch target size --domain ux`，得到移动触点/间距指导；检索 `lifecycle cleanup --stack vue`，得到卸载/副作用清理指导。用于触控和恢复要求，但不以Vue网页生命周期替代uni-app onShow/onHide等平台生命周期。
- `progressive disclosure mobile`及一次缩小重试未命中直接相关规则；本方案渐进展开来自 `information-architect` 的明确指导及移动技能通用规则，不伪称搜索命中。
- 已读 `references/pro-rules.md`：对比度、安全区、图标、系统字体、减少动效、触点、状态与原生设备检查。规范按App能力取舍，未宣称真实App已逐项通过。
- `information-architect`：采用“以题目为对象、以学习任务组织入口”的结构；产出页面图、导航、页面类型、标签和展示层级，汇总在UI_SPEC，不再另建冲突的一套IA。
- `user-research`：区分代码事实、公开产品观察、设计假设、真实学生验证。没有虚构访谈和试用结论。

## 3. 官方技术与智能体来源

| 来源 | 支持内容 |
| --- | --- |
| [DCloud CLI](https://uniapp.dcloud.net.cn/worktile/CLI.html) | uni CLI与HBuilderX CLI能力、App资源与云打包区别、Linux限制 |
| [DCloud App运行](https://uniapp.dcloud.net.cn/tutorial/run/run-app.html) | 真机/基座运行路径；不等于最终发布包 |
| [DCloud安心打包](https://uniapp.dcloud.net.cn/tutorial/build/SafePack) | 应用代码/签名打包流程与平台环境区别 |
| [官方App离线SDK](https://nativesupport.dcloud.net.cn/AppDocs/) | uni-app的Android/iOS本地打包路径，区别于uni-app x |
| [DCloud打包环境](https://uniapp.dcloud.net.cn/tutorial/app-env.html) | 工具链/SDK随版本变化，实施时再核对 |
| [Apple分发指南](https://developer.apple.com/documentation/xcode/distributing-your-app-for-beta-testing-and-releases) | 真机/TestFlight/App Store的相应分发与签名路径 |
| [ReAct论文](https://arxiv.org/abs/2210.03629) | 行动与外部观察反馈结合；本方案不保存隐藏思维链 |
| [Anthropic Building effective agents](https://www.anthropic.com/engineering/building-effective-agents) | 工作流和动态智能体的区分、以必要复杂度解决问题 |

部分DCloud页面直接打开偶发超时，相关技术结论使用官方域名搜索索引中可读取的正文交叉核对；未把访问失败当作功能不支持。最终打包时仍需按所选工具链再次核实。

## 4. 设计提交ba3323d的代码事实与证据边界

- 当前基线 `c31890e`；94/94接口、23算法/27仓颉原生及HTTP/MySQL、18浏览器通过/4角色场景跳过均来自当时仓库验收记录，设计阶段没有重新执行这些套件。后续实际代码验证见 [实施进度](IMPLEMENTATION_STATUS.md)。
- 250知识卡/65关系是初始化快照能力，不等于所有学科题库已准备充分。
- 现有AgentPlan/六工具/记忆/验证为源码事实；任务级重规划、取消恢复、语义块UI是计划新增。
- 本版页面稿全部为设计示意数据，不连接API，不证明数据库或智能体已经完成。
- 美观由视觉一致性与真实页面评审评估；适用性由学生任务试用评估；创新不宣称全球首创或未测量的效果提升。

代码实施补充：自定义导航状态栏占位使用DCloud官方 [CSS变量说明](https://uniapp.dcloud.net.cn/tutorial/syntax-css)，仅应用于当前普通Vue页面；H5布局证据不等价于App真机证据。


2026-10-17复习页补充：`ui-ux-pro-max`定向查询`form error recovery --domain ux`命中恢复路径、可播报错误与提交反馈指导，用于操作附近持续错误、保留答案和重试。沿用既有蓝白视觉与按需展开，不创建新设计系统。实际实现与分层验证见[复习恢复记录](REVIEW_RECOVERY_IMPLEMENTATION.md)。
