# 错题帮竞赛项目 Word 重构实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 基于用户提供的旧版项目 Word 和官方模板，生成一份含完整文字、统一技术图、真实功能截图且达到 58～62 页的《错题帮》竞赛项目文档 Word。

**架构：** 以 Markdown 源稿维护官方四章正文，以 JSON 图清单锁定图号、位置、来源和样式；Python 生成统一风格的技术图并将真实页面截图组合为证据图；DOCX 构建器读取旧 Word 的样式体系、清除旧内容与隐私元数据，再插入新正文、表格、图片、题注、目录域和页码。最终使用结构检查、敏感词检查、Office 转换页数检查和逐页渲染抽查完成验收。

**技术栈：** Python 3.11、python-docx、Pillow、ReportLab（仅用于内部预览）、Playwright、Vue 3 页面、WordprocessingML、LibreOffice headless（仅用于临时分页验证）。

---

## 文件结构

- 修改：`docs/competition/错题帮项目文档源稿.md`——按官方四章重写约 60 页的完整中文正文。
- 创建：`docs/competition/figure_manifest.json`——24 个图号的章节位置、图名、类型、尺寸、来源 Vue 文件和生成文件清单。
- 创建：`docs/competition/generate_figures.py`——生成架构图、流程图、数据图、甘特图并组合页面截图。
- 创建：`docs/competition/capture_screenshots.mjs`——在不启动或停止服务的前提下，从当前 H5 和真实后端数据采集学生端及管理员端截图。
- 修改：`docs/competition/build_project_document.py`——复用旧 Word 样式、插入真实图片和题注、生成最终 Word，不再生成 PDF 交付物。
- 创建：`docs/competition/verify_project_document.py`——检查结构、图号、图片、禁用词、匿名信息、Word 包完整性和临时 PDF 页数。
- 生成：`docs/competition/figures/*.png`——24 个图号对应的高清图片。
- 生成：`docs/competition/screenshots/*.png`——当前系统的脱敏页面截图及组合图输入。
- 更新：`docs/competition/题醐灌顶队_错题帮_项目文档.docx`——唯一最终交付文件。

### 任务 1：锁定模板、图清单和失败验收基线

**文件：**
- 创建：`docs/competition/figure_manifest.json`
- 创建：`docs/competition/verify_project_document.py`
- 读取：`/root/.codex/attachments/9843abe3-d753-476e-a27a-df4967afb885/题醐灌顶队-项目文档.docx`
- 读取：`/root/.codex/attachments/3adce956-de5e-489c-8b39-120dde2e255d/附件2：第八届中国研究生人工智能创新大赛项目文档模版 (1).pdf`

- [ ] **步骤 1：提取旧 Word 的页面尺寸、页边距、标题样式、正文样式、页眉页脚、表格样式和修订记录格式**

运行：

```bash
/root/miniconda3/envs/minddimension/bin/python - <<'PY'
from docx import Document
from pathlib import Path
p=Path('/root/.codex/attachments/9843abe3-d753-476e-a27a-df4967afb885/题醐灌顶队-项目文档.docx')
d=Document(p)
print('sections', len(d.sections), 'styles', len(d.styles), 'tables', len(d.tables))
for i,s in enumerate(d.sections):
    print(i, s.page_width.cm, s.page_height.cm, s.top_margin.cm, s.bottom_margin.cm, s.left_margin.cm, s.right_margin.cm)
for name in ['Normal','Title','Heading 1','Heading 2','Heading 3']:
    st=d.styles[name]
    print(name, st.font.name, st.font.size.pt if st.font.size else None)
PY
```

预期：输出 A4 页面、旧模板标题和正文样式参数；全程只读附件。

- [ ] **步骤 2：创建 24 图清单**

`figure_manifest.json` 顶层为数组，每项必须包含：

```json
{
  "id": "1-1",
  "chapter": "1.1 背景和基础",
  "title": "教育数字化背景下的错题学习需求链",
  "kind": "diagram",
  "width_cm": 15.8,
  "height_cm": 8.6,
  "output": "figures/fig-1-1.png",
  "sources": ["教育政策背景", "学生错题学习场景"]
}
```

24 项必须严格覆盖设计文档 5.1 的 6＋7＋11 个图号；截图图项的 `sources` 写入对应 Vue 文件绝对项目路径。

- [ ] **步骤 3：编写验收脚本并让当前交付物失败**

