"""Generated practice fallback with source-bound cache and learning receipts."""

from .learning_evidence import apply_evidence, knowledge_point
from .lessons import compact
from .practice_context import source_version
from .protocol import ApiError
from .question_data import insert, rows, select_rows, update
from .retrieval import answer_text
from .task_sources import source_equal
from .tutoring import points


def payload(question, variant):
    meta = variant["generation_metadata"]
    return {
        "question_id": variant["id"],
        "stem": variant["question_text"],
        "subject": question["subject"],
        "grade": question["grade"],
        "question_type": meta["question_type"],
        "options": meta.get("options") or [],
        "images": [],
        "mode": meta["mode"],
        "generated": True,
        "recommendation": "根据这道错题练习相同的方法",
    }


def generate(service, owner, question, mode, force):
    with service.database.session() as db:
        version = source_version(db, question)
        found = select_rows(
            db,
            "variant_questions",
            "SELECT v.* FROM variant_questions v JOIN tutor_sessions s ON s.id=v.session_id WHERE s.user_id=? AND v.question_id=? AND s.stage='standalone_practice' ORDER BY v.created_at DESC LIMIT 20",
            [owner, question["id"]],
        )
        previous = None
        for item in found:
            meta = item.get("generation_metadata") or {}
            if (
                meta.get("source_version") == version
                and meta.get("mode") == mode
                and item.get("verified") is True
            ):
                previous = previous or item
                if not force:
                    result = payload(question, item)
                    sessions = select_rows(
                        db,
                        "tutor_sessions",
                        "SELECT * FROM tutor_sessions WHERE id=?",
                        [item["session_id"]],
                    )
                    state = sessions[0]["state"] if sessions else {}
                    if "receipt" in state:
                        result.update(
                            previous_result=state["receipt"],
                            previous_answer=state.get("answer"),
                        )
                    return result
        detail = service.detail(db, question["id"], owner)
    original = (
        question["question_text"]
        + "\n选项："
        + compact(question.get("options") or [])
        + "\n年级："
        + (question.get("grade") or "")
    )
    if previous:
        original += "\n请勿重复此前练习：" + previous["question_text"]
    computed = {}
    try:
        if service.compute is not None:
            computed = service.compute.compute(
                "generate_practice",
                text=original,
                subject=question["subject"],
                question_type=question["question_type"],
                transfer_type="far" if mode == "variation" else "near",
                knowledge_points=[answer_text(point) for point in points(detail)],
            )
    except ApiError:
        pass
    if computed.get("verified") is not True:
        if previous:
            result = payload(question, previous)
            result["recommendation"] = "再练一次，巩固这道题的方法"
            return result
        raise ApiError(503, "类似题暂未通过核对，请稍后重试。原错题和学习记录已保留。")
    generated, meta = computed["variant"], dict(computed.get("generation") or {})
    meta.update(
        options=generated.get("options") or [],
        mode=mode,
        source_version=version,
        question_type=question["question_type"]
        if generated.get("options")
        else "综合题",
    )
    with service.database.session() as db, db.begin():
        current = select_rows(
            db,
            "questions",
            "SELECT * FROM questions WHERE id=? AND user_id=? AND status<>'archived' FOR UPDATE",
            [question["id"], owner],
        )
        if not current or source_version(db, current[0]) != version:
            raise ApiError(409, "原题已更新，请重新获取练习")
        sid = insert(
            db,
            "tutor_sessions",
            timestamp_microseconds=False,
            user_id=owner,
            question_id=question["id"],
            stage="standalone_practice",
            hint_level=0,
            turn_count=0,
            mastery_score=0,
            state={},
            status="standalone",
        )
        vid = insert(
            db,
            "variant_questions",
            timestamp_microseconds=False,
            question_id=question["id"],
            session_id=sid,
            transfer_type="far" if mode == "variation" else "near",
            question_text=generated["question_text"],
            answer=generated["answer"],
            explanation=generated["explanation"],
            reference_solution=generated["reference_solution"],
            verified=True,
            generation_metadata=meta,
        )
        return payload(
            question,
            select_rows(
                db,
                "variant_questions",
                "SELECT * FROM variant_questions WHERE id=?",
                [vid],
            )[0],
        )


def attempt(service, db, owner, mistake, variant, mode, answer, duration):
    meta, id = variant["generation_metadata"], variant["id"]
    if meta.get("mode") != mode or meta.get("source_version") != source_version(
        db, mistake
    ):
        raise ApiError(409, "原题或练习目标已更新，请重新获取练习")
    sessions = select_rows(
        db,
        "tutor_sessions",
        "SELECT * FROM tutor_sessions WHERE id=? FOR UPDATE",
        [variant["session_id"]],
    )
    state = sessions[0]["state"] if sessions else {}
    if (
        source_equal(state.get("answer"), answer)
        and (state.get("receipt") or {}).get("can_update_learning") is True
    ):
        return state["receipt"]
    if service.compute is None:
        raise ApiError(503, "内部算法服务未配置")
    grading = service.compute.compute(
        "grade_answer",
        text=variant["question_text"],
        answer=answer,
        expected=variant["answer"],
        subject=mistake["subject"],
        question_type=meta["question_type"],
        options=meta.get("options") or [],
        reference_solution=variant["reference_solution"],
    )
    decisive = (
        grading.get("can_update_learning") is True and variant.get("verified") is True
    )
    answer_seen = state.get("answer_revealed") is True
    prior = rows(
        db,
        "SELECT id FROM variant_attempts WHERE variant_id=? AND user_id=? LIMIT 1",
        [id, owner],
    )
    old = rows(
        db,
        "SELECT mastery_score FROM mastery_states WHERE user_id=? AND subject=? AND knowledge_point=? LIMIT 1",
        [owner, mistake["subject"], knowledge_point(db, mistake)],
    )
    before = float(old[0]["mastery_score"]) if old else 0.0
    saved = {
        "answer": answer,
        "grading": grading,
        "duration_seconds": duration,
        "answer_revealed": True,
    }
    update(
        db,
        "tutor_sessions",
        variant["session_id"],
        timestamp_microseconds=False,
        state=saved,
    )
    mastery = None
    if decisive:
        aid = insert(
            db,
            "variant_attempts",
            timestamp_microseconds=False,
            variant_id=id,
            user_id=owner,
            answer=answer_text(answer),
            correct=grading["correct"],
            elapsed_seconds=duration,
            hint_level=0,
        )
        if not prior and not answer_seen:
            evidence = {
                "near_transfer" if mode == "reinforce" else "far_transfer": grading[
                    "correct"
                ],
                "hint_level": 0,
                "strategy": "generated_practice",
                "variant_id": id,
                "practice_attempt_id": aid,
            }
            mastery = apply_evidence(service, db, owner, mistake, evidence)[
                "mastery_after"
            ]["mastery_score"]
    result = {
        key: grading[key] for key in ["verdict", "confidence", "evidence", "feedback"]
    }
    result.update(
        correct=grading["correct"] if decisive else None,
        can_update_learning=decisive,
        answer=variant["answer"],
        solution=variant["explanation"],
        mastery_before=before,
        mastery=mastery,
        grading_method=grading["method"],
    )
    if answer_seen:
        result["learning_note"] = "已看过参考答案，这次练习不重复计入掌握情况。"
    saved["receipt"] = result
    update(
        db,
        "tutor_sessions",
        variant["session_id"],
        timestamp_microseconds=False,
        state=saved,
    )
    return result
