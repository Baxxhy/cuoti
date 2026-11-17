"""Administrator-only read projections and redacted teaching audit traces."""

from fastapi import APIRouter, Request

from .accounts import require_role
from .protocol import ApiError, envelope
from .question_data import rows, select_rows
from .system import state as system_state

router = APIRouter(prefix="/api/v1/admin")
SENSITIVE = [
    "credential",
    "password",
    "secret",
    "api_key",
    "apikey",
    "access_token",
    "refresh_token",
    "authorization",
    "chain_of_thought",
    "reasoning_content",
    "raw_prompt",
    "system_prompt",
]
LABELS = {
    "agent": {
        "mindtrace_tutor": "教学决策智能体",
        "diagnosis": "错因诊断智能体",
        "cognition": "认知建模智能体",
    },
    "branch": {
        "guided_question": "引导式提问",
        "direct_explanation": "直接讲解",
        "worked_example": "例题示范",
        "visualization": "可视化讲解",
        "teach_back": "学生复述",
        "near_transfer": "近迁移检验",
        "far_transfer": "远迁移检验",
        "review_schedule": "安排复习",
    },
    "tool": {
        "knowledge_search": "知识检索",
        "step_alignment": "步骤对齐",
        "visualization": "生成教学图示",
        "rediagnose": "动态再诊断",
        "answer_reveal": "答案与步骤核对",
        "answer_check": "数学结论验证",
        "variant_generator": "生成迁移题",
        "cognition_update": "更新认知状态",
        "review_scheduler": "生成复习计划",
    },
}


def sanitize(value):
    if isinstance(value, dict):
        return {
            key: sanitize(item)
            for key, item in value.items()
            if not any(part in key.lower() for part in SENSITIVE)
        }
    if isinstance(value, list):
        return [sanitize(item) for item in value]
    return value


def timestamp(value):
    return (
        value.removesuffix("+00:00").removesuffix(".000000")
        if isinstance(value, str)
        else value
    )


def fields(value, keys):
    return {
        key: timestamp(value.get(key))
        if key in ["created_at", "updated_at", "due_at"]
        else value.get(key)
        for key in keys
    }


def student_metrics(db, owner):
    return {
        key: int(
            rows(
                db,
                f"SELECT COUNT(*) AS total FROM {table} WHERE user_id=?" + extra,
                [owner],
            )[0]["total"]
        )
        for key, table, extra in [
            ("questions", "questions", " AND status<>'archived'"),
            ("sessions", "tutor_sessions", ""),
            ("pending_reviews", "review_plans", " AND status='pending'"),
        ]
    }


def trace(db, id):
    result = []
    for run in select_rows(
        db,
        "agent_runs",
        "SELECT * FROM agent_runs WHERE session_id=? ORDER BY created_at,id",
        [id],
    ):
        raw = run.get("result") or {}
        branch = raw.get("branch") if isinstance(raw.get("branch"), str) else ""
        item = {
            "id": run["id"],
            "time": timestamp(run["created_at"]),
            "agent": LABELS["agent"].get(run["agent_name"], run["agent_name"]),
            "status": run["status"],
            "decision": LABELS["branch"].get(branch, branch)
            if branch
            else "完成一次决策",
            "goal": next(
                (
                    raw[key]
                    for key in ["next_goal", "goal"]
                    if isinstance(raw.get(key), str) and raw[key]
                ),
                "",
            ),
        }
        item.update(
            {
                key: sanitize(raw.get(key, {}))
                for key in ["observation", "plan", "verification"]
            }
        )
        item["actions"] = [
            {
                "id": call["id"],
                "tool": LABELS["tool"].get(call["tool_name"], call["tool_name"]),
                "input": sanitize(call.get("input_json", {})),
                "output": sanitize(call.get("output_json", {})),
            }
            for call in select_rows(
                db,
                "agent_tool_calls",
                "SELECT * FROM agent_tool_calls WHERE agent_run_id=? ORDER BY created_at,id",
                [run["id"]],
            )
        ]
        result.append(item)
    return result