脚本必须检查：官方标题齐全；不存在独立“摘要”“术语与阅读说明”“图表与证据使用约定”；不存在“占位”；24 个图号连续且均有真实图片；DOCX 嵌入图片不少于 24；不存在学校、学院、导师、EduMind、EduVision-Nano、PaddleOCR、Spring Boot、微服务、应用商店、离线模式；正文包含“当前原型结果”“目标指标”“后续预期”的边界说明；指定临时 PDF 时页数为 58～62。

运行：

```bash
/root/miniconda3/envs/minddimension/bin/python docs/competition/verify_project_document.py \
  --source docs/competition/错题帮项目文档源稿.md \
  --docx docs/competition/题醐灌顶队_错题帮_项目文档.docx
```

预期：FAIL，明确报告旧源稿仍有摘要、63 个占位图且 Word 没有 24 个真实图。

- [ ] **步骤 4：提交图清单和验收基线**

```bash
git add docs/competition/figure_manifest.json docs/competition/verify_project_document.py
git commit -m "test: define competition document acceptance"
```

### 任务 2：重写官方四章完整源稿

**文件：**
- 修改：`docs/competition/错题帮项目文档源稿.md`
- 参考：`docs/competition/项目文档证据核对表.md`
- 参考：`docs/superpowers/specs/2026-08-28-competition-word-template-redesign.md`

- [ ] **步骤 1：删除模板外前置章节并恢复模板顺序**

正文只保留修订记录和官方四章。将原摘要中的项目定位、原型边界和“一体双环三引擎”分别并入 `1.1 背景和基础`、`2.1 整体目标`和 `2.2 技术创新点`。

- [ ] **步骤 2：扩写第 1 章到约 13～15 页**

复用旧稿的教育数字化背景、学生错题痛点、项目起因、诊断／即时教学／长期复习场景、目标用户、市场调研、竞品对比、学生价值、教师价值和社会价值。加入 6 个图引用和竞品对比表；不写学校、导师和成员身份。

- [ ] **步骤 3：扩写第 2 章到约 11～13 页**

按“产品目标—Agent 能力目标—Inference 目标—教育验证目标—可信工程目标”阐述整体目标；四项创新均按“现有不足—本项目机制—实现方法—实际价值—验证指标”展开；加入 7 个图引用和可替换指标表。

- [ ] **步骤 4：扩写第 3 章到约 28～31 页**

完整写入数据来源与许可、20,839 道题库规模、无本地 GPU 的 API 池部署、前后端与 MySQL、图像原证据保护、Pydantic 结构化校验、SymPy、步骤对齐、反事实式根因验证、公开计划、六类白名单工具、证据契约、LangGraph 分支、BGE-M3/Qdrant/RRF/reranker、可信作答安全门、长期认知记忆、主动复习、16 类 VisualizationSpec、多角色辅助、Inference 评测和消融设计；加入 11 个图引用。

- [ ] **步骤 5：完善计划、匿名分工与参考资料**

计划按四阶段呈现到 2026 年 9 月 1 日前的时间线；职责只写智能体与算法、后端与数据、前端与产品、共同测试验收。参考资料使用顺序编码，并在正文首次出现处引用。

- [ ] **步骤 6：运行文本验收**

```bash
/root/miniconda3/envs/minddimension/bin/python docs/competition/verify_project_document.py \
  --source docs/competition/错题帮项目文档源稿.md --source-only
```

预期：PASS；官方章节、24 个图引用、禁用词、匿名要求和结果边界全部通过。

- [ ] **步骤 7：提交完整源稿**

```bash
git add docs/competition/错题帮项目文档源稿.md
git commit -m "docs: rewrite competition manuscript to official template"
```

### 任务 3：生成统一风格的技术图和数据图

**文件：**
- 创建：`docs/competition/generate_figures.py`
- 生成：`docs/competition/figures/*.png`
- 读取：`docs/competition/figure_manifest.json`
- 读取：`reports/adaptive_practice_verification.json`
- 读取：`reports/verification/*.json`

- [ ] **步骤 1：实现统一图形主题**

脚本定义并只使用以下主题：主蓝 `#2F6BFF`、深色 `#0F172A`、辅助灰 `#64748B`、浅蓝 `#EEF4FF`、成功绿 `#168A45`、警示橙 `#C87A08`、错误红 `#D92D20`；字体使用 `frontend/src/assets/fonts/NotoSansSC.ttf`；输出 300 dpi PNG；普通边框 1～1.25 pt、主流程箭头 1.5～2 pt；禁止渐变、3D、机器人、芯片和大脑装饰。

- [ ] **步骤 2：实现通用绘图组件**

