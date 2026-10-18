#!/usr/bin/env python3
"""Build the final competition Word document from the approved manuscript.

The generated document follows the official four-chapter structure and reuses
the supplied team's Word template for its theme, styles and page geometry. It
does not embed figures: every figure is represented by a replacement box with
its purpose, recommended form and exact Vue/source files.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION_START
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.table import WD_ALIGN_VERTICAL, WD_ROW_HEIGHT_RULE, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "错题帮项目文档源稿.md"
MANIFEST = HERE / "figure_manifest.json"
OUTPUT = HERE / "题醐灌顶队_错题帮_项目文档.docx"
TEMPLATE = Path(
    "/root/.codex/attachments/9843abe3-d753-476e-a27a-df4967afb885/题醐灌顶队-项目文档.docx"
)

BLUE = "2F6BFF"
BLUE_DARK = "1D4FB8"
NAVY = "0F172A"
TEXT = "222222"
GREY = "64748B"
LIGHT_BLUE = "EEF4FF"
ORANGE = "C87A08"
FONT_CN = "宋体"

HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$")
FIGURE_RE = re.compile(r"^【图\s+(?P<id>\d+-\d+)】(?P<title>.+)$")


@dataclass
class Block:
    kind: str
    text: str = ""
    level: int = 0
    rows: list[list[str]] | None = None
    figure_id: str = ""


def clean_inline(text: str) -> str:
    text = text.strip()
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"\1", text)
    return text.replace("\\|", "|")


def parse_table(lines: list[str]) -> list[list[str]]:
    rows: list[list[str]] = []
    for line in lines:
        values = [clean_inline(item) for item in line.strip().strip("|").split("|")]
        if values and all(re.fullmatch(r":?-{3,}:?", value.replace(" ", "")) for value in values):
            continue
        rows.append(values)
    width = max((len(row) for row in rows), default=0)
    return [row + [""] * (width - len(row)) for row in rows]


def parse_source() -> list[Block]:
    lines = SOURCE.read_text(encoding="utf-8").splitlines()
    blocks: list[Block] = []
    started = False
    index = 0
    while index < len(lines):
        raw = lines[index].strip()
        index += 1
        if not raw or raw == "---":
            continue
        heading = HEADING_RE.match(raw)
        if heading:
            title = clean_inline(heading.group(2))
            if title == "1 项目概况":
                started = True
            if started:
                blocks.append(Block("heading", title, len(heading.group(1))))
            continue
        if not started:
            continue
        figure = FIGURE_RE.match(raw)
        if figure:
            blocks.append(Block("figure", clean_inline(figure.group("title")), figure_id=figure.group("id")))
            continue
        if raw.startswith("|"):
            table_lines = [raw]
            while index < len(lines) and lines[index].strip().startswith("|"):
                table_lines.append(lines[index].strip())
                index += 1
            blocks.append(Block("table", rows=parse_table(table_lines)))
            continue
        if raw.startswith("- ") or raw.startswith("● "):
            blocks.append(Block("bullet", clean_inline(raw[2:])))
            continue
        blocks.append(Block("paragraph", clean_inline(raw)))
    return blocks


def set_font(run, size: float | None = None, bold: bool | None = None, color: str | None = None) -> None:
    run.font.name = FONT_CN
    run._element.get_or_add_rPr().get_or_add_rFonts().set(qn("w:eastAsia"), FONT_CN)
    if size is not None:
        run.font.size = Pt(size)
    if bold is not None:
        run.bold = bold
    if color:
        run.font.color.rgb = RGBColor.from_string(color)


def shade_cell(cell, fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = tc_pr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        tc_pr.append(shd)
    shd.set(qn("w:fill"), fill)


def border_cell(cell, color: str = "CBD5E1", size: str = "8") -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    borders = tc_pr.first_child_found_in("w:tcBorders")
    if borders is None:
        borders = OxmlElement("w:tcBorders")
        tc_pr.append(borders)
    for edge in ("top", "left", "bottom", "right"):
        node = borders.find(qn(f"w:{edge}"))
        if node is None:
            node = OxmlElement(f"w:{edge}")
            borders.append(node)
        node.set(qn("w:val"), "single")
        node.set(qn("w:sz"), size)
        node.set(qn("w:color"), color)


def set_cell_margins(cell, value: int = 120) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    margins = tc_pr.first_child_found_in("w:tcMar")
    if margins is None:
        margins = OxmlElement("w:tcMar")
        tc_pr.append(margins)
    for side in ("top", "start", "bottom", "end"):
        node = margins.find(qn(f"w:{side}"))
        if node is None:
            node = OxmlElement(f"w:{side}")
            margins.append(node)
        node.set(qn("w:w"), str(value))
        node.set(qn("w:type"), "dxa")


def add_field(paragraph, instruction: str) -> None:
    run = paragraph.add_run()
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = instruction
    separate = OxmlElement("w:fldChar")
    separate.set(qn("w:fldCharType"), "separate")
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    run._r.extend([begin, instr, separate, end])


def clear_document(document: Document) -> None:
    body = document._element.body
    for child in list(body):
        if child.tag != qn("w:sectPr"):
            body.remove(child)


def configure_styles(document: Document) -> None:
    styles = document.styles
    normal = styles["Normal"]
    normal.font.name = FONT_CN
    normal._element.get_or_add_rPr().get_or_add_rFonts().set(qn("w:eastAsia"), FONT_CN)
    normal.font.size = Pt(11)
    normal.font.color.rgb = RGBColor.from_string(TEXT)
    normal.paragraph_format.line_spacing_rule = WD_LINE_SPACING.ONE_POINT_FIVE
    normal.paragraph_format.space_after = Pt(4)

    heading_specs = {
        "Title": (24, NAVY, 16, 8),
        "Heading 1": (16, NAVY, 18, 10),
        "Heading 2": (14, NAVY, 14, 8),
        "Heading 3": (12, BLUE_DARK, 11, 6),
        "Heading 4": (11, NAVY, 9, 5),
        "Heading 5": (10.5, NAVY, 8, 4),
        "Heading 6": (10.5, NAVY, 8, 4),
    }
    for name, (size, color, before, after) in heading_specs.items():
        style = styles[name] if name in styles else styles.add_style(name, WD_STYLE_TYPE.PARAGRAPH)
        style.font.name = FONT_CN
        style._element.get_or_add_rPr().get_or_add_rFonts().set(qn("w:eastAsia"), FONT_CN)
        style.font.size = Pt(size)
        style.font.bold = True
        style.font.color.rgb = RGBColor.from_string(color)
        style.paragraph_format.space_before = Pt(before)
        style.paragraph_format.space_after = Pt(after)
        style.paragraph_format.keep_with_next = True

    if "FigureNote" not in styles:
        style = styles.add_style("FigureNote", WD_STYLE_TYPE.PARAGRAPH)
        style.font.name = FONT_CN
        style._element.get_or_add_rPr().get_or_add_rFonts().set(qn("w:eastAsia"), FONT_CN)
        style.font.size = Pt(9.5)
        style.font.color.rgb = RGBColor.from_string(GREY)
        style.paragraph_format.line_spacing = 1.25
        style.paragraph_format.space_after = Pt(2)


def configure_page(document: Document) -> None:
    section = document.sections[0]
    section.start_type = WD_SECTION_START.NEW_PAGE
    section.page_width = Cm(21)
    section.page_height = Cm(29.7)
    section.top_margin = Cm(2.61)
    section.bottom_margin = Cm(2.43)
    section.left_margin = Cm(2.75)
    section.right_margin = Cm(1.75)
    section.header_distance = Cm(1.1)
    section.footer_distance = Cm(1.1)
    section.different_first_page_header_footer = True

    for element in list(section.header._element):
        section.header._element.remove(element)
    header_p = section.header.add_paragraph()
    header_p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    run = header_p.add_run("错题帮｜赛题一：生成式大语言模型与智能体")
    set_font(run, 8.5, color=GREY)

    for element in list(section.footer._element):
        section.footer._element.remove(element)
    footer_p = section.footer.add_paragraph()
    footer_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = footer_p.add_run("— ")
    set_font(run, 9, color=GREY)
    add_field(footer_p, "PAGE")
    run = footer_p.add_run(" —")
    set_font(run, 9, color=GREY)


def add_cover(document: Document) -> None:
    p = document.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(52)
    run = p.add_run("第八届中国研究生人工智能创新大赛")
    set_font(run, 20, True, NAVY)

    p = document.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(72)
    run = p.add_run("错题帮")
    set_font(run, 32, True, BLUE)

    p = document.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(14)
    p.paragraph_format.left_indent = Cm(1.3)
    p.paragraph_format.right_indent = Cm(1.3)
    run = p.add_run("具有长期认知记忆、动态工具调用与可验证决策轨迹的多模态教学智能体")
    set_font(run, 16, True, NAVY)

    p = document.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(48)
    run = p.add_run("项 目 文 档")
    set_font(run, 22, True, NAVY)

    for text in ("团队名称：题醐灌顶队", "参赛赛题：赛题一——生成式大语言模型与智能体", "编制日期：2026 年 8 月"):
        p = document.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(12)
        run = p.add_run(text)
        set_font(run, 11.5, color=TEXT)
    document.add_page_break()


def add_front_matter(document: Document) -> None:
    p = document.add_paragraph("目录", style="Heading 1")
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(0)
    toc = document.add_paragraph()
    add_field(toc, 'TOC \\o "1-3" \\h \\z \\u')
    hint = document.add_paragraph("提示：首次打开文档后，在目录区域选择“更新整个目录”，即可显示最终页码。")
    hint.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for run in hint.runs:
        set_font(run, 9, color=GREY)
    document.add_page_break()

    p = document.add_paragraph("记录更改历史", style="Heading 1")
    p.paragraph_format.space_before = Pt(0)
    table = document.add_table(rows=2, cols=6)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = True
    headers = ["序号", "更改原因", "版本", "作者", "更改日期", "备注"]
    values = ["1", "依据官方模板重构，补全竞赛论证、技术实现、评测与插图说明", "v3.0", "项目组", "2026 年 8 月", "匿名参赛版"]
    for row_index, values_row in enumerate((headers, values)):
        for col_index, value in enumerate(values_row):
            cell = table.cell(row_index, col_index)
            cell.text = value
            cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            set_cell_margins(cell)
            border_cell(cell)
            if row_index == 0:
                shade_cell(cell, LIGHT_BLUE)
            for paragraph in cell.paragraphs:
                paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
                for run in paragraph.runs:
                    set_font(run, 9.5, row_index == 0, NAVY if row_index == 0 else TEXT)
    note = document.add_paragraph(
        "说明：本文档严格保持官方四章框架。所有插图位置均已标注图号、内容、风格和源码依据，团队可在定稿阶段直接用自绘架构图或真实系统截图替换。"
    )
    note.paragraph_format.space_before = Pt(18)
    note.paragraph_format.first_line_indent = Pt(22)
    note.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    document.add_page_break()


FIGURE_FORMS = {
    "diagram": "横向扁平信息图；白底、单一品牌蓝、线性箭头和少量状态色",
    "comparison": "左右对比图；两条流程等宽排列，突出能力差异，不使用装饰性素材",
    "architecture": "分层架构图；自上而下或自左向右，组件边界与数据流方向明确",
    "flow": "横向闭环流程图；步骤不超过八个，关键验证点使用加粗边框",
    "agent": "智能体决策循环图；展示观察、记忆、规划、工具行动和证据核验",
    "data": "数据治理流程图；同时标示数据规模、许可边界和进入系统的条件",
    "screenshots": "真实系统截图组；使用同一测试记录、统一裁切比例和简洁设备框",
    "mixed": "机制图与真实页面组合；机制在左或上，运行证据在右或下",
}


def guidance_for(item: dict) -> str:
    title = item["title"]
    if item["kind"] == "screenshots":
        return f"选取能直接证明“{title}”的核心状态，不展示空页面、重复菜单或与正文无关的列表。"
    if item["kind"] == "mixed":
        return f"用一半版面概括“{title}”的机制，另一半使用真实运行界面或评测结果作为证据。"
    return f"围绕“{title}”只表达正文已经论证的关系，节点文案简短，避免机器人、芯片、大脑、3D 和炫光渐变。"


def add_figure_placeholder(document: Document, item: dict) -> None:
    table = document.add_table(rows=1, cols=1)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    row = table.rows[0]
    row.height = Cm(5.6)
    row.height_rule = WD_ROW_HEIGHT_RULE.AT_LEAST
    cell = row.cells[0]
    cell.width = Cm(15.8)
    cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
    shade_cell(cell, "F8FAFC")
    border_cell(cell, BLUE, "12")
    set_cell_margins(cell, 180)

    p = cell.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(f"【图 {item['id']} 待替换】{item['title']}")
    set_font(run, 11.5, True, BLUE_DARK)

    form = FIGURE_FORMS.get(item["kind"], "简洁的信息图或真实界面截图")
    lines = [
        ("建议形式：", form),
        ("绘制要求：", guidance_for(item)),
        ("建议尺寸：", f"横向约 {item['width_cm']} cm × {item['height_cm']} cm；按版心等比例调整"),
    ]
    vue_sources = [source for source in item.get("sources", []) if source.endswith(".vue")]
    other_sources = [source for source in item.get("sources", []) if not source.endswith(".vue")]
    if vue_sources:
        lines.append(("截图对应 Vue 文件：", "；".join(vue_sources)))
    if other_sources:
        lines.append(("绘图依据：" if not vue_sources else "其他依据：", "；".join(other_sources)))
    for label, value in lines:
        p = cell.add_paragraph(style="FigureNote")
        p.paragraph_format.left_indent = Cm(0.25)
        p.paragraph_format.right_indent = Cm(0.25)
        run = p.add_run(label)
        set_font(run, 9.3, True, NAVY)
        run = p.add_run(value)
        set_font(run, 9.3, color=GREY)

    caption = document.add_paragraph()
    caption.alignment = WD_ALIGN_PARAGRAPH.CENTER
    caption.paragraph_format.space_after = Pt(8)
    run = caption.add_run(f"图 {item['id']}  {item['title']}（定稿时替换上方说明框）")
    set_font(run, 10, color=GREY)


def add_body_table(document: Document, rows: list[list[str]]) -> None:
    if not rows:
        return
    table = document.add_table(rows=len(rows), cols=len(rows[0]))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = True
    for row_index, values in enumerate(rows):
        row = table.rows[row_index]
        row.height_rule = WD_ROW_HEIGHT_RULE.AT_LEAST
        for col_index, value in enumerate(values):
            cell = row.cells[col_index]
            cell.text = value
            cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            set_cell_margins(cell, 90)
            border_cell(cell, "D7DEE8", "6")
            if row_index == 0:
                shade_cell(cell, LIGHT_BLUE)
            elif row_index % 2 == 0:
                shade_cell(cell, "F8FAFC")
            for paragraph in cell.paragraphs:
                paragraph.paragraph_format.first_line_indent = Pt(0)
                paragraph.paragraph_format.line_spacing = 1.15
                paragraph.paragraph_format.space_after = Pt(0)
                paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER if row_index == 0 else WD_ALIGN_PARAGRAPH.LEFT
                for run in paragraph.runs:
                    set_font(run, 8.7, row_index == 0, NAVY if row_index == 0 else TEXT)
    document.add_paragraph().paragraph_format.space_after = Pt(1)


def paragraph_units(text: str) -> float:
    return max(2.0, math.ceil(len(text) / 36) * 1.15 + 0.8)


def block_units(block: Block) -> float:
    if block.kind == "heading":
        return {1: 4.5, 2: 3.7, 3: 3.2, 4: 2.8, 5: 2.5, 6: 2.5}.get(block.level, 3)
    if block.kind in {"paragraph", "bullet"}:
        return paragraph_units(block.text)
    if block.kind == "figure":
        return 13.0
    if block.kind == "table":
        rows = block.rows or []
        return max(4.0, len(rows) * 2.25 + 1.5)
    return 1.0


def add_manuscript(document: Document, blocks: list[Block], manifest: dict[str, dict]) -> int:
    # Conservative page budgeting keeps coherent blocks together and targets
    # roughly sixty Word pages before the final figures replace their boxes.
    capacity = 36.5
    current = 0.0
    estimated_pages = 1
    first_chapter = True

    for block in blocks:
        units = block_units(block)
        if block.kind == "heading" and block.level == 1:
            if not first_chapter:
                document.add_page_break()
                estimated_pages += 1
            first_chapter = False
            current = 0.0
        elif current > 12 and current + units > capacity:
            document.add_page_break()
            estimated_pages += 1
            current = 0.0

        if block.kind == "heading":
            paragraph = document.add_paragraph(block.text, style=f"Heading {min(block.level, 6)}")
            if block.level == 1:
                paragraph.paragraph_format.space_before = Pt(0)
            current += units
            continue

        if block.kind == "paragraph":
            text = block.text
            paragraph = document.add_paragraph()
            paragraph.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            paragraph.paragraph_format.first_line_indent = Pt(22)
            if text.startswith("【已验证结果】"):
                label = paragraph.add_run("已验证结果｜")
                set_font(label, 10.5, True, BLUE_DARK)
                text = text.removeprefix("【已验证结果】").lstrip()
            elif text.startswith("【目标指标】"):
                label = paragraph.add_run("目标指标｜")
                set_font(label, 10.5, True, ORANGE)
                text = text.removeprefix("【目标指标】").lstrip()
            elif text.startswith("【待替换结果】"):
                label = paragraph.add_run("待补正式结果｜")
                set_font(label, 10.5, True, ORANGE)
                text = text.removeprefix("【待替换结果】").lstrip()
            run = paragraph.add_run(text)
            set_font(run, 11, color=TEXT)
        elif block.kind == "bullet":
            paragraph = document.add_paragraph(style="List Bullet")
            paragraph.paragraph_format.left_indent = Cm(0.75)
            run = paragraph.add_run(block.text)
            set_font(run, 11, color=TEXT)
        elif block.kind == "table":
            add_body_table(document, block.rows or [])
        elif block.kind == "figure":
            item = manifest.get(block.figure_id)
            if item is None:
                raise ValueError(f"figure {block.figure_id} is missing from figure_manifest.json")
            add_figure_placeholder(document, item)

        current += units
        if current >= capacity:
            estimated_pages += int(current // capacity)
            current %= capacity
    return estimated_pages


def enable_field_updates(document: Document) -> None:
    settings = document.settings._element
    node = settings.find(qn("w:updateFields"))
    if node is None:
        node = OxmlElement("w:updateFields")
        settings.append(node)
    node.set(qn("w:val"), "true")


def scrub_metadata(document: Document) -> None:
    props = document.core_properties
    props.title = "错题帮——具有长期认知记忆、动态工具调用与可验证决策轨迹的多模态教学智能体"
    props.subject = "第八届中国研究生人工智能创新大赛项目文档"
    props.author = "题醐灌顶队"
    props.last_modified_by = "题醐灌顶队"
    props.keywords = "错题帮；多模态教学智能体；长期认知记忆；动态工具调用；可验证决策轨迹"
    props.comments = "匿名参赛项目文档"


def build() -> None:
    if not TEMPLATE.exists():
        raise FileNotFoundError(f"template not found: {TEMPLATE}")
    document = Document(TEMPLATE)
    clear_document(document)
    configure_styles(document)
    configure_page(document)
    scrub_metadata(document)
    enable_field_updates(document)
    add_cover(document)
    add_front_matter(document)

    manifest_items = json.loads(MANIFEST.read_text(encoding="utf-8"))
    manifest = {item["id"]: item for item in manifest_items}
    blocks = parse_source()
    estimated_body_pages = add_manuscript(document, blocks, manifest)
    document.save(OUTPUT)
    print(f"Built: {OUTPUT}")
    print(f"Official manuscript blocks: {len(blocks)}")
    print(f"Figure replacement boxes: {len(manifest_items)}")
    print(f"Layout estimate: about {estimated_body_pages + 3} pages before Word updates the TOC")


if __name__ == "__main__":
    build()
