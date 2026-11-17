"""Database snapshots around existing BGE/Qdrant preparation and ranking."""

from .question_data import rows, select_rows


def answer_text(value):
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "、".join(answer_text(item) for item in value)
    if isinstance(value, dict):
        return "；".join(
            str(key) + "：" + answer_text(item) for key, item in value.items()
        )
    return str(value).lower() if isinstance(value, bool) else str(value)


def grade_label(value, band):
    clean = (value or "").strip()
    for prefix, label in [
        ("七年级", "初一"),
        ("八年级", "初二"),
        ("九年级", "初三"),
        ("初中", "初中"),
        ("高中", "高中"),
    ]:
        if clean.startswith(prefix):
            return label
    return clean or band


def usable(source, candidate, kind):
    options = candidate.get("options") or []
    texts = [
        candidate.get("question_text") or "",
        answer_text(candidate.get("answer")),
        candidate.get("solution") or "",
    ]
    for option in options:
        texts.append(
            answer_text(
                option.get("text", option.get("content", option.get("value", "")))
            )
            if isinstance(option, dict)
            else answer_text(option)
        )
    total = sum(text.count("<ImageHere>") for text in texts)
    metadata = candidate.get("source_metadata") or {}
    visual = isinstance(metadata, dict) and metadata.get("has_visual") is True
    if total != len(candidate.get("image_paths") or []) and (total > 0 or visual):
        return False
    if (
        source["subject"] != candidate["subject"]
        or not candidate["usable_for_practice"]
        or not candidate["has_answer"]
        or not answer_text(candidate["answer"]).strip()
    ):
        return False
    if kind == "practice" and not candidate["usable_for_auto_grade"]:
        return False
    raw = source.get("grade") or ""
    band = "高中" if raw.startswith("高") else "初中"
    return grade_label(candidate.get("grade"), candidate.get("grade_band") or "") in [
        grade_label(raw, band),
        band,
    ]


def prepare(service, db, question, analysis, kind, mode):
    compute = service.compute
    diagnoses = select_rows(
        db,
        "diagnoses",
        "SELECT * FROM diagnoses WHERE question_id=? ORDER BY created_at DESC,id DESC LIMIT 1",
        [question["id"]],
    )
    cards = select_rows(
        db,
        "knowledge_points",
        "SELECT * FROM knowledge_points WHERE subject=?",
        [question["subject"]],
    )
    return compute.compute(
        "retrieval_prepare",
        retrieval_source=question,
        retrieval_analysis=analysis,
        retrieval_kind=kind,
        retrieval_mode=mode,
        retrieval_diagnosis=diagnoses[0] if diagnoses else {},
        retrieval_cards=cards,
    )


def candidates(service, db, question, analysis, excluded, kind, mode):
    compute = service.compute
    preparation = prepare(service, db, question, analysis, kind, mode)
    grade = question.get("grade") or ""
    found = compute.compute(
        "retrieval_search",
        retrieval_query=preparation["query"],
        subject=question["subject"],
        grade=grade,
        grade_band="高中" if grade.startswith("高") else "初中",
    )
    snapshots = []
    for hit in found.get("hits", []):
        matches = select_rows(
            db,
            "dataset_questions",
            "SELECT * FROM dataset_questions WHERE id=? AND subject=? AND usable_for_practice=1",
            [hit["id"], question["subject"]],
        )
        if not matches or not usable(question, matches[0], kind):
            continue
        candidate = matches[0]
        sources = rows(
            db,
            "SELECT `key` FROM dataset_sources WHERE id=?",
            [candidate["dataset_source_id"]],
        )
        links = rows(
            db,
            "SELECT k.id,k.name,l.role FROM question_knowledge_links l JOIN knowledge_points k ON k.id=l.knowledge_point_id WHERE l.dataset_question_id=?",
            [candidate["id"]],
        )
        snapshots.append(
            {
                **{
                    key: hit.get(key)
                    for key in [
                        "dense_rank",
                        "sparse_rank",
                        "fusion_rank",
                        "fusion_score",
                    ]
                },
                "question": candidate,
                "source_dataset": sources[0]["key"] if sources else "unknown",
                "knowledge_points": links,
            }
        )
    return compute.compute(
        "retrieval_rank",
        retrieval_query=preparation["query"],
        text=question["question_text"],
        question_type=question["question_type"],
        retrieval_candidates=snapshots,
        retrieval_excluded_ids=excluded,
        retrieval_kind=kind,
        retrieval_mode=mode,
    )
