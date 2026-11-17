"""Standalone transfer submissions, preserving the existing variant API contract."""

from fastapi import APIRouter, Request
from starlette.concurrency import run_in_threadpool

from .learning_evidence import complete
from .protocol import ApiError, envelope
from .question_data import insert, select_rows, update
from .question_routes import body
from .question_validation import number, text_value
from .retrieval import answer_text
from .tutoring import session_owned
from .variants import ensure_variant

router = APIRouter(prefix="/api/v1/variants")


def bounded(value, label):
    result = number(value)
    if not 0 <= result <= 2147483647:
        raise ApiError(422, label + "无效")
    return int(result)


@router.post("/{id}/attempt")
async def attempt_route(request: Request, id: str):
    return envelope(
        request, await run_in_threadpool(attempt, request, id, await body(request))
    )


def attempt(request, id, value):
    answer = text_value(value.get("answer", ""), 12000)
    elapsed = bounded(value.get("elapsed_seconds", 0), "作答时长")
    service = request.app.state.questions
    with service.database.session() as db, db.begin():
        owner = service.user(request, db).id
        variants = select_rows(
            db,
            "variant_questions",
            "SELECT v.* FROM variant_questions v JOIN tutor_sessions s ON s.id=v.session_id WHERE v.id=? AND s.user_id=?",
            [id, owner],
        )
        if not variants:
            raise ApiError(404, "迁移题不存在或无权访问")
        variant = variants[0]
        session = session_owned(db, variant["session_id"], owner)
        state, transfer = session["state"], variant["transfer_type"]
        if session["stage"] != transfer + "_transfer":
            raise ApiError(409, "这道练习与当前教学阶段不匹配")
        current = state.get(transfer + "_variant_id") or ""
        if current and current != id:
            raise ApiError(409, "这道练习已经变化，请刷新")
        question = service.detail(db, session["question_id"], owner)
        if state.get("question_changed") is True or question["status"] == "archived":
            raise ApiError(409, "题目已变化或归档，请重新开始学习")
        hints = bounded(value.get("hint_level", session["hint_level"]), "提示等级")
        if service.compute is None:
            raise ApiError(503, "内部算法服务未配置")
        grading = service.compute.compute(
            "grade_answer",
            text=variant["question_text"],
            answer=answer,
            expected=variant["answer"],
            reference_solution=variant["reference_solution"],
            subject=question["subject"],
            question_type=question["question_type"],
        )
        decisive, correct = (
            grading.get("can_update_learning") is True,
            grading.get("correct") is True,
        )
        feedback = grading["feedback"]
        branch = (
            transfer
            + "_transfer_"
            + ("review_required" if not decisive else "pass" if correct else "fail")
        )
        saved_attempt = None
        if decisive:
            aid = insert(
                db,
                "variant_attempts",
                timestamp_microseconds=False,
                variant_id=id,
                user_id=owner,
                answer=answer,
                correct=correct,
                elapsed_seconds=elapsed,
                hint_level=hints,
            )
            saved_attempt = select_rows(
                db,
                "variant_attempts",
                "SELECT * FROM variant_attempts WHERE id=?",
                [aid],
            )[0]
            count = state.get(transfer + "_attempts", 0) + 1
            state.update({transfer + "_attempts": count, "branch": branch})
            if transfer == "near" and correct:
                state["near_transfer"] = True
                session["stage"] = "far_transfer"
                ensure_variant(service, db, session, question, "far")
            elif transfer == "near" and count >= 2:
                state.update(
                    near_transfer=False,
                    assisted=True,
                    near_confirmation={
                        "id": "near-remediation-" + id,
                        "type": "single_choice",
                        "title": "看懂这一步就继续",
                        "question": "根据刚才的讲解，这道题的参考结论是什么？",
                        "options": [
                            {
                                "value": "expected",
                                "label": answer_text(variant["answer"]),
                            },
                            {"value": "unsure", "label": "我还不能确定"},
                        ],
                        "correct_answers": ["expected"],
                        "hint": "",
                        "teaching": variant["explanation"]
                        or "先对照题目条件，再按顺序完成关键步骤。",
                    },
                )
                feedback = "先看这道题的简短讲解，再完成一个简单确认。"
            elif transfer == "far" and (correct or count >= 2):
                state["far_transfer"] = correct
                if not correct:
                    state.update(transfer_insufficient=True, assisted=True)
                complete(service, db, session, question, not correct)
                if not correct:
                    feedback = (
                        "这次换一种题目还不稳定，本轮先结束，并提高后续复习优先级。"
                    )
            update(
                db,
                "tutor_sessions",
                session["id"],
                timestamp_microseconds=False,
                stage=session["stage"],
                state=state,
            )
        user_meta = {"branch": branch, "variant_id": id}
        assistant_meta = {"branch": branch}
        if not decisive:
            user_meta.update(grading=grading, attempt_consumed=False)
            assistant_meta["grading_verdict"] = grading["verdict"]
        else:
            assistant_meta["correct"] = correct
        for role, content, stage, metadata in [
            ("user", answer, transfer + "_transfer", user_meta),
            ("assistant", feedback, session["stage"], assistant_meta),
        ]:
            insert(
                db,
                "tutor_turns",
                session_id=session["id"],
                role=role,
                content=content,
                stage=stage,
                metadata_json=metadata,
            )
        if decisive:
            output = {"correct": correct, "stage": session["stage"]}
            run = insert(
                db,
                "agent_runs",
                timestamp_microseconds=False,
                session_id=session["id"],
                agent_name="mindtrace_tutor",
                status="completed",
                result={**output, "branch": branch},
            )
            insert(
                db,
                "agent_tool_calls",
                timestamp_microseconds=False,
                agent_run_id=run,
                tool_name="grade_answer",
                input_json={"variant_id": id, "answer": answer},
                output_json=output,
            )
        result = {
            "attempt": saved_attempt,
            "correct": correct if decisive else None,
            "branch": branch,
            "stage": session["stage"],
            "feedback": feedback,
            "grading": grading,
        }
        for key, table in [
            ("mastery", "mastery_states"),
            ("misconception", "misconception_states"),
        ]:
            states = (
                select_rows(
                    db,
                    table,
                    f"SELECT * FROM {table} WHERE user_id=? ORDER BY updated_at DESC,id DESC LIMIT 1",
                    [owner],
                )
                if decisive
                else []
            )
            result[key] = states[0] if states else None
        return result
