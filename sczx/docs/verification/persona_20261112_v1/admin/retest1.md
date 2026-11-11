# 管理员模拟角色第一次复测

AI模拟管理员的浏览器认知走查，非真人访谈或真实用户满意度。2026-11-12，新Chrome profile，8102隔离实例，1440×1000。已读取实际页面资源：index-BxirpJC8.js / index-BRBChled.css。真实按钮和表单寻路，无hash绕路、无源码改动。

## 评分与结论

按基线冻结标准：**99/100（基线94）**。六任务全部完成，原5项修复均有实际证据；保留一项管理tab跨页记忆轻微扣分，不为95目标调标。

| 项目 | 得分 | 依据 |
|---|---:|---|
| 六任务 | 30/30 | 6项各5分，真实保存、处理、建账号及已成功指导恢复 |
| 导航 | 24/25 | 分组、重复、子功能、主次各5；返回上下文4 |
| 信息主次 | 20/20 | 材料、课程、问题、能力4视图各5 |
| 字体 | 15/15 | 字族一致，案例标题恢复24px/650，公式继承统一字族 |
| 反馈与键盘 | 10/10 | 解析终态通知、重复账号失败恢复、Tab和Escape通过 |

## 六任务点击记录

### A1 上传并保存合成材料

登录 → 上传材料 → 选择新合成DOCX → 填写标题 → 上传并解析 → 编辑信息 → 保存信息。

3/3已就绪与解析完成一致；元信息保存成功，保存通知未被旧解析通知覆盖。

证据：A1 parse completed, A1 save metadata, 02-material-parsed.png。

### A2 从材料整理并查看案例

整理成案例 → 手动整理 → 填写案例 → 保存修改 → 预览 → Escape。

仅创建新合成草稿；标题清楚；离开后返回并刷新均恢复同一案例及正文。

证据：A2 save draft, A2 preview, R1 restored selection, R2 reload complete, 03-case-preview.png, fonts-case-preview.json。

### A3 编辑课程草稿并学生预览

课程内容 → 新建课程 → 单元 → 课时 → 添加内容块 → 填写标题正文 → 保存草稿 → 预览 → Escape。

新课程/单元/课时草稿保存成功，学生预览显示同减4及代回过程；未发布或改变既有课时。

证据：A3 save lesson draft, A3 student preview, 04-course-student-preview.png, fonts-course-preview.json。

### A4 提交并处理问题

管理与运行 → 提交问题 → 填写合成问题 → 提交 → 处理意见 → 保存处理。

新合成问题由待处理改为已回复，处理意见可回看；帮助与反馈按钮进入同一问题页。

证据：A4 save resolution, 05-issue-resolved.png, H1 issue page loaded, 16-help-issue-page.png。

### A5 创建学生账号并检查服务

账号 → 新建账号 → 填写学生账号/私有密码 → 创建账号 → 检查连接。

新合成学生创建成功且服务数据库已连接；重复账号真实失败、表单保留、改名重试成功。

证据：A5 created result, A5 check connection, 07-student-created-service-ready.png, K2 duplicate error, K2 retry success, 10-duplicate-account-error.png, 11-account-recovered.png。

### A6 找到能力验证、失败任务与重试入口

能力验证 → 最近任务 → 选择已成功文字指导 → 失败与重试。

最近已完成的真实文字指导可重新读取并显示结果；历史失败显示AI备课；重试按原提交者限制禁用且提示原因。本轮未发起新模型调用，也未把未执行的重试称为成功。

证据：A6 restore successful guidance, A6 failed jobs, 08-capabilities-and-failed-jobs.png, 09-successful-guidance-restored.png。

## 原问题复测

- ADM-01：终态已就绪3/3同时提示解析完成；后续保存信息提示优先。 证据：A1 parse completed, A1 save metadata, 02-material-parsed.png。
- ADM-02：案例业务标题24px/650，正文15px，层级恢复。 证据：03-case-preview.png, 18-case-preview-settled.png, fonts-case-preview.json。
- ADM-03：一级管理与运行可预测账号和能力归属，三个一级入口保持简洁。 证据：06-account-service.png, 08-capabilities-and-failed-jobs.png。
- ADM-04：失败业务任务标题中文AI备课，不再由内部标识承担任务名称。 证据：08-capabilities-and-failed-jobs.png。
- ADM-05：跨一级页返回恢复案例tab和同一草稿；刷新后仍恢复，无须点列表。 证据：R1 restored selection, R2 reload complete, 12-case-context-restored.png, 13-case-reload-restored.png。

## 保留1分扣分

ADM-R1-01（P3）：账号tab离开到案例、刷新案例后，再点管理与运行进入默认问题反馈；查看账号需再点一次账号tab。账号tab自身带section=accounts URL刷新则正确恢复。

可记住最后管理分区，使跨一级页返回与材料案例的记忆行为一致。 冻结导航“返回上下文”项扣1分。证据：R3 return to management section, R3 account tab restored, 14-account-section-restored.png, R4 account refresh complete, 17-account-section-url-refresh.png。

## 交互和验证边界

重复账号真实返回“此账号名已存在”，错误在弹窗内可见，输入保持；改名重试成功。Tab焦点可见2px实线，Escape可关闭两种预览。控制台脚本异常0，测试驱动错误0。模型能力只恢复本轮基线已真实成功的指导，未反复新增付费调用；历史失败不属于当前提交者，未绕过限制执行重试。

新资料、案例、课程和课时均为本轮合成数据/草稿，既有发布版本未修改。报告只说明所测任务和视图，不把99分当成真人打分或所有页面无改进空间。

截图、字体、事件和资源清单位于retest1/。口令不在报告、事件或截图中；private-account.json不作为交付证据。