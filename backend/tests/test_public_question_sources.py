import io
import json
import tarfile

from app.services.public_question_sources import iter_gaokao, iter_race, iter_tal
from app.services.question_quality import quality_flags


def test_race_keeps_passage_and_aligns_answers(tmp_path):
    path = tmp_path / "race.tar.gz"
    raw = json.dumps(
        {
            "article": "A long reading passage.",
            "id": "p1",
            "questions": ["Who?", "When?"],
            "options": [["Alice", "Bob"], ["Today", "Tomorrow"]],
            "answers": ["A", "B"],
        }
    ).encode()
    with tarfile.open(path, "w:gz") as tar:
        item = tarfile.TarInfo("RACE/train/middle/1.txt")
        item.size = len(raw)
        tar.addfile(item, io.BytesIO(raw))
    rows = list(iter_race(path))
    assert len(rows) == 2 and rows[0].grade_band == "初中"
    assert rows[1].answer == "B" and rows[1].options[1]["text"] == "Tomorrow"
    assert rows[1].question_text == "A long reading passage.\n\nWhen?"
    assert rows[0].source_item_id != rows[1].source_item_id
    assert quality_flags(rows[1], tmp_path)["usable_for_practice"]


def test_gaokao_composite_is_not_multiselect_and_missing_diagram_blocked(tmp_path):
    folder = tmp_path / "Data/Objective_Questions"
    folder.mkdir(parents=True)
    (folder / "2010-2022_English_MCQs.json").write_text(
        json.dumps(
            {
                "example": [
                    {"index": 0, "question": "Choose. A. One B. Two C. Three D. Four", "answer": ["B"]},
                    {
                        "index": 1,
                        "question": "1. Q A. One B. Two C. Three D. Four\n2. Q A. One B. Two C. Three D. Four",
                        "answer": ["A", "B"],
                    },
                    {"index": 2, "question": "如图 A. One B. Two C. Three D. Four", "answer": ["A"]},
                ]
            }
        )
    )
    rows = list(iter_gaokao(tmp_path))
    assert rows[0].subject == "英语" and rows[0].question_text == "Choose."
    assert rows[0].answer == "B" and len(rows[0].options) == 4
    assert quality_flags(rows[0], tmp_path)["usable_for_practice"]
    assert rows[1].answer == ["A", "B"] and rows[1].options == []
    assert not quality_flags(rows[1], tmp_path)["usable_for_auto_grade"]
    assert quality_flags(rows[2], tmp_path)["quality_status"] == "missing_asset"


def test_tal_keeps_unknown_level_and_does_not_duplicate_translation(tmp_path):
    folder = tmp_path / "ch_single_choice_constructed_5K"
    folder.mkdir()
    row = {
        "queId": "unique",
        "qid": "1",
        "problem": "题目",
        "answer_value": "A",
        "answer_option_list": [[{"aoVal": "A", "content": "1"}], [{"aoVal": "B", "content": "2"}]],
        "answer_analysis": ["解析"],
        "knowledge_point_routes": ["数论"],
    }
    (folder / "train.jsonl").write_text(json.dumps(row))
    result = list(iter_tal(tmp_path))
    assert len(result) == 1 and result[0].grade_band == "拓展"
    assert result[0].solution == "解析" and result[0].knowledge_points == ["数论"]


def test_short_subjective_answer_is_not_marked_auto_gradable(tmp_path):
    from app.services.public_question_sources import question

    row = question("subjective", "all", "语文", "高中", "解释作者的态度", "赞同", kind="主观题")
    assert quality_flags(row, tmp_path)["quality_status"] == "manual_grade_only"


def test_native_import_retries_transient_failure_only(monkeypatch):
    import importlib
    from pathlib import Path
    from types import SimpleNamespace

    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / "scripts"))
    prepare = importlib.import_module("prepare_cangjie_question_bank")
    responses = iter(
        [
            SimpleNamespace(returncode=1, stdout='{"code":503}'),
            SimpleNamespace(returncode=0, stdout='{"stored":"1"}'),
        ]
    )
    monkeypatch.setattr(prepare.subprocess, "run", lambda *a, **kw: next(responses))
    monkeypatch.setattr(prepare.time, "sleep", lambda _: None)
    assert prepare.native({"operation": "import"}) == {"stored": "1"}
    calls = []

    def reject(*a, **kw):
        calls.append(1)
        return SimpleNamespace(returncode=1, stdout='{"code":422}')

    monkeypatch.setattr(prepare.subprocess, "run", reject)
    import pytest

    with pytest.raises(RuntimeError):
        prepare.native({"operation": "import"})
    assert len(calls) == 1


def test_placeholder_choice_is_kept_but_not_practiced(tmp_path):
    from app.services.public_question_sources import question

    row = question(
        "placeholder",
        "all",
        "数学",
        "初中",
        "计算结果",
        "A",
        [{"key": "A", "text": "请在答题卡作答"}],
        metadata={"answer_review": True},
    )
    assert quality_flags(row, tmp_path)["quality_status"] == "manual_grade_only"


def test_incomplete_choice_is_not_auto_graded(tmp_path):
    from app.services.public_question_sources import question

    row = question(
        "incomplete", "all", "数学", "高中", "选择正确答案", "A", [{"key": "A", "text": "残缺的选项"}]
    )
    assert not quality_flags(row, tmp_path)["usable_for_practice"]


def test_gaokao_physics_multiselect_keeps_all_correct_options(tmp_path):
    folder = tmp_path / "Data/Objective_Questions"
    folder.mkdir(parents=True)
    (folder / "2010-2022_Physics_MCQs.json").write_text(
        json.dumps(
            {"example": [{"index": 0, "question": "选择正确说法 A. 甲 B. 乙 C. 丙 D. 丁", "answer": ["AC"]}]}
        )
    )
    row = next(iter_gaokao(tmp_path))
    assert row.question_type == "多项选择题"
    assert row.answer == "AC"
