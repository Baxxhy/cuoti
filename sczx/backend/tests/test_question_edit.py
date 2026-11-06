import pytest
from fastapi import HTTPException
from sczx_api.question_edit import validate_edit


def test_edit_preserves_original_whitelist_and_work_endpoint_contract():
    assert validate_edit({'unknown': 1, 'student_steps': ['合法步骤'], 'teacher_marks': [{'comment': '批注', 'bbox': [0, '1']} ]}) == {}
    assert validate_edit({'favorite': 'off', 'question_text': ' 题目 ', 'student_answer': None, 'tags': [' 标签 ']}) == {'favorite': False, 'question_text': '题目', 'student_answer': None, 'tags': ['标签']}


@pytest.mark.parametrize('body', [
    {'question_text': '  '}, {'favorite': 'perhaps'}, {'grade': 2},
    {'options': [{'label': 'A', 'text': ''}, {'label': 'A', 'text': '重复'}]},
    {'student_steps': [{'confidence': 1.1}]},
    {'teacher_marks': [{'bbox': [0, 1, 2, 3, 4]}]},
    {'knowledge_points': ['x' * 31]}, {'tags': '标签'},
])
def test_edit_invalid_fields_rejected(body):
    with pytest.raises(HTTPException) as error:
        validate_edit(body)
    assert error.value.status_code == 422
