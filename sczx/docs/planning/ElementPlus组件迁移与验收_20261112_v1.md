# Element Plus 组件迁移与验收

2026-11-12。按用户要求，Vue 3＋JavaScript 前端从旧 shadcn/Reka 基础控件迁移到 Element Plus 2.14.8，使用官方组件承担外观和基础交互。保留现有路由、Pinia、业务接口、Lucide、Motion 和教学内容。

## 替换范围

| 界面能力 | 当前实现 |
| --- | --- |
| 主操作、普通操作、图标按钮 | ElButton |
| 文本、密码、日期和多行输入 | ElInput |
| 单选、多选下拉 | ElSelect / ElOption |
| 布尔及数组勾选 | ElCheckbox |
| 页内业务页签 | ElTabs / ElTabPane |
| 弹窗、提示说明 | ElDialog / ElTooltip |
| 状态标签、卡片 | ElTag / ElCard |
| 行内错误、提示 | ElAlert |
| 保存成功、失败等浮层提醒 | ElMessage |
| 学情、成员及业务表格 | ElTable / ElTableColumn |
| 文件选择 | ElUpload，关闭自动上传，沿用原业务上传方法 |
| 原图、来源图、缩略图展示 | ElImage及统一失败占位 |
| 空列表、找不到页面等 | ElEmpty，保留原标题、操作及必要说明 |
| 进度、双栏调整 | ElProgress / ElSplitter |
| 中文环境 | ElConfigProvider |

适配代码集中在 `frontend/src/components/app`，业务页面继续消费已有数据和方法。兼容原生选择器的ID、选项标签、多选数组及change事件；文件选择只交给既有业务方法处理，不会由组件再重复上传。

旧 `components/ui` 目录、粗色边自定义通知和对应视觉反馈样式已删除。移除 reka-ui、cn、class-variance-authority、@vueuse/core 的直接依赖；Element Plus 自身所需的传递依赖保留。项目没有新增 React、业务TypeScript或TS配置。

导航分组、课程内容结构和教学专用组件保留。原图裁剪区域仍使用原生图像及坐标滑块，因为代码需要读取原始图像尺寸和选区；不删除或替换学生原始上传文件。数学公式、天平互动及教学图示不以通用UI占位图代替。

## 外观约束

优先采用 Element Plus 的组件结构、尺寸、边框和反馈方式。只保留工作区布局、宽弹窗和必要的中文字体/对比度适配；不再给通知添加粗左边线。普通、待处理、进行中、完成和错误状态继续保留文字与图标，使用库提供的标签类型。

较大的教案预览、学情和题图弹窗使用宽布局；文字录入错题弹窗为680px，并限制在视口范围内。最小状态文字对比度约4.57:1，见样本测量。

实现参考：[Element Plus快速开始](https://element-plus.org/en-US/guide/quickstart.html)、[Dialog](https://element-plus.org/en-US/component/dialog.html)、[Input](https://element-plus.org/en-US/component/input.html)。文档中的TypeScript示例没有引入本项目。

## 返修过程

回归检查实际发现并修复以下问题：

- 旧全局Button命名会干扰库对原生button的动态解析；统一采用AppButton全局名，补充表单提交回归。
- 控件DOM结构变化后，修正表单标签、输入定位及旧测试中的页签点击方式；保留原业务断言。
- 多选勾选迁移时恢复循环作用域，验证材料内容选择及数组ID保存。
- 弹窗按打开状态挂载，避免旧关闭弹窗影响当前交互和焦点检查。
- 卡片内容改为ElCard body后，恢复课程网格布局。
- 保留空状态中的标题语义和返回操作。

## 验收结果

| 检查 | 结果 |
| --- | --- |
| JavaScript检查 | 17/17通过 |
| 浏览器回归 | 42/42通过 |
| 新增适配行为检查 | 下拉选择真实ID、勾选数组、文件选择回调、表单仅提交一次，通过 |
| 三端桌面页面 | 26页、1440/1920/2560三种宽度共78次检查，无横向溢出、页面错误提示或捕获到的脚本异常 |
| 构建 | 通过，写入构建输入记录；保留大包体积提示 |
| 本地8099 | qmx登录、选班、刷新、进入任务、目录点击、保存进度和错题录入弹窗通过 |
| 旧通知清理 | 自定义toast节点为0；实际ElMessage左边框1px，无粗边装饰 |
| 依赖 | 只保留Element Plus作为基础控件库，直接依赖清单已归档 |

[原始日志、截图与本地验收记录](../verification/element_plus_20261112_v1/README.md)。页面检查不等于重新验收所有业务组合；本轮未修改后端与数据库，未重跑全量MySQL和算法测试。没有把截图自审记作真实用户满意度评分。
