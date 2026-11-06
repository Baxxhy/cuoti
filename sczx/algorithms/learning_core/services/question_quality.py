from __future__ import annotations

import re
from pathlib import Path
from typing import Any

SUBJECTIVE_TYPES = ("主观", "作文", "论述", "简答", "材料", "开放", "写作", "翻译")


def answer_present(answer: Any) -> bool:
    if answer is None:
        return False
    if isinstance(answer, str):
        return bool(answer.strip()) and answer.strip().lower() not in {"null", "none", "unknown"}
    if isinstance(answer, (list, dict)):
        return bool(answer)
    return True




def selection_answer_verified(answer: Any, options: list[dict[str, str]]) -> bool:
    if len(options) < 2 or not answer_present(answer):
        return False
    valid = {str(item.get("key", "")).upper() for item in options}
    values = answer if isinstance(answer, list) else re.findall(r"[A-Z]", str(answer).upper())
    return bool(values) and all(str(value).upper() in valid for value in values)


def can_auto_grade(question_type: str, answer: Any, options: list[dict[str, str]]) -> bool:
    if not answer_present(answer):
        return False
    if options:
        return selection_answer_verified(answer, options)
    if any(label in question_type for label in SUBJECTIVE_TYPES):
        return False
    if isinstance(answer, (dict, list)):
        return False
    return len(str(answer).strip()) <= 200


def missing_images(image_paths: list[str], project_root: Path) -> list[str]:
    return [path for path in image_paths if not (project_root / path).is_file()]


def quality_flags(question: Any, project_root: Path) -> dict[str, Any]:
    has_answer = answer_present(question.answer)
    has_solution = bool(str(question.solution or "").strip())
    missing = missing_images(question.image_paths or [], project_root)
    answer_verified = selection_answer_verified(question.answer, question.options or [])
    auto_grade = can_auto_grade(question.question_type, question.answer, question.options or [])
    metadata = getattr(question, "source_metadata", None) or {}
    public_markers = str(question.question_text or "").count("<ImageHere>") + sum(
        str(option.get("text") or "").count("<ImageHere>") for option in (question.options or [])
    )
    markers = (
        public_markers
        + str(question.answer or "").count("<ImageHere>")
        + str(question.solution or "").count("<ImageHere>")
    )
    image_count = len(question.image_paths or [])
    image_layout_review = (
        markers != image_count
        and (markers > 0 or bool(metadata.get("has_visual")))
    )
    review = metadata.get("format_review", {}) if isinstance(metadata, dict) else {}
    malformed = (
        isinstance(review, dict)
        and bool(review.get("fields"))
        and review.get("content_hash") == getattr(question, "content_hash", None)
    )
    if not str(question.question_text or "").strip():
        status = "invalid"
    elif metadata.get("duplicate_of"):
        status = "duplicate"
    elif malformed:
        status = "format_review"
    elif missing or metadata.get("asset_review") or image_layout_review:
        status = "missing_asset"
    elif not has_answer:
        status = "no_answer"
    elif not auto_grade or metadata.get("answer_review"):
        status = "manual_grade_only"
    else:
        status = "usable"
    return {
        "has_answer": has_answer,
        "has_solution": has_solution,
        "answer_verified": answer_verified,
        "quality_status": status,
        "usable_for_practice": status == "usable",
        "usable_for_auto_grade": status == "usable" and auto_grade,
        "image_missing": len(missing),
    }
