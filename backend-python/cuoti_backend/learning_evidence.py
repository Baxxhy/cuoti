"""Persist original cognition calculations with reproducible source stamps."""

from datetime import datetime, timezone

from .lessons import compact, digest
from .protocol import ApiError
from .question_data import execute, insert, select_rows, update
from .retrieval import answer_text


def first_label(values):
    for value in values if isinstance(values, list) else []:
        text = (
            next(
                (
                    value[k]
                    for k in ["name", "label", "code"]
                    if isinstance(value.get(k), str) and value[k]
                ),
                "",
            )
            if isinstance(value, dict)
            else answer_text(value)
        )
        if text.strip():
            return text.strip()
    return ""


def stamp_compact(value):
    # The native JSON writer prints integral JsonFloat values as integers.
    # Ordinary API JSON remains unchanged; only legacy source stamps use this.
    def normalize(item):
        if isinstance(item, dict):
            return {key: normalize(value) for key, value in item.items()}
        if isinstance(item, list):
            return [normalize(value) for value in item]
        if isinstance(item, float) and item.is_integer():
            return int(item)
        return item

    return compact(normalize(value))


def question_version(db, question):
    id = question["id"]
    source = [
        question.get(key)
        for key in [
            "id",
            "user_id",
            "subject",
            "grade",
            "question_type",
            "question_text",
            "student_answer",
            "options",
            "knowledge_points",
        ]
    ]
    work = select_rows(
        db,
        "student_works",
        "SELECT * FROM student_works WHERE question_id=? ORDER BY created_at DESC,id DESC LIMIT 1",
        [id],
    )
    source.append(work[0] if work else None)
    source.append(
        select_rows(
            db,
            "student_steps",
            "SELECT * FROM student_steps WHERE work_id=(SELECT id FROM student_works WHERE question_id=? ORDER BY created_at DESC,id DESC LIMIT 1) ORDER BY step_index,id",
            [id],
        )
    )
    source.append(
        select_rows(
            db,
            "question_assets",
            "SELECT * FROM question_assets WHERE question_id=? AND kind IN ('crop','question_figure') ORDER BY created_at,id",
            [id],
        )
    )
    analyses = select_rows(
        db,
        "problem_analyses",
        "SELECT * FROM problem_analyses WHERE question_id=? ORDER BY created_at,id LIMIT 1",
        [id],
    )
    source.append(analyses[0] if analyses else None)
    source.append(
        select_rows(
            db,
            "reference_steps",
            "SELECT r.* FROM reference_steps r JOIN problem_analyses a ON a.id=r.analysis_id WHERE a.question_id=? ORDER BY r.step_index,r.id",
            [id],
        )
    )
    source.append([])
    return digest(stamp_compact(source))


def knowledge_point(db, question, preferred="", include_analysis=True):
    point = preferred.strip() or first_label(question["knowledge_points"])
    if not point and include_analysis:
        analyses = select_rows(
            db,
            "problem_analyses",
            "SELECT * FROM problem_analyses WHERE question_id=? ORDER BY created_at,id LIMIT 1",
            [question["id"]],
        )
        point = first_label(analyses[0]["knowledge_points"]) if analyses else ""
    point = (
        point
        or (question.get("title") or "").strip()
        or question["subject"].strip() + "·" + question["question_type"]
    )
    return point


