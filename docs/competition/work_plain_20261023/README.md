# 本轮文档制作与证据

`product.md`和`system.md`为最终正文依据。`prepare.py`准备已有图表与参考文献，`build.py`生成Word，`layout.py`使用LibreOffice UNO更新目录、重新打开及直接逐页渲染PNG，`audit.py`核对文件结构和实际页码。

`revisions/`及三轮修改JSON保留审阅轨迹。`revise_round*.py`是针对各轮输入的历史修改脚本，不应对终稿重复执行。`finalize_reports.py`从真实原段落、终稿和审阅结果生成交付报告。

复现顺序：

1. 用Python执行`build.py`。
2. 使用已启动LibreOffice 25.2 UNO端口2012对应的Python运行`layout.py`。
3. 运行`layout.py --update-final`再次打开、更新并保存最终文件。
4. 运行`layout.py --render --readonly`直接导出每页PNG，不生成PDF。
5. 执行`audit.py`，随后`finalize_reports.py`。

本轮Linux的LibreOffice运行环境位于`/tmp/lo_new/root/opt/libreoffice25.2/program/`，非项目运行依赖；该临时路径在其他机器需自行调整。当前字体环境可能替代SimHei，DOCX内的字体指定保持正确。不要修改系统安全配置来复现。

`originals.json`记录原件校验；`技术事实核查.md`记录源码与测试依据；`references.json`是重新核实的文献索引；日志摘录是2026年10月22日既有记录，不能作为本轮重新运行全量业务测试的证明。

未把附件内容、原稿文本抽取、逐页预览和中间Word作为正式交付。原件仍保留原目录。当前变更只涉及文档材料；另有业务文件和视频工作未包含在本轮提交中。
