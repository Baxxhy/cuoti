"""Practice recommendations with provenance-checked cache and generated fallback."""

from fastapi import APIRouter, Request
from starlette.concurrency import run_in_threadpool

from . import practice_context as context
from . import practice_generated
from .dataset_images import question_images, solution_images
from .lessons import compact
from .protocol import ApiError, envelope
from .question_data import execute, insert, rows, select_rows
from .question_routes import body
from .question_validation import boolean, text_value
from .retrieval import answer_text, candidates, usable
from .task_sources import source_equal

router = APIRouter(prefix="/api/v1/practice")


def mode_value(value):
    mode = text_value(value.get("mode", ""), 30)
    if mode not in ["reinforce", "variation"]:
        raise ApiError(422, "请选择有效的练习模式")
    return mode


def receipt(service, question, saved):
    return {**saved, **solution_images(service.media, question)}


def payload(service, question, mode, trace, points):
    if service.compute is None:
        raise ApiError(503, "内部算法服务未配置")
    pictures = question_images(service.media, question)
    options = service.compute.compute(
        "normalize_options", raw_options=question["options"]
    )["options"]
    for index, option in enumerate(options):
        shown = pictures["options"]
        if index < len(shown) and shown[index].get("image_urls"):
            option["image_urls"] = shown[index]["image_urls"]
    names = trace.get("knowledge_match") or []
    name = answer_text(names[0]) if names else "关键方法"
    return {
        "question_id": question["id"],
        **{key: question[key] for key in ["subject", "grade", "question_type"]},
        "stem": question["question_text"],
        "images": pictures["image_urls"],
        "options": options,
        "knowledge_points": points,
        "recommendation": "这道题会继续检查你需要加强的" + name + "。",
        "mode": mode,
    }


@router.post("/recommend")
async def recommend_route(request: Request):
    return envelope(
        request, await run_in_threadpool(recommend, request, await body(request))
    )


