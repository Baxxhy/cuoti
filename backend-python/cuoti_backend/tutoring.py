"""Persisted tutoring sessions; stage gates belong to the application."""

from fastapi import APIRouter, Request
from learning_core.services.tutor_activities import (
    activity_public,
    build_understanding_plan,
    choice_answer_label,
)
from starlette.concurrency import run_in_threadpool

from .diagnostics import snapshot
from .protocol import ApiError, envelope
from .question_data import insert, select_rows, update
from .question_routes import body
from .question_validation import text_value

router = APIRouter(prefix="/api/v1/tutor/sessions")
PUBLIC = [
    "understood",
    "understanding_passed",
    "teach_back",
    "teach_back_passed",
    "near_transfer",
    "far_transfer",
    "next_goal",
    "strategy",
    "branch",
    "mastery_proven",
    "assisted",
    "understanding_index",
    "answer_reveal_acknowledged",
    "targeted_check_pending",
    "transfer_insufficient",
    "question_changed",
]
VISUALS = [
    ("勾股|直角三角形", "right_triangle"),
    ("圆周角|圆心角|圆", "circle"),
    ("坐标|中点|两点距离", "coordinate_geometry"),
    ("三角形|全等|相似", "triangle"),
    ("二次函数|抛物线", "quadratic_function"),
    ("一次函数|直线函数", "linear_function"),
    ("方程|等式|移项", "equation_balance"),
    ("匀加速|速度时间|v-t", "uniform_acceleration"),
    ("抛体|平抛|斜抛", "projectile_motion"),
    ("匀速|路程|s=vt", "uniform_motion"),
    ("受力|合力|支持力", "force_diagram"),
    ("机械能|动能|势能|功与能", "work_energy"),
    ("压强|压力", "pressure"),
    ("浮力|排液", "buoyancy"),
    ("时间轴|年代|先后顺序", "history_timeline"),
    ("时空|传播|地图", "timeline_map"),
]


def canonical(stage):
    value = stage.strip(" \t\r\n")
    return (
        {
            "teach_back_retry": "teach_back",
            "near_remediation": "near_transfer",
            "transfer_insufficient": "far_transfer",
        }.get(value, value)
        if value
        in [
            "teach_back",
            "teach_back_retry",
            "near_transfer",
            "near_remediation",
            "far_transfer",
            "transfer_insufficient",
            "finished",
        ]
        else "understanding"
    )


def policy(kind, options, working, answer):
    raw = kind.strip().lower()
    normalized = {
        "单选题": "choice",
        "选择题": "choice",
        "multiple-choice": "multiple_choice",
        "多选题": "multiple_choice",
        "填空题": "fill_blank",
        "计算题": "calculation",
        "证明题": "proof",
        "主观题": "subjective",
    }.get(raw, raw)
    if options and normalized in ["other", "综合题", ""]:
        normalized = "choice"
    normalized = normalized or "other"
    compressed = bool(answer.strip()) and (
        normalized in ["choice", "multiple_choice", "fill_blank"] or not working
    )
    return {
        "mode": "compressed" if compressed else "full",
        "question_type": normalized,
        "show_answer_immediately": bool(answer.strip()),
        "max_understanding_checks": 1 if compressed else 3,
        "skip_teach_back": compressed,
        "skip_far_transfer": compressed,
        "has_working": bool(working),
    }


def points(detail):
    return (detail["analysis"] or {}).get("knowledge_points") or detail[
        "knowledge_points"
    ]


def visualization(detail):
    context = " ".join(
        [detail["subject"], detail["question_type"], *points(detail)]
    ).lower()
    return next(
        (
            visual
            for words, visual in VISUALS
            if any(word in context for word in words.split("|"))
        ),
        None,
    )


def plan(detail):
    return build_understanding_plan(
        question_text=detail["question_text"],
        subject=detail["subject"],
        question_type=detail["question_type"],
        knowledge_points=points(detail),
        reference_steps=[r["text"] for r in detail["reference_steps"]],
    )


