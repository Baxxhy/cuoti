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


def test_format_review_blocks_only_the_reviewed_content_version(tmp_path: Path) -> None:
    from types import SimpleNamespace

    from app.services.question_quality import quality_flags

    question = SimpleNamespace(
        question_text="保留的原始题干",
        question_type="单选题",
        answer="A",
        options=[{"key": "A", "text": "1"}, {"key": "B", "text": "2"}],
        solution="",
        image_paths=[],
        content_hash="a" * 64,
        source_metadata={"format_review": {"content_hash": "a" * 64, "fields": ["solution"]}},
    )
    flags = quality_flags(question, tmp_path)
    assert flags["quality_status"] == "format_review"
    assert not flags["usable_for_practice"] and not flags["usable_for_auto_grade"]
    question.content_hash = "b" * 64
    assert quality_flags(question, tmp_path)["usable_for_practice"] is True
    question.content_hash = "a" * 64
    question.source_metadata["format_review"]["fields"] = []
    assert quality_flags(question, tmp_path)["usable_for_practice"] is True


def test_native_preparation_audits_new_source_before_import(tmp_path: Path, monkeypatch) -> None:
    import copy
    import importlib
    from dataclasses import asdict

    from app.services.question_bank_import import NormalizedDatasetQuestion

    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / "scripts"))
    prepare = importlib.import_module("prepare_cangjie_question_bank")
    rows = []
    for item_id, text in [("good", r"在 $$\triangleABC$$ 中"), ("bad", r"坏公式 $$\overset{⇌}$$")]:
        rows.append(
            NormalizedDatasetQuestion(
                source_item_id=item_id,
                split="test",
                subject="数学",
                grade="初一",
                grade_band="初中",
                title="题目",
                question_text=text,
                question_type="单选题",
                options=[{"key": "A", "text": "1"}, {"key": "B", "text": "2"}],
                answer="A",
                solution="",
                knowledge_points=[],
                image_paths=[],
                difficulty="",
                source_metadata={},
            ).finalize()
        )
    originals = [asdict(row) for row in rows]
    stored = []

    def native(payload):
        if payload["operation"] == "cards":
            return []
        stored.extend(copy.deepcopy(payload["questions"]))
        return {"stored": "2"}

    monkeypatch.setattr(prepare, "native", native)
    monkeypatch.setattr(prepare, "normalized_records", lambda source, include_primary=False: iter(rows))
    prepare.import_records("cmmu")
    assert stored[0]["usable_for_practice"] is True
    assert stored[1]["quality_status"] == "format_review"
    assert stored[1]["usable_for_practice"] is False
    assert stored[1]["source_metadata"]["format_review"]["fields"] == ["question"]
    assert stored[1]["question_text"] == originals[1]["question_text"]
    assert stored[1]["content_hash"] == originals[1]["content_hash"]


def test_recover_missing_first_marker_and_spaced_choice_labels():
    expected = [
        {"key": "A", "text": "1"},
        {"key": "B", "text": "2"},
        {"key": "C", "text": "3"},
        {"key": "D", "text": "4"},
    ]
    assert normalize_choice_options("1\nB. 2\nC. 3\nD. 4") == expected
    assert normalize_choice_options("A. 1\nB . 2\nC . 3\nD. 4") == expected
    assert normalize_choice_options("B. 2 C. 3 D. 4") == []


def test_unparsed_or_incomplete_options_do_not_become_short_answer(tmp_path):
    from app.services.question_quality import quality_flags

    path = tmp_path / "cmm.jsonl"
    rows = [
        {
            "id": "lost",
            "level": "高一",
            "question": "选择正确答案",
            "options": "选项图片无法解析",
            "answer": "A",
        },
        {
            "id": "gap",
            "level": "高一",
            "question": "选择正确答案",
            "options": "A. 甲 C. 丙 D. 丁",
            "answer": "A",
        },
    ]
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows))
    for row in iter_cmm_math(path):
        assert row.source_metadata["answer_review"]
        assert not quality_flags(row, tmp_path)["usable_for_auto_grade"]


def test_math_multiselect_does_not_become_single_choice(tmp_path):
    path = tmp_path / "cmm.jsonl"
    path.write_text(
        json.dumps(
            {
                "id": "multi",
                "level": "高一",
                "question": "选择正确答案",
                "options": "A. 甲 B. 乙 C. 丙 D. 丁",
                "answer": "ACD",
            }
        )
    )
    assert next(iter_cmm_math(path)).question_type == "多项选择题"