def recommend(request, value):
    id = text_value(value.get("mistake_id", ""), 100)
    if not id.strip():
        raise ApiError(422, "mistake_id 长度不正确")
    mode = mode_value(value)
    debug, force = (
        boolean(value.get("debug", False)),
        boolean(value.get("force_new", False)),
    )
    service = request.app.state.questions
    with service.database.session() as db, db.begin():
        owner = service.user(request, db).id
        found = select_rows(
            db,
            "questions",
            "SELECT * FROM questions WHERE id=? AND user_id=? AND status<>'archived'",
            [id, owner],
        )
        if not found:
            raise ApiError(404, "没有找到这道错题")
        question = found[0]
        fingerprint = context.source_fingerprint(db, question)
        version = context.source_version(db, question)
        generated = select_rows(
            db,
            "variant_questions",
            "SELECT v.* FROM variant_questions v JOIN tutor_sessions s ON s.id=v.session_id WHERE s.user_id=? AND v.question_id=? AND s.stage='standalone_practice' AND v.verified=1 ORDER BY v.created_at DESC LIMIT 20",
            [owner, id],
        )
        generate = any(
            (item.get("generation_metadata") or {}).get("mode") == mode
            and item["generation_metadata"].get("source_version") == version
            for item in generated
        )
        prepared = {}
        if not generate:
            try:
                prepared = context.preparation(service, db, question, mode)
            except ApiError:
                pass
            if not force:
                previous = select_rows(
                    db,
                    "practice_recommendations",
                    "SELECT * FROM practice_recommendations WHERE user_id=? AND mistake_id=? AND mode=? ORDER BY created_at DESC LIMIT 1",
                    [owner, id, mode],
                )
                if previous:
                    saved = previous[0]
                    trace = saved.get("retrieval_trace") or {}
                    qid = saved["dataset_question_id"]
                    attempts = select_rows(
                        db,
                        "dataset_practice_attempts",
                        "SELECT * FROM dataset_practice_attempts WHERE user_id=? AND mistake_id=? AND dataset_question_id=? AND mode=? ORDER BY created_at DESC,id DESC LIMIT 1",
                        [owner, id, qid, mode],
                    )
                    selected = select_rows(
                        db,
                        "dataset_questions",
                        "SELECT * FROM dataset_questions WHERE id=?",
                        [qid],
                    )
                    if (
                        trace.get("source_question_fingerprint") == fingerprint
                        and trace.get("target_knowledge_id", "")
                        == prepared.get("target_knowledge_id", "")
                        and selected
                        and usable(question, selected[0], "practice")
                    ):
                        candidate = selected[0]
                        valid = context.proof_valid(
                            db, question, prepared, candidate, trace
                        )
                        if not valid:
                            checks = context.aligned(
                                service,
                                db,
                                question,
                                prepared,
                                [{"question": candidate}],
                            )
                            method = context.alignment_method(checks, qid)
                            valid = bool(method)
                            if valid:
                                context.save_proof(
                                    db, question, prepared, candidate, trace, method
                                )
                                execute(
                                    db,
                                    "UPDATE practice_recommendations SET retrieval_trace=?,updated_at=UTC_TIMESTAMP(6) WHERE id=?",
                                    [compact(trace), saved["id"]],
                                )
                        if valid and attempts:
                            details = attempts[0].get("grading_details") or {}
                            valid = bool(
                                details.get("practice_receipt")
                            ) and source_equal(
                                (details.get("alignment_proof") or {}).get("context"),
                                context.proof_context(
                                    db, question, prepared, candidate
                                ),
                            )
                        if valid:
                            output = payload(
                                service,
                                candidate,
                                mode,
                                trace,
                                candidate["knowledge_points"],
                            )
                            if attempts:
                                details = attempts[0]["grading_details"]
                                output.update(
                                    previous_result=receipt(
                                        service, candidate, details["practice_receipt"]
                                    ),
                                    previous_answer=attempts[0]["student_answer"],
                                )
                            if debug:
                                output["debug"] = trace
                            return output
    if generate or not prepared.get("target_knowledge_id"):
        return practice_generated.generate(service, owner, question, mode, force)
    with service.database.session() as db:
        excluded = []
        for table in ["dataset_practice_attempts", "practice_recommendations"]:
            for row in rows(
                db,
                f"SELECT dataset_question_id FROM {table} WHERE user_id=? AND mistake_id=?",
                [owner, id],
            ):
                if row["dataset_question_id"] not in excluded:
                    excluded.append(row["dataset_question_id"])
        try:
            analyses = select_rows(
                db,
                "problem_analyses",
                "SELECT * FROM problem_analyses WHERE question_id=? ORDER BY created_at DESC,id DESC LIMIT 1",
                [id],
            )
            ranked = candidates(
                service,
                db,
                question,
                analyses[0] if analyses else None,
                excluded,
                "practice",
                mode,
            )["ranked"]
            checks = context.aligned(service, db, question, prepared, ranked)
        except ApiError:
            ranked, checks = [], []
    admitted = [
        candidate
        for candidate in ranked
        if context.alignment_method(checks, candidate["question"]["id"])
    ]
    if not admitted:
        return practice_generated.generate(service, owner, question, mode, force)
    with service.database.session() as db, db.begin():
        found = select_rows(
            db,
            "questions",
            "SELECT * FROM questions WHERE id=? AND user_id=? AND status<>'archived' FOR UPDATE",
            [id, owner],
        )
        if not found or context.source_fingerprint(db, found[0]) != fingerprint:
            raise ApiError(409, "题目已修改，请重新获取推荐题")
        current = found[0]
        if context.source_version(db, current) != version:
            raise ApiError(409, "题目分析或诊断已更新，请重新获取练习")
        candidate = admitted[0]
        selected = candidate["question"]
        if context.preparation(service, db, current, mode).get(
            "target_knowledge_id", ""
        ) != prepared.get("target_knowledge_id", ""):
            raise ApiError(409, "学习目标已更新，请重新获取练习")
        fresh = select_rows(
            db,
            "dataset_questions",
            "SELECT * FROM dataset_questions WHERE id=? AND subject=? AND usable_for_practice=1",
            [selected["id"], question["subject"]],
        )
        if (
            not fresh
            or not usable(question, fresh[0], "practice")
            or not source_equal(fresh[0], selected)
        ):
            raise ApiError(409, "推荐题已更新，请重新获取")
        for table in ["practice_recommendations", "dataset_practice_attempts"]:
            if rows(
                db,
                f"SELECT id FROM {table} WHERE user_id=? AND mistake_id=? AND dataset_question_id=? LIMIT 1",
                [owner, id, selected["id"]],
            ):
                raise ApiError(409, "推荐已变化，请重新获取练习题")
        trace = {
            "source_question_fingerprint": fingerprint,
            "alignment_method": context.alignment_method(checks, selected["id"]),
        }
        trace.update(
            {
                key: prepared[key]
                for key in [
                    "knowledge_match",
                    "target_knowledge_id",
                    "target_knowledge_name",
                    "target_skill",
                    "error_match",
                ]
            }
        )
        trace.update(
            difficulty_match=selected.get("difficulty") or "同年级",
            question_type_difference=selected["question_type"]
            != question["question_type"],
        )
        trace.update(
            {
                key: candidate[key]
                for key in ["dense_rank", "sparse_rank", "fusion_rank"]
            }
        )
        trace.update(
            {
                key: candidate["score_trace"][key]
                for key in ["structure_similarity", "reranker_score", "mode_score"]
            }
        )
        context.save_proof(
            db, question, prepared, selected, trace, trace["alignment_method"]
        )
        insert(
            db,
            "practice_recommendations",
            user_id=owner,
            mistake_id=id,
            dataset_question_id=selected["id"],
            mode=mode,
            retrieval_rank=candidate["fusion_rank"],
            retrieval_trace=trace,
        )
        output = payload(service, selected, mode, trace, candidate["knowledge_points"])
        if debug:
            output["debug"] = trace
        return output


