# 模型切换验证

2026年10月23日，按用户要求将当前运行配置切换为 xiaojing / gpt-6-luna。

- Base URL：https://open.xiaojingai.com/v1。
- 实际密钥从 XIAOJING_API_KEY 环境变量读取，示例配置只保存变量名。
- 本地API池原有条目保留并禁用；唯一启用条目为xiaojing。
- 请求不向该模型发送Qwen专用chat_template_kwargs或固定temperature；保留旧Qwen请求兼容。
- 业务响应及健康状态根据配置报告实际模型。

## 实测

1. 真实Chat Completions请求HTTP 200，返回模型gpt-6-luna，方程2x+3=11回答4。
2. 项目/v1/compute结构化英语题分析HTTP 200，child复数返回children。
3. 图片输入读取2+3算式，结构化输出answer=5。第一次图片调用失败，重试HTTP 200成功；未将首次失败隐去，也不据此声明长期稳定性。
4. 已重启原8012算法服务，保留原内部认证和启动参数，在线/livez返回gpt-6-luna。
5. 完整算法测试692项通过，耗时28.73秒；存在原有Starlette弃用提示。

首次业务测试发现采样参数兼容问题，移除非Qwen模型的temperature后成功；首次完整回归发现测试替身没有logical_model属性，兼容处理后完整复测通过。

未改数据库及前端。旧参赛文档和历史测试仍描述其当时的Qwen基线，不作为本次新模型的验证记录。仓颉OCR记录中的历史命名qwen-pool、qwen_crop及固定model_name尚未迁移，它们不控制真实模型请求；实际模型以算法池与响应为准。

后续重启时，须将XIAOJING_API_KEY提供给算法服务进程；当前运行进程已加载该变量。没有提交真实密钥或推送远程GitHub。
