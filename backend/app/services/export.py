from __future__ import annotations

from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from openpyxl import Workbook
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer


def option_text(option: Any, index: int) -> str:
    if not isinstance(option, dict):
        return str(option)
    label = option.get("label") or option.get("key") or chr(65 + index)
    value = option.get("text") or option.get("content") or option.get("value") or ""
    return f"{label}. {value}"


def build_pdf(path: Path, title: str, questions: list[dict[str, Any]], answers: bool = False) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    body = ParagraphStyle(
        "body", fontName="STSong-Light", fontSize=11, leading=19, wordWrap="CJK", spaceAfter=9
    )
    heading = ParagraphStyle("heading", parent=body, fontSize=17, leading=25, spaceAfter=22)
    muted = ParagraphStyle("muted", parent=body, textColor=colors.HexColor("#526078"))
    flow: list[Any] = []

    def paragraph(text: Any, style: ParagraphStyle = body) -> Paragraph:
        return Paragraph(escape(str(text)).replace("\n", "<br/>"), style)

    flow.append(paragraph(title, heading))
    for index, item in enumerate(questions, 1):
        flow.append(paragraph(f"{index}.（{item.get('score', 10)}分）{item.get('question_text', '')}"))
        for option_index, option in enumerate(item.get("options") or []):
            flow.append(paragraph(option_text(option, option_index)))
        if item.get("formula"):
            flow.append(paragraph(f"公式：{item['formula']}"))
        # Only explicitly isolated problem figures belong in an unanswered paper.
        for image_path in item.get("figure_paths") or []:
            source = Path(image_path)
            if not source.is_file():
                continue
            picture = Image(str(source))
            factor = min(440 / picture.imageWidth, 300 / picture.imageHeight, 1)
            picture.drawWidth = picture.imageWidth * factor
            picture.drawHeight = picture.imageHeight * factor
            picture.hAlign = "LEFT"
            flow.extend([picture, Spacer(1, 12)])
        if answers:
            flow.append(paragraph(f"答案：{item.get('answer') or '尚未生成，请先完成题目分析'}"))
            flow.append(paragraph(f"解析：{item.get('explanation') or '暂无解析'}", muted))
        else:
            flow.append(Spacer(1, 50))
        flow.append(Spacer(1, 12))

    def footer(canvas, document):
        canvas.saveState()
        canvas.setFont("STSong-Light", 9)
        canvas.drawRightString(545, 28, f"第 {document.page} 页")
        canvas.restoreState()

    document = SimpleDocTemplate(
        str(path), pagesize=A4, title=title, leftMargin=50, rightMargin=50, topMargin=45, bottomMargin=50
    )
    document.build(flow, onFirstPage=footer, onLaterPages=footer)
    return path


def build_excel(path: Path, rows: list[dict[str, Any]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    wb = Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "学习数据"
    ws.append(["题目", "学科", "错因", "掌握度", "复习日期"])
    for index, row in enumerate(rows, 2):
        for column, key in enumerate(("question", "subject", "misconception", "mastery", "review"), 1):
            value = row.get(key, "")
            cell = ws.cell(index, column, value)
            if isinstance(value, str):
                cell.data_type = "s"  # Student text must never become a spreadsheet formula.
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    for column_letter, width in {"A": 65, "B": 12, "C": 40, "D": 14, "E": 22}.items():
        ws.column_dimensions[column_letter].width = width
    wb.save(path)
    return path
