"""Prepare learning workflow input from a verified source and owned records."""

from .learning_evidence import first_label
from .learning_memory import memory
from .protocol import ApiError
from .question_data import rows, select_rows
from .question_validation import short_title
from .task_planning import plan_candidates


def prepare_context(db, snapshot, owner):
    q = snapshot["question"]
    if q["user_id"] != owner:
        raise ApiError(404, "题目不存在或无权访问")
    analysis = snapshot.get("analysis") or {}
    diagnosis = snapshot.get("diagnosis") or {}
    work = snapshot.get("work") or {}
    points = analysis.get("knowledge_points") or q["knowledge_points"]
    step = diagnosis.get("first_error_step") or 0
    result = {
        key: q.get(key) or ""
        for key in ["subject", "grade", "question_type", "question_text"]
    }
    result.update(
        question_id=q["id"],
        options=q["options"],
        student_work_id=work.get("id", ""),
        student_step_ids=[s["id"] for s in snapshot["steps"]],
        reference_step_ids=[r["id"] for r in snapshot["references"]],
        expected=analysis.get("final_answer", ""),
        reference_steps=[r["text"] for r in snapshot["references"]],
        student_steps=[s["text"] for s in snapshot["steps"]],
        first_error_step=step if 0 <= step <= 99 else 0,
        diagnosed_correct=diagnosis.get("first_error_step") is None
        and diagnosis.get("error_type") in ["exact", "equivalent"],
        diagnosis_confirmed=diagnosis.get("user_confirmed") is True,
        diagnosis_hypothesis=diagnosis.get("root_misconception", ""),
        knowledge_points=points,
    )
    cards, seen = [], set()
    for point in points:
        if len(cards) >= 3:
            break
        for card in select_rows(
            db,
            "knowledge_points",
            "SELECT * FROM knowledge_points WHERE subject=? AND (name=? OR code=?) ORDER BY code LIMIT 3",
            [q["subject"], point, point],
        ):
            if card["code"] not in seen and len(cards) < 3:
                cards.append(card)
                seen.add(card["code"])
    result["cards"] = cards
    prerequisites = []
    for label in diagnosis.get("missing_prerequisites", []):
        if len(prerequisites) >= 6:
            break
        prerequisites.extend(
            r["id"]
            for r in rows(
                db,
                "SELECT k.id FROM knowledge_points k JOIN mastery_states m ON m.subject=k.subject AND (m.knowledge_point=k.name OR m.knowledge_point=k.code) WHERE m.user_id=? AND k.subject=? AND (k.name=? OR k.code=?) AND m.evidence_count>0 AND m.mastery_score<0.3 ORDER BY k.id LIMIT 1",
                [owner, q["subject"], label, label],
            )
        )
    result["prerequisite_card_ids"] = prerequisites
    result["practice_candidates"] = plan_candidates(db, owner, q, points)
    result["seen_contrasts"] = [
        r["prompt"]
        for r in rows(
            db,
            "SELECT DISTINCT JSON_UNQUOTE(JSON_EXTRACT(t.checkpoint,'$.contrast.question')) AS prompt FROM learning_tasks t JOIN questions q ON q.id=t.question_id WHERE t.user_id=? AND q.subject=? AND (JSON_UNQUOTE(JSON_EXTRACT(t.checkpoint,'$.contrast_passed'))='true' OR JSON_UNQUOTE(JSON_EXTRACT(t.checkpoint,'$.assistance.contrast'))='true') AND JSON_EXTRACT(t.checkpoint,'$.contrast.question') IS NOT NULL ORDER BY prompt LIMIT 50",
            [owner, q["subject"]],
        )
    ]
    point = (
        first_label(q["knowledge_points"])
        or first_label(analysis.get("knowledge_points", []))
        or (q.get("title") or "").strip()
        or q["subject"].strip() + "·" + q["question_type"]
    )
    mastery = rows(
        db,
        "SELECT mastery_score,evidence_count,CAST(last_evidence_at AS CHAR) AS last_evidence_at FROM mastery_states WHERE user_id=? AND subject=? AND knowledge_point=? ORDER BY updated_at DESC,id DESC LIMIT 1",
        [owner, q["subject"], point],
    )
    if mastery:
        value = mastery[0]
        counts = rows(
            db,
            "SELECT COUNT(CASE WHEN JSON_EXTRACT(u.evidence,'$.aemt_event.hint_used')=false THEN 1 END) AS independent_count,COUNT(CASE WHEN JSON_EXTRACT(u.evidence,'$.aemt_event.hint_used')=false AND JSON_UNQUOTE(JSON_EXTRACT(u.evidence,'$.aemt_event.verdict'))='confirmed_correct' THEN 1 END) AS independent_correct,COUNT(CASE WHEN JSON_EXTRACT(u.evidence,'$.aemt_event.hint_used')=true THEN 1 END) AS hinted_count FROM cognitive_updates u JOIN questions q ON q.id=u.question_id WHERE u.user_id=? AND q.subject=? AND u.entity_type='mastery' AND u.entity_key=? AND JSON_EXTRACT(u.evidence,'$.aemt_event.solution_seen')=false",
            [owner, q["subject"], point],
        )[0]
        result["mastery_state"] = {
            "mastery": float(value["mastery_score"])
            if value["evidence_count"] > 0
            else 0.35,
            "evidence_count": int(value["evidence_count"]),
            "last_effective_at": value["last_evidence_at"] or "",
            **{
                key: int(counts[key])
                for key in ["independent_count", "independent_correct", "hinted_count"]
            },
        }
    profiles = select_rows(
        db,
        "student_profiles",
        "SELECT preferences FROM student_profiles WHERE user_id=?",
        [owner],
    )
    minutes = (
        (profiles[0]["preferences"] or {}).get("daily_minutes", 0) if profiles else 0
    )
    if type(minutes) is int and 0 < minutes <= 120:
        goal = 3 if minutes <= 5 else 5 if minutes <= 10 else 10
        count = rows(
            db,
            "SELECT (SELECT COUNT(DISTINCT question_id) FROM learning_tasks WHERE user_id=? AND status='completed' AND updated_at>=UTC_DATE()) AS tasks,(SELECT COUNT(*) FROM study_session_items i JOIN study_sessions s ON s.id=i.session_id WHERE s.user_id=? AND s.status='submitted' AND s.submitted_at>=UTC_DATE() AND JSON_EXTRACT(i.grading,'$.can_update_learning')=true) AS practice",
            [owner, owner],
        )[0]
        result.update(
            available_minutes=max(
                0, minutes - int(count["tasks"]) * 3 - int(count["practice"])
            ),
            goal_remaining=max(0, goal - int(count["tasks"]) - int(count["practice"])),
        )
    snapshot_memory = memory(db, owner, q)["snapshot"]
    summary = ""
    for entry in snapshot_memory["entries"]:
        text = entry["summary"] + "；"
        if len(summary) + len(text) <= 1800:
            summary += text
    result.update(
        memory_snapshot=snapshot_memory,
        memory_refs=[e["ref"] for e in snapshot_memory["entries"]],
        memory_versions={e["ref"]: e["version"] for e in snapshot_memory["entries"]},
        memory_summary=short_title(summary, 1800),
    )
    return result
