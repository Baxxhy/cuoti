# Element Plus全站统一与区域边界验收

2026-11-12 / v1

## 交付

本轮继续“全部通用控件使用Element Plus”，并处理页面和区域连成白色一片的问题。使用executing-plans跟踪实施，verification-before-completion核对实际证据。

- 页面背景改为浅灰`#f2f4f8`，内容卡片白色，边框`#d6deea`，侧栏和顶栏白色；通过官方主题变量统一。主操作蓝色，成功、待完成、异常保持各自语义颜色。没有文字左侧装饰线。
- 全站剩余按钮、链接、表单、数字输入、日期、图片、上传、头像、进度、目录及容器统一官方组件。卡片适配层实际使用ElCard，弹窗、确认、提示和图标继续统一官方实现。
- 教案、课程、试题排序改为ElTree draggable，保持拖拽把手与顺序保存；移除vuedraggable、SortableJS和motion-v。
- 音频播放界面使用ElButton、ElSlider、ElSpace、ElText、ElAlert。隐藏audio只承担浏览器播放能力，无原生可见控制条。
- 图片裁剪改为ElImage与ElInputNumber；保留原图和实际鼠标选区，裁剪坐标读取真实图片区域。
- 修复官方按钮内部嵌套与旧样式冲突导致的首页消息文字重叠。

应用仍负责页面组织、文字、数据、教学计算和媒体调用；这些业务代码不是另写一套基础UI。后端、数据库结构与原始上传未改。

## 验收表

| 检查 | 结果 | 证据 |
| --- | --- | --- |
| 源码原生UI控件、自绘通用框 | 两类均0；隐藏媒体引擎1 | source-audit.json |
| 浏览器回归 | 48/48通过 | browser-tests.log |
| JavaScript检查 | 18/18通过 | js-tests.log |
| 三端桌面页面 | 32路由×1440/1920，共64次通过 | pages.json |
| 区域分层 | 灰色页面、白卡、统一边框，计算样式符合主题 | pages.json及三端截图 |
| 实际拖拽 | 鼠标拖动后顺序改变，事件只发一次 | element-sortable.test.mjs |
| 图片裁剪 | 原图200×100保留，选区导出100×60 | element-all-controls.test.mjs |
| 日期、数字、密码和音频控制 | 控件值与交互通过 | element-all-controls.test.mjs |
| 三端点击检查 | 成功/待评阅、展开讲稿、取消恢复、备课步骤及管理内容通过 | walkthrough.json |
| 生产构建 | 通过 | build.log |
| 本地8099 | qmx登录、学科筛选、脚本无异常 | local-update.json、07-local-built.png |

[证据目录](../verification/element_complete_20261112_v1/README.md)。页面检查未发现横向溢出或脚本异常；截图人工复查后修复消息重叠并再次检查。以上是工程浏览器检查，不冒充真实用户满意度或课堂效果评测。真实麦克风/扬声器的既有环境例外继续保留，本轮未声称通过物理设备测试。

## 复查命令

```bash
npm --prefix frontend run audit:ui
npm --prefix frontend run test:unit
npm --prefix frontend test
python deploy/build_frontend.py
```

浏览器测试需可用Chromium；隔离验收服务通过SCZX_TEST_ORIGIN指定，不写入日常使用数据。