def student_data(db, id):
    users = select_rows(
        db, "users", "SELECT * FROM users WHERE id=? AND role='student'", [id]
    )
    if not users:
        raise ApiError(404, "未找到学生")
    profiles = select_rows(
        db, "student_profiles", "SELECT * FROM student_profiles WHERE user_id=?", [id]
    )
    profile = profiles[0] if profiles else {}
    student = fields(users[0], ["id", "name", "created_at"])
    student.update(
        grade=profile.get("grade", "未设置"),
        learning_goal=profile.get("learning_goal") or "",
    )
    mastery = []
    for item in select_rows(
        db,
        "mastery_states",
        "SELECT * FROM mastery_states WHERE user_id=? ORDER BY updated_at DESC,id DESC LIMIT 20",
        [id],
    ):
        mastery.append(
            {
                **fields(
                    item,
                    [
                        "subject",
                        "knowledge_point",
                        "confidence",
                        "forgetting_risk",
                        "evidence_count",
                    ],
                ),
                "score": item["mastery_score"],
            }
        )
    misconceptions = [
        fields(item, ["code", "label", "probability", "status", "evidence_count"])
        for item in select_rows(
            db,
            "misconception_states",
            "SELECT * FROM misconception_states WHERE user_id=? ORDER BY probability DESC,id DESC LIMIT 20",
            [id],
        )
    ]
    reviews = [
        fields(item, ["id", "question_id", "due_at", "status", "reason"])
        for item in select_rows(
            db,
            "review_plans",
            "SELECT * FROM review_plans WHERE user_id=? ORDER BY due_at,id LIMIT 20",
            [id],
        )
    ]
    return {
        "student": student,
        "metrics": student_metrics(db, id),
        "mastery": mastery,
        "misconceptions": misconceptions,
        "reviews": reviews,
    }


def session_data(db, id):
    sessions = select_rows(
        db, "tutor_sessions", "SELECT * FROM tutor_sessions WHERE id=?", [id]
    )
    if not sessions:
        raise ApiError(404, "未找到教学会话")
    session = sessions[0]
    owner, qid = session["user_id"], session["question_id"]
    users = select_rows(db, "users", "SELECT * FROM users WHERE id=?", [owner])
    questions = select_rows(
        db, "questions", "SELECT * FROM questions WHERE id=?", [qid]
    )
    diagnoses = select_rows(
        db,
        "diagnoses",
        "SELECT * FROM diagnoses WHERE question_id=? ORDER BY created_at DESC,id DESC LIMIT 1",
        [qid],
    )
    turns = [
        {
            **fields(item, ["id", "role", "content", "stage"]),
            "time": timestamp(item["created_at"]),
            "decision": sanitize(item.get("metadata_json", {})),
        }
        for item in select_rows(
            db,
            "tutor_turns",
            "SELECT * FROM tutor_turns WHERE session_id=? ORDER BY created_at,id",
            [id],
        )
    ]
    updates = [
        {
            **fields(
                item,
                ["id", "entity_type", "entity_key", "old_value", "new_value", "reason"],
            ),
            "time": timestamp(item["created_at"]),
        }
        for item in select_rows(
            db,
            "cognitive_updates",
            "SELECT * FROM cognitive_updates WHERE user_id=? AND question_id=? ORDER BY created_at,id",
            [owner, qid],
        )
    ]
    return {
        "session": fields(
            session,
            [
                "id",
                "stage",
                "status",
                "turn_count",
                "hint_level",
                "mastery_score",
                "created_at",
                "updated_at",
            ],
        ),
        "student": fields(users[0], ["id", "name"]) if users else None,
        "question": fields(
            questions[0],
            [
                "id",
                "title",
                "subject",
                "question_text",
                "student_answer",
                "knowledge_points",
            ],
        )
        if questions
        else None,
        "diagnosis": fields(
            diagnoses[0],
            [
                "first_error_step",
                "first_error_text",
                "error_type",
                "root_misconception",
                "confidence",
                "recommended_strategy",
            ],
        )
        if diagnoses
        else None,
        "turns": turns,
        "trace": trace(db, id),
        "cognitive_updates": updates,
    }


