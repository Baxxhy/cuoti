"""Persist validated transfer exercises and their retrieval evidence."""

import logging

from sqlalchemy.exc import SQLAlchemyError

from .protocol import ApiError
from .question_data import insert, select_rows, update
from .retrieval import candidates

logger = logging.getLogger("cuoti.backend")


def ensure_variant(service, db, session, detail, transfer):
    state = session["state"]
    points = (detail["analysis"] or {}).get("knowledge_points") or detail[
        "knowledge_points"
    ]
    if detail["status"] == "archived":
        raise ApiError(409, "题目已归档，不能生成新练习")
    if state.get("question_changed"):
        raise ApiError(409, "题目已变化，请重新开始学习")
    compute = service.compute
    if compute is None:
        raise ApiError(503, "内部算法服务未配置")
    existing = select_rows(
        db,
        "variant_questions",
        "SELECT * FROM variant_questions WHERE id=? AND session_id=?",
        [state.get(transfer + "_variant_id", ""), session["id"]],
    )
    if existing:
        item = existing[0]
        candidate = {
            key: item[key]
            for key in ["question_text", "answer", "explanation", "reference_solution"]
        }
        validation = compute.compute(
            "validate_variant",
            text=detail["question_text"],
            subject=detail["subject"],
            knowledge_points=points,
            variant_candidate=candidate,
        )
        if validation.get("valid") is True:
            state[transfer + "_validated_variant_id"] = item["id"]
            from .lessons import compact
            from .question_data import execute

            execute(
                db,
                "UPDATE tutor_sessions SET state=? WHERE id=?",
                [compact(state), session["id"]],
            )
            return item
        state.setdefault("invalidated_variant_ids", []).append(item["id"])
        state[transfer + "_variant_id"] = None
        state[transfer + "_validated_variant_id"] = None
    question = {
        key: value
        for key, value in detail.items()
        if key
        in [
            "id",
            "user_id",
            "subject",
            "grade",
            "question_text",
            "question_type",
            "knowledge_points",
            "student_answer",
            "options",
            "title",
            "status",
            "confirmed",
        ]
    }
    previous = select_rows(
        db,
        "variant_questions",
        "SELECT * FROM variant_questions WHERE question_id=?",
        [detail["id"]],
    )
    excluded = [
        id
        for item in previous
        for id in (item.get("generation_metadata") or {}).get("retrieval_ids", [])
    ]
    used = {item["question_text"] for item in previous}
    references, retrieval_status = [], "unavailable"
    try:
        ranked = candidates(
            service,
            db,
            question,
            detail["analysis"],
            excluded,
            "variant",
            "reinforce" if transfer == "near" else "variation",
        )
        references = [
            ref
            for ref in ranked.get("references", [])
            if ref.get("question_text") not in used
        ]
        retrieval_status = "ok"
    except (ApiError, SQLAlchemyError, ValueError, KeyError, TypeError):
        logger.info("variant_retrieval=unavailable")
    context = detail["question_text"] + "".join("；" + point for point in points)
    if detail.get("diagnosis"):
        context += "；" + detail["diagnosis"]["root_misconception"]
    computed = compute.compute(
        "generate_variant",
        text=context,
        subject=detail["subject"],
        question_type=detail["question_type"],
        transfer_type=transfer,
        knowledge_points=points,
        variant_references=references,
    )
    generated = computed["variant"]
    generation = {
        **computed["generation"],
        "retrieval_pipeline": "bge_m3_qdrant_reranker",
        "retrieval_status": retrieval_status,
    }
    id = insert(
        db,
        "variant_questions",
        question_id=detail["id"],
        session_id=session["id"],
        transfer_type=transfer,
        question_text=generated["question_text"],
        answer=generated["answer"],
        explanation=generated["explanation"],
        reference_solution=generated["reference_solution"],
        verified=computed["verified"],
        generation_metadata=generation,
    )
    state.update(
        {
            transfer + "_variant_id": id,
            transfer + "_validated_variant_id": id if computed["verified"] else None,
            transfer + "_attempts": 0,
            transfer + "_variant_generation": generation,
            transfer + "_variant_options": generated["options"],
            "activity_feedback": "",
        }
    )
    update(db, "tutor_sessions", session["id"], state=state)
    output = {"variant_id": id, "verified": computed["verified"], **generation}
    run_id = insert(
        db,
        "agent_runs",
        session_id=session["id"],
        agent_name="mindtrace_tutor",
        status="completed",
        result={**output, "branch": transfer + "_transfer_generated"},
    )
    insert(
        db,
        "agent_tool_calls",
        agent_run_id=run_id,
        tool_name="generate_variant",
        input_json={
            "transfer_type": transfer,
            "knowledge_points": points,
            "retrieval_pipeline": "bge_m3_qdrant_reranker",
        },
        output_json=output,
    )
    return select_rows(
        db, "variant_questions", "SELECT * FROM variant_questions WHERE id=?", [id]
    )[0]
