"""ECED: rank existing diagnosis hypotheses against supplied source records.

Scores are configurable evidence rankings, not calibrated probabilities. This
module never calls a model or treats an unverified model assertion as a rule.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from grounded_knowledge import KnowledgeEvidence


class EvidenceWeights(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    step: float = Field(default=1, ge=0, le=10)
    rule: float = Field(default=2, ge=0, le=10)
    reference: float = Field(default=1, ge=0, le=10)
    knowledge: float = Field(default=0.5, ge=0, le=10)
    contradiction: float = Field(default=4, ge=0, le=10)


class DiagnosisEvidence(BaseModel):
    source: Literal[
        "student_step", "student_answer", "reference_step", "rule", "knowledge"
    ]
    source_id: str
    text: str
    verified: bool = False


class DiagnosisCandidate(BaseModel):
    first_error_step: int = Field(ge=0)
    error_type: str
    reason: str
    evidence: list[DiagnosisEvidence]
    score: float
    verified: bool


class EvidenceDiagnosis(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    algorithm: Literal["eced-v1"] = "eced-v1"
    first_error_step: int | None = None
    error_type: str = "unknown"
    reason: str
    evidence: list[DiagnosisEvidence] = Field(default_factory=list)
    confidence_level: Literal["verified", "needs_confirmation", "insufficient"]
    verified: bool = False
    next_action: Literal["repair", "retry", "confirm_work", "confirm_question"]
    question: str = ""
    candidates: list[DiagnosisCandidate] = Field(default_factory=list)
    score_kind: Literal["uncalibrated_evidence_score"] = "uncalibrated_evidence_score"


def assess_diagnosis(
    *,
    students,
    references,
    alignment,
    diagnosis=None,
    student_answer: str | None = None,
    knowledge: list[KnowledgeEvidence] | None = None,
    weights: EvidenceWeights | None = None,
) -> EvidenceDiagnosis:
    """Only actual records and independently checked rows can supply evidence.

    A model's proposed index, reference ID or confidence alone cannot establish
    an error. Exact/equivalent rows cannot be ranked as erroneous candidates.
    """
    weights = weights or EvidenceWeights()
    student_map = {step.id: (i, step.text) for i, step in enumerate(students)}
    reference_map = {step.id: step.text for step in references}
    hypotheses = []
    for row in alignment:
        source = student_map.get(row.get("student_step_id"))
        if source is None or not row.get("is_first_error"):
            continue
        index, text = source
        if row.get("student_text") != text or row.get("index") != index:
            continue
        if row.get("alignment") in {"exact", "equivalent", "branch_solution"}:
            continue
        scope = row.get("verification_scope", "")
        rule_verified = (
            scope
            in {
                "different_roots",
                "different_solution_set",
            }
            and row.get("math_valid") is False
        )
        # Explanatory prose from the model is still a hypothesis, even when the
        # *location* was established symbolically. State only the checked fact.
        reason = (
            "这一步与原题的解不等价。"
            if rule_verified
            else "这一步可能有误，需要核对你的计算过程。"
        )
        evidence = [
            DiagnosisEvidence(
                source="student_step", source_id=row["student_step_id"], text=text
            )
        ]
        score = weights.step
        conflict = row.get("math_valid") is True or row.get("equivalent") is True
        if conflict:
            score -= weights.contradiction
            rule_verified = False
            reason = "步骤核验结果存在矛盾，请先核对原题和这一步的依据。"
        reference_id = row.get("reference_step_id")
        if (
            reference_id in reference_map
            and row.get("reference_text") == reference_map[reference_id]
        ):
            evidence.append(
                DiagnosisEvidence(
                    source="reference_step",
                    source_id=reference_id,
                    text=reference_map[reference_id],
                )
            )
            score += weights.reference
        proposal = str(getattr(diagnosis, "root_misconception", "") or "")
        for raw in knowledge or []:
            card = KnowledgeEvidence.model_validate(raw)
            if card.name in proposal or card.code in proposal:
                # Retrieval establishes a source association, not a proof of
                # the student's mental cause. Keep it explicitly unverified.
                evidence.append(
                    DiagnosisEvidence(
                        source="knowledge",
                        source_id=card.code,
                        text=card.definition,
                        verified=False,
                    )
                )
                score += weights.knowledge
                break
        if rule_verified:
            evidence.append(
                DiagnosisEvidence(
                    source="rule",
                    source_id=scope,
                    text="比较原题与该步骤的实数解集",
                    verified=True,
                )
            )
            score += weights.rule
        hypotheses.append(
            DiagnosisCandidate(
                first_error_step=index,
                error_type=str(row.get("alignment") or "unknown"),
                reason=reason,
                evidence=evidence,
                score=score,
                verified=rule_verified,
            )
        )
    hypotheses.sort(key=lambda item: (-item.score, item.first_error_step))
    if hypotheses:
        best = hypotheses[0]
        # A later checked error does not prove it was the first one: every
        # preceding row must itself have been verified before naming a first.
        preceding = [
            row
            for row in alignment
            if isinstance(row.get("index"), int)
            and row["index"] < best.first_error_step
        ]
        prefix_verified = len(preceding) == best.first_error_step and all(
            row.get("math_valid") is True
            and row.get("verification_scope")
            in {
                "original_equation_real_roots",
                "branch_root",
                "boundary_zeros",
                "necessary_condition",
                "original_inequality_real_solution_set",
            }
            for row in preceding
        )
        verified = best.verified and prefix_verified
        return EvidenceDiagnosis(
            first_error_step=best.first_error_step,
            error_type=best.error_type,
            reason=best.reason,
            evidence=best.evidence,
            confidence_level="verified" if verified else "needs_confirmation",
            verified=verified,
            next_action="repair" if verified else "confirm_work",
            question=""
            if verified
            else f"请核对第 {best.first_error_step + 1} 步，补充这一步的计算依据。",
            candidates=hypotheses[:3],
        )
    checked_correct = (
        bool(students)
        and len(alignment) == len(students)
        and all(
            row.get("math_valid") is True and not row.get("is_first_error")
            for row in alignment
        )
    )
    if checked_correct:
        return EvidenceDiagnosis(
            reason="当前步骤在已支持的规则范围内核验通过。",
            error_type="exact",
            confidence_level="verified",
            verified=True,
            next_action="retry",
        )
    # An answer is real work even when there is no written solution path.
    # Explain the answer-level hypothesis without inventing a step or proof.
    if str(student_answer or "").strip() or any(step.text.strip() for step in students):
        error_type = str(getattr(diagnosis, "error_type", "unknown") or "unknown")
        correct = error_type in {"exact", "equivalent"}
        reason = str(getattr(diagnosis, "root_misconception", "") or "").strip()
        if not reason or any(
            word in reason for word in ("无法分析", "无法确定", "不足以", "证据不足")
        ):
            reason = (
                "本次作答未发现错误，可以对照参考解析检查判断依据。"
                if correct
                else (
                    "请对照参考答案，检查本次作答是否用全题目条件，以及结论是否符合题意。"
                )
            )
        return EvidenceDiagnosis(
            error_type=error_type,
            reason=reason,
            evidence=[
                DiagnosisEvidence(
                    source="student_answer",
                    source_id="student_answer",
                    text=str(student_answer).strip(),
                )
            ]
            if str(student_answer or "").strip()
            else [],
            confidence_level="needs_confirmation",
            next_action="retry" if correct else "repair",
        )
    return EvidenceDiagnosis(
        reason="还没有你的作答，请先完成这道题。",
        confidence_level="insufficient",
        next_action="confirm_work" if students else "confirm_question",
        question="请补充你从哪一步开始不确定，以及对应的计算过程。"
        if students
        else "请确认题目和识别结果，并补充你的原始作答。",
    )
