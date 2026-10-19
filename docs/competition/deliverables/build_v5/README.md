# Word参赛定稿构建

仅处理文档与图表，不修改项目业务实现。原文档保留，输出后缀为“_参赛定稿”。

1. `build_documents.py`用python-docx从product.md/system.md生成原始Word与标准Markdown；双截图布局仅为内部源语法，输出Markdown自动转换为独立标准图片链接。
2. `update_export.py 输入raw.docx 输出.docx - 2007`连接本机LibreOffice更新目录，第三参数`-`明确跳过PDF。
3. `audit_word_revision.py`统一显式字体/黑色并检查网格、题注和无页眉页脚。
4. `refresh_word_layout.py`保存重分页及目录。
5. `render_word_pages.py`从Word直接渲染PNG，`check_word_layout.py`核对目录并生成总览。
6. `verify_final.py`、`check_word_images.py`、`check_content.py`只读检查成品字体、源图片、正文、链接与参考段落复制情况。
7. `package.py`按43文件白名单生成新ZIP并校验CRC及源文件一致性。

Word正文和标题指定SimSun/SimHei。本机没有实体字体，PNG预览使用系统回退；在有对应字体的电脑更新目录时，页数可能变化。文件中的页码以当前渲染记录为准。图片源为imagegen输出PNG，重绘通过最终独立提示词进行；不把提示词称为确定性矢量源代码。

Python-docx构建环境为`/tmp/cuoti-docs-venv/bin/python`，普通检查使用Python/lxml/Pillow，UNO步骤使用`/usr/bin/python3`及本机端口2007。这些是本轮工具环境，不属于产品运行依赖。临时raw.docx、PNG逐页预览与缓存不进入正式ZIP或Git。

正式文件、三轮评审及最终哈希定位见上级《正式交付导航.md》《最终文档质量审查报告.md》。
