"""Persist validated visualization specs; the frontend only receives JSON."""

from fastapi import APIRouter, Request
from starlette.concurrency import run_in_threadpool

from .protocol import ApiError, envelope
from .question_data import insert, select_rows
from .question_routes import body
from .question_validation import text_value
from .retrieval import answer_text
from .tutoring import points

router = APIRouter(prefix="/api/v1")


def config(service, question, labels, values):
    if service.compute is None:
        raise ApiError(503, "内部算法服务未配置")
    return service.compute.compute(
        "visualization_config",
        subject=question["subject"],
        question_type=question["question_type"],
        teach_back_points=[answer_text(item) for item in labels],
        visualization_values=values,
    )


@router.get("/visualizations/types")
def types(request: Request):
    return envelope(
        request,
        config(
            request.app.state.questions,
            {"subject": "数学", "question_type": "综合题"},
            [],
            {},
        )["catalog"],
    )


@router.get("/tutor/sessions/{id}/visualization")
def current(request: Request, id: str):
    return envelope(request, session_visualization(request, id, {}, False))


@router.post("/tutor/sessions/{id}/visualization")
async def save_route(request: Request, id: str):
    return envelope(
        request,
        await run_in_threadpool(
            session_visualization, request, id, await body(request, empty=True), True
        ),
    )


def session_visualization(request, id, value, writing):
    values = value.get("values", {})
    if not isinstance(values, dict):
        raise ApiError(422, "演示参数格式不正确")
    observation = text_value(value.get("observation", ""), 12000)
    service = request.app.state.questions
    with service.database.session() as db, db.begin():
        owner = service.user(request, db).id
        sessions = select_rows(
            db,
            "tutor_sessions",
            "SELECT * FROM tutor_sessions WHERE id=? AND user_id=?",
            [id, owner],
        )
        if not sessions:
            raise ApiError(404, "教学会话不存在或无权访问")
        session = sessions[0]
        question = service.detail(db, session["question_id"], owner)
        if writing and (
            (session.get("state") or {}).get("question_changed") is True
            or question["status"] == "archived"
        ):
            raise ApiError(409, "题目已变化或归档，请重新开始学习")
        spec = config(service, question, points(question), values)["spec"]
        if not isinstance(spec, dict):
            raise ApiError(404, "这道题暂时没有匹配的互动演示")
        if not writing:
            return {
                "question": {
                    key: question[key] for key in ["id", "title", "question_text"]
                },
                "spec": spec,
            }
        vid = insert(
            db,
            "visualization_specs",
            timestamp_microseconds=False,
            session_id=id,
            type=spec["type"],
            title=spec["title"],
            spec=spec,
        )
        if observation:
            iid = insert(
                db,
                "visualization_interactions",
                timestamp_microseconds=False,
                visualization_id=vid,
                user_id=owner,
                values=values,
                observation=observation,
            )
            output = {
                "interaction_id": iid,
                "observation": observation,
                "expected_observation": spec["expected_observation"],
            }
            rid = insert(
                db,
                "agent_runs",
                timestamp_microseconds=False,
                session_id=id,
                agent_name="mindtrace_tutor",
                status="completed",
                result={**output, "branch": "visualization_evidence"},
            )
            insert(
                db,
                "agent_tool_calls",
                timestamp_microseconds=False,
                agent_run_id=rid,
                tool_name="observe_visualization",
                input_json={"type": spec["type"], "values": values},
                output_json=output,
            )
        return select_rows(
            db,
            "visualization_specs",
            "SELECT * FROM visualization_specs WHERE id=?",
            [vid],
        )[0]


@router.get("/visualizations/{id}")
def read(request: Request, id: str):
    service = request.app.state.questions
    with service.database.session() as db:
        owner = service.user(request, db).id
        found = select_rows(
            db,
            "visualization_specs",
            "SELECT v.* FROM visualization_specs v JOIN tutor_sessions s ON s.id=v.session_id WHERE v.id=? AND s.user_id=?",
            [id, owner],
        )
        if not found:
            raise ApiError(404, "可视化不存在或无权访问")
        result = found[0]
        result["interactions"] = select_rows(
            db,
            "visualization_interactions",
            "SELECT * FROM visualization_interactions WHERE visualization_id=? ORDER BY created_at,id",
            [id],
        )
        return envelope(request, result)
