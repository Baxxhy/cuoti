import base64
import hashlib
import io

from fastapi.testclient import TestClient
from openpyxl import load_workbook

from service import create_app


def test_paper_rendering_uses_original_export_and_safe_spreadsheet(tmp_path):
    secret = "paper-rendering-" + "x" * 32
    app = create_app(secret=secret, pool_path=tmp_path / "missing.json")
    with TestClient(app) as client:
        for kind in ["question", "answer", "excel"]:
            response = client.post(
                "/v1/compute",
                headers={"Authorization": "Bearer " + secret},
                json={
                    "operation": "render_paper",
                    "paper_title": "函数练习",
                    "paper_kind": kind,
                    "paper_questions": [
                        {
                            "question_text": "=1+1",
                            "answer": "2",
                            "explanation": "相加",
                            "subject": "数学",
                            "score": 20,
                        }
                    ],
                },
            )
            assert response.status_code == 200, response.text
            result = response.json()["result"]
            data = base64.b64decode(result["file_base64"])
            assert hashlib.sha256(data).hexdigest() == result["sha256"]
            if kind == "excel":
                workbook = load_workbook(io.BytesIO(data))
                assert (
                    workbook.active["A2"].value == "=1+1"
                    and workbook.active["A2"].data_type == "s"
                )
            else:
                assert data.startswith(b"%PDF-") and len(data) > 1000
        assert app.state.provider is None
        assert (
            client.post(
                "/v1/compute",
                headers={"Authorization": "Bearer " + secret},
                json={"operation": "render_paper", "paper_kind": "unknown"},
            ).status_code
            == 422
        )


def test_paper_renderer_includes_only_supplied_question_figures():
    from test_service import image_input

    from paper_export_compute import ExportQuestion, render_paper

    question = ExportQuestion(question_text="观察题图", figure_images=[image_input()])
    rendered = render_paper("图形题", "question", [question])
    data = base64.b64decode(rendered["file_base64"])
    assert b"/Subtype /Image" in data


def test_answer_export_rejects_missing_analysis_before_rendering():
    import pytest

    from paper_export_compute import ExportQuestion, render_paper

    with pytest.raises(ValueError, match="缺少答案或解析"):
        render_paper(
            "缺解析", "answer", [ExportQuestion(question_text="1+1=?", answer="2")]
        )


def test_excel_repairs_json_fraction_before_writing_xml(tmp_path, monkeypatch):
    import json
    from PIL import Image
    from learning_core.services import export

    png = io.BytesIO()
    Image.new('RGB', (8, 8), 'white').save(png, format='PNG')
    captured = []
    def render(payload):
        captured.extend(cell['text'] for cell in payload['cells'])
        return json.dumps([{'png': base64.b64encode(png.getvalue()).decode(),
                            'width': 8, 'height': 8} for _ in payload['cells']])
    monkeypatch.setattr(export, 'render_math_document', render)
    original = '答案 $x=\x0crac{19}{3}$'
    target = export.build_excel(tmp_path / 'fraction.xlsx', [{'question': original}])
    workbook = load_workbook(target)
    assert captured == [r'答案 $x=\frac{19}{3}$']
    assert workbook.active['A2'].comment.text == captured[0]
    assert len(workbook.active._images) == 1


def test_excel_reports_other_invalid_controls_as_bad_input(tmp_path):
    import pytest
    from learning_core.services.export import build_excel
    with pytest.raises(ValueError, match='控制字符'):
        build_excel(tmp_path / 'invalid.xlsx', [{'question': '内容\x00'}])