def current_activity(db, session, detail):
    state, stage = session["state"], session["stage"]
    feedback = state.get("activity_feedback", "")
    if stage == "understanding" and not state.get("understanding_passed"):
        if state.get("teaching_policy", {}).get("mode") == "compressed":
            if not state.get("answer_reveal_acknowledged"):
                return {
                    "id": "answer-reveal",
                    "type": "explanation",
                    "title": "先看清这次错在哪",
                    "question": "",
                    "options": [],
                    "attempt": 1,
                    "max_attempts": 1,
                    "feedback": "",
                    "teaching": "",
                }
            if state.get("targeted_check_pending"):
                check = state["teaching_brief"]["check"]
                return activity_public(
                    check,
                    attempt=state.get("activity_attempts", {}).get(check["id"], 0) + 1,
                    feedback=feedback,
                )
            return None
        activities = state.get("understanding_plan") or []
        if not activities:
            return None
        source = activities[
            max(0, min(state.get("understanding_index", 0), len(activities) - 1))
        ]
        if state.get("understanding_confirmation"):
            return activity_public(
                {
                    "id": source["id"] + "-confirmation",
                    "type": "single_choice",
                    "title": "确认一下就继续",
                    "question": "解题时，需要依据题目条件一步一步检查，对吗？",
                    "options": [
                        {"value": "yes", "label": "对，需要检查条件"},
                        {"value": "unsure", "label": "我还不确定"},
                    ],
                    "teaching": source.get("teaching", ""),
                },
                attempt=1,
                feedback=feedback,
            )
        return activity_public(
            source,
            attempt=state.get("activity_attempts", {}).get(source["id"], 0) + 1,
            feedback=feedback,
        )
    if stage == "teach_back":
        labels = points(detail)
        cube = any(
            "正方体" in value or "相对面" in value
            for value in [*labels, *[r["text"] for r in detail["reference_steps"]]]
        )
        return activity_public(
            {
                "id": "teach-back",
                "type": "teach_back",
                "title": "用一句话讲清楚",
                "question": "如果再遇到这种题，你会先看什么、再怎么判断？",
                "sentence_starter": "我会先看……",
                "keywords": ["相间", "Z字两端", "折叠"] if cube else labels[:3],
            },
            attempt=state.get("teach_back_attempts", 0) + 1,
            feedback=feedback,
        )
    if stage in ["near_transfer", "far_transfer"]:
        transfer = "near" if stage == "near_transfer" else "far"
        if transfer == "near" and state.get("near_confirmation"):
            return activity_public(
                state["near_confirmation"], attempt=1, feedback=feedback
            )
        matches = select_rows(
            db,
            "variant_questions",
            "SELECT * FROM variant_questions WHERE id=? AND session_id=?",
            [state.get(transfer + "_variant_id"), session["id"]],
        )
        if not matches:
            raise ApiError(503, "迁移练习尚未生成，请稍后重试")
        variant = matches[0]
        if state.get(transfer + "_validated_variant_id") != variant["id"]:
            raise ApiError(503, "练习需要重新验证，请稍后重试")
        options = state.get(transfer + "_variant_options") or []
        kind = (
            state.get("teaching_policy", {}).get("question_type")
            or detail["question_type"]
        )
        activity_type = (
            ("multiple_choice" if kind == "multiple_choice" else "single_choice")
            if options
            else "short_answer"
            if kind == "fill_blank"
            else "variant"
        )
        public_options = [
            {
                "value": o.get("label", ""),
                "label": o.get("label", "") + "  " + o.get("text", "")
                if o.get("label") and o.get("text")
                else o.get("label") or o.get("text", ""),
            }
            for o in options
        ]
        value = {
            "id": transfer + "-variant-" + variant["id"],
            "type": activity_type,
            "title": "相似题练习" if transfer == "near" else "换个场景试一试",
            "question": variant["question_text"],
            "options": public_options,
            "variant_id": variant["id"],
            "input_mode": "multiple_choice"
            if activity_type == "multiple_choice"
            else "choice"
            if activity_type == "single_choice"
            else kind,
            "teaching": state.get("transfer_guidance", ""),
        }
        if value["teaching"]:
            value["teaching_title"] = "我们一步一步写"
        return activity_public(
            value, attempt=state.get(transfer + "_attempts", 0) + 1, feedback=feedback
        )
    return None


