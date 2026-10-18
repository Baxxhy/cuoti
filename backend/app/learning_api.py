from collections.abc import Callable
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, StringConstraints, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import Question, StudentStep, StudentWork, User
from app.services.learning_journey import get_learning_journey

NonemptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=12000)]


class ManualOption(BaseModel):
    label: Annotated[str, StringConstraints(pattern=r"^[A-H]$")]
    text: NonemptyText


class ManualQuestion(BaseModel):
    question_text: NonemptyText
    question_type: Literal["综合题", "单选题", "多选题"] = "综合题"
    options: list[ManualOption] = Field(default_factory=list, max_length=8)
    student_answer: str = Field(default="", max_length=6000)
    subject: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=30)] = "数学"
    grade: str | None = Field(default=None, max_length=30)
    student_steps: list[NonemptyText] = Field(default_factory=list, max_length=30)

    @model_validator(mode="after")
    def validate_options(self):
        if self.question_type != "综合题" and len(self.options) < 2:
            raise ValueError("选择题至少需要两个选项")
        if self.question_type == "综合题" and self.options:
            raise ValueError("有选项的题目请选择单选题或多选题")
        if len({option.label for option in self.options}) != len(self.options):
            raise ValueError("选项标记不能重复")
        return self


def create_learning_router(current_user: Callable) -> APIRouter:
    router = APIRouter(prefix="/api/v1", tags=["learning"])

    @router.post("/questions/manual")
    async def create_manual_question(
        payload: ManualQuestion, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
    ):
        if user.role != "student":
            raise HTTPException(403, "请使用学生账号记录错题")
        question = Question(
            user_id=user.id,
            subject=payload.subject,
            grade=payload.grade,
            title=payload.question_text[:80],
            question_text=payload.question_text,
            student_answer=payload.student_answer.strip() or None,
            question_type=payload.question_type,
            options=[item.model_dump() for item in payload.options],
            status="confirmed",
            confirmed=True,
        )
        db.add(question)
        await db.flush()
        work = StudentWork(question_id=question.id, user_id=user.id, answer=payload.student_answer.strip())
        db.add(work)
        await db.flush()
        for index, value in enumerate(payload.student_steps):
            db.add(
                StudentStep(
                    work_id=work.id,
                    step_index=index,
                    text=value,
                    raw_text=value,
                    normalized_text=value,
                    formula=value if "=" in value else "",
                    source="user",
                    user_confirmed=True,
                    confidence=1.0,
                )
            )
        await db.commit()
        return {"success": True, "data": {"id": question.id, "status": question.status}, "error": None}

    @router.get("/questions/{question_id}/journey")
    async def journey(
        question_id: str, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
    ):
        question = await db.get(Question, question_id)
        if question is None or question.user_id != user.id or question.status == "archived":
            raise HTTPException(404, "题目不存在")
        return {"success": True, "data": await get_learning_journey(db, question), "error": None}

    return router
