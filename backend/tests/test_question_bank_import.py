from __future__ import annotations

import json
import zipfile
from pathlib import Path

from app.services.question_bank_import import (
    iter_cmm_math,
    iter_cmmu,
    iter_m3ke,
    normalize_choice_options,
)


def test_cmm_math_keeps_only_middle_and_high_school(tmp_path: Path) -> None:
    path = tmp_path / "cmm.jsonl"
    rows = [
        {"id": "1", "level": "六年级", "question": "小学题", "options": "", "subject": "算术"},
        {
            "id": "2",
            "level": "八年级",
            "question": "中学题",
            "options": "A. 1\nB. 2",
            "answer": "B",
            "subject": "代数",
            "image": ["a.jpg"],
        },
        {
            "id": "3",
            "level": "高二",
            "question": "高中题",
            "options": "",
            "answer": "2",
            "subject": "解析几何",
        },
    ]
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows), encoding="utf-8")
    result = list(iter_cmm_math(path, {"a.jpg": "data/assets/a.jpg"}))
    assert [item.source_item_id for item in result] == ["2", "3"]
    assert result[0].options == [{"key": "A", "text": "1"}, {"key": "B", "text": "2"}]
    assert result[0].image_paths == ["data/assets/a.jpg"]
    assert result[0].content_hash


def test_options_split_when_source_omits_all_separating_whitespace() -> None:
    expected = [
        {"key": "A", "text": "3"},
        {"key": "B", "text": "-1"},
        {"key": "C", "text": "-1 或 3"},
        {"key": "D", "text": "-3 或 1"},
    ]
    assert normalize_choice_options("A. 3B. -1C. -1 或 3D. -3 或 1") == expected
    assert (
        normalize_choice_options(
            [
                {
                    "key": "A",
                    "text": "3B. -1C. -1 或 3D. -3 或 1",
                }
            ]
        )
        == expected
    )
    assert normalize_choice_options("A. xB. yC. x+yD. x-y") == [
        {"key": "A", "text": "x"},
        {"key": "B", "text": "y"},
        {"key": "C", "text": "x+y"},
        {"key": "D", "text": "x-y"},
    ]


def test_m3ke_filters_school_tasks_and_preserves_hidden_answers(tmp_path: Path) -> None:
    path = tmp_path / "M3KE.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "test/Math-Natural Sciences-Junior high school.jsonl",
            json.dumps(
                {"id": 0, "question": "题目", "A": "甲", "B": "乙", "C": "丙", "D": "丁", "answer": ""},
                ensure_ascii=False,
            ),
        )
        archive.writestr(
            "test/Advanced Mathematics-Natural Sciences-College.jsonl",
            json.dumps({"id": 0, "question": "大学题"}, ensure_ascii=False),
        )
    result = list(iter_m3ke(path))
    assert len(result) == 1
    assert result[0].subject == "数学"
    assert result[0].grade_band == "初中"
    assert result[0].answer == ""
    assert result[0].source_metadata["answer_available"] is False


def test_cmmu_appends_sub_questions_and_excludes_primary(tmp_path: Path) -> None:
    rows = [
        {"id": "p1", "grade_band": "primary", "question_info": "小学题", "subject": "math"},
        {
            "id": "m1",
            "grade_band": "middle",
            "question_info": "阅读材料",
            "sub_questions": ["第一问", "第二问"],
            "subject": "physics",
            "type": "fill-in-the-blank",
            "options": None,
            "answer": ["1", "2"],
        },
    ]
    (tmp_path / "physics.jsonl").write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows), encoding="utf-8"
    )
    result = list(iter_cmmu(tmp_path))
    assert len(result) == 1
    assert result[0].subject == "物理"
    assert "1. 第一问" in result[0].question_text
    assert result[0].answer == ["1", "2"]