def payload(service, db, session, detail):
    state = session["state"]
    figures = select_rows(
        db,
        "question_assets",
        "SELECT path FROM question_assets WHERE question_id=? AND kind IN ('question_figure','crop') ORDER BY (kind='question_figure') DESC,created_at DESC,id DESC LIMIT 1",
        [detail["id"]],
    )
    turns = select_rows(
        db,
        "tutor_turns",
        "SELECT * FROM tutor_turns WHERE session_id=? ORDER BY created_at,id",
        [session["id"]],
    )
    for turn in turns:
        meta = turn["metadata_json"] if isinstance(turn["metadata_json"], dict) else {}
        if meta.get("handwriting_image_url"):
            meta["handwriting_image_url"] = service.media.url(
                meta["handwriting_image_url"]
            )
    return {
        **session,
        "state": {key: state[key] for key in PUBLIC if key in state},
        "stage_status": "completed"
        if session["stage"] == "finished"
        else "passed"
        if session["stage"] == "understanding" and state.get("understanding_passed")
        else "active",
        "activity": current_activity(db, session, detail),
        "assisted": state.get("assisted", False),
        "teaching_policy": state.get("teaching_policy", {"mode": "full"}),
        "answer_reveal": state.get("answer_reveal"),
        "completion_summary": state.get("completion_summary", ""),
        "knowledge_title": " · ".join(points(detail)[:2]) or detail["title"],
        "visualization_available": visualization(detail) is not None,
        "question": {
            "id": detail["id"],
            "text": detail["question_text"],
            "figure_url": service.media.url("/" + figures[0]["path"])
            if figures
            else None,
        },
        "turns": turns,
    }


def session_owned(db, id, owner):
    matches = select_rows(
        db,
        "tutor_sessions",
        "SELECT * FROM tutor_sessions WHERE id=? AND user_id=? FOR UPDATE",
        [id, owner],
    )
    if not matches:
        raise ApiError(404, "教学会话不存在或无权访问")
    session = matches[0]
    session["stage"] = canonical(session["stage"])
    if not isinstance(session["state"], dict):
        session["state"] = {}
    return session


@router.get("/{id}")
def read(request: Request, id: str):
    service = request.app.state.questions
    with service.database.session() as db, db.begin():
        owner = service.user(request, db).id
        session = session_owned(db, id, owner)
        detail = service.detail(db, session["question_id"], owner)
        state = session["state"]
        state.setdefault("understanding_passed", False)
        state.setdefault("assisted", False)
        if state.get("teaching_policy", {}).get("mode") == "compressed" and state.get(
            "teaching_brief"
        ):
            state.setdefault("answer_reveal_acknowledged", False)
            state.setdefault("targeted_check_pending", False)
        elif not state.get("understanding_plan"):
            state.update(
                understanding_plan=plan(detail),
                understanding_index=0,
                activity_attempts={},
            )
        # Match legacy read normalization without advancing its timestamp.
        from .lessons import compact
        from .question_data import execute

        execute(
            db,
            "UPDATE tutor_sessions SET stage=?,state=? WHERE id=?",
            [session["stage"], compact(state), id],
        )
        return envelope(request, payload(service, db, session, detail))


@router.post("")
async def start_route(request: Request):
    value = await body(request)
    return envelope(request, await run_in_threadpool(start, request, value))


