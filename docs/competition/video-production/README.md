# 演示视频制作源文件

本目录保存错题帮学生端实录的旁白、原创动画和剪辑工具。成片位于 `../deliverables/演示视频/`。

## 素材与环境

- 手机视口432×936，Chromium/Playwright实际操作。网页服务位于5175端口。
- `assets/`为自行制作的题纸和作答图片。识别及后续判定通过实际项目服务运行。
- `narration.json`保存完整旁白、章节标题及必要披露文字。
- `browser-control.cjs`提供本地交互式浏览器控制；`init-recording.js`和`record-ingestion.js`保存注册及录题脚本。后续步骤根据实际生成的题目和可见控件完成，不能把本次题目答案硬编码成通用验收答案。
- 原始录像、时间范围、接口回执和独立演示账号仅留在本地 `.runtime/competition-video/`。登录状态文件不属于交付内容。
- 图形与字幕使用Noto Sans CJK字体，旁白使用中文合成语音。FFmpeg通过imageio-ffmpeg提供；生产工具不是应用运行依赖。

## 制作顺序

1. 确认仓颉、MySQL、算法服务及5175前端健康。
2. 以独立演示账号实际操作并录制，保存 `take2/clips.json` 和 `take2/raw-path.txt`。源素材中的可见结果不能替换成模拟通过状态。
3. 执行 `synthesize.py` 生成各段音轨；修改旁白后，需要重建对应音轨。
4. 执行 `render_animation.py intro` 和 `render_animation.py outro`。
5. 读取本次真实导出的PDF，以PDF渲染工具生成 `take2/exports/questions.png` 与 `answers.png`；执行 `export_preview.py`。
6. 分别执行 `compose.py landscape` 和 `compose.py portrait`。`edit_ranges.json`仅用于经过画面检查的剪辑区间；已存在的片段需重建时使用 `--force`，可用 `--only=片段ID,...`限制范围。
7. 执行 `finish.py landscape` 和 `finish.py portrait`；音轨统一格式，章节按实际视频帧时长对齐。
8. 执行 `quality_check.py`，完整解码、检测音量、检查字幕及章节，并为每章抽取画面。人工检查抽帧后，执行 `deliver_report.py` 生成索引、验收记录及ZIP。

以上脚本在项目根目录运行。`requirements.txt`为视频后期处理依赖，不修改应用依赖清单；使用本地已有Playwright环境进行录制。

## 真实性记录

`prepare_review_demo.py`只针对符合邮箱格式和所有者校验的演示账号，将其一条已有待复习计划设为到期；具有重复执行保护。没有添加判题结果、答案、掌握度或虚构学生实验。画面、旁白和说明中均披露该预置。

长旁白采用最后一帧真实页面续留，字幕继续更新；模型等待有明确压缩标记。最终交付不含内部回执、原始录屏、账号密码和模型配置。

录制中发现的H5练习模式地址恢复问题已修复，并附有前端回归测试。详细实际结果见交付目录的《功能覆盖与验收》。