至少实现 `canvas()`、`rounded_box()`、`text_block()`、`arrow()`、`stage_flow()`、`metric_bar()`、`legend()`、`save_figure()`；所有组件使用厘米尺寸到像素的统一换算，保证图内最小字号印刷后不小于 9 pt。

- [ ] **步骤 3：生成第 1 章和第 2 章的 13 个矢量式信息图**

逐项读取清单生成背景需求链、痛点链、流程对比、角色价值、功能总览、部署协同、目标层次、一体双环三引擎、单题闭环、长期闭环、多模态首错机制、Agent 决策循环和创新协同图。

- [ ] **步骤 4：生成第 3 章的非截图技术图**

生成数据流程与分布、部署与安全边界、系统分层架构、步骤对齐、白名单工具与证据契约、状态机、混合检索、可信判定与长期记忆、Inference 指标与消融、甘特图与匿名分工。组合图允许使用（a）（b）（c）分区，但每个图号只对应一个最终 PNG。

- [ ] **步骤 5：验证所有生成图**

```bash
/root/miniconda3/envs/minddimension/bin/python docs/competition/generate_figures.py --diagrams-only
/root/miniconda3/envs/minddimension/bin/python - <<'PY'
from pathlib import Path
from PIL import Image
files=sorted(Path('docs/competition/figures').glob('*.png'))
assert files
for p in files:
    im=Image.open(p)
    assert im.width >= 1800 and im.height >= 800, (p, im.size)
    assert im.mode in ('RGB','RGBA'), (p, im.mode)
print('verified', len(files), 'diagram assets')
PY
```

预期：全部非截图图达到清晰度要求，且没有空白占位图。

- [ ] **步骤 6：提交生成脚本和技术图**

```bash
git add docs/competition/generate_figures.py docs/competition/figures
git commit -m "docs: add competition technical figures"
```

### 任务 4：采集并组合当前系统功能截图

**文件：**
- 创建：`docs/competition/capture_screenshots.mjs`
- 生成：`docs/competition/screenshots/*.png`
- 更新：`docs/competition/figures/fig-1-5.png`
- 更新：`docs/competition/figures/fig-3-4.png`
- 更新：`docs/competition/figures/fig-3-6.png`
- 更新：`docs/competition/figures/fig-3-7.png`
- 更新：`docs/competition/figures/fig-3-8.png`
- 更新：`docs/competition/figures/fig-3-10.png`

- [ ] **步骤 1：实现只读截图采集器**

脚本连接现有 `FRONTEND_URL`，不启动、不停止、不重启任何服务；通过后端登录获取学生和管理员会话；学生端使用 Pixel 7 视口，管理员端使用 1440×1000 视口。截图前隐藏浏览器调试层、滚动悬浮按钮和敏感标识。

- [ ] **步骤 2：采集学生端核心页面**

采集首页、拍题、框选、确认题目、错因诊断、针对教学、受控可视化、迁移练习、学习报告、知识关联和主动复习。每页等待后端数据加载完成和数学公式渲染完成，不截空白、骨架屏、错误提示或公式源码。

- [ ] **步骤 3：采集管理员可验证决策轨迹**

以管理员账号进入 `pages/admin/workbench`，选择“智能体轨迹”和一条具有公开计划、工具调用、证据核验、认知变化的会话，只截只读轨迹详情，不显示凭据、内部思维链或敏感字段。

- [ ] **步骤 4：组合截图图组**

运行：

```bash
node docs/competition/capture_screenshots.mjs
/root/miniconda3/envs/minddimension/bin/python docs/competition/generate_figures.py --screenshots-only
```

预期：生成 6 个截图图号；学生三联图等高、间距一致；管理端轨迹文字可读；所有截图品牌为“错题帮”。

- [ ] **步骤 5：提交截图采集器和脱敏截图**

```bash
git add docs/competition/capture_screenshots.mjs docs/competition/screenshots docs/competition/figures
git commit -m "docs: add current product evidence screenshots"
```

### 任务 5：按旧模板构建最终 Word

**文件：**
- 修改：`docs/competition/build_project_document.py`
- 更新：`docs/competition/题醐灌顶队_错题帮_项目文档.docx`

- [ ] **步骤 1：让构建器加载旧 Word 模板**

增加 `--template` 参数，默认使用用户提供的旧 Word；保留样式、主题、A4 页面、页边距、标题层级、修订记录表、页眉页脚和题注格式；删除旧正文、旧图片关系、旧自定义属性、作者、学校、导师和隐藏元数据，再写入新内容。

- [ ] **步骤 2：替换占位图逻辑为真实图片逻辑**