@router.post("/attempt")
async def attempt_route(request: Request):
    return envelope(
        request, await run_in_threadpool(attempt, request, await body(request))
    )


def attempt(request, value):
    from .learning_evidence import apply_evidence, knowledge_point
    from .question_validation import number
    from .tutor_answers import handwriting

    mistake_id = text_value(value.get("mistake_id", ""), 100)
    id = text_value(value.get("question_id", ""), 100)
    mode = mode_value(value)
    if "student_answer" not in value:
        raise ApiError(422, "请提交作答")
    answer = value["student_answer"]
    duration = number(value.get("duration_seconds", 0))
    if not 0 <= duration <= 7200 or not duration.is_integer():
        raise ApiError(422, "整数超出允许范围")
    duration = int(duration)
    service = request.app.state.questions
    with service.database.session() as db, db.begin():
        owner = service.user(request, db).id
        found = select_rows(
            db,
            "questions",
            "SELECT * FROM questions WHERE id=? AND user_id=? AND status<>'archived' FOR UPDATE",
            [mistake_id, owner],
        )
        if not found:
            raise ApiError(404, "没有找到这道错题")
        mistake = found[0]
        generated = select_rows(
            db,
            "variant_questions",
            "SELECT v.* FROM variant_questions v JOIN tutor_sessions s ON s.id=v.session_id WHERE v.id=? AND v.question_id=? AND s.user_id=? AND s.stage='standalone_practice' FOR UPDATE",
            [id, mistake_id, owner],
        )
        if generated:
            handwriting(service, value, owner, id, kind="practice")
            return practice_generated.attempt(
                service, db, owner, mistake, generated[0], mode, answer, duration
            )
        questions = select_rows(
            db,
            "dataset_questions",
            "SELECT * FROM dataset_questions WHERE id=? FOR UPDATE",
            [id],
        )
        if not questions or questions[0].get("usable_for_auto_grade") is not True:
            raise ApiError(422, "这道题不能自动判分")
        question = questions[0]
        existing = select_rows(
            db,
            "dataset_practice_attempts",
            "SELECT * FROM dataset_practice_attempts WHERE user_id=? AND mistake_id=? AND dataset_question_id=? AND mode=? ORDER BY created_at DESC,id DESC LIMIT 1 FOR UPDATE",
            [owner, mistake_id, id, mode],
        )
        if existing:
            context.served(db, owner, mistake, id, mode)
            record = existing[0]
            details = record.get("grading_details") or {}
            saved = details.get("practice_receipt") or {}
            prepared = context.preparation(service, db, mistake, mode)
            if (
                source_equal(
                    (details.get("alignment_proof") or {}).get("context") or {},
                    context.proof_context(db, mistake, prepared, question),
                )
                and source_equal(record["student_answer"], answer)
                and saved
            ):
                return receipt(service, question, saved)
            raise ApiError(409, "这道练习已经完成，请换一道题继续练习")
        written = handwriting(service, value, owner, id, kind="practice")
        served = context.served(db, owner, mistake, id, mode)
        trace = served.get("retrieval_trace") or {}
        answer_seen = trace.get("answer_revealed") is True
        prepared = context.preparation(service, db, mistake, mode)
        target = trace.get("target_knowledge_id") or ""
        if (
            not usable(mistake, question, "practice")
            or not target
            or target != prepared.get("target_knowledge_id", "")
        ):
            raise ApiError(409, "学习目标或题目资格已变化，请重新获取练习")
        if not context.proof_valid(db, mistake, prepared, question, trace):
            checks = context.aligned(
                service, db, mistake, prepared, [{"question": question}]
            )
            method = context.alignment_method(checks, id)
            if not method:
                raise ApiError(
                    409,
                    "这道练习与当前学习目标不匹配，请重新获取练习；本次未更新学习记录",
                )
            context.save_proof(db, mistake, prepared, question, trace, method)
        if service.compute is None:
            raise ApiError(503, "内部算法服务未配置")
        grading = service.compute.compute(
            "grade_answer",
            text=question["question_text"],
            answer=answer,
            expected=question["answer"],
            subject=question["subject"],
            question_type=question["question_type"],
            options=question["options"],
            reference_solution=[
                line.strip()
                for line in question["solution"].split("\n")
                if line.strip()
            ],
        )
        decisive = grading.get("can_update_learning") is True
        execute(
            db,
            "UPDATE practice_recommendations SET retrieval_trace=JSON_SET(retrieval_trace,'$.answer_revealed',true),updated_at=UTC_TIMESTAMP(6) WHERE id=?",
            [served["id"]],
        )
        knowledge = select_rows(
            db,
            "knowledge_points",
            "SELECT * FROM knowledge_points WHERE id=? AND subject=? FOR UPDATE",
            [target, mistake["subject"]],
        )
        if not knowledge or knowledge[0]["name"] != prepared.get(
            "target_knowledge_name", ""
        ):
            raise ApiError(409, "练习知识点已变化，请重新获取练习")
        preferred = knowledge[0]["name"]
        point = knowledge_point(db, mistake, preferred, False)
        old = rows(
            db,
            "SELECT mastery_score FROM mastery_states WHERE user_id=? AND subject=? AND knowledge_point=? LIMIT 1",
            [owner, mistake["subject"].strip(), point],
        )
        before = float(old[0]["mastery_score"]) if old else 0.0
        mastery, aid = None, ""
        if decisive:
            sources = rows(
                db,
                "SELECT `key` FROM dataset_sources WHERE id=?",
                [question["dataset_source_id"]],
            )
            details = {
                **grading,
                "independent_answer": not answer_seen,
                "handwriting_image_url": service.media.url(written["image_url"]),
                "handwriting_recognition": written["recognition"],
                "alignment_method": trace["alignment_proof"]["method"],
                "target_knowledge_name": prepared["target_knowledge_name"],
                "alignment_proof": trace["alignment_proof"],
            }
            aid = insert(
                db,
                "dataset_practice_attempts",
                timestamp_microseconds=False,
                user_id=owner,
                mistake_id=mistake_id,
                dataset_question_id=id,
                source_dataset=sources[0]["key"] if sources else "unknown",
                knowledge_id=knowledge[0]["id"],
                mode=mode,
                student_answer=answer,
                correct=grading["correct"],
                duration_seconds=duration,
                grading_details=details,
            )
            if not answer_seen:
                evidence = {
                    "near_transfer" if mode == "reinforce" else "far_transfer": grading[
                        "correct"
                    ],
                    "hint_level": 0,
                    "strategy": "independent_dataset_practice",
                    "dataset_question_id": id,
                    "practice_attempt_id": aid,
                }
                mastery = apply_evidence(
                    service,
                    db,
                    owner,
                    mistake,
                    evidence,
                    preferred=preferred,
                    include_analysis=False,
                )["mastery_after"]["mastery_score"]
        result = {
            "correct": grading["correct"] if decisive else None,
            **{
                key: grading[key]
                for key in [
                    "verdict",
                    "can_update_learning",
                    "confidence",
                    "evidence",
                    "feedback",
                ]
            },
            "answer": question["answer"],
            "solution": question["solution"],
            **solution_images(service.media, question),
            "mastery_before": before,
            "mastery": mastery,
            "grading_method": grading["method"],
        }
        if answer_seen:
            result["learning_note"] = "已看过参考答案，这次练习不重复计入掌握情况。"
        if aid:
            execute(
                db,
                "UPDATE dataset_practice_attempts SET grading_details=JSON_SET(grading_details,'$.practice_receipt',JSON_EXTRACT(?,'$')) WHERE id=?",
                [compact(result), aid],
            )
        return result
