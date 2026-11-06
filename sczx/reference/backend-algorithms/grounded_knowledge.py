"""Bounded curriculum-graph retrieval; evidence comes from native MySQL snapshots."""

import hashlib
import json
import re

from pydantic import BaseModel, ConfigDict, Field


class KnowledgeEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    role: str
    anchor_code: str = ""
    definition: str = Field(max_length=1800)
    formulas: list[str] = Field(default_factory=list, max_length=8)
    source_hash: str


def build_knowledge_evidence(cards, subject: str, grade: str = ""):
    """Respect subject, dependency provenance, deduplication and a strict token bound."""
    sources = []
    seen = set()
    anchors = {str(c.get("code", "")) for c in cards if c.get("retrieval_role", "anchor") == "anchor"}
    for card in cards:
        if len(sources) >= 6:
            break
        if card.get("subject") not in (None, "", subject):
            continue
        content = card.get("content") or {}
        if not isinstance(content, dict):
            continue
        card_grade = str(content.get("grade", ""))
        if grade.startswith("初") and card_grade.startswith("高"):
            continue
        code = str(card.get("code", ""))
        name = str(card.get("name", ""))
        definition = str(content.get("definition", "")).strip()
        if not code or not name or not definition or code in seen:
            continue
        role = card.get("retrieval_role", "anchor")
        anchor = str(card.get("anchor_code", ""))
        if role == "prerequisite" and (anchor not in anchors or anchor == code):
            continue
        if role not in {"anchor", "prerequisite"}:
            continue
        formulas = [str(x)[:240] for x in content.get("formulas", [])[:8]]
        if re.search(r"是.*(?:中用于解释和解决.*问题的核心知识|核心学习主题，作答时要结合题目条件和本学科证据)[。.]?$", definition):
            if not formulas:
                continue
            definition = ""  # A generic placeholder is not explanatory evidence.

        text = json.dumps({"definition": definition, "formulas": formulas}, ensure_ascii=False, sort_keys=True)
        sources.append(KnowledgeEvidence(code=code, name=name, role=role, anchor_code=anchor,
            definition=definition[:1800], formulas=formulas,
            source_hash=hashlib.sha256(text.encode()).hexdigest()).model_dump())
        seen.add(code)
    accepted = {s["code"] for s in sources if s["role"] == "anchor"}
    return [s for s in sources if s["role"] == "anchor" or s["anchor_code"] in accepted]