解析 `figure_manifest.json`，按源稿中的图引用插入 PNG；按清单厘米尺寸限制宽高；图片和题注保持同页；题注使用 Word `Caption` 样式并统一为“图 X-X  图名”；缺图立即失败，不绘制占位框。

- [ ] **步骤 3：恢复官方前置页面**

封面使用旧模板版式；第二页插入 Word TOC 域；第三页使用旧模板“记录更改历史”表；不生成摘要、关键词、术语表和插图约定。正文从“1 项目概况”开始。

- [ ] **步骤 4：生成唯一 Word 交付物**

```bash
/root/miniconda3/envs/minddimension/bin/python docs/competition/build_project_document.py \
  --template '/root/.codex/attachments/9843abe3-d753-476e-a27a-df4967afb885/题醐灌顶队-项目文档.docx' \
  --output docs/competition/题醐灌顶队_错题帮_项目文档.docx
```

预期：只生成 DOCX；构建输出报告正文字符数、表格数、图号数和嵌入图片数。

- [ ] **步骤 5：提交构建器和 Word**

```bash
git add docs/competition/build_project_document.py docs/competition/题醐灌顶队_错题帮_项目文档.docx
git commit -m "docs: build template-based competition Word"
```

### 任务 6：分页、视觉和完整性验收

**文件：**
- 修改：`docs/competition/错题帮项目文档源稿.md`（仅在分页或重复内容需要收敛时）
- 修改：`docs/competition/build_project_document.py`（仅在版式问题需要修正时）
- 更新：`docs/competition/题醐灌顶队_错题帮_项目文档.docx`

- [ ] **步骤 1：检查 Word 包和正文结构**

```bash
unzip -t docs/competition/题醐灌顶队_错题帮_项目文档.docx
/root/miniconda3/envs/minddimension/bin/python docs/competition/verify_project_document.py \
  --source docs/competition/错题帮项目文档源稿.md \
  --docx docs/competition/题醐灌顶队_错题帮_项目文档.docx
```

预期：ZIP 完整；官方结构、24 图、嵌入图片、匿名、禁词、引用和结果边界全部通过。

- [ ] **步骤 2：使用临时 PDF 验证分页，不交付 PDF**

```bash
tmpdir=$(mktemp -d)
soffice --headless --convert-to pdf --outdir "$tmpdir" docs/competition/题醐灌顶队_错题帮_项目文档.docx
/root/tools/pdfenv/bin/pdfinfo "$tmpdir/题醐灌顶队_错题帮_项目文档.pdf" | rg '^Pages:'
/root/miniconda3/envs/minddimension/bin/python docs/competition/verify_project_document.py \
  --source docs/competition/错题帮项目文档源稿.md \
  --docx docs/competition/题醐灌顶队_错题帮_项目文档.docx \
  --pdf "$tmpdir/题醐灌顶队_错题帮_项目文档.pdf"
```

预期：58～62 页。临时 PDF 仅用于分页检查，不复制到项目目录。

- [ ] **步骤 3：逐页视觉抽查**

将临时 PDF 关键页渲染成图片并检查：封面、目录、修订记录、第 1 章首尾、第 2 章架构与创新、第 3 章截图和指标、第 4 章参考资料；确认无裁切、重叠、孤行、大段空白、模糊截图、小于 9 pt 的图中文字和跨页断裂题注。

- [ ] **步骤 4：检查服务和业务代码未受影响**

```bash
git diff --name-only HEAD~1..HEAD
git status --short
```

预期：文档任务只修改 `docs/competition` 与对应设计／计划文件；不停止、重启或监听前后端、MySQL 和 Qdrant；用户已有前端修改保持原状。

- [ ] **步骤 5：提交最终收敛版本**

```bash
git add docs/competition/错题帮项目文档源稿.md \
  docs/competition/build_project_document.py \
  docs/competition/题醐灌顶队_错题帮_项目文档.docx
git commit -m "docs: finalize sixty-page competition Word"
```

## 自检结果

- 规格覆盖：官方结构、旧稿文字复用、三大能力、Agent 赛题定位、24 图、统一图形风格、真实截图、约 60 页、Word-only、匿名和不停止服务均已有对应任务。
- 占位符扫描：计划不允许最终 Word 保留空白占位图；源稿中的图引用必须映射为真实 PNG。
- 类型一致性：图清单 `id/output/title/width_cm/height_cm/kind/sources` 字段在生成、构建和验收脚本中统一；结果状态统一使用“当前原型结果／目标指标／后续预期”。
