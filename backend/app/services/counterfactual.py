from __future__ import annotations

import json
import re
from typing import Any

from app.providers.api_pool import ApiPoolProvider, ApiPoolUnavailable
from app.schemas import CounterfactualRepairProposal
from app.services.diagnosis import equation_equivalent


def _same_step(left: str, right: str) -> bool:
    def compact(value: str) -> str:
        # Decimal points, root separators and variable case carry meaning.
        # Formatting equality must not turn 0.2 into 02 or R into r.
        return re.sub(r"\s+", "", value)

    return bool(left and right) and (compact(left) == compact(right) or equation_equivalent(left, right))


def _fallback_proposal(alignment: list[dict[str, Any]], first_index: int) -> CounterfactualRepairProposal:
    repaired: list[str] = []
    for entry in alignment:
        original = str(entry.get("student_text") or "")
        reference = str(entry.get("reference_text") or "")
        repaired.append(
            reference if entry["index"] >= first_index and entry.get("propagated", False) else original
        )
    first = alignment[first_index]
    if first_index < len(repaired):
        repaired[first_index] = str(first.get("reference_text") or repaired[first_index] or "补上该步骤")
    return CounterfactualRepairProposal(
        corrected_first_step=str(first.get("reference_text") or "补上该步骤"),
        repaired_steps=repaired,
        reasoning="仅修正最早出错的一步，并同步修正由它带来的后续结果。",
        confidence=0.7,
    )


async def validate_first_error_counterfactual(
    provider: ApiPoolProvider,
    *,
    question_text: str,
    subject: str,
    alignment: list[dict[str, Any]],
) -> dict[str, Any]:
    """Test whether minimally repairing the suspected first error recovers the solution path."""
    first = next((entry for entry in alignment if entry.get("is_first_error")), None)
    if first is None:
        return {
            "status": "not_needed",
            "root_cause_confirmed": False,
            "conclusion": "现有步骤中没有定位到明确错误，因此无需进行首错反事实验证。",
            "independent_errors": [],
            "repaired_steps": [],
            "verification_method": "local_alignment",
            "confidence": 0.5,
        }
    first_index = int(first["index"])
    context = {
        "question_text": question_text,
        "subject": subject,
        "suspected_first_error_index": first_index,
        "steps": [
            {
                "index": item["index"],
                "reference": item.get("reference_text", ""),
                "student": item.get("student_text", ""),
                "relation": item.get("alignment", ""),
            }
            for item in alignment
        ],
    }
    used_model = True
    try:
        proposal = await provider.generate_structured(
            "请做反事实验证：只把疑似最早错误改成正确的最小一步，并把受它影响的数值或结论同步向后重算；"
            "学生原本正确且无关的步骤必须保留。repaired_steps 要给出从第0步开始的完整修复路径，"
            "independent_error_steps 使用从0开始的下标，只填写修复首错后仍然独立存在的错误。"
            "不要重新写一份完全不同的标准答案。上下文：" + json.dumps(context, ensure_ascii=False),
            CounterfactualRepairProposal,
            system="你是中学解题过程的反事实验证器。只返回符合JSON Schema的结果。no_think",
        )
    except (ApiPoolUnavailable, ValueError):
        proposal = _fallback_proposal(alignment, first_index)
        used_model = False

    repaired = list(proposal.repaired_steps)
    if len(repaired) != len(alignment):
        proposal = _fallback_proposal(alignment, first_index)
        repaired = list(proposal.repaired_steps)
        used_model = False
    corrected = proposal.corrected_first_step.strip()
    reference_first = str(first.get("reference_text") or "")
    first_fixed = _same_step(reference_first, corrected)
    repaired_equivalence = [
        _same_step(str(entry.get("reference_text") or ""), repaired[index] if index < len(repaired) else "")
        for index, entry in enumerate(alignment)
    ]
    independent_indices = sorted(
        {
            index
            for index in proposal.independent_error_steps
            if first_index < index < len(alignment) and not repaired_equivalence[index]
        }
    )
    recovered = sum(
        1
        for index, entry in enumerate(alignment)
        if index >= first_index and not entry.get("equivalent") and repaired_equivalence[index]
    )
    affected = sum(1 for entry in alignment if entry["index"] >= first_index and not entry.get("equivalent"))
    all_affected_repaired = all(
        repaired_equivalence[index]
        for index, entry in enumerate(alignment)
        if index >= first_index and not entry.get("equivalent")
    )
    preserved_prefix = all(
        _same_step(str(entry.get("student_text") or ""), repaired[index])
        for index, entry in enumerate(alignment[:first_index])
    )
    reference_consistent = (
        first_fixed and preserved_prefix and recovered > 0
        and all_affected_repaired and not independent_indices
    )
    symbolic = equation_equivalent(reference_first, corrected, require_symbolic=True) and all(
        equation_equivalent(str(entry.get("reference_text") or ""), repaired[index], require_symbolic=True)
        for index, entry in enumerate(alignment)
        if index >= first_index and not entry.get("equivalent")
    )
    confirmed = reference_consistent and symbolic
    status = "confirmed" if confirmed else "partial" if first_fixed else "inconclusive"
    if confirmed:
        conclusion = f"只修正第 {first_index + 1} 步后，后续 {recovered} 个受影响步骤可以恢复，说明这里确实是主要根因。"
    elif not preserved_prefix:
        conclusion = "这份修复改动了前面原本正确的步骤，请保留原作答后重新核对。"
    elif reference_consistent:
        conclusion = "这份修复与当前参考过程一致，但尚未经过本地规则验证，请结合原题核对。"
    elif independent_indices:
        shown = "、".join(str(index + 1) for index in independent_indices)
        conclusion = (
            f"修正第 {first_index + 1} 步后，第 {shown} 步仍有独立问题，不能把后续错误全部归因于这一处。"
        )
    else:
        conclusion = f"修正第 {first_index + 1} 步后仍不足以恢复完整路径，这个根因还需要进一步核对。"
    return {
        "status": status,
        "root_cause_confirmed": confirmed,
        "reference_consistent": reference_consistent,
        "preserved_prefix": preserved_prefix,
        "suspected_step": first_index,
        "original_step": str(first.get("student_text") or "缺少对应步骤"),
        "corrected_step": corrected,
        "repaired_steps": repaired,
        "recovered_steps": recovered,
        "affected_steps": affected,
        "independent_errors": independent_indices,
        "conclusion": conclusion,
        "reasoning": proposal.reasoning,
        "verification_method": (
            "qwen_proposal_sympy_check" if used_model else "reference_repair_sympy_check"
        ) if symbolic else (
            "qwen_proposal_reference_alignment" if used_model else "reference_repair_alignment"
        ),
        "confidence": round(min(float(proposal.confidence), 0.95 if first_fixed else 0.55), 3),
    }
