"""Evidence-gated tutoring activities and transfer attempt persistence."""

import re

from fastapi import APIRouter, Request
from learning_core.services.academic_text import academic_summary
from starlette.concurrency import run_in_threadpool

from .learning_evidence import complete
from .protocol import ApiError, envelope
from .question_data import insert, select_rows, update
from .question_routes import body
from .question_validation import boolean, number, text_value
from .retrieval import answer_text
from .tutoring import PUBLIC, current_activity, payload, points, session_owned
from .variants import ensure_variant

router = APIRouter(prefix="/api/v1/tutor/sessions")


def handwriting(service, value, owner, sid):
    raw = text_value(value.get("handwriting_image_url", ""), 2048, trim=True)
    recognition = value.get("handwriting_recognition")
    if not raw:
        if recognition is not None:
            raise ApiError(422, "手写识别结果缺少对应原图")
        return {"image_url": "", "recognition": None}
    path = raw.split("?", 1)[0]
    prefix = f"/uploads/answers/{owner}/tutor/{sid}/handwriting-"
    if not re.fullmatch(re.escape(prefix) + r"[0-9a-f]{32}\.jpg", path):
        raise ApiError(422, "手写作答图片无效")
    try:
        service.media.read(path[1:])
    except ApiError:
        raise ApiError(422, "手写作答图片无效") from None
    if recognition is not None and not isinstance(recognition, dict):
        raise ApiError(422, "手写作答识别结果无效")
    return {
        "image_url": path,
        "recognition": service.compute.compute(
            "validate_handwriting", recognition=recognition or {}
        ),
    }


def micro(service, source, answer, detail):
    expected = source.get("correct_answers") or []
    result = service.compute.compute(
        "grade_answer",
        text=source.get("question") or detail["question_text"],
        answer=answer,
        expected=expected
        if source["type"] == "multiple_choice"
        else expected[0]
        if expected
        else "",
        subject=detail["subject"],
        question_type=source["type"],
        options=source.get("options", []),
    )
    return result.get("correct") is True and result.get("can_update_learning") is True


def transfer_answer(service, db, session, detail, answer, unknown, elapsed):
    state, stage = session["state"], session["stage"]
    near = stage == "near_transfer"
    kind = "near" if near else "far"
    skip_far = state.get("teaching_policy", {}).get("skip_far_transfer", False)
    passed, feedback, result = False, "", {}
    if near and isinstance(state.get("near_confirmation"), dict):
        state.update(near_confirmation=None, near_transfer=False, assisted=True)
        passed = True
        if skip_far:
            complete(service, db, session, detail, True)
            feedback = "本轮练习完成。"
        else:
            session["stage"] = "far_transfer"
            state["next_goal"] = "换个场景再试一次"
            ensure_variant(service, db, session, detail, "far")
            feedback = "继续换个场景练习。"
    else:
        records = select_rows(
            db,
            "variant_questions",
            "SELECT * FROM variant_questions WHERE id=? AND session_id=?",
            [state.get(kind + "_variant_id"), session["id"]],
        )
        if not records:
            raise ApiError(409, "练习已变化，请刷新后继续")
        variant = records[0]
        help_needed = unknown or any(
            phrase in answer_text(answer)
            for phrase in [
                "不会写",
                "不知道怎么写",
                "没有思路",
                "没思路",
                "教我写",
                "请教我",
                "不会做",
            ]
        )
        if help_needed:
            steps = [
                answer_text(s).strip()
                for s in variant["reference_solution"]
                if answer_text(s).strip()
            ][:6]
            steps = steps or [
                variant["explanation"] or "先找出已知条件，再列出关系式。"
            ]
            guidance = "可以按这个顺序写：" + "".join(
                f"\n{i + 1}. {step}" for i, step in enumerate(steps)
            )
            expected = answer_text(variant["answer"])
            if expected and expected not in guidance:
                guidance += f"\n{len(steps) + 1}. 得到结论：{expected}"
            state.update(transfer_guidance=guidance, assisted=True)
            result.update(
                assistant_content=guidance, attempt_consumed=False, unknown=True
            )
            feedback = "不会写没关系，先按提示一步步写，这次不计作答次数。"
        else:
            state["transfer_guidance"] = None
            grading = service.compute.compute(
                "grade_answer",
                text=variant["question_text"],
                answer=answer,
                expected=variant["answer"],
                reference_solution=variant["reference_solution"],
                subject=detail["subject"],
                question_type=detail["question_type"],
                options=state.get(kind + "_variant_options") or [],
            )
            result["grading"] = grading
            feedback = grading.get("feedback", "")
            if grading.get("can_update_learning") is not True:
                state["last_grading"] = grading
                result["attempt_consumed"] = False
            else:
                passed = grading.get("correct") is True
                count = state.get(kind + "_attempts", 0) + 1
                state[kind + "_attempts"] = count
                result["attempt_consumed"] = True
                insert(
                    db,
                    "variant_attempts",
                    variant_id=variant["id"],
                    user_id=session["user_id"],
                    answer=answer_text(answer),
                    correct=passed,
                    elapsed_seconds=elapsed,
                    hint_level=session["hint_level"],
                )
                if passed:
                    state[stage] = True
                    if near and not skip_far:
                        session["stage"] = "far_transfer"
                        state["next_goal"] = "换个场景再试一次"
                        ensure_variant(service, db, session, detail, "far")
                        feedback = "相似题做对了，换个场景再试一次。"
                    else:
                        complete(service, db, session, detail, False)
                        feedback = "练习完成，本轮学习结束。"
                elif count >= 2:
                    state.update({stage: False, "assisted": True})
                    if near and not skip_far:
                        state["near_confirmation"] = {
                            "id": "near-remediation-" + variant["id"],
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
                            "teaching": variant["explanation"],
                        }
                        feedback = "先看简短讲解，确认后继续。"
                    else:
                        state["transfer_insufficient"] = True
                        complete(service, db, session, detail, True)
                        feedback = "本轮学习结束，已安排近期复习。"
    return {**result, "passed": passed, "feedback": feedback}


