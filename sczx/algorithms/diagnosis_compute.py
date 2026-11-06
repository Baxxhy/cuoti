"""Database-free diagnosis and counterfactual computation over supplied step records."""

from __future__ import annotations

import asyncio
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from diagnosis_alignment import polynomial_alignment, verify_polynomial_repair
from error_diagnosis import assess_diagnosis
from grounded_knowledge import build_knowledge_evidence
from inequality_compute import inequality_alignment, verify_inequality_repair
from learning_core.providers.api_pool import ApiPoolProvider
from learning_core.services.ai_pipeline import diagnose_steps
from learning_core.services.counterfactual import validate_first_error_counterfactual
from learning_core.services.diagnosis import align_steps


class StepRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1, max_length=36)
    text: str = Field(max_length=12000)


async def compute_diagnosis(
    provider: ApiPoolProvider,
    *,
    text: str,
    subject: str,
    question_type: str,
    student_answer: str | None,
    options: list[dict[str, str]],
    references: list[StepRecord],
    students: list[StepRecord],
    images: list[Path],
    counterfactual_only: bool = False,
    knowledge_cards: list[dict] | None = None,
    grade: str = "",
) -> dict:
    alignment = await asyncio.to_thread(
        align_steps, references, students, subject, text
    )
    checked = None
    inequality_checked = None
    if subject == "数学":
        checked = await asyncio.to_thread(
            polynomial_alignment, text, references, students, student_answer
        )
        if checked is not None:
            alignment = checked[0]
        else:
            inequality_checked = await asyncio.to_thread(
                inequality_alignment, text, references, students, student_answer
            )
            if inequality_checked is not None:
                alignment = inequality_checked[0]
    if not students:
        for entry in alignment:
            entry["is_first_error"] = False
            entry["propagated"] = False
    diagnosis = None
    if not counterfactual_only or (checked is None and inequality_checked is None):
        diagnosis = await diagnose_steps(
            provider,
            text,
            [step.text for step in references],
            [step.text for step in students],
            subject,
            question_type,
            images,
            student_answer,
            options,
        )
        if checked is None and inequality_checked is None:
            # A reference explanation is not a required sequence of actions.
            # Model-reviewed rows remain hypotheses, never symbolic proof or
            # invented reference-step links based on the same array position.
            index = diagnosis.first_error_step
            correct = diagnosis.error_type in {"exact", "equivalent"}
            alignment = [
                {
                    "index": i,
                    "reference_step_id": None,
                    "student_step_id": step.id,
                    "reference_text": "",
                    "student_text": step.text,
                    "alignment": diagnosis.error_type
                    if i == index
                    else "exact"
                    if correct
                    else "unknown",
                    "equivalent": False,
                    "uses_condition": False,
                    "math_valid": False,
                    "is_first_error": i == index,
                    "propagated": False,
                    "verification_scope": "model_review_requires_confirmation",
                }
                for i, step in enumerate(students)
            ]
        first = next((entry for entry in alignment if entry["is_first_error"]), None)
        if first and students:
            diagnosis.first_error_step = first["index"]
            diagnosis.first_error_text = first["student_text"] or "缺少对应步骤"
            diagnosis.error_type = first["alignment"]
            diagnosis.error_location = f"学生路径第 {first['index'] + 1} 步"
        if not students or first is None:
            # Neither absent work nor a matching path establishes an erroneous step.
            diagnosis.first_error_step = None
            diagnosis.first_error_text = ""
            diagnosis.error_location = ""
        if (checked is not None and checked[1]) or (
            inequality_checked is not None and inequality_checked[1]
        ):
            diagnosis.error_type = "exact"
            diagnosis.root_misconception = ""
            diagnosis.missing_prerequisites = []
        diagnosis.recommended_strategy = diagnosis.recommended_strategy or (
            diagnosis.strategy_candidates[0]
            if diagnosis.strategy_candidates
            else "路径对比与针对性提示"
        )
    counterfactual = await validate_first_error_counterfactual(
        provider,
        question_text=text,
        subject=subject,
        alignment=alignment if students else [],
    )
    if checked is not None:
        counterfactual = await asyncio.to_thread(
            verify_polynomial_repair,
            text,
            references,
            students,
            alignment,
            counterfactual,
        )
    elif inequality_checked is not None:
        counterfactual = await asyncio.to_thread(
            verify_inequality_repair,
            text,
            references,
            students,
            alignment,
            counterfactual,
        )
    elif counterfactual.get("status") != "not_needed":
        counterfactual.update(
            root_cause_confirmed=False,
            status="inconclusive",
            recovered_steps=0,
            verification_method="qwen_proposal_requires_review",
            conclusion="这是根据原题与实际作答提出的修复建议，尚未通过本地规则验证，请核对条件和每一步推理。",
        )
    result = {
        "alignment": alignment,
        "counterfactual": counterfactual,
        "logical_model": "Qwen",
        "evidence_diagnosis": assess_diagnosis(
            students=students,
            references=references,
            alignment=alignment,
            diagnosis=diagnosis,
            student_answer=student_answer,
            knowledge=build_knowledge_evidence(knowledge_cards or [], subject, grade),
        ).model_dump(mode="json"),
    }
    if diagnosis is not None and not counterfactual_only:
        result["diagnosis"] = diagnosis.model_dump(mode="json")
    return result
