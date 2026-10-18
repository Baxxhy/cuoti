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
    from paper_export_compute import ExportQuestion, render_paper
    from test_service import image_input

    question = ExportQuestion(question_text="观察题图", figure_images=[image_input()])
    rendered = render_paper("图形题", "question", [question])
    data = base64.b64decode(rendered["file_base64"])
    assert b"/Subtype /Image" in data