def start(request, value):
    service = request.app.state.questions
    id = text_value(value.get("question_id", ""), 36)
    with service.database.session() as db, db.begin():
        owner = service.user(request, db).id
        before = snapshot(service, db, id, owner)
        if (
            not before["analysis"]
            or not before["analysis"]["final_answer"].strip()
            or before["analysis"]["final_answer"].startswith("需要根据完整题目")
        ):
            raise ApiError(409, "请先完成题目分析，再开始学习")
    teaching = policy(
        before["question_type"],
        bool(before["options"]),
        bool(before["student_steps"]),
        before["analysis"]["final_answer"],
    )
    brief = None
    if teaching["mode"] == "compressed":
        if request.app.state.compute is None:
            raise ApiError(503, "内部算法服务未配置")
        brief = request.app.state.compute.compute(
            "teaching_brief",
            text=before["question_text"],
            student_answer=before["student_answer"],
            options=before["options"],
            question_type=teaching["question_type"],
            correct_answer=before["analysis"]["final_answer"],
            student_steps=[s["text"] for s in before["student_steps"]],
            knowledge_points=points(before),
            diagnosis=before["diagnosis"] or {},
        )["brief"]
        if not isinstance(brief, dict):
            raise ApiError(503, "教学简报不完整")
    reveal = (
        {
            key: brief[key]
            for key in [
                "topic",
                "correct_answer",
                "key_explanation",
                "option_explanations",
            ]
        }
        if brief
        else {
            "topic": points(before)[0] if points(before) else before["question_type"],
            "correct_answer": before["analysis"]["final_answer"].strip(),
            "key_explanation": "",
            "option_explanations": [],
        }
    )
    answer = before["student_answer"] or ""
    reveal["student_answer"] = (
        choice_answer_label(answer, before["options"])
        if brief and teaching["question_type"] in ["choice", "multiple_choice"]
        else answer or "未作答"
    )
    state = {
        "understood": False,
        "understanding_passed": False,
        "teach_back": None,
        "near_transfer": None,
        "far_transfer": None,
        "next_goal": "完成一个小问题",
        "strategy": "micro_activity",
        "branch": "opening",
        "mastery_proven": False,
        "last_message": "",
        "repeated_count": 0,
        "assisted": False,
        "understanding_index": 0,
        "activity_attempts": {},
        "activity_feedback": "",
        "answer_reveal_acknowledged": False,
        "targeted_check_pending": False,
        "teaching_policy": teaching,
        "teaching_brief": brief,
        "subject": before["subject"],
        "question_type": before["question_type"],
        "visualization_type": visualization(before),
        "understanding_plan": [] if brief else plan(before),
        "answer_reveal": reveal,
    }
    with service.database.session() as db, db.begin():
        if snapshot(service, db, id, owner) != before:
            raise ApiError(409, "题目或诊断已变化，请重新开始学习")
        sid = insert(
            db,
            "tutor_sessions",
            user_id=owner,
            question_id=id,
            stage="understanding",
            hint_level=0,
            turn_count=0,
            mastery_score=0,
            state=state,
            status="active",
        )
        insert(
            db,
            "tutor_turns",
            session_id=sid,
            role="assistant",
            content="先看清正确答案和刚才选项的关键差别。"
            if brief
            else "我们先只解决一个小问题。选出你认为正确的答案就可以。",
            stage="understanding",
            metadata_json={"branch": "opening", "next_goal": "解释首错步骤"},
        )
        diagnosis_id = before["diagnosis"]["id"] if before["diagnosis"] else None
        run_id = insert(
            db,
            "agent_runs",
            session_id=sid,
            agent_name="mindtrace_tutor",
            status="completed",
            result={"branch": "opening", "diagnosis_id": diagnosis_id},
        )
        insert(
            db,
            "agent_tool_calls",
            agent_run_id=run_id,
            tool_name="diagnosis_lookup",
            input_json={"question_id": id},
            output_json={"diagnosis_id": diagnosis_id},
        )
        return payload(service, db, session_owned(db, sid, owner), before)


