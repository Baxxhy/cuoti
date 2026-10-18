from __future__ import annotations

import pytest

from app.main import apply_ocr_edits
from app.models import Question, StudentStep


class _EmptyScalars:
    def __iter__(self):
        return iter(())

    def first(self):
        return None


class _FakeDb:
    def __init__(self) -> None:
        self.added: list[object] = []

    async def scalars(self, _query):
        return _EmptyScalars()

    async def execute(self, _query):
        return None

    def add(self, value: object) -> None:
        self.added.append(value)

    async def flush(self) -> None:
        for index, value in enumerate(self.added):
            if getattr(value, "id", None) is None:
                value.id = f"generated-{index}"


@pytest.mark.asyncio
async def test_choice_letter_recognized_as_step_is_promoted_to_student_answer():
    question = Question(
        id="question-1",
        user_id="user-1",
        question_type="choice",
        student_answer=None,
    )
    db = _FakeDb()

    await apply_ocr_edits(
        question,
        {
            "student_answer": "",
            "student_steps": [{"text": "c", "source": "qwen_vision"}],
        },
        db,
    )

    assert question.student_answer == "C"
    assert not any(isinstance(value, StudentStep) for value in db.added)
