from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterator
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

SUBJECTS = {
    "Math": "数学",
    "Chinese": "语文",
    "Physics": "物理",
    "Chemistry": "化学",
    "Biology": "生物",
    "History": "历史",
    "Geography": "地理",
    "Politics": "思想政治",
    "math": "数学",
    "physics": "物理",
    "chemistry": "化学",
    "biology": "生物",
    "history": "历史",
    "geography": "地理",
    "politics": "思想政治",
}


@dataclass(slots=True)
class NormalizedDatasetQuestion:
    source_item_id: str
    split: str
    subject: str
    grade: str
    grade_band: str
    title: str
    question_text: str
    question_type: str
    options: list[dict[str, str]]
    answer: Any
    solution: str
    knowledge_points: list[str]
    image_paths: list[str]
    difficulty: str
    source_metadata: dict[str, Any]
    content_hash: str = ""

    def finalize(self) -> "NormalizedDatasetQuestion":
        payload = asdict(self)
        payload.pop("content_hash", None)
        self.content_hash = hashlib.sha256(
            json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()
        return self


def _title(text: str) -> str:
    clean = re.sub(r"\s+", " ", text).strip()
    return clean[:80] + ("…" if len(clean) > 80 else "")


OPTION_MARKER = re.compile(r"([A-H])[ \t]*[\.、．]\s*")


def _split_marked_options(value: str) -> list[dict[str, str]]:
    candidates = list(OPTION_MARKER.finditer(value))
    # Recover a missing A marker only when B/C/D follow in their complete order
    # and there is a non-empty first option. Do not invent missing option text.
    if [m.group(1) for m in candidates] == ["B", "C", "D"] and value[: candidates[0].start()].strip():
        value = "A. " + value
    markers = []
    expected_key = "A"
    for marker in OPTION_MARKER.finditer(value):
        if marker.group(1) != expected_key:
            continue
        markers.append(marker)
        expected_key = chr(ord(expected_key) + 1)
    rows = []
    for index, marker in enumerate(markers):
        end = markers[index + 1].start() if index + 1 < len(markers) else len(value)
        text = value[marker.end() : end].strip()
        if text:
            rows.append({"key": marker.group(1), "text": text})
    return rows


def normalize_choice_options(value: Any) -> list[dict[str, str]]:
    """Normalize source and legacy DB options, including `A. 1B. 2` rows."""
    if isinstance(value, str):
        return _split_marked_options(value)
    if not isinstance(value, list):
        return []
    rows = []
    for index, raw in enumerate(value):
        if isinstance(raw, dict):
            key = str(raw.get("key") or raw.get("label") or chr(65 + index)).strip().upper()
            text = str(raw.get("text") or raw.get("content") or "").strip()
            parsed = _split_marked_options(f"{key}. {text}")
        else:
            text = str(raw).strip()
            parsed = _split_marked_options(text)
        rows.extend(parsed or ([{"key": chr(65 + index), "text": text}] if text else []))
    return rows


def has_multiple_choice_answers(answer: Any) -> bool:
    text = "、".join(str(x) for x in answer) if isinstance(answer, list) else str(answer)
    return (
        bool(re.fullmatch(r"[A-H](?:[、,，;；/\s]*[A-H])+", text.strip()))
        and len(set(re.findall(r"[A-H]", text))) > 1
    )


def _asset_paths(images: Any, asset_index: dict[str, str]) -> list[str]:
    if not images:
        return []
    if isinstance(images, str):
        images = [images]
    return [asset_index.get(Path(str(item)).name, str(item)) for item in images]


def iter_cmm_math(
    path: Path, asset_index: dict[str, str] | None = None, *, include_primary: bool = False
) -> Iterator[NormalizedDatasetQuestion]:
    assets = asset_index or {}
    with path.open(encoding="utf-8") as source:
        for line in source:
            row = json.loads(line)
            grade = str(row.get("level", ""))
            if not include_primary and not (
                grade.startswith("七")
                or grade.startswith("八")
                or grade.startswith("九")
                or grade.startswith("高")
            ):
                continue
            choices = normalize_choice_options(row.get("options"))
            question_type = (
                ("多项选择题" if has_multiple_choice_answers(row.get("answer", "")) else "选择题")
                if choices
                else "解答题"
            )
            solution = str(row.get("analysis") or row.get("solution") or "")
            if solution.lower() == "null":
                solution = ""
            question = str(row.get("question", "")).strip()
            yield NormalizedDatasetQuestion(
                source_item_id=str(row["id"]),
                split="all",
                subject="数学",
                grade=grade,
                grade_band="初中" if grade[0] in "七八九" else "高中" if grade.startswith("高") else "小学",
                title=_title(question),
                question_text=question,
                question_type=question_type,
                options=choices,
                answer=row.get("answer", ""),
                solution=solution,
                knowledge_points=[str(row.get("subject", "数学"))],
                image_paths=_asset_paths(row.get("image"), assets),
                difficulty="",
                source_metadata={
                    "raw_subject": row.get("subject", ""),
                    "has_visual": bool(row.get("image")),
                    **(
                        {"answer_review": True, "raw_options": row["options"]}
                        if row.get("options")
                        and (not choices or any(OPTION_MARKER.search(option["text"]) for option in choices))
                        else {}
                    ),
                },
            ).finalize()




def iter_cmmu(
    directory: Path, asset_index: dict[str, str] | None = None, *, include_primary: bool = False
) -> Iterator[NormalizedDatasetQuestion]:
    assets = asset_index or {}
    for path in sorted(directory.glob("*.jsonl")):
        with path.open(encoding="utf-8") as source:
            for line in source:
                row = json.loads(line)
                raw_band = str(row.get("grade_band", ""))
                if raw_band not in ({"middle", "high", "primary"} if include_primary else {"middle", "high"}):
                    continue
                question = str(row.get("question_info", "")).strip()
                sub_questions = [str(item) for item in (row.get("sub_questions") or [])]
                if sub_questions:
                    question = (
                        question
                        + "\n"
                        + "\n".join(f"{index + 1}. {item}" for index, item in enumerate(sub_questions))
                    )
                yield NormalizedDatasetQuestion(
                    source_item_id=str(row["id"]),
                    split=str(row.get("split", "val")),
                    subject=SUBJECTS.get(str(row.get("subject", "")), str(row.get("subject", ""))),
                    grade={"middle": "初中", "high": "高中", "primary": "小学"}[raw_band],
                    grade_band={"middle": "初中", "high": "高中", "primary": "小学"}[raw_band],
                    title=_title(question),
                    question_text=question,
                    question_type=str(row.get("type", "综合题")),
                    options=normalize_choice_options(row.get("options")),
                    answer=row.get("answer", ""),
                    solution=str(row.get("solution_info") or ""),
                    knowledge_points=[],
                    image_paths=_asset_paths(row.get("images") or row.get("image"), assets),
                    difficulty=str(row.get("difficulty", "")),
                    source_metadata={"sub_questions": sub_questions, "raw_subject": row.get("subject", "")},
                ).finalize()


def build_asset_index(root: Path, project_root: Path) -> dict[str, str]:
    if not root.exists():
        return {}
    return {path.name: str(path.relative_to(project_root)) for path in root.rglob("*") if path.is_file()}
