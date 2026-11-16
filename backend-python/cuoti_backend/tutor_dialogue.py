"""Two-phase teaching Agent computation with fresh source checks before writes."""

import base64

from fastapi import APIRouter, Request
from starlette.concurrency import run_in_threadpool

from .knowledge_mapping import dialogue_cards
from .learning_memory import audit_manifest, memory
from .lessons import compact
from .protocol import ApiError, envelope
from .question_data import insert, owned, select_rows, update
from .question_routes import body
from .question_validation import text_value
from .tutoring import session_owned

router = APIRouter(prefix="/api/v1/tutor/sessions")


def dialogue_snapshot(service, db, id, owner):
    session = session_owned(db, id, owner)
    if session["stage"] == "finished":
        raise ApiError(409, "本次学习已经完成")
    q = owned(db, session["question_id"], owner)
    if q["status"] == "archived" or session["state"].get("question_changed"):
        raise ApiError(409, "题目已变化或归档，请重新开始学习")
    qid = q["id"]
    analyses = select_rows(
        db,
        "problem_analyses",
        "SELECT * FROM problem_analyses WHERE question_id=?",
        [qid],
    )
    refs = select_rows(
        db,
        "reference_steps",
        "SELECT r.* FROM reference_steps r JOIN problem_analyses a ON a.id=r.analysis_id WHERE a.question_id=? ORDER BY r.step_index,r.id",
        [qid],
    )
    work = select_rows(
        db,
        "student_works",
        "SELECT * FROM student_works WHERE question_id=? ORDER BY created_at DESC,id DESC LIMIT 1",
        [qid],
    )
    steps = select_rows(
        db,
        "student_steps",
        "SELECT * FROM student_steps WHERE work_id=(SELECT id FROM student_works WHERE question_id=? ORDER BY created_at DESC,id DESC LIMIT 1) ORDER BY step_index,id",
        [qid],
    )
    assets = select_rows(
        db,
        "question_assets",
        "SELECT * FROM question_assets WHERE question_id=? AND kind IN ('crop','question_figure') ORDER BY created_at,id",
        [qid],
    )
    turns = select_rows(
        db,
        "tutor_turns",
        "SELECT * FROM tutor_turns WHERE session_id=? ORDER BY created_at DESC,id DESC LIMIT 7",
        [id],
    )
    records = memory(db, owner, q)
    return {
        "question": q,
        "analysis": analyses[0] if analyses else None,
        "references": refs,
        "session": session,
        "work": work[0] if work else None,
        "steps": steps,
        "assets": assets,
        "turns": turns,
        "memory": records["legacy_rows"],
        "memory_snapshot": records["snapshot"],
    }


def context(snapshot, message):
    q, analysis, session = (
        snapshot["question"],
        snapshot["analysis"] or {},
        snapshot["session"],
    )
    state = session["state"]
    points, seen = [], set()
    for container in [q, analysis]:
        for point in container.get("knowledge_points", []):
            key = compact(point)
            if key not in seen and len(points) < 10:
                points.append(point)
                seen.add(key)
    recent = [
        {"role": t["role"], "content": t["content"]}
        for t in reversed(snapshot["turns"])
    ]
    recent.append({"role": "user", "content": message})
    return {
        **{
            key: q[key]
            for key in ["subject", "question_type", "question_text", "student_answer"]
        },
        "knowledge_points": points,
        "grade": q.get("grade") or "",
        "final_answer": analysis.get("final_answer", ""),
        "reference_steps": [r["text"] for r in snapshot["references"]],
        "student_steps": [s["text"] for s in snapshot["steps"]],
        "student_message": message,
        "turn_count": session["turn_count"] + 1,
        "hint_level": session["hint_level"],
        "repeated_count": state.get("repeated_count", 0) + 1
        if message == state.get("last_message", "")
        else 0,
        "recent_turns": recent,
        "memory_snapshot": snapshot["memory_snapshot"],
    }


@router.post("/{id}/turns")
async def dialogue_route(request: Request, id: str):
    value = await body(request)
    return envelope(request, await run_in_threadpool(dialogue, request, id, value))