def apply_evidence(
    service,
    db,
    owner,
    question,
    evidence,
    preferred="",
    include_analysis=True,
    compute_timeout=None,
):
    if service.compute is None:
        raise ApiError(503, "内部算法服务未配置")
    execute(db, "SELECT id FROM users WHERE id=? FOR UPDATE", [owner])
    point = knowledge_point(db, question, preferred, include_analysis)
    subject = question["subject"].strip()
    diagnoses = select_rows(
        db,
        "diagnoses",
        "SELECT * FROM diagnoses WHERE question_id=? ORDER BY created_at DESC,id DESC LIMIT 1",
        [question["id"]],
    )
    diagnosis = diagnoses[0] if diagnoses else {}
    code = (diagnosis.get("error_type") or "").strip()
    if not code or code in ["exact", "equivalent", "branch_solution"]:
        code = "unclassified"
    label = (diagnosis.get("root_misconception") or "").strip() or code
    old_mastery = select_rows(
        db,
        "mastery_states",
        "SELECT * FROM mastery_states WHERE user_id=? AND subject=? AND knowledge_point=? ORDER BY updated_at DESC,id DESC LIMIT 1",
        [owner, subject, point],
    )
    old_mistake = select_rows(
        db,
        "misconception_states",
        "SELECT * FROM misconception_states WHERE user_id=? AND subject=? AND code=? ORDER BY updated_at DESC,id DESC LIMIT 1",
        [owner, subject, code],
    )
    mastery_defaults = {
        "mastery_score": 0.0,
        "evidence_count": 0,
        "confidence": 0.0,
        "near_transfer_rate": 0.0,
        "far_transfer_rate": 0.0,
        "forgetting_risk": 0.5,
    }
    mistake_defaults = {
        "probability": 0.5,
        "evidence_count": 1,
        "related_question_count": 1,
        "label": label,
        "status": "active",
        "successful_strategy": "",
        "failed_strategy": "",
    }
    mastery = {
        key: old_mastery[0][key] if old_mastery else value
        for key, value in mastery_defaults.items()
    }
    mastery["update_reason"] = ""
    mistake = {
        key: old_mistake[0][key] if old_mistake else value
        for key, value in mistake_defaults.items()
    }
    computed = service.compute.compute(
        "cognition_update",
        **({"timeout": compute_timeout} if compute_timeout is not None else {}),
        mastery_values=mastery,
        misconception_values=mistake,
        learning_evidence=evidence,
        misconception_label=label,
    )
    next_mastery, next_mistake = computed["mastery"], computed["misconception"]
    mid = (
        old_mastery[0]["id"]
        if old_mastery
        else insert(
            db,
            "mastery_states",
            timestamp_microseconds=False,
            user_id=owner,
            subject=subject,
            knowledge_point=point,
            **mastery,
        )
    )
    now = datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)
    mistake_id = (
        old_mistake[0]["id"]
        if old_mistake
        else insert(
            db,
            "misconception_states",
            timestamp_microseconds=False,
            user_id=owner,
            subject=subject,
            code=code,
            first_seen_at=now,
            **mistake,
        )
    )
    update(
        db,
        "mastery_states",
        mid,
        timestamp_microseconds=False,
        **{key: next_mastery[key] for key in [*mastery_defaults, "update_reason"]},
        last_evidence_at=now,
    )
    update(
        db,
        "misconception_states",
        mistake_id,
        timestamp_microseconds=False,
        **{key: next_mistake[key] for key in mistake_defaults},
        last_seen_at=now,
    )
    dataset = evidence.get("dataset_question_id") or ""
    datasets = (
        select_rows(
            db,
            "dataset_questions",
            "SELECT * FROM dataset_questions WHERE id=? AND usable_for_auto_grade=1",
            [dataset],
        )
        if dataset
        else []
    )
    evidence["memory_source"] = {
        "rule_version": "learning-memory-v1",
        "question_version": question_version(db, question),
        "mastery_id": mid,
        "misconception_id": mistake_id,
        "dataset_version": digest(stamp_compact(datasets[0])) if datasets else "",
    }
    for kind, key, old, new in [
        ("mastery", point, mastery["mastery_score"], next_mastery["mastery_score"]),
        ("misconception", code, mistake["probability"], next_mistake["probability"]),
    ]:
        insert(
            db,
            "cognitive_updates",
            timestamp_microseconds=False,
            user_id=owner,
            question_id=question["id"],
            entity_type=kind,
            entity_key=key,
            old_value=old,
            new_value=new,
            evidence=evidence,
            reason=next_mastery["update_reason"],
        )
    return {
        "mastery_before": old_mastery[0] if old_mastery else None,
        "misconception_before": old_mistake[0] if old_mistake else None,
        "mastery_after": select_rows(
            db, "mastery_states", "SELECT * FROM mastery_states WHERE id=?", [mid]
        )[0],
        "misconception_after": select_rows(
            db,
            "misconception_states",
            "SELECT * FROM misconception_states WHERE id=?",
            [mistake_id],
        )[0],
    }


def complete(service, db, session, detail, insufficient):
    state = session["state"]
    evidence = {
        key: state.get(key) for key in ["teach_back", "near_transfer", "far_transfer"]
    }
    evidence.update(
        hint_level=session["hint_level"],
        strategy="assisted_progression" if state.get("assisted") else "micro_activity",
        tutor_session_id=session["id"],
    )
    updated = apply_evidence(service, db, session["user_id"], detail, evidence)
    score = updated["mastery_after"]["mastery_score"]
    days = 1 if insufficient else 3 if state.get("assisted") else 15
    from uuid import uuid4

    pid = str(uuid4())
    execute(
        db,
        "INSERT INTO review_plans (id,user_id,question_id,due_at,interval_days,reason,status,created_at,updated_at) VALUES (?,?,?,TIMESTAMPADD(DAY,?,UTC_TIMESTAMP()),?,?,'pending',UTC_TIMESTAMP(),UTC_TIMESTAMP())",
        [
            pid,
            session["user_id"],
            detail["id"],
            days,
            days,
            "迁移练习还不稳定，已提高复习优先级"
            if insufficient
            else "本轮学习已完成，按掌握情况复习",
        ],
    )
    state.update(
        completion_summary="这次换一种题目还不够稳定，我已经把它放到近期优先复习。"
        if insufficient
        else "本轮已经完成。下一次复习会根据这次是否需要提示来安排。",
        mastery_proven=not insufficient and state.get("far_transfer") is True,
    )
    session.update(stage="finished", status="completed", mastery_score=score)
    update(db, "tutor_sessions", session["id"], status="completed", mastery_score=score)
    output = {
        "mastery": score,
        "interval_days": days,
        "priority": "high" if insufficient else "normal",
    }
    run_id = insert(
        db,
        "agent_runs",
        session_id=session["id"],
        agent_name="mindtrace_tutor",
        status="completed",
        result={**output, "branch": "activity_finish"},
    )
    insert(
        db,
        "agent_tool_calls",
        agent_run_id=run_id,
        tool_name="update_cognition",
        input_json=evidence,
        output_json=output,
    )
    return {
        "mastery": updated["mastery_after"],
        "misconception": updated["misconception_after"],
        "review": select_rows(
            db, "review_plans", "SELECT * FROM review_plans WHERE id=?", [pid]
        )[0],
    }
