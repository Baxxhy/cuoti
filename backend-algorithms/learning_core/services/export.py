from __future__ import annotations

import base64
import io
import json
import os
import re
import signal
import subprocess
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from openpyxl import Workbook
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
from openpyxl.comments import Comment
from openpyxl.drawing.image import Image as SheetImage
from openpyxl.styles import Alignment
from PIL import Image as PillowImage
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


def build_math_pdf(path: Path, title: str, questions: list[dict[str, Any]], answers: bool) -> Path:
    """Render trusted KaTeX HTML offline; student text never becomes script."""
    rows = []
    for question in questions:
        row = {key: value for key, value in question.items() if key not in {"figure_paths", "image_path"}}
        row["figures"] = []
        for source in question.get("figure_paths") or []:
            if not Path(source).is_file():
                continue
            with PillowImage.open(source) as image:
                image.thumbnail((1800, 1800))
                data = io.BytesIO()
                image.convert("RGB").save(data, format="PNG")
            row["figures"].append("data:image/png;base64," + base64.b64encode(data.getvalue()).decode())
        if not answers:
            row.pop("answer", None)
            row.pop("explanation", None)
        rows.append(row)
    render_math_document({"title": title, "questions": rows, "answers": answers, "output": str(path.resolve())})
    if not path.is_file():
        raise ValueError("PDF公式排版未完成，请核对公式及本地Chromium环境后重试")
    return path


def render_math_document(payload: dict[str, Any]) -> str:
    label = "Excel" if payload.get("mode") == "excel" else "PDF"
    worker = Path(__file__).resolve().parents[3] / "scripts" / "render_math_pdf.cjs"
    try:
        process = subprocess.Popen(
            ["node", str(worker)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, start_new_session=True,
        )
        try:
            output, _ = process.communicate(json.dumps(payload), timeout=35)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.communicate()
            raise ValueError(label + "公式排版超时，请缩小导出范围后重试") from None
    except OSError:
        raise ValueError(label + "公式排版未完成，请检查本地Chromium环境后重试") from None
    if process.returncode:
        raise ValueError(label + "公式排版未完成，请核对公式及本地Chromium环境后重试")
    return output


def build_pdf(path: Path, title: str, questions: list[dict[str, Any]], answers: bool = False) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if answers:
        missing = [
            str(index)
            for index, item in enumerate(questions, 1)
            if not str(item.get("answer") or "").strip() or not str(item.get("explanation") or "").strip()
        ]
        if missing:
            raise ValueError("第" + "、".join(missing) + "题缺少答案或解析，请先补齐分析")
    source = json.dumps([title, questions], ensure_ascii=False)
    if re.search(r"\$|\\[A-Za-z(\[]", source):
        return build_math_pdf(path, title, questions, answers)
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
    formula_cells = []
    for index, row in enumerate(rows, 2):
        for column, key in enumerate(("question", "subject", "misconception", "mastery", "review"), 1):
            value = row.get(key, "")
            if isinstance(value, str):
                # Match the frontend's repair of JSON-decoded LaTeX \\frac.
                value = re.sub(r"\x0c(?=rac\b)", r"\\f", value)
                if ILLEGAL_CHARACTERS_RE.search(value):
                    raise ValueError("导出文字含有无效控制字符，请编辑相关题目或错因后重试")
            cell = ws.cell(index, column, value)
            cell.alignment = Alignment(vertical="top", wrap_text=True)
            if isinstance(value, str) and re.search(r"\$|\\[A-Za-z(\[]", value):
                formula_cells.append((cell, value, 450 if column == 1 else 275))
            if isinstance(value, str):
                cell.data_type = "s"  # Student text must never become a spreadsheet formula.
    if formula_cells:
        rendered = json.loads(render_math_document({
            "mode": "excel",
            "cells": [{"text": value, "width": width} for _, value, width in formula_cells],
        }))
        if len(rendered) != len(formula_cells):
            raise ValueError("Excel公式排版结果不完整，请重新导出")
        for (cell, source, width), result in zip(formula_cells, rendered):
            picture = SheetImage(io.BytesIO(base64.b64decode(result["png"], validate=True)))
            # Excel caps row height at 409 points; keep the whole image in its row.
            factor = min(1, width / result["width"], 530 / result["height"])
            picture.width = result["width"] * factor
            picture.height = result["height"] * factor
            cell.value = ""
            cell.comment = Comment(source, "公式原文")
            ws.add_image(picture, cell.coordinate)
            ws.row_dimensions[cell.row].height = max(
                ws.row_dimensions[cell.row].height or 0, (picture.height + 10) * 0.75
            )
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    for column_letter, width in {"A": 65, "B": 12, "C": 40, "D": 14, "E": 22}.items():
        ws.column_dimensions[column_letter].width = width
    wb.save(path)
    return path