def workbench(request, db):
    metrics = {
        key: int(
            rows(db, f"SELECT COUNT(*) AS total FROM {table} WHERE {condition}")[0][
                "total"
            ]
        )
        for key, table, condition in [
            ("students", "users", "role='student'"),
            ("questions", "questions", "status<>'archived'"),
            ("diagnoses", "diagnoses", "1=1"),
            ("sessions", "tutor_sessions", "1=1"),
            ("active_sessions", "tutor_sessions", "status='active'"),
            ("agent_runs", "agent_runs", "1=1"),
            ("cognitive_updates", "cognitive_updates", "1=1"),
            ("pending_reviews", "review_plans", "status='pending'"),
        ]
    }
    students = []
    for user in select_rows(
        db,
        "users",
        "SELECT * FROM users WHERE role='student' ORDER BY updated_at DESC,id DESC LIMIT 50",
    ):
        profiles = rows(
            db, "SELECT grade FROM student_profiles WHERE user_id=?", [user["id"]]
        )
        counts = student_metrics(db, user["id"])
        students.append(
            {
                **fields(user, ["id", "name", "updated_at"]),
                "grade": profiles[0]["grade"] if profiles else "未设置",
                "question_count": counts["questions"],
                "session_count": counts["sessions"],
            }
        )
    sessions = []
    for row in rows(
        db,
        "SELECT s.*,u.name AS student_name,q.title AS question_title,q.subject AS question_subject FROM tutor_sessions s JOIN users u ON u.id=s.user_id JOIN questions q ON q.id=s.question_id ORDER BY s.updated_at DESC,s.id DESC LIMIT 50",
    ):
        sessions.append(
            {
                "id": row["id"],
                "stage": row["stage"],
                "status": row["status"],
                "updated_at": row["updated_at"].isoformat(),
                "student_id": row["user_id"],
                "student_name": row["student_name"],
                "question_id": row["question_id"],
                "question_title": row["question_title"],
                "subject": row["question_subject"],
                "turn_count": int(row["turn_count"]),
                "mastery_score": float(row["mastery_score"]),
            }
        )
    state = system_state(request)
    provider = state["provider"]
    return {
        "generated_at": rows(
            db,
            "SELECT DATE_FORMAT(UTC_TIMESTAMP(6),'%Y-%m-%dT%H:%i:%s.%f+00:00') AS generated_at",
        )[0]["generated_at"],
        "metrics": metrics,
        "students": students,
        "sessions": sessions,
        "system": {
            "database": "mysql",
            "provider": {
                **fields(
                    provider,
                    [
                        "logical_model",
                        "total_entries",
                        "text_entries",
                        "vision_entries",
                    ],
                ),
                "status": provider["last_status"],
            },
            "voice": fields(
                state["voice"], ["status", "loaded", "stt_model", "tts_model"]
            ),
        },
    }


def dispatch(request, kind, id=""):
    service = request.app.state.questions
    with service.database.session() as db, db.begin():
        require_role(service.user(request, db), "admin")
        return (
            student_data(db, id)
            if kind == "student"
            else session_data(db, id)
            if kind == "session"
            else workbench(request, db)
        )


@router.get("/workbench")
def workbench_route(request: Request):
    return envelope(request, dispatch(request, "workbench"))


@router.get("/students/{id}")
def student_route(request: Request, id: str):
    return envelope(request, dispatch(request, "student", id))


@router.get("/sessions/{id}")
def session_route(request: Request, id: str):
    return envelope(request, dispatch(request, "session", id))
