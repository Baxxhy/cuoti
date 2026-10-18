# 公开考试题回归集

题目文本来自 [C-Eval](https://github.com/hkust-nlp/ceval) 的中学与高中验证集，数据许可为
[CC BY-NC-SA 4.0](https://github.com/hkust-nlp/ceval/blob/main/LICENSE-DATA)。项目只下载少量代表题用于本地、
非商业功能测试。

开放题、填空题、材料题、默写题和英语改错题来自
[GAOKAO-Bench](https://github.com/OpenLMLab/GAOKAO-Bench)，仓库使用 Apache-2.0 许可。

`scripts/verify_real_exam_samples.py` 会在运行时下载公开题目，并生成带蓝色作答、红色教师批注的派生图片。
派生图片用于稳定测试图片处理和OCR流程；它们不是真实学生笔迹。项目内已有上传图片会被单独统计，不能通过颜色检测
自动断言为真实学生手写，必须人工确认后才能在验收报告中这样标注。

生成目录不纳入 Git，避免复制整套题库和用户上传内容。
