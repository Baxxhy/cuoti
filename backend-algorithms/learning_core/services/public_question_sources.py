"""Offline adapters. Preserve source answers, passage context and stable identities."""

from __future__ import annotations

import json
import re
import tarfile
from pathlib import Path

from learning_core.services.question_bank_import import (
    SUBJECTS,
    NormalizedDatasetQuestion,
    _title,
    has_multiple_choice_answers,
    normalize_choice_options,
)


def question(
    identity,
    split,
    subject,
    band,
    text,
    answer,
    options=None,
    solution="",
    kind="单项选择题",
    metadata=None,
    topics=None,
    difficulty="",
):
    return NormalizedDatasetQuestion(
        source_item_id=identity,
        split=split,
        subject=subject,
        grade=band,
        grade_band=band,
        title=_title(text),
        question_text=text,
        question_type=kind,
        options=options or [],
        answer=answer,
        solution=solution,
        knowledge_points=topics or [],
        image_paths=[],
        difficulty=difficulty,
        source_metadata=metadata or {},
    ).finalize()


def iter_race(archive: Path):
    with tarfile.open(archive) as tar:
        for member in tar:
            if not member.isfile() or not member.name.endswith(".txt"):
                continue
            stream = tar.extractfile(member)
            row = json.load(stream)
            parts = Path(member.name).parts
            band = "初中" if "middle" in parts else "高中"
            split = next((x for x in parts if x in {"train", "dev", "test"}), "all")
            if not len(row["questions"]) == len(row["options"]) == len(row["answers"]):
                raise ValueError("RACE question/option/answer alignment mismatch")
            for index, (prompt, choices, answer) in enumerate(
                zip(row["questions"], row["options"], row["answers"], strict=True)
            ):
                yield question(
                    f"{split}:{parts[-2]}:{Path(member.name).stem}:{index}",
                    split,
                    "英语",
                    band,
                    row["article"].strip() + "\n\n" + prompt.strip(),
                    answer,
                    [{"key": chr(65 + i), "text": value} for i, value in enumerate(choices)],
                    metadata={
                        "passage_id": row.get("id", member.name),
                        "question_index": index,
                        "usage": "non-commercial-research-only",
                    },
                    topics=["阅读理解"],
                )


def iter_tal(directory: Path):
    # English is a translation of the same items; keep the complete raw archive,
    # but publish only Chinese questions to avoid doubling the practice pool.
    for path in sorted((directory / "ch_single_choice_constructed_5K").glob("*.jsonl")):
        for line in path.read_text().splitlines():
            row = json.loads(line)
            origins = " ".join(row.get("competition_source_list", []))
            band = (
                "高中"
                if re.search(r"高中|高[一二三]", origins)
                else "初中"
                if re.search(r"初中|初[一二三]|[七八九]年级", origins)
                else "小学"
                if re.search(r"小学|小升初|[一二三四五六]年级", origins)
                else "拓展"
            )
            options = [
                {"key": group[0]["aoVal"], "text": "\n".join(x["content"] for x in group)}
                for group in row["answer_option_list"]
            ]
            yield question(
                str(row["queId"]),
                "test" if "test" in path.name else "train",
                "数学",
                band,
                row["problem"],
                row["answer_value"],
                options,
                "\n".join(row.get("answer_analysis", [])),
                metadata={
                    "origins": row.get("competition_source_list", []),
                    "qid": row["qid"],
                    "level_inferred_from_origin": band != "拓展",
                    **({"answer_review": True} if len(options) < 2 else {}),
                },
                topics=row.get("knowledge_point_routes", []),
                difficulty=str(row.get("difficulty", "")),
            )


def iter_gaokao(directory: Path):
    for path in sorted((directory / "Data").rglob("*.json")):
        rows = json.loads(path.read_text())["example"]
        subject_key = path.stem.split("_")[1]
        subject = {"English": "英语", "Political": "思想政治"}.get(
            subject_key, SUBJECTS.get(subject_key, subject_key)
        )
        for index, row in enumerate(rows):
            text = row["question"].strip()
            answer = row.get("answer", "")
            options = []
            kind = "主观题"
            # Composite reading/cloze rows keep their original answer order. Never
            # reinterpret multiple subquestion answers as a multi-select answer.
            if "Objective_Questions" in path.parts and isinstance(answer, list) and len(answer) == 1:
                markers = list(re.finditer(r"(?<![A-Za-z])([A-D])[.．、]\s*", text))
                if [m.group(1) for m in markers] == list("ABCD"):
                    options = normalize_choice_options(text[markers[0].start() :])
                    if len(options) == 4:
                        text = text[: markers[0].start()].strip()
                        answer = answer[0]
                        kind = "多项选择题" if has_multiple_choice_answers(answer) else "单项选择题"
            elif "Fill-in-the-Blank" in path.name:
                kind = "填空题"
            metadata = {
                "year": row.get("year"),
                "paper": row.get("category"),
                "score": row.get("score"),
                "file": path.name,
            }
            # These text-only exports sometimes reference diagrams absent from the
            # release. Retain the row for review instead of silently losing them.
            if re.search(r"如图|下图|图中|图示|图所示|shown in (?:the )?(?:figure|diagram)", text, re.I):
                metadata["asset_review"] = True
            yield question(
                f"{path.stem}:{row.get('index', index)}",
                "all",
                subject,
                "高中",
                text,
                answer,
                options,
                row.get("analysis") or "",
                kind,
                metadata,
            )
