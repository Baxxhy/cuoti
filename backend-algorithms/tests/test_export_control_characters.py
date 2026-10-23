import base64
import io
from openpyxl import load_workbook


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
