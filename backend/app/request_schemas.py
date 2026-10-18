"""Validation for editable recognition text and crop geometry."""

from typing import Annotated, Any

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError, field_validator

ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=30)]
AnswerText = Annotated[str, StringConstraints(max_length=12000)]


class RecognitionStepEdit(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    text: AnswerText = ""
    raw_text: AnswerText = ""
    normalized_text: AnswerText = ""
    formula: AnswerText = ""
    confidence: float = Field(default=1, ge=0, le=1)
    source: str = Field(default="user", max_length=50)
    bbox: list[float] = Field(default_factory=list, max_length=4)


class TeacherMarkEdit(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    comment: AnswerText = ""
    mark_type: str = Field(default="comment", max_length=50)
    confidence: float = Field(default=1, ge=0, le=1)
    bbox: list[float] = Field(default_factory=list, max_length=4)


class ChoiceOptionEdit(BaseModel):
    label: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=8)]
    text: AnswerText


class QuestionEditRequest(BaseModel):
    question_text: AnswerText = ""
    student_answer: AnswerText | None = None
    subject: ShortText = "数学"
    grade: str | None = Field(default=None, max_length=30)
    question_type: str = Field(default="综合题", min_length=1, max_length=50)
    formulas: list[AnswerText] = Field(default_factory=list, max_length=100)
    options: list[ChoiceOptionEdit] = Field(default_factory=list, max_length=26)
    knowledge_points: list[ShortText] = Field(default_factory=list, max_length=50)
    student_steps: list[RecognitionStepEdit | AnswerText] = Field(default_factory=list, max_length=100)
    teacher_marks: list[TeacherMarkEdit | AnswerText] = Field(default_factory=list, max_length=100)
    title: str = Field(default="", max_length=255)
    favorite: bool = False
    tags: list[ShortText] = Field(default_factory=list, max_length=50)


class CropRequest(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    box: list[float] = Field(min_length=4, max_length=4)

    @field_validator("box")
    @classmethod
    def valid_box(cls, box: list[float]) -> list[float]:
        x, y, width, height = box
        if not (0 <= x < 1 and 0 <= y < 1 and 0 < width <= 1 and 0 < height <= 1):
            raise ValueError("裁剪范围必须在图片内且有非零面积")
        if x + width > 1.000001 or y + height > 1.000001:
            raise ValueError("裁剪范围超出图片")
        return box


def validated_body(model: type[BaseModel], payload: Any) -> dict[str, Any]:
    try:
        return model.model_validate(payload).model_dump(exclude_unset=True)
    except ValidationError as exc:
        message = (
            "裁剪范围无效，请重新框选题目"
            if model is CropRequest
            else "输入格式不正确，请检查题目文字、选项、步骤和置信度"
        )
        raise HTTPException(422, message) from exc
