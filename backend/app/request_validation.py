"""Small request contracts for account and paper mutations."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import HTTPException
from pydantic import BaseModel, Field, StringConstraints, ValidationError, model_validator

ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
Email = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, min_length=3, max_length=190, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
    ),
]
Password = Annotated[str, StringConstraints(min_length=1, max_length=256)]
ResourceId = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=36)]


class RegisterRequest(BaseModel):
    email: Email
    password: Password
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)] = "智维同学"
    grade: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=30)] = "初二"


class LoginRequest(BaseModel):
    email: Email
    password: Password


class PaperEntry(BaseModel):
    question_id: ResourceId
    score: int = Field(default=10, ge=1, le=100)


class PaperFilters(BaseModel):
    subject: str = Field(default="", max_length=30)
    knowledge_point: str = Field(default="", max_length=100)
    error_type: str = Field(default="", max_length=100)
    mastery_min: float = Field(default=0, ge=0, le=1)
    mastery_max: float = Field(default=1, ge=0, le=1)
    due_review: bool = False

    @model_validator(mode="after")
    def validate_range(self):
        if self.mastery_min > self.mastery_max:
            raise ValueError("最低掌握度不能超过最高掌握度")
        return self


class PaperCreateRequest(BaseModel):
    limit: int = Field(default=10, ge=1, le=200)
    default_score: int = Field(default=10, ge=1, le=100)
    title: ShortText = "专项练习"
    question_ids: list[ResourceId] = Field(default_factory=list, max_length=200)
    items: list[PaperEntry] = Field(default_factory=list, max_length=200)
    filters: PaperFilters = Field(default_factory=PaperFilters)


class PaperUpdateRequest(BaseModel):
    title: ShortText = "专项练习"
    items: list[PaperEntry] = Field(default_factory=list, max_length=200)
    filters: PaperFilters = Field(default_factory=PaperFilters)


def validated_payload(model: type[BaseModel], payload: Any) -> dict[str, Any]:
    try:
        return model.model_validate(payload).model_dump(exclude_unset=True)
    except ValidationError as exc:
        # Exclude input values (especially account passwords) from error responses.
        raise HTTPException(
            422,
            detail=[
                {"loc": ["body", *error["loc"]], "msg": error["msg"], "type": error["type"]}
                for error in exc.errors(include_input=False, include_url=False)
            ],
        ) from exc
