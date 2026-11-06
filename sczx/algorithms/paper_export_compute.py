"""Document rendering only. Business selection, ownership and storage stay in Cangjie."""

import base64
import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Literal

from pydantic import BaseModel, Field, JsonValue

from learning_core.services.export import build_excel, build_pdf


class ExportQuestion(BaseModel):
    question_text: str = Field(max_length=12000)
    answer: str = Field(default="", max_length=12000)
    explanation: str = Field(default="", max_length=1200000)
    subject: str = Field(default="", max_length=30)
    score: int = Field(default=10, ge=1, le=100)
    formula: str = Field(default="", max_length=120000)
    options: list[dict[str, JsonValue]] = Field(default_factory=list, max_length=26)
    misconception: str = Field(default="", max_length=12000)
    figure_images: list[str] = Field(default_factory=list, max_length=100)


def render_paper(
    title: str,
    kind: Literal["question", "answer", "excel"],
    questions: list[ExportQuestion],
):
    with TemporaryDirectory(prefix="zhiwei-paper-render-") as directory:
        root = Path(directory)
        rows = []
        for index, question in enumerate(questions):
            item = question.model_dump(exclude={"figure_images"})
            item["figure_paths"] = []
            for number, encoded in enumerate(question.figure_images):
                raw = base64.b64decode(encoded, validate=True)
                if len(raw) > 15 * 1024 * 1024:
                    raise ValueError("figure too large")
                path = root / f"figure-{index}-{number}.jpg"
                path.write_bytes(raw)
                item["figure_paths"].append(str(path))
            rows.append(item)
        target = root / ("paper.xlsx" if kind == "excel" else "paper.pdf")
        if kind == "excel":
            build_excel(
                target,
                [
                    {
                        "question": q["question_text"],
                        "subject": q["subject"],
                        "misconception": q["misconception"],
                        "mastery": "",
                        "review": "",
                    }
                    for q in rows
                ],
            )
        else:
            build_pdf(
                target,
                title + ("-答案解析" if kind == "answer" else ""),
                rows,
                answers=kind == "answer",
            )
        data = target.read_bytes()
        return {
            "file_base64": base64.b64encode(data).decode(),
            "sha256": hashlib.sha256(data).hexdigest(),
        }
