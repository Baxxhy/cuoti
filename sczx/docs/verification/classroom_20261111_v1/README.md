# 第十八步验收证据

2026-11-11。独立合成数据MySQL＋8091，多角色真实HTTP与桌面Chromium。

- live-browser.json：实时课堂；groups-browser.json：分层链；community-browser.json：教师交流改编发布。
- recovery-memory.json：真实断网/重试/刷新保存与师生同源学习证据。
- migration-check.json：0014隔离库到0015所有旧表行摘要不变；backup-preflight.json：正式备份完整性，未执行正式迁移。
- stage-gate.json与desktop-environment.json：用户语音环境例外和真实环境限制，不能算V01/V03通过。
- tests-final.log/json、frontend-final.log、frontend-unit-final.log、build-final.log：最终回归；初验日志保留，不能以初次失败覆盖最终结论。
- *-1440/1920/2560.png：实际截图；failure.png为脚本初验中间状态，非最终通过截图。
- CI回执会在推送后补齐。私有配置、密码、SQL、上传备份不入库。

脚本从本机/tmp/sczx-step18/private.json读取隔离凭据，密码不内联。脚本以已有合成夹具为前提，重复执行可能新增合成记录；不要对正式库运行。日志归档仅去除行尾空格，原日志仍在/tmp。