def dialogue(request, id, value):
    service = request.app.state.questions
    message = text_value(value.get("message", ""), 12000, trim=True)
    if not message:
        raise ApiError(422, "请输入你的想法")
    with service.database.session() as db, db.begin():
        owner = service.user(request, db).id
        before = dialogue_snapshot(service, db, id, owner)
    if service.compute is None:
        raise ApiError(503, "内部算法服务未配置")
    domain = context(before, message)
    inputs = {"dialogue_context": domain, "dialogue_memory_rows": before["memory"]}
    preparation = service.compute.compute("tutor_dialogue_prepare", **inputs)
    plan = preparation.get("plan") or {}
    knowledge = plan.get("tool_name") == "knowledge_search"
    with service.database.session() as db:
        cards = (
            dialogue_cards(
                db, preparation["knowledge_query"], domain["subject"], domain["grade"]
            )
            if knowledge
            else []
        )
    images = []
    for path in dict.fromkeys(asset["path"] for asset in before["assets"]):
        try:
            images.append(base64.b64encode(service.media.read(path)).decode())
        except ApiError as error:
            if error.status != 404:
                raise
    computed = service.compute.compute(
        "tutor_dialogue_finish",
        **inputs,
        dialogue_preparation=preparation,
        dialogue_cards=cards,
        images_base64=images,
    )
    with service.database.session() as db, db.begin():
        current = dialogue_snapshot(service, db, id, owner)
        if current != before:
            raise ApiError(409, "题目、会话或学习记录已变化，请刷新后重试")
        if knowledge and cards != dialogue_cards(
            db, preparation["knowledge_query"], domain["subject"], domain["grade"]
        ):
            raise ApiError(409, "知识卡已更新，请重试")
        session = current["session"]
        state, stage = session["state"], session["stage"]
        graph, agent = computed["graph"], computed["agent"]
        tool, verification = agent["tool"], agent["verification"]
        state.update(last_message=message, repeated_count=domain["repeated_count"])
        for key in ["branch", "strategy", "next_goal", "mastery_proven"]:
            state[key] = graph[key]
        state.setdefault("understanding_passed", False)
        state.update(
            dialogue_stage=graph["stage"],
            agent_verification=verification["status"],
            agent_memory_refs=plan["memory_source_ids"],
        )
        if plan["tool_name"] == "visualization":
            state["visualization_type"] = (tool.get("evidence") or {}).get(
                "visualization_type"
            )
        update(
            db,
            "tutor_sessions",
            id,
            stage=stage,
            turn_count=domain["turn_count"],
            hint_level=graph["hint_level"],
            state=state,
        )
        metadata = {
            key: graph[key]
            for key in ["branch", "strategy", "next_goal", "mastery_proven"]
        }
        metadata.update(
            knowledge_sources=computed.get("knowledge_sources", []),
            tool_name=plan["tool_name"],
            decision_verified=verification["status"],
            planner_status=agent["planner_status"],
        )
        for role, text, meta in [
            ("user", message, {"input_stage": stage}),
            ("assistant", computed["reply"], metadata),
        ]:
            insert(
                db,
                "tutor_turns",
                session_id=id,
                role=role,
                content=text,
                stage=stage,
                metadata_json=meta,
            )
        output = {
            **(tool.get("evidence") or {}),
            "stage": stage,
            "next_goal": graph["next_goal"],
            "executed": tool["executed"],
        }
        details = {
            "memory_manifest": audit_manifest(before["memory_snapshot"]),
            **{
                key: agent[key]
                for key in ["observation", "plan", "verification", "planner_status"]
            },
        }
        run_id = insert(
            db,
            "agent_runs",
            session_id=id,
            agent_name="mindtrace_tutor",
            status="completed",
            result={**output, "branch": graph["branch"], **details},
        )
        insert(
            db,
            "agent_tool_calls",
            agent_run_id=run_id,
            tool_name=plan["tool_name"],
            input_json=tool.get("consumed_input") or {},
            output_json=output,
        )
        return {
            "message": computed["reply"],
            "stage": stage,
            "hint_level": graph["hint_level"],
            **metadata,
        }
