from cuoti_backend.learning_evidence import first_label, stamp_compact
from cuoti_backend.lessons import compact


def test_source_stamp_native_number_format_keeps_api_json_unchanged():
    value = {"confidence": 1.0, "coordinates": [0.0, 0.25, True], "label": "方程"}
    assert (
        stamp_compact(value)
        == '{"confidence":1,"coordinates":[0,0.25,true],"label":"方程"}'
    )
    assert "1.0" in compact(value)
    assert first_label([{}, {"name": "", "label": "等式性质"}]) == "等式性质"
