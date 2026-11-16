import pytest
from cuoti_backend.retrieval import grade_label, usable


@pytest.mark.parametrize(
    "raw,band,expected",
    [
        ("七年级上", "初中", "初一"),
        ("八年级", "初中", "初二"),
        ("九年级", "初中", "初三"),
        ("高中选修", "高中", "高中"),
        ("", "初中", "初中"),
    ],
)
def test_retrieval_grade_labels(raw, band, expected):
    assert grade_label(raw, band) == expected


def test_retrieval_candidate_grade_answer_and_image_checks():
    source = {"subject": "数学", "grade": "初一"}
    item = {
        "subject": "数学",
        "grade": "七年级",
        "grade_band": "初中",
        "usable_for_practice": True,
        "has_answer": True,
        "usable_for_auto_grade": True,
        "answer": "5",
        "question_text": "2x=10",
        "options": [],
        "solution": "",
        "image_paths": [],
        "source_metadata": {},
    }
    assert usable(source, item, "variant")
    assert not usable(source, {**item, "answer": ""}, "variant")
    assert not usable(source, {**item, "grade": "高一"}, "variant")
    assert not usable(source, {**item, "question_text": "图<ImageHere>"}, "variant")
    assert usable(source, {**item, "image_paths": ["figure.jpg"]}, "variant")
    assert not usable(source, {**item, "usable_for_auto_grade": False}, "practice")
