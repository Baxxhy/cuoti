"""Preserve the original label-based knowledge linking rules."""

import re
from uuid import uuid4

from .question_data import execute, select_rows


def label(value):
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]", "", value.lower())


def sync_links(db, question, analysis, diagnosis=None):
    cards = select_rows(
        db,
        "knowledge_points",
        "SELECT * FROM knowledge_points WHERE subject=? ORDER BY id",
        [question["subject"]],
    )
    sources = [
        (question["knowledge_points"], "primary"),
        (analysis["knowledge_points"], "primary"),
        (analysis["prerequisites"], "prerequisite"),
    ]
    if diagnosis:
        sources.append((diagnosis["missing_prerequisites"], "prerequisite"))
    selected = {}
    for phrases, role in sources:
        for phrase in phrases:
            needle = label(phrase)
            if len(needle) < 2:
                continue
            best = None
            for card in cards:
                content = card["content"] if isinstance(card["content"], dict) else {}
                names = [
                    card["name"],
                    card["code"],
                    *content.get("related_knowledge", []),
                ]
                score = max(
                    (
                        1.0
                        if label(str(name)) == needle
                        else 0.86
                        if len(label(str(name))) >= 2
                        and (needle in label(str(name)) or label(str(name)) in needle)
                        else 0
                        for name in names
                    ),
                    default=0,
                )
                rank = (score, len(label(card["name"])))
                if score and (best is None or rank > best[0]):
                    best = (rank, card["id"])
            if best:
                rank, card_id = best
                old = selected.get(card_id)
                if old and (
                    (old[0] == "primary" and role == "prerequisite")
                    or (old[0] == role and old[1] >= rank[0])
                ):
                    continue
                selected[card_id] = (role, rank[0], phrase)
    for card_id, (role, score, phrase) in selected.items():
        execute(
            db,
            "INSERT INTO user_question_knowledge_links (id,user_id,question_id,knowledge_point_id,role,confidence,mapping_method,evidence_text,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,UTC_TIMESTAMP(),UTC_TIMESTAMP()) ON DUPLICATE KEY UPDATE role=VALUES(role),confidence=VALUES(confidence),mapping_method=VALUES(mapping_method),evidence_text=VALUES(evidence_text),updated_at=UTC_TIMESTAMP()",
            [
                str(uuid4()),
                question["user_id"],
                question["id"],
                card_id,
                role,
                score,
                "exact_label" if score == 1 else "contained_label",
                phrase[:255],
            ],
        )


def dialogue_cards(db, query, subject, grade):
    available = select_rows(
        db,
        "knowledge_points",
        "SELECT * FROM knowledge_points WHERE subject=? ORDER BY code LIMIT 200",
        [subject],
    )

    def score(card):
        content = card["content"] if isinstance(card["content"], dict) else {}
        level = content.get("grade", "")
        if grade.startswith("初") and isinstance(level, str) and level.startswith("高"):
            return 0
        context = label(query)
        value = 0
        for name in [card["name"], card["code"]]:
            key = label(name)
            if len(key) >= 2 and key in context:
                value = 100 + len(key)
        for alias in (
            content.get("related_knowledge", [])
            if isinstance(content.get("related_knowledge", []), list)
            else []
        ):
            if isinstance(alias, str):
                key = label(alias)
                if len(key) >= 2 and key in context and value == 0:
                    value = len(key)
        return value

    ranked = sorted(
        ((score(card), index, card) for index, card in enumerate(available)),
        key=lambda item: (-item[0], item[1]),
    )
    anchors = [card for value, _, card in ranked if value > 0][:3]
    result = [{**card, "retrieval_role": "anchor"} for card in anchors]
    seen = {card["code"] for card in anchors}
    for anchor in anchors:
        dependencies = select_rows(
            db,
            "knowledge_points",
            "SELECT k.* FROM knowledge_relations r JOIN knowledge_points k ON r.target_id=k.id WHERE r.source_id=? AND r.relation_type='prerequisite' AND k.subject=? ORDER BY k.code LIMIT 2",
            [anchor["id"], subject],
        )
        for card in dependencies:
            if len(result) >= 8 or card["code"] in seen:
                continue
            result.append(
                {
                    **card,
                    "retrieval_role": "prerequisite",
                    "anchor_code": anchor["code"],
                }
            )
            seen.add(card["code"])
    return result