@router.post("/{id}/advance")
async def advance_route(request: Request, id: str):
    value = await body(request)
    return envelope(
        request, await run_in_threadpool(navigate, request, id, value, False)
    )


@router.post("/{id}/rewind")
def rewind_route(request: Request, id: str):
    return envelope(request, navigate(request, id, {}, True))


def navigate(request, id, value, rewind):
    service = request.app.state.questions
    with service.database.session() as db, db.begin():
        owner = service.user(request, db).id
        session = session_owned(db, id, owner)
        state = session["state"]
        detail = service.detail(db, session["question_id"], owner)
        if detail["status"] == "archived" or state.get("question_changed"):
            raise ApiError(409, "题目已变化或归档，请重新开始学习")
        current = session["stage"]
        compressed = state.get("teaching_policy", {}).get("mode") == "compressed"
        if rewind:
            target = (
                "understanding"
                if compressed and current == "near_transfer"
                else {
                    "teach_back": "understanding",
                    "near_transfer": "teach_back",
                    "far_transfer": "near_transfer",
                }.get(current)
            )
            if target is None:
                raise ApiError(409, f"阶段 {current} 不能返回上一步")
        else:
            if value.get("target_stage") != "teach_back":
                raise ApiError(422, "只支持进入讲清阶段")
            if current != "understanding":
                raise ApiError(409, "当前不在理解阶段")
            if not state.get("understanding_passed"):
                raise ApiError(409, "需要先通过理解检查")
            target = "teach_back"
        branch = f"rewind_{current}_to_{target}" if rewind else "understanding_advance"
        message = "现在请用自己的话讲一遍：用了什么规则，为什么能用，又怎样得到结论。"
        if not rewind:
            state["next_goal"] = "用自己的话说明规则、依据和结论"
            insert(
                db,
                "tutor_turns",
                session_id=id,
                role="assistant",
                content=message,
                stage="teach_back",
                metadata_json={
                    "branch": "understanding_advance",
                    "explicit_transition": True,
                },
            )
        else:
            if current in ["teach_back", "near_transfer"]:
                state.update(
                    teach_back=None, teach_back_passed=None, teach_back_attempts=0
                )
            if current == "teach_back":
                state.update(
                    understanding_passed=True,
                    understood=True,
                    next_goal="回顾已经理解的关键点",
                )
            else:
                state.update(
                    near_transfer=None,
                    near_confirmation=None,
                    far_transfer=None,
                    near_attempts=0,
                    far_attempts=0,
                    next_goal="重新用自己的话说清关键判断"
                    if current == "near_transfer"
                    else "重新完成一道相似题",
                )
                if compressed and current == "near_transfer":
                    state.update(
                        understanding_passed=False,
                        understood=False,
                        answer_reveal_acknowledged=False,
                        targeted_check_pending=False,
                        next_goal="重新查看答案讲解",
                    )
            state["activity_feedback"] = (
                "已返回“"
                + {"understanding": "理解", "teach_back": "讲清"}.get(target, "练习")
                + "”。"
            )
        state["branch"] = branch
        update(db, "tutor_sessions", id, stage=target, state=state)
        tool_input = {"from": current}
        if not rewind:
            tool_input["event"] = "understanding_advance"
        run_id = insert(
            db,
            "agent_runs",
            session_id=id,
            agent_name="mindtrace_tutor",
            status="completed",
            result={"to": target, "branch": branch},
        )
        insert(
            db,
            "agent_tool_calls",
            agent_run_id=run_id,
            tool_name="rewind_tutor_stage" if rewind else "transition_tutor_stage",
            input_json=tool_input,
            output_json={"to": target},
        )
        if rewind:
            return payload(service, db, session_owned(db, id, owner), detail)
        return {"stage": target, "message": message, "next_goal": state["next_goal"]}