@router.post("/{id}/activity/answer")
async def answer_route(request: Request, id: str):
    value = await body(request, maximum=2 * 1024 * 1024)
    return envelope(
        request, await run_in_threadpool(answer_activity, request, id, value)
    )


def answer_activity(request, id, value):
    answer = value.get("answer", "")
    if isinstance(answer, list):
        if len(answer) > 100:
            raise ApiError(422, "选项数量过多")
        for item in answer:
            text_value(item, 12000)
    else:
        text_value(answer, 12000)
    working = text_value(value.get("working", ""), 12000, trim=True)
    elapsed = number(value.get("elapsed_seconds", 0))
    if not 0 <= elapsed <= 2147483647:
        raise ApiError(422, "作答时长无效")
    unknown = (
        boolean(value.get("unknown", False)) or answer_text(answer) == "__unknown__"
    )
    service = request.app.state.questions
    with service.database.session() as db, db.begin():
        owner = service.user(request, db).id
        session = session_owned(db, id, owner)
        state, stage = session["state"], session["stage"]
        if stage not in [
            "understanding",
            "teach_back",
            "near_transfer",
            "far_transfer",
        ]:
            raise ApiError(409, "当前阶段不能继续作答")
        detail = service.detail(db, session["question_id"], owner)
        if state.get("question_changed") or detail["status"] == "archived":
            raise ApiError(409, "题目已变化或归档，请重新开始学习")
        if service.compute is None:
            raise ApiError(503, "内部算法服务未配置")
        activity = current_activity(service, db, session, detail)
        if not activity or value.get("activity_id") != activity["id"]:
            raise ApiError(409, "当前小任务已经变化，请刷新后继续")
        image = handwriting(service, value, owner, id)
        passed, feedback, transfer = False, "", {}
        compressed = state.get("teaching_policy", {}).get("mode") == "compressed"
        if stage in ["near_transfer", "far_transfer"]:
            transfer = transfer_answer(
                service, db, session, detail, answer, unknown, int(elapsed)
            )
            passed, feedback = transfer["passed"], transfer["feedback"]
        elif stage == "teach_back":
            result = service.compute.compute(
                "evaluate_teach_back",
                text=answer_text(answer).strip(),
                subject=detail["subject"],
                question_type=detail["question_type"],
                teach_back_points=points(detail),
                reference_solution=[r["text"] for r in detail["reference_steps"]],
            )
            passed = result.get("passed") is True
            count = state.get("teach_back_attempts", 0) + 1
            state["teach_back_attempts"] = count
            if passed or count >= 2:
                state.update(
                    teach_back=passed,
                    teach_back_passed=passed,
                    next_goal="完成一道相似题",
                )
                if not passed:
                    state["assisted"] = True
                session["stage"] = "near_transfer"
                feedback = (
                    "讲清楚了，接着做一道相似题。"
                    if passed
                    else "这次还少一个关键点，我先记录下来，我们继续练一道相似题。"
                )
            else:
                feedback = result["feedback"]
        elif compressed and activity["type"] == "explanation":
            state["answer_reveal_acknowledged"] = True
            passed = True
            if answer_text(answer) == "need_help":
                state["targeted_check_pending"] = True
                feedback = "只确认一个易错点。"
            else:
                state.update(
                    understanding_passed=True,
                    understood=True,
                    near_transfer=None,
                    next_goal="做一道相似题",
                )
                session["stage"] = "near_transfer"
                feedback = "好，直接练一道。"
        elif compressed and state.get("targeted_check_pending"):
            source = state["teaching_brief"]["check"]
            passed = not unknown and micro(service, source, answer, detail)
            attempts = state.setdefault("activity_attempts", {})
            count = attempts.get(source["id"], 0) + 1
            attempts[source["id"]] = count
            if passed or count >= 2 or unknown:
                if not passed:
                    state["assisted"] = True
                state.update(
                    targeted_check_pending=False,
                    understanding_passed=True,
                    understood=True,
                    near_transfer=None,
                    next_goal="做一道相似题",
                )
                session["stage"] = "near_transfer"
                feedback = (
                    "答对了，练一道类似的。"
                    if passed
                    else "记住这个条件，我们直接练一道。"
                )
            else:
                feedback = academic_summary(
                    source.get("hint") or "再用刚才的关键条件判断一次。", 70
                )
        else:
            index = state.get("understanding_index", 0)
            plan = state.get("understanding_plan") or []
            if not 0 <= index < len(plan):
                raise ApiError(409, "活动计划已变化，请刷新")
            source = plan[index]
            if state.get("understanding_confirmation"):
                state.update(
                    assisted=True,
                    understanding_confirmation=False,
                    understanding_index=index + 1,
                )
                passed, feedback = True, "记住这个判断方法，我们继续下一个小问题。"
            else:
                passed = not unknown and micro(service, source, answer, detail)
                attempts = state.setdefault("activity_attempts", {})
                count = attempts.get(source["id"], 0) + 1
                attempts[source["id"]] = count
                if passed:
                    state["understanding_index"] = index + 1
                    feedback = "答对了，我们继续。"
                elif unknown or count >= 2:
                    state.update(understanding_confirmation=True, assisted=True)
                    feedback = "先看一个最短讲解，再确认一次就继续。"
                else:
                    feedback = (
                        academic_summary(source.get("hint", ""), 70)
                        if source.get("hint")
                        else ""
                    )
            if state.get("understanding_index", 0) >= len(plan):
                state.update(
                    understanding_passed=True,
                    understood=True,
                    next_goal="用自己的话说一遍",
                )
                feedback = "已经抓住这个关键点。"
        if session["stage"] == "near_transfer":
            ensure_variant(service, db, session, detail, "near")
        state.update(
            activity_feedback=feedback,
            branch="activity_"
            + session["stage"]
            + ("_pass" if passed else "_continue"),
        )
        update(
            db,
            "tutor_sessions",
            id,
            stage=session["stage"],
            state=state,
            turn_count=session["turn_count"] + 1,
        )
        user_meta = {
            "activity_id": activity["id"],
            "activity_type": activity["type"],
            "working": working[:500],
            "handwriting_image_url": image["image_url"],
            "handwriting_recognition": image["recognition"],
            "grading": transfer.get("grading", {}),
        }
        if "attempt_consumed" in transfer:
            user_meta["attempt_consumed"] = transfer["attempt_consumed"]
        if transfer.get("unknown"):
            user_meta["unknown"] = True
        labels = {
            option.get("value"): option.get("label", "")
            for option in activity.get("options", [])
        }
        content = "、".join(
            labels.get(item, answer_text(item))
            for item in (answer if isinstance(answer, list) else [answer])
        )
        for role, text, meta in [
            ("user", content, user_meta),
            (
                "assistant",
                transfer.get("assistant_content") or feedback,
                {
                    "activity_id": activity["id"],
                    "passed": passed,
                    "assisted": state.get("assisted", False),
                },
            ),
        ]:
            insert(
                db,
                "tutor_turns",
                session_id=id,
                role=role,
                content=text,
                stage=session["stage"],
                metadata_json=meta,
            )
        return payload(service, db, session_owned(db, id, owner), detail)


