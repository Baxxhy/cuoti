from __future__ import annotations

from dataclasses import dataclass
from typing import Any

GRADE_ALIASES = {
    "七年级": "初一",
    "八年级": "初二",
    "九年级": "初三",
    "七年级上": "初一",
    "七年级下": "初一",
    "八年级上": "初二",
    "八年级下": "初二",
    "九年级上": "初三",
    "九年级下": "初三",
    "初中": "初中",
    "高中": "高中",
}

QUESTION_TYPE_LABELS = {
    "fill_blank": "填空题",
    "choice": "单选题",
    "multiple_choice": "多选题",
    "calculation": "计算题",
    "proof": "证明题",
    "subjective": "主观题",
    "other": "其他题型",
}

ALIASES = {
    "参数讨论": ("参数", "取值范围", "分类讨论", "恒成立"),
    "边界条件": ("边界", "临界", "端点", "等号", "取等", "a=", "参数范围"),
    "二次函数": ("二次函数", "抛物线", "开口", "对称轴", "顶点"),
    "受力对象": ("研究对象", "受力对象", "隔离法", "物体受力"),
    "力与受力分析": ("受力", "合力", "支持力", "拉力", "斜面"),
    "定语从句": ("定语从句", "关系代词", "关系副词", "which", "that", "who", "whose"),
    "离子方程式": ("离子方程式", "可拆", "不可拆", "离子反应", "净离子"),
    "化学方程式": ("化学方程式", "配平", "反应方程式"),
    "一元二次方程": ("一元二次方程", "判别式", "根的判别", "韦达"),
    "一次函数": ("一次函数", "正比例函数", "斜率"),
    "三角函数": ("正弦", "余弦", "正切", "sin", "cos", "tan"),
    "数列": ("数列", "等差", "等比", "通项", "前n项和"),
}


@dataclass(slots=True)
class KnowledgeMatch:
    knowledge_id: str
    role: str
    confidence: float
    method: str = "offline_rules"


def normalized_grade(grade: str, grade_band: str) -> str:
    clean = grade.strip()
    for raw, normalized in GRADE_ALIASES.items():
        if clean.startswith(raw):
            return normalized
    return clean or grade_band


def student_facing_topic(knowledge_points: list[Any] | None, question_type: str | None) -> str:
    raw = str((knowledge_points or [question_type or "错题学习"])[0]).strip()
    return QUESTION_TYPE_LABELS.get(raw, raw or "错题学习")


def _terms(card: Any) -> set[str]:
    content = card.content or {}
    values = {card.name, str(content.get("chapter", ""))}
    values.update(ALIASES.get(card.name, ()))
    values.update(str(item) for item in content.get("related_knowledge", []))
    return {value.lower() for value in values if len(value.strip()) >= 2}


def map_question(question: Any, cards: list[Any], limit: int = 3) -> list[KnowledgeMatch]:
    source_kp = " ".join(str(item) for item in (question.knowledge_points or []))
    metadata = question.source_metadata or {}
    text = " ".join(
        (
            question.question_text or "",
            question.title or "",
            source_kp,
            str(metadata.get("task", "")),
            str(metadata.get("raw_subject", "")),
        )
    ).lower()
    grade = normalized_grade(question.grade, question.grade_band)
    ranked: list[tuple[float, Any]] = []
    for card in cards:
        content = card.content or {}
        score = 0.0
        for term in _terms(card):
            if term in text:
                score += 8.0 if term == card.name.lower() else min(4.0, 1.0 + len(term) / 4)
        card_grade = str(content.get("grade", ""))
        if card_grade == grade:
            score += 2.5
        elif card_grade in {question.grade_band, "初中" if grade.startswith("初") else "高中"}:
            score += 1.0
        chapter = str(content.get("chapter", "")).lower()
        if chapter and chapter in text:
            score += 3.0
        ranked.append((score, card))
    ranked.sort(key=lambda item: (-item[0], item[1].code))
    positive = [item for item in ranked if item[0] > 0]
    selected = positive[:limit] if positive else ranked[:1]
    if not selected:
        return []
    peak = max(selected[0][0], 1.0)
    return [
        KnowledgeMatch(
            knowledge_id=card.id,
            role="primary" if index == 0 else "secondary",
            confidence=round(max(0.35, min(0.99, score / (peak + 2))), 3),
            method="offline_rules" if score > 0 else "subject_grade_fallback",
        )
        for index, (score, card) in enumerate(selected)
    ]
