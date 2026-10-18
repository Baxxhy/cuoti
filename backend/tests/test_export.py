from unittest.mock import patch

from openpyxl import load_workbook

from app.services.export import build_excel, build_pdf, option_text


def test_spreadsheet_student_text_is_literal_and_numbers_stay_numeric(tmp_path):
    path = build_excel(
        tmp_path / "report.xlsx",
        [{"question": "=1+1", "subject": "数学", "misconception": "@SUM(A1:A2)", "mastery": 0.6}],
    )
    sheet = load_workbook(path).active
    assert sheet["A2"].value == "=1+1" and sheet["A2"].data_type == "s"
    assert sheet["C2"].data_type == "s"
    assert sheet["D2"].value == 0.6 and sheet["D2"].data_type == "n"


def test_export_options_keep_labels_and_text():
    assert option_text({"label": "B", "text": "x < 3"}, 1) == "B. x < 3"
    assert option_text("A. x = 2", 0) == "A. x = 2"


def test_pdf_includes_options_and_does_not_embed_original_work(tmp_path):
    # Capture the document flow, as well as generating a real PDF, to inspect content.
    from reportlab.platypus import SimpleDocTemplate

    build = SimpleDocTemplate.build
    paragraphs = []

    def inspect(document, flow, **kwargs):
        paragraphs.extend(item.text for item in flow if hasattr(item, "text"))
        return build(document, flow, **kwargs)

    with patch.object(SimpleDocTemplate, "build", inspect), patch("app.services.export.Image") as image:
        path = build_pdf(
            tmp_path / "paper.pdf",
            "测试试卷",
            [
                {
                    "question_text": "题目中的 < 与 > 要保留",
                    "options": [{"label": "A", "text": "x=2"}, {"label": "B", "text": "x=4"}],
                    "image_path": str(tmp_path / "original-with-answer.jpg"),
                    "answer": "机密参考答案",
                }
            ],
        )
    assert path.read_bytes().startswith(b"%PDF-")
    assert "A. x=2" in paragraphs and "B. x=4" in paragraphs
    assert any("&lt;" in text for text in paragraphs)
    assert not any("机密参考答案" in text for text in paragraphs)
    image.assert_not_called()
