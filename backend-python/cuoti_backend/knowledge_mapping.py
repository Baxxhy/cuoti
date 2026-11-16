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
