"""Keep complete formula source in display summaries and recover old auto-titles."""
from typing import Any


def academic_summary(value: str, limit: int) -> str:
    return value if "$" in value or "\\" in value else value[:limit]


def question_display_title(title: str, text: str) -> str:
    if title and title != text and text.startswith(title) and ("$" in title or "\\" in title):
        return text
    return title


def repair_question_title(row: dict[str, Any]) -> dict[str, Any]:
    if isinstance(row.get("question_text"), str) and isinstance(row.get("title"), str):
        row["title"] = question_display_title(row["title"], row["question_text"])
    return row