@router.post("/{id}/finish")
async def finish_route(request: Request, id: str):
    await body(request, empty=True)
    return envelope(request, await run_in_threadpool(finish, request, id))


def finish(request, id):
    service = request.app.state.questions
    with service.database.session() as db, db.begin():
        owner = service.user(request, db).id
        session = session_owned(db, id, owner)
        if session["stage"] != "finished":
            raise ApiError(409, "请先完成讲清、相似题和综合应用")
        state = session["state"]
        if session["status"] == "completed":
            plans = select_rows(
                db,
                "review_plans",
                "SELECT * FROM review_plans WHERE user_id=? AND question_id=? ORDER BY created_at DESC,id DESC LIMIT 1",
                [owner, session["question_id"]],
            )
            return {
                "session": {
                    **session,
                    "state": {key: state[key] for key in PUBLIC if key in state},
                },
                "mastery": None,
                "review": plans[0] if plans else None,
            }
        detail = service.detail(db, session["question_id"], owner)
        if state.get("question_changed") or detail["status"] == "archived":
            raise ApiError(409, "题目已变化或归档，请重新开始学习")
        result = complete(
            service,
            db,
            session,
            detail,
            state.get("transfer_insufficient") is True
            or state.get("far_transfer") is False,
        )
        update(db, "tutor_sessions", id, stage=session["stage"], state=state)
        saved = session_owned(db, id, owner)
        return {
            "session": {
                **saved,
                "state": {
                    key: saved["state"][key] for key in PUBLIC if key in saved["state"]
                },
            },
            "mastery": result["mastery"],
            "review": result["review"],
        }
