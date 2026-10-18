from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from fastapi import (
    BackgroundTasks,
    Body,
    Depends,
    FastAPI,
    File,
    Form,
    Header,
    HTTPException,
    Query,
    UploadFile,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import Text, cast, delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import create_access_token, hash_password, verify_password
from app.config import settings
from app.db import SessionLocal, engine, get_db
from app.learning_api import create_learning_router
from app.media import SignedStaticFiles, sign_media_url
from app.models import (
    AgentRun,
    AgentToolCall,
    AssignmentStudent,
    Base,
    CognitiveUpdate,
    DatasetPracticeAttempt,
    DatasetQuestion,
    DatasetSource,
    Diagnosis,
    DiagnosisEvidence,
    ExportJob,
    GuardianStudentLink,
    KnowledgePoint,
    KnowledgeRelation,
    MasteryState,
    MisconceptionState,
    OCRRun,
    Paper,
    PaperItem,
    PracticeRecommendation,
    ProblemAnalysis,
    ProcessingJob,
    Question,
    QuestionAsset,
    QuestionAssignment,
    QuestionKnowledgeLink,
    ReferenceStep,
    ReviewPlan,
    ReviewRecord,
    StudentProfile,
    StudentStep,
    StudentWork,
    TeacherClass,
    TeacherClassStudent,
    TeacherMark,
    TeacherReviewResult,
    TeacherReviewTask,
    TutorSession,
    TutorTurn,
    User,
    UserQuestionKnowledgeLink,
    VariantAttempt,
    VariantQuestion,
    VisualizationInteraction,
    VisualizationSpec,
    VoiceRecord,
)
from app.providers.api_pool import ApiPoolProvider, ApiPoolUnavailable
from app.request_schemas import CropRequest, QuestionEditRequest, validated_body
from app.request_validation import (
    LoginRequest,
    PaperCreateRequest,
    PaperUpdateRequest,
    RegisterRequest,
    validated_payload,
)
from app.schemas import (
    PracticeAttemptRequest,
    PracticeRecommendRequest,
    VariantOutput,
    VisualizationPayload,
)
from app.services.access_control import authenticated_account, authorize_api_request, owned_resource
from app.services.admin_workbench import get_admin_session, get_admin_student, get_admin_workbench
from app.services.agent_runtime import (
    AgentToolContext,
    ground_reply_with_tool,
    load_long_term_memory,
    run_agent_turn,
)
from app.services.ai_pipeline import analyze_question, diagnose_steps, generate_tutor_guidance
from app.services.answer_handwriting import validate_answer_handwriting
from app.services.cognition import cognition_target, update_cognition
from app.services.counterfactual import validate_first_error_counterfactual
from app.services.diagnosis import align_steps, equation_equivalent
from app.services.export import build_excel, build_pdf
from app.services.grading import grade_answer
from app.services.handwritten_answer import recognize_handwritten_answer
from app.services.image_recognition import recognize_cropped_question
from app.services.knowledge_base import search_knowledge_cards
from app.services.pedagogy import (
    error_codes_for_label,
    evaluate_teach_back,
)
from app.services.personal_knowledge_graph import sync_personal_knowledge_links
from app.services.practice_retrieval import (
    hybrid_ids,
    load_candidates,
    rerank_candidates,
    retrieve_variant_references,
)
from app.services.question_bank_import import normalize_choice_options
from app.services.question_lifecycle import (
    invalidate_question_learning,
    learning_source_fingerprint,
    recognition_question_for_write,
    recover_interrupted_recognition,
)
from app.services.question_mapping import student_facing_topic
from app.services.recognition_jobs import (
    active_recognition_job,
    crop_box,
    lock_recognition_question,
    same_crop,
)
from app.services.timestamps import iso_timestamp
from app.services.tutor_activities import (
    activity_public,
    adaptive_teaching_policy,
    answer_reveal_activity,
    build_adaptive_teaching_brief,
    build_understanding_plan,
    build_writing_guidance,
    choice_answer_label,
    confirmation_activity,
    remediation_confirmation,
    teach_back_activity,
    writing_help_requested,
)
from app.services.tutor_graph import ensure_fresh_tutor_reply, run_tutor_step
from app.services.tutor_state import canonical_tutor_stage, previous_tutor_stage, transition_tutor_stage
from app.services.variants import generate_variant, verify_knowledge_alignment, verify_variant
from app.services.vision import (
    MAX_UPLOAD_BYTES,
    VISUAL_REGION_KINDS,
    crop_image,
    persist_recognition_regions,
    preprocess_image,
    save_original,
)
from app.services.visualizations import recommended_visualization, visualization_catalog, visualization_spec
from app.services.voice import voice_provider
from app.teacher_api import create_teacher_router

settings.upload_dir.mkdir(parents=True, exist_ok=True)
Path("reports").mkdir(exist_ok=True)
provider = ApiPoolProvider(settings.api_pool_path, allowed_hosts={"api.chat.csu.edu.cn"})
logger = logging.getLogger("uvicorn.error").getChild("recognition")


def envelope(data: Any = None) -> dict[str, Any]:
    return {"success": True, "data": data, "error": None, "request_id": str(uuid.uuid4())}


def row_dict(row: Any) -> dict[str, Any]:
    result = {column.name: getattr(row, column.name) for column in row.__table__.columns}
    for key, value in result.items():
        if isinstance(value, datetime):
            result[key] = iso_timestamp(value)
    return result


def user_dict(user: User) -> dict[str, Any]:
    return {key: value for key, value in row_dict(user).items() if key != "password_hash"}


def learning_method_label(value: str | None) -> str:
    return {
        "socratic": "逐步提问",
        "micro_activity": "小步练习",
        "assisted_progression": "分步辅助练习",
        "independent_dataset_practice": "独立完成题库练习",
        "teacher_review": "教师复核指导",
        "incremental_hint": "分层提示",
        "understanding_check_prompt": "理解检查",
        "preserve_correct_part": "保留正确部分再提示",
        "visual_counterexample": "图形演示和反例",
        "prerequisite_example": "补充基础例子",
        "temporary_rediagnosis": "重新分析题目",
        "answer_with_explanation": "结合答案讲解",
        "targeted_remediation": "针对错误讲解",
        "guided": "逐步引导",
    }.get(value or "", value or "尚未确定")


def learner_text(value: str | None) -> str:
    text = value or "根据最近的学习情况更新"
    return (
        text.replace("教回", "讲解思路")
        .replace("近迁移", "相似题")
        .replace("远迁移", "综合题")
        .replace("提示等级", "使用提示")
    )


def canonical_misconception_label(value: str) -> str:
    if "移项" in value and ("符号" in value or "变号" in value):
        return "移项符号"
    return value


def question_display_key(question: Question) -> str:
    """Collapse exact duplicate records consistently for every student."""
    text = (question.question_text or "").strip()
    if not text:
        return f"pending:{question.id}"
    return re.sub(r"[\s，。？?：:]+", "", text).lower()


async def record_agent_tool(
    db: AsyncSession,
    session_id: str,
    branch: str,
    tool_name: str,
    tool_input: dict[str, Any],
    tool_output: dict[str, Any],
    run_result: dict[str, Any] | None = None,
) -> AgentRun:
    run = AgentRun(
        session_id=session_id,
        agent_name="mindtrace_tutor",
        result={"branch": branch, **tool_output, **(run_result or {})},
    )
    db.add(run)
    await db.flush()
    db.add(
        AgentToolCall(
            agent_run_id=run.id,
            tool_name=tool_name,
            input_json=tool_input,
            output_json=tool_output,
        )
    )
    return run


async def current_user(
    authorization: str | None = Header(default=None), db: AsyncSession = Depends(get_db)
) -> User:
    return await authenticated_account(authorization, db)


def require_roles(*roles: str):
    async def dependency(user: User = Depends(current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=403, detail="当前登录账号没有此身份")
        return user

    return dependency


async def process_question(
    job_id: str,
    question_id: str,
    image_path: str,
    *,
    require_crop: bool = False,
) -> None:
    async with SessionLocal() as db:
        job = await db.get(ProcessingJob, job_id)
        question = await db.get(Question, question_id)
        if not job or not question:
            return
        if question.status == "archived":
            await recognition_question_for_write(db, job)
            return
        try:
            job.status = "running"
            job.progress = 15
            await db.commit()
            original_asset = (
                await db.scalars(
                    select(QuestionAsset).where(
                        QuestionAsset.question_id == question_id,
                        QuestionAsset.kind == "original",
                    )
                )
            ).first()
            crop_asset = (
                await db.scalars(
                    select(QuestionAsset).where(
                        QuestionAsset.question_id == question_id,
                        QuestionAsset.kind == "crop",
                    )
                )
            ).first()
            recognition_path = Path(image_path)
            if require_crop:
                if crop_asset is None:
                    raise RuntimeError("CROP_REQUIRED: 尚未生成裁剪图片")
                persisted_crop_path = Path(crop_asset.path)
                if recognition_path.resolve() != persisted_crop_path.resolve():
                    raise RuntimeError("CROP_PATH_MISMATCH: 主识别禁止读取原始整图")
                recognition_path = persisted_crop_path
            if not recognition_path.is_file():
                raise FileNotFoundError(f"识别图片不存在: {recognition_path}")

            def path_size(path: str | None) -> int:
                return Path(path).stat().st_size if path and Path(path).is_file() else 0

            logger.info(
                "recognition_start question_id=%s original_path=%s original_size=%s "
                "cropped_path=%s cropped_size=%s qwen_image_path=%s qwen_image_size=%s",
                question_id,
                original_asset.path if original_asset else None,
                path_size(original_asset.path if original_asset else None),
                crop_asset.path if crop_asset else None,
                path_size(crop_asset.path if crop_asset else None),
                str(recognition_path),
                recognition_path.stat().st_size,
            )
            root = settings.upload_dir / question_id
            clean, mask, overlay = root / "clean.jpg", root / "red_mask.png", root / "overlay.jpg"
            await asyncio.to_thread(preprocess_image, recognition_path, clean, mask, overlay)
            for kind, path in (("clean", clean), ("red_mask", mask), ("overlay", overlay)):
                db.add(
                    QuestionAsset(
                        question_id=question_id,
                        kind=kind,
                        path=str(path),
                        sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                    )
                )
            job.progress = 45
            await db.commit()
            qwen_started = time.perf_counter()
            extraction = await recognize_cropped_question(provider, recognition_path)
            qwen_duration_ms = round((time.perf_counter() - qwen_started) * 1000)
            logger.info(
                "recognition_result question_id=%s qwen_image_path=%s result=%s",
                question_id,
                str(recognition_path),
                json.dumps(extraction.model_dump(mode="json"), ensure_ascii=False),
            )
            question = await recognition_question_for_write(db, job)
            if question is None:
                return
            await db.execute(delete(TeacherMark).where(TeacherMark.question_id == question_id))
            region_kinds = tuple(VISUAL_REGION_KINDS.values())
            await db.execute(
                delete(QuestionAsset).where(
                    QuestionAsset.question_id == question_id,
                    QuestionAsset.kind.in_(region_kinds),
                )
            )
            saved_regions = await asyncio.to_thread(
                persist_recognition_regions,
                recognition_path,
                root,
                extraction,
            )
            for region in saved_regions:
                db.add(
                    QuestionAsset(
                        question_id=question_id,
                        kind=region["kind"],
                        path=region["path"],
                        sha256=region["sha256"],
                        role=region["role"],
                        bbox=region["bbox"],
                        description=region["description"],
                    )
                )
            actual_models = provider.health_check().get("actual_models", [])
            db.add(
                OCRRun(
                    question_id=question_id,
                    provider="qwen-pool",
                    stream="qwen_crop",
                    raw_result=extraction.model_dump(mode="json"),
                    confidence=extraction.recognition_confidence,
                    model_name=",".join(actual_models),
                    duration_ms=qwen_duration_ms,
                )
            )
            await invalidate_question_learning(db, question)
            question.confirmed = False
            question.question_text = extraction.question_text
            question.student_answer = extraction.student_answer
            question.subject = extraction.subject
            question.grade = extraction.grade
            question.question_type = extraction.question_type
            question.formulas = []
            question.options = [item.model_dump(mode="json") for item in extraction.options]
            question.title = extraction.question_text[:60] or "待确认错题"
            question.status = "needs_confirmation"
            work = StudentWork(
                question_id=question_id,
                user_id=question.user_id,
                answer=extraction.student_answer or "",
            )
            db.add(work)
            await db.flush()
            for item in extraction.student_steps:
                text = item.text
                db.add(
                    StudentStep(
                        work_id=work.id,
                        step_index=item.index - 1,
                        text=text,
                        raw_text=text,
                        normalized_text=" ".join(text.split()),
                        formula=text if "=" in text else "",
                        bbox=[],
                        confidence=extraction.recognition_confidence,
                        source="qwen_crop",
                    )
                )
            for annotation in extraction.teacher_annotations:
                db.add(
                    TeacherMark(
                        question_id=question_id,
                        mark_type=annotation.type,
                        comment=annotation.text,
                        bbox=[],
                        confidence=extraction.recognition_confidence,
                        source="qwen_crop",
                    )
                )
            job.status = "completed"
            job.progress = 100
            await db.commit()
        except Exception as exc:
            await db.rollback()
            job = await db.get(ProcessingJob, job_id)
            if job is None:
                return
            question = await recognition_question_for_write(db, job)
            if question is None:
                return
            job.status = "failed"
            job.error = "识别暂时未完成，请检查图片后重试"
            question.status = "partial"
            logger.warning("recognition_failed question_id=%s error_type=%s", question_id, type(exc).__name__)
            await db.commit()


@asynccontextmanager
async def lifespan(_: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with SessionLocal() as db:
        recovered = await recover_interrupted_recognition(db)
        await db.commit()
        if recovered:
            logger.info("recognition_interrupted_jobs_recovered count=%s", recovered)
    probe_task = asyncio.create_task(provider.probe()) if settings.ai_probe_on_startup else None
    yield
    if probe_task is not None and not probe_task.done():
        probe_task.cancel()
    await provider.close()


app = FastAPI(
    title="错题帮 API",
    version="0.1.0",
    lifespan=lifespan,
    dependencies=[Depends(authorize_api_request)],
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.mount(
    "/uploads", SignedStaticFiles(directory=settings.upload_dir, secret=settings.auth_secret), name="uploads"
)
app.mount("/reports", SignedStaticFiles(directory="reports", secret=settings.auth_secret), name="reports")
app.include_router(create_teacher_router(provider))


@app.exception_handler(ApiPoolUnavailable)
async def ai_unavailable_handler(_request, _error):
    return JSONResponse(
        status_code=503,
        content={
            "detail": "AI 服务暂时不可用，请稍后重试；已保存的题目和作答仍然保留",
        },
    )


@app.post("/api/v1/auth/register")
async def register(payload: dict = Body(...), db: AsyncSession = Depends(get_db)):
    payload = validated_payload(RegisterRequest, payload)
    email = str(payload.get("email", "")).strip().lower()
    password = str(payload.get("password", ""))
    if not email or "@" not in email:
        raise HTTPException(status_code=422, detail="请输入正确的邮箱")
    if not password:
        raise HTTPException(status_code=422, detail="请输入密码")
    existing = (await db.scalars(select(User).where(User.email == email))).first()
    if existing:
        raise HTTPException(status_code=409, detail="这个邮箱已经注册，请直接登录")
    user = User(
        email=email,
        name=payload.get("name", "智维同学"),
        role="student",
        password_hash=hash_password(password),
    )
    db.add(user)
    await db.flush()
    db.add(StudentProfile(user_id=user.id, grade=payload.get("grade", "初二")))
    await db.commit()
    await db.refresh(user)
    return envelope(
        {
            **user_dict(user),
            "access_token": create_access_token(user.id, settings.auth_secret, credential=user.password_hash),
        }
    )


@app.post("/api/v1/auth/login")
async def login(payload: dict = Body(...), db: AsyncSession = Depends(get_db)):
    payload = validated_payload(LoginRequest, payload)
    email = str(payload.get("email", "")).strip().lower()
    user = (await db.scalars(select(User).where(User.email == email))).first()
    if user is None or not verify_password(str(payload.get("password", "")), user.password_hash):
        raise HTTPException(status_code=401, detail="账号或密码不正确")
    return envelope(
        {
            **user_dict(user),
            "access_token": create_access_token(user.id, settings.auth_secret, credential=user.password_hash),
        }
    )


@app.post("/api/v1/auth/reset-password")
async def reset_password(payload: dict = Body(...), db: AsyncSession = Depends(get_db)):
    email = str(payload.get("email", "")).strip().lower()
    password = str(payload.get("new_password", ""))
    if not password:
        raise HTTPException(status_code=422, detail="请输入新密码")
    user = (await db.scalars(select(User).where(User.email == email))).first()
    if user is None or not verify_password(str(payload.get("current_password", "")), user.password_hash):
        raise HTTPException(status_code=401, detail="账号或当前密码不正确，无法修改密码")
    user.password_hash = hash_password(password)
    await db.commit()
    return envelope({"email": user.email, "reset": True})


@app.get("/api/v1/auth/me")
async def me(user: User = Depends(current_user)):
    return envelope(user_dict(user))


@app.patch("/api/v1/auth/me")
async def update_me(
    payload: dict = Body(...), user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    for field in ("name",):
        if field in payload:
            setattr(user, field, payload[field])
    await db.commit()
    return envelope(user_dict(user))




@app.get("/api/v1/system/health")
async def health():
    try:
        async with engine.connect() as connection:
            await connection.execute(select(func.count()).select_from(User))
    except Exception:
        # asyncmy 在 MySQL 重启或空闲连接被关闭后，偶尔会把已关闭 transport 留在池中。
        # 清空连接池并只重试一次，让健康检查和后续请求能够自行恢复。
        await engine.dispose()
        async with engine.connect() as connection:
            await connection.execute(select(func.count()).select_from(User))
    return envelope(
        {
            "status": "healthy",
            "database": "mysql",
            "ai": provider.state.last_status,
            "image_recognition": bool(provider.vision_entries),
        }
    )




@app.get("/api/v1/system/providers")
async def providers():
    return envelope(provider.health_check())


@app.post("/api/v1/system/providers/probe")
async def probe_provider():
    return envelope(await provider.probe())




@app.get("/api/v1/system/voice")
async def voice_status():
    return envelope(voice_provider.health_check())


@app.get("/api/v1/admin/workbench")
async def admin_workbench(
    _: User = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
):
    return envelope(await get_admin_workbench(db, provider.health_check(), voice_provider.health_check()))


@app.get("/api/v1/admin/students/{student_id}")
async def admin_student(
    student_id: str,
    _: User = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
):
    return envelope(await get_admin_student(db, student_id))


@app.get("/api/v1/admin/sessions/{session_id}")
async def admin_session(
    session_id: str,
    _: User = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
):
    return envelope(await get_admin_session(db, session_id))


@app.get("/api/v1/dashboard")
async def dashboard(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    user_questions = list(
        await db.scalars(
            select(Question).where(
                Question.user_id == user.id,
                Question.status != "archived",
            )
        )
    )
    question_count = len({question_display_key(item) for item in user_questions})
    now = datetime.now(timezone.utc)
    study_timezone = timezone(timedelta(hours=8))
    today_end = (
        now.astimezone(study_timezone)
        .replace(
            hour=23,
            minute=59,
            second=59,
            microsecond=999999,
        )
        .astimezone(timezone.utc)
    )
    review_count = await db.scalar(
        select(func.count())
        .select_from(ReviewPlan)
        .where(
            ReviewPlan.user_id == user.id,
            ReviewPlan.status == "pending",
            ReviewPlan.due_at <= today_end,
        )
    )
    mastery = list(
        await db.scalars(
            select(MasteryState)
            .where(
                MasteryState.user_id == user.id,
            )
            .order_by(MasteryState.updated_at.desc())
            .limit(8)
        )
    )
    misconceptions = list(
        await db.scalars(
            select(MisconceptionState)
            .where(
                MisconceptionState.user_id == user.id,
            )
            .order_by(MisconceptionState.probability.desc())
            .limit(8)
        )
    )
    mastery_by_point: dict[tuple[str, str], MasteryState] = {}
    for mastery_item in mastery:
        mastery_by_point.setdefault(
            (mastery_item.subject, mastery_item.knowledge_point),
            mastery_item,
        )
    mastery = list(mastery_by_point.values())
    profile = (await db.scalars(select(StudentProfile).where(StudentProfile.user_id == user.id))).first()
    session = (
        await db.scalars(
            select(TutorSession)
            .where(
                TutorSession.user_id == user.id,
                TutorSession.status == "active",
            )
            .order_by(TutorSession.updated_at.desc())
        )
    ).first()
    active_question = await db.get(Question, session.question_id) if session else None
    continue_learning = None
    if (
        session
        and active_question
        and not (session.state or {}).get("question_changed")
        and active_question.status != "archived"
    ):
        next_step = {
            "understanding": "理解错误原因",
            "teach_back": "用自己的话讲清思路",
            "teach_back_retry": "补充说明关键理由",
            "near_transfer": "完成一道相似题",
            "near_remediation": "再巩固一次",
            "far_transfer": "完成综合应用",
            "transfer_insufficient": "回顾方法后再练习",
        }.get(session.stage, "继续完成本次学习")
        continue_learning = {
            "session_id": session.id,
            "question_id": active_question.id,
            "knowledge_point": student_facing_topic(
                active_question.knowledge_points,
                active_question.question_type,
            ),
            "stage": session.stage,
            "next_step": next_step,
        }
    deduped_misconceptions: dict[tuple[str, str], MisconceptionState] = {}
    for misconception_item in misconceptions:
        label = canonical_misconception_label(misconception_item.label)
        key = (misconception_item.subject, label)
        previous = deduped_misconceptions.get(key)
        if previous is None or misconception_item.probability > previous.probability:
            deduped_misconceptions[key] = misconception_item
    discoveries = [
        {
            "kind": "attention",
            "title": label,
            "detail": "这是目前最需要优先巩固的错误原因",
            "value": round(item.probability * 100),
        }
        for (_, label), item in list(deduped_misconceptions.items())[:2]
    ]
    discoveries.extend(
        {
            "kind": "stable" if item.mastery_score >= 0.75 else "progress",
            "title": item.knowledge_point,
            "detail": "掌握状态已经比较稳定" if item.mastery_score >= 0.75 else "继续完成相似题会更牢固",
            "value": round(item.mastery_score * 100),
        }
        for item in mastery[:2]
    )
    activity_days = sorted(
        {
            item.created_at.replace(tzinfo=timezone.utc).astimezone(study_timezone).date()
            for item in user_questions
            if item.created_at is not None
        },
        reverse=True,
    )
    today = now.astimezone(study_timezone).date()
    streak_days = 0
    if activity_days and activity_days[0] in {today, today - timedelta(days=1)}:
        expected_day = activity_days[0]
        for activity_day in activity_days:
            if activity_day != expected_day:
                break
            streak_days += 1
            expected_day -= timedelta(days=1)
    has_learning_data = bool(user_questions or review_count or mastery or misconceptions or continue_learning)
    assignment_count = int(
        await db.scalar(
            select(func.count())
            .select_from(AssignmentStudent)
            .where(
                AssignmentStudent.student_id == user.id,
                AssignmentStudent.status == "pending",
            )
        )
        or 0
    )
    teacher_feedback_row = (
        await db.execute(
            select(TeacherReviewResult, TeacherReviewTask)
            .join(
                TeacherReviewTask,
                TeacherReviewTask.id == TeacherReviewResult.task_id,
            )
            .where(
                TeacherReviewTask.student_id == user.id,
                TeacherReviewResult.revoked_at.is_(None),
            )
            .order_by(TeacherReviewResult.created_at.desc())
            .limit(1)
        )
    ).first()
    teacher_feedback = None
    if teacher_feedback_row:
        feedback, feedback_task = teacher_feedback_row
        teacher_feedback = {
            "conclusion": feedback.conclusion,
            "reason": feedback.reason,
            "student_hint": feedback.student_hint,
            "next_task": feedback.next_task,
            "question_id": feedback_task.question_id,
            "handled_at": feedback.created_at.isoformat(),
        }
    return envelope(
        {
            "today_reviews": review_count or 0,
            "weekly_questions": question_count or 0,
            "mastered_points": sum(1 for item in mastery if item.mastery_score >= 0.7),
            "streak_days": streak_days,
            "grade": profile.grade if profile else "初二",
            "estimated_minutes": (
                max(3, int(review_count or 0) + (5 if continue_learning else 2)) if has_learning_data else 0
            ),
            "continue_learning": continue_learning,
            "discoveries": discoveries,
            "teacher_assignment_count": assignment_count,
            "teacher_feedback": teacher_feedback,
            "mastery": [row_dict(x) for x in mastery],
            "misconceptions": [
                row_dict(item) | {"label": label} for (_, label), item in deduped_misconceptions.items()
            ],
            "ai_suggestion": (
                "先弄懂最常出错的一步，再完成一道相似题。"
                if has_learning_data
                else "拍下第一道错题，我会从你的解题步骤开始分析。"
            ),
        }
    )


@app.post("/api/v1/questions/ingest")
async def ingest_question(
    background: BackgroundTasks,
    file: UploadFile = File(...),
    subject: str = "数学",
    defer_processing: bool = Form(False),
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    raw = await file.read(MAX_UPLOAD_BYTES + 1)
    if not raw:
        raise HTTPException(422, "图片为空，请重新选择图片")
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "图片不能超过 15 MB")
    question = Question(user_id=user.id, subject=subject, title=file.filename or "上传错题")
    db.add(question)
    await db.flush()
    root = settings.upload_dir / question.id
    original = root / "original.jpg"
    try:
        digest = save_original(raw, original)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    db.add(QuestionAsset(question_id=question.id, kind="original", path=str(original), sha256=digest))
    if defer_processing:
        question.status = "awaiting_crop"
        await db.commit()
        return envelope({"question_id": question.id, "job_id": None, "status": "awaiting_crop"})
    job = ProcessingJob(question_id=question.id, kind="ingest", status="pending")
    db.add(job)
    await db.commit()
    background.add_task(process_question, job.id, question.id, str(original))
    return envelope({"question_id": question.id, "job_id": job.id, "status": "pending"})


@app.get("/api/v1/questions")
async def questions(
    subject: str | None = None,
    search: str | None = None,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(Question)
        .where(
            Question.user_id == user.id,
            Question.status != "archived",
        )
        .order_by(Question.created_at.desc())
    )
    if subject:
        query = query.where(Question.subject == subject)
    if search:
        conditions = [
            Question.question_text.contains(search),
            Question.title.contains(search),
            cast(Question.knowledge_points, Text).contains(search),
            cast(Question.tags, Text).contains(search),
            Diagnosis.root_misconception.contains(search),
            Diagnosis.error_type.contains(search),
            Diagnosis.first_error_text.contains(search),
        ]
        error_codes = error_codes_for_label(search)
        if error_codes:
            conditions.append(Diagnosis.error_type.in_(error_codes))
        query = (
            query.outerjoin(Diagnosis, Diagnosis.question_id == Question.id)
            .where(or_(*conditions))
            .distinct()
        )
    rows = list(await db.scalars(query))
    visible_rows, seen_keys = [], set()
    for question in rows:
        key = question_display_key(question)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        visible_rows.append(question)
    rows = visible_rows
    result = []
    for question in rows:
        diagnosis = (
            await db.scalars(
                select(Diagnosis)
                .where(
                    Diagnosis.question_id == question.id,
                )
                .order_by(Diagnosis.created_at.desc())
            )
        ).first()
        review = (
            await db.scalars(
                select(ReviewPlan)
                .where(
                    ReviewPlan.user_id == user.id,
                    ReviewPlan.question_id == question.id,
                    ReviewPlan.status == "pending",
                )
                .order_by(ReviewPlan.due_at.asc())
            )
        ).first()
        knowledge = list(question.knowledge_points or [])
        mastery = (
            await db.scalars(
                select(MasteryState)
                .where(
                    MasteryState.user_id == user.id,
                    MasteryState.subject == question.subject,
                    MasteryState.knowledge_point.in_(knowledge or ["__none__"]),
                )
                .order_by(MasteryState.updated_at.desc())
            )
        ).first()
        asset = (
            await db.scalars(
                select(QuestionAsset)
                .where(
                    QuestionAsset.question_id == question.id,
                    QuestionAsset.kind.in_(["crop", "original"]),
                )
                .order_by(QuestionAsset.created_at.desc())
            )
        ).first()
        latest_job = (
            await db.scalars(
                select(ProcessingJob)
                .where(
                    ProcessingJob.question_id == question.id,
                )
                .order_by(ProcessingJob.created_at.desc())
            )
        ).first()
        score = mastery.mastery_score if mastery else 0.0
        mastery_status = "基本稳定" if score >= 0.75 else "继续巩固" if score >= 0.5 else "需要巩固"
        result.append(
            row_dict(question)
            | {
                "diagnosis_summary": diagnosis.root_misconception if diagnosis else "等待完成错因诊断",
                "mastery_score": score,
                "mastery_status": mastery_status,
                "review_due_at": iso_timestamp(review.due_at) if review else None,
                "thumbnail_url": sign_media_url("/" + asset.path, settings.auth_secret) if asset else None,
                "latest_job_id": latest_job.id if latest_job else None,
                "latest_job_status": latest_job.status if latest_job else None,
            }
        )
    return envelope(result)


async def question_payload(question_id: str, db: AsyncSession) -> dict[str, Any]:
    question = await db.get(Question, question_id)
    if not question:
        raise HTTPException(404, "题目不存在")
    assets = list(await db.scalars(select(QuestionAsset).where(QuestionAsset.question_id == question_id)))
    ocr_runs = list(
        await db.scalars(
            select(OCRRun).where(OCRRun.question_id == question_id).order_by(OCRRun.created_at.desc())
        )
    )
    ocr = next((item for item in ocr_runs if item.stream == "qwen_crop"), ocr_runs[0] if ocr_runs else None)
    analysis = (
        await db.scalars(select(ProblemAnalysis).where(ProblemAnalysis.question_id == question_id))
    ).first()
    diagnosis = (
        await db.scalars(
            select(Diagnosis)
            .where(Diagnosis.question_id == question_id)
            .order_by(Diagnosis.created_at.desc())
        )
    ).first()
    works = list(
        await db.scalars(
            select(StudentWork)
            .where(StudentWork.question_id == question_id)
            .order_by(StudentWork.created_at.desc())
            .limit(1)
        )
    )
    steps: list[StudentStep] = []
    for work in works:
        steps.extend(
            list(
                await db.scalars(
                    select(StudentStep).where(StudentStep.work_id == work.id).order_by(StudentStep.step_index)
                )
            )
        )
    marks = list(await db.scalars(select(TeacherMark).where(TeacherMark.question_id == question_id)))
    references = (
        list(
            await db.scalars(
                select(ReferenceStep)
                .where(ReferenceStep.analysis_id == analysis.id)
                .order_by(ReferenceStep.step_index)
            )
        )
        if analysis
        else []
    )
    evidence = (
        list(
            await db.scalars(select(DiagnosisEvidence).where(DiagnosisEvidence.diagnosis_id == diagnosis.id))
        )
        if diagnosis
        else []
    )
    counterfactual = next((x.metadata_json for x in evidence if x.kind == "counterfactual_validation"), None)
    step_evidence = [row_dict(x) for x in evidence if x.kind == "step_alignment"]
    asset_payloads = [
        row_dict(x) | {"url": sign_media_url("/" + x.path, settings.auth_secret)} for x in assets
    ]
    visual_groups = {
        "question_figures": [item for item in asset_payloads if item["kind"] == "question_figure"],
        "student_working_figures": [
            item for item in asset_payloads if item["kind"] == "student_working_figure"
        ],
        "teacher_annotation_regions": [
            item for item in asset_payloads if item["kind"] == "teacher_annotation_region"
        ],
    }
    active_job = await active_recognition_job(db, question.id)
    current_crop = next((asset for asset in assets if asset.kind == "crop"), None)
    return {
        **row_dict(question),
        "processing_job": row_dict(active_job) if active_job else None,
        "crop_box": crop_box(current_crop),
        "assets": asset_payloads,
        **visual_groups,
        "ocr": row_dict(ocr) if ocr else None,
        "analysis": row_dict(analysis) if analysis else None,
        "ocr_runs": [row_dict(x) for x in ocr_runs],
        "teacher_marks": [row_dict(x) for x in marks],
        "reference_steps": [row_dict(x) for x in references],
        "diagnosis": (
            row_dict(diagnosis)
            | {
                "evidence": step_evidence,
                "counterfactual": counterfactual,
            }
        )
        if diagnosis
        else None,
        "student_steps": [row_dict(x) for x in steps],
    }


async def question_visual_paths(question_id: str, db: AsyncSession) -> list[Path]:
    """给分析、诊断和教学统一提供crop原图与原题自带图。"""
    rows = list(
        await db.scalars(
            select(QuestionAsset)
            .where(
                QuestionAsset.question_id == question_id,
                QuestionAsset.kind.in_(("crop", "question_figure")),
            )
            .order_by(QuestionAsset.created_at)
        )
    )
    paths: list[Path] = []
    seen: set[str] = set()
    for row in rows:
        path = Path(row.path)
        resolved = str(path.resolve())
        if path.is_file() and resolved not in seen:
            paths.append(path)
            seen.add(resolved)
    return paths


@app.get("/api/v1/questions/{question_id}")
async def get_question(question_id: str, db: AsyncSession = Depends(get_db)):
    return envelope(await question_payload(question_id, db))


@app.patch("/api/v1/questions/{question_id}")
async def patch_question(question_id: str, payload: dict = Body(...), db: AsyncSession = Depends(get_db)):
    payload = validated_body(QuestionEditRequest, payload)
    question = await db.get(Question, question_id)
    if not question:
        raise HTTPException(404, "题目不存在")
    learning_fields = {
        "question_text",
        "student_answer",
        "subject",
        "grade",
        "formulas",
        "options",
        "question_type",
        "knowledge_points",
    }
    changed = any(
        field in payload and getattr(question, field) != payload[field] for field in learning_fields
    )
    if changed:
        await invalidate_question_learning(db, question)
    for field in (
        "question_text",
        "student_answer",
        "subject",
        "grade",
        "title",
        "favorite",
        "tags",
        "formulas",
        "options",
        "question_type",
        "knowledge_points",
    ):
        if field in payload:
            setattr(question, field, payload[field])
    await db.commit()
    return envelope(row_dict(question))


@app.post("/api/v1/questions/{question_id}/crop")
async def crop_question(
    question_id: str,
    background: BackgroundTasks,
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
):
    payload = validated_body(CropRequest, payload)
    question = await db.get(Question, question_id)
    if question is None or question.status == "archived":
        raise HTTPException(404, "题目不存在或已归档")

    async def resume_existing(job):
        asset = (
            await db.scalars(
                select(QuestionAsset).where(
                    QuestionAsset.question_id == question_id,
                    QuestionAsset.kind == "crop",
                )
            )
        ).first()
        if asset is None or not same_crop(asset, payload["box"]):
            raise HTTPException(409, "已有识别任务正在处理，请先查看结果再调整范围")
        return envelope(
            row_dict(asset)
            | {
                "url": sign_media_url("/" + asset.path, settings.auth_secret),
                "job_id": job.id,
                "status": job.status,
                "resumed": True,
                "crop_box": crop_box(asset),
            }
        )

    # Avoid waiting on a worker's write lock when only resuming existing work.
    existing = await active_recognition_job(db, question_id)
    if existing:
        return await resume_existing(existing)
    question = await lock_recognition_question(db, question_id)
    existing = await active_recognition_job(db, question_id)
    if existing:
        return await resume_existing(existing)
    original = (
        await db.scalars(
            select(QuestionAsset).where(
                QuestionAsset.question_id == question_id, QuestionAsset.kind == "original"
            )
        )
    ).first()
    if original is None:
        raise HTTPException(404, "原图不存在")
    target = settings.upload_dir / question_id / "crop.jpg"
    try:
        geometry = crop_image(Path(original.path), target, payload.get("box", []))
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    old = (
        await db.scalars(
            select(QuestionAsset).where(
                QuestionAsset.question_id == question_id, QuestionAsset.kind == "crop"
            )
        )
    ).first()
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    if old:
        old.path, old.sha256 = str(target), digest
        asset = old
    else:
        asset = QuestionAsset(question_id=question_id, kind="crop", path=str(target), sha256=digest)
        db.add(asset)
        await db.flush()
    x, y, width, height = payload["box"]
    asset.bbox = [x, y, min(1.0, x + width), min(1.0, y + height)]
    job = ProcessingJob(question_id=question_id, kind="crop", status="pending")
    db.add(job)
    question.status = "processing"
    await db.flush()
    await db.commit()
    background.add_task(process_question, job.id, question_id, str(target), require_crop=True)
    return envelope(
        row_dict(asset)
        | {
            "url": sign_media_url("/" + str(target), settings.auth_secret),
            "geometry": geometry,
            "original_preserved": Path(original.path).exists(),
            "job_id": job.id,
            "status": "pending",
        }
    )


@app.delete("/api/v1/questions/{question_id}")
async def delete_question(question_id: str, db: AsyncSession = Depends(get_db)):
    question = await db.get(Question, question_id, with_for_update=True, populate_existing=True)
    if question:
        question.status = "archived"
        plans = await db.scalars(
            select(ReviewPlan).where(
                ReviewPlan.question_id == question_id,
                ReviewPlan.status == "pending",
            )
        )
        for plan in plans:
            plan.status = "cancelled"
        await db.commit()
    return envelope({"deleted": bool(question)})


async def apply_ocr_edits(question: Question, payload: dict, db: AsyncSession) -> None:
    payload = validated_body(QuestionEditRequest, payload)
    learning_fields = (
        "question_text",
        "subject",
        "formulas",
        "options",
        "question_type",
        "knowledge_points",
        "student_answer",
        "grade",
    )
    before = {field: getattr(question, field) for field in learning_fields}
    steps_changed = False
    for field in ("question_text", "subject", "formulas", "options", "question_type", "knowledge_points"):
        if field in payload:
            setattr(question, field, payload[field])

    submitted_steps = list(payload.get("student_steps") or [])
    submitted_answer = str(payload.get("student_answer") or "").strip()
    is_choice = bool(re.search(r"选择|choice|multiple", str(question.question_type), re.IGNORECASE))
    if is_choice and not submitted_answer:
        nonempty_steps = []
        for value in submitted_steps:
            item = value if isinstance(value, dict) else {"text": str(value)}
            text = str(item.get("text", item.get("raw_text", "")) or "").strip()
            if text:
                nonempty_steps.append(text)
        if len(nonempty_steps) == 1 and re.fullmatch(
            r"[A-Z](?:\s*[、,，]\s*[A-Z])*", nonempty_steps[0], re.IGNORECASE
        ):
            labels = re.findall(r"[A-Z]", nonempty_steps[0].upper())
            known_labels = {
                str(option.get("label", option.get("key", ""))).upper()
                for option in (question.options or [])
                if isinstance(option, dict)
            }
            if not known_labels or all(label in known_labels for label in labels):
                submitted_answer = "、".join(dict.fromkeys(labels))
                submitted_steps = []

    if "student_answer" in payload:
        question.student_answer = submitted_answer or None
    if "grade" in payload:
        question.grade = str(payload["grade"]).strip() if payload["grade"] else None
    if "student_steps" in payload:
        previous_work = (
            await db.scalars(
                select(StudentWork)
                .where(
                    StudentWork.question_id == question.id,
                )
                .order_by(StudentWork.created_at.desc())
            )
        ).first()
        previous_steps = (
            list(
                await db.scalars(
                    select(StudentStep)
                    .where(
                        StudentStep.work_id == previous_work.id,
                    )
                    .order_by(StudentStep.step_index)
                )
            )
            if previous_work
            else []
        )
        new_texts = [
            str(value.get("text", value.get("raw_text", "")) or "") if isinstance(value, dict) else str(value)
            for value in submitted_steps
        ]
        steps_changed = [step.text for step in previous_steps] != new_texts
        # A new work revision preserves steps referenced by existing diagnosis evidence.
        work = StudentWork(
            question_id=question.id, user_id=question.user_id, answer=question.student_answer or ""
        )
        db.add(work)
        await db.flush()
        for index, value in enumerate(submitted_steps):
            item = value if isinstance(value, dict) else {"text": str(value)}
            text = str(item.get("text", item.get("raw_text", "")) or "")
            db.add(
                StudentStep(
                    work_id=work.id,
                    step_index=index,
                    text=text,
                    raw_text=item.get("raw_text", text),
                    normalized_text=" ".join(text.split()),
                    formula=text if "=" in text else "",
                    bbox=item.get("bbox", []),
                    confidence=float(item.get("confidence", 1)),
                    source=item.get("source", "user"),
                    user_confirmed=True,
                )
            )
    if "teacher_marks" in payload:
        await db.execute(delete(TeacherMark).where(TeacherMark.question_id == question.id))
        for value in payload["teacher_marks"]:
            item = value if isinstance(value, dict) else {"comment": str(value)}
            db.add(
                TeacherMark(
                    question_id=question.id,
                    mark_type=item.get("mark_type", "comment"),
                    comment=item.get("comment", ""),
                    bbox=item.get("bbox", []),
                    confidence=float(item.get("confidence", 1)),
                    source="user",
                )
            )
    changed = any(before[field] != getattr(question, field) for field in learning_fields)
    if changed or steps_changed:
        await invalidate_question_learning(db, question)


@app.post("/api/v1/questions/{question_id}/draft")
async def save_ocr_draft(
    question_id: str, payload: dict = Body(default={}), db: AsyncSession = Depends(get_db)
):
    question = await db.get(Question, question_id)
    if not question:
        raise HTTPException(404, "题目不存在")
    await apply_ocr_edits(question, payload, db)
    question.status = "ocr_draft"
    await db.commit()
    return envelope(await question_payload(question_id, db))


@app.post("/api/v1/questions/{question_id}/confirm")
async def confirm_question(
    question_id: str, payload: dict = Body(default={}), db: AsyncSession = Depends(get_db)
):
    question = await db.get(Question, question_id)
    if not question:
        raise HTTPException(404, "题目不存在")
    await apply_ocr_edits(question, payload, db)
    if not question.question_text.strip():
        raise HTTPException(422, "请先补充题目文字再确认")
    question.confirmed = True
    question.status = "confirmed"
    await db.commit()
    return envelope(await question_payload(question_id, db))


@app.post("/api/v1/questions/{question_id}/ocr")
async def run_question_ocr(question_id: str, db: AsyncSession = Depends(get_db)):
    question = await lock_recognition_question(db, question_id)
    existing = await active_recognition_job(db, question_id)
    if existing:
        return envelope(
            {"job": row_dict(existing), "question": await question_payload(question_id, db), "resumed": True}
        )
    asset = (
        await db.scalars(
            select(QuestionAsset).where(
                QuestionAsset.question_id == question_id,
                QuestionAsset.kind == "crop",
            )
        )
    ).first()
    if not asset:
        raise HTTPException(422, "请先框选题目，生成裁剪图片后再识别")
    job = ProcessingJob(question_id=question_id, kind="ocr", status="pending")
    question.status = "processing"
    db.add(job)
    await db.commit()
    await process_question(job.id, question_id, asset.path, require_crop=True)
    await db.refresh(job)
    await db.refresh(question)
    return envelope({"job": row_dict(job), "question": await question_payload(question_id, db)})


@app.post("/api/v1/questions/{question_id}/reprocess")
async def reprocess(question_id: str, background: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    question = await lock_recognition_question(db, question_id)
    existing = await active_recognition_job(db, question_id)
    if existing:
        return envelope({"job_id": existing.id, "resumed": True})
    asset = (
        await db.scalars(
            select(QuestionAsset).where(
                QuestionAsset.question_id == question_id,
                QuestionAsset.kind == "crop",
            )
        )
    ).first()
    if not asset:
        raise HTTPException(422, "请先框选题目，生成裁剪图片后再识别")
    job = ProcessingJob(question_id=question_id, kind="reprocess")
    question.status = "processing"
    db.add(job)
    await db.commit()
    background.add_task(process_question, job.id, question_id, asset.path, require_crop=True)
    return envelope({"job_id": job.id})


@app.post("/api/v1/questions/{question_id}/analyze")
async def analyze(question_id: str, db: AsyncSession = Depends(get_db)):
    question = await db.get(Question, question_id)
    if not question:
        raise HTTPException(404, "题目不存在")
    if not question.confirmed or not question.question_text.strip():
        raise HTTPException(409, "请先核对并确认题目文字，再开始分析")
    work = (
        await db.scalars(
            select(StudentWork)
            .where(
                StudentWork.question_id == question_id,
            )
            .order_by(StudentWork.created_at.desc())
        )
    ).first()
    step_rows = (
        list(
            await db.scalars(
                select(StudentStep)
                .where(
                    StudentStep.work_id == work.id,
                )
                .order_by(StudentStep.step_index)
            )
        )
        if work
        else []
    )
    visual_paths = await question_visual_paths(question_id, db)
    result = await analyze_question(
        provider,
        question.question_text,
        question.subject,
        question.grade or "",
        question.question_type,
        visual_paths,
        question.student_answer,
        [row.text for row in step_rows],
        options=question.options,
    )
    await invalidate_question_learning(db, question)
    analysis = ProblemAnalysis(
        question_id=question_id,
        subject=result.subject,
        problem_type=result.problem_type,
        known_conditions=result.known_conditions,
        goal=result.goal,
        knowledge_points=result.knowledge_points,
        prerequisites=result.prerequisites,
        final_answer=result.final_answer,
        verified=result.answer_verified,
        raw_result=result.model_dump(),
    )
    db.add(analysis)
    await db.flush()
    for index, text in enumerate(result.reference_steps):
        db.add(
            ReferenceStep(
                analysis_id=analysis.id,
                step_index=index,
                text=text,
                expression=text if "=" in text else None,
                explanation="由题目条件进行等价变形" if "=" in text else "推理步骤",
                math_valid=bool(
                    result.answer_verified
                    and question.subject == "数学"
                    and equation_equivalent(text, result.final_answer, require_symbolic=True)
                ),
                uses_condition=index == 0,
            )
        )
    await sync_personal_knowledge_links(db, question, analysis)
    question.status = "analyzed"
    await db.commit()
    return envelope(row_dict(analysis) | {"reference_steps": result.reference_steps})


@app.post("/api/v1/questions/{question_id}/student-work")
async def add_student_work(
    question_id: str,
    payload: dict = Body(...),
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    question = await owned_resource(db, Question, question_id, user)
    await invalidate_question_learning(db, question)
    question.student_answer = str(payload.get("answer", "")) or None
    work = StudentWork(
        question_id=question_id,
        user_id=user.id,
        answer=payload.get("answer", ""),
        explanation=payload.get("explanation", ""),
    )
    db.add(work)
    await db.flush()
    for index, text in enumerate(payload.get("steps", [])):
        db.add(StudentStep(work_id=work.id, step_index=index, text=text))
    await db.commit()
    return envelope(row_dict(work))


async def create_counterfactual_evidence(
    db: AsyncSession,
    *,
    question: Question,
    diagnosis: Diagnosis,
    reference_rows: list[ReferenceStep],
    student_rows: list[StudentStep],
    alignment: list[dict[str, Any]],
) -> dict[str, Any]:
    counterfactual = await validate_first_error_counterfactual(
        provider,
        question_text=question.question_text,
        subject=question.subject,
        alignment=alignment,
    )
    suspected = counterfactual.get("suspected_step")
    first_entry = next((entry for entry in alignment if entry.get("index") == suspected), None)
    first_reference = next(
        (row for row in reference_rows if first_entry and row.id == first_entry.get("reference_step_id")),
        None,
    )
    first_student = next(
        (row for row in student_rows if first_entry and row.id == first_entry.get("student_step_id")),
        None,
    )
    db.add(
        DiagnosisEvidence(
            diagnosis_id=diagnosis.id,
            kind="counterfactual_validation",
            content=counterfactual["conclusion"],
            reference_step_id=first_reference.id if first_reference else None,
            student_step_id=first_student.id if first_student else None,
            alignment=counterfactual["status"],
            equivalent=counterfactual["root_cause_confirmed"],
            uses_condition=bool(first_reference),
            is_first_error=suspected is not None,
            propagated=counterfactual.get("recovered_steps", 0) > 0,
            math_valid=counterfactual["root_cause_confirmed"],
            metadata_json=counterfactual,
        )
    )
    return counterfactual


@app.post("/api/v1/questions/{question_id}/diagnose")
async def diagnose(question_id: str, db: AsyncSession = Depends(get_db)):
    question = await db.get(Question, question_id)
    analysis = (
        await db.scalars(select(ProblemAnalysis).where(ProblemAnalysis.question_id == question_id))
    ).first()
    if not question:
        raise HTTPException(404, "题目不存在")
    if not analysis:
        await analyze(question_id, db)
        analysis = (
            await db.scalars(select(ProblemAnalysis).where(ProblemAnalysis.question_id == question_id))
        ).first()
    if analysis is None:
        raise HTTPException(500, "题目分析未生成")
    reference_rows = list(
        await db.scalars(
            select(ReferenceStep)
            .where(ReferenceStep.analysis_id == analysis.id)
            .order_by(ReferenceStep.step_index)
        )
    )
    work = (
        await db.scalars(
            select(StudentWork)
            .where(StudentWork.question_id == question_id)
            .order_by(StudentWork.created_at.desc())
        )
    ).first()
    student_rows = (
        list(
            await db.scalars(
                select(StudentStep).where(StudentStep.work_id == work.id).order_by(StudentStep.step_index)
            )
        )
        if work
        else []
    )
    references = [x.text for x in reference_rows]
    students = [x.text for x in student_rows]
    result = await diagnose_steps(
        provider,
        question.question_text,
        references,
        students,
        question.subject,
        question.question_type,
        await question_visual_paths(question_id, db),
        question.student_answer,
        question.options,
    )
    alignment = align_steps(reference_rows, student_rows, question.subject, question.question_text)
    first = next((entry for entry in alignment if entry["is_first_error"]), None)
    # 没有手写步骤时只能诊断真实提交的答案，不能把“缺少步骤”伪装成学生的首错步骤。
    if first and student_rows:
        result.first_error_step = first["index"]
        result.first_error_text = first["student_text"] or "缺少对应步骤"
        result.error_type = first["alignment"]
        result.error_location = f"学生路径第 {first['index'] + 1} 步"
    result.recommended_strategy = result.recommended_strategy or (
        result.strategy_candidates[0] if result.strategy_candidates else "路径对比与针对性提示"
    )
    item = Diagnosis(question_id=question_id, **result.model_dump())
    db.add(item)
    await db.flush()
    for entry in alignment:
        db.add(
            DiagnosisEvidence(
                diagnosis_id=item.id,
                kind="step_alignment",
                content=f"{entry['reference_text']} ⇄ {entry['student_text']}",
                reference_step_id=entry["reference_step_id"],
                student_step_id=entry["student_step_id"],
                alignment=entry["alignment"],
                equivalent=entry["equivalent"],
                uses_condition=entry["uses_condition"],
                is_first_error=entry["is_first_error"],
                propagated=entry["propagated"],
                math_valid=entry["math_valid"],
                metadata_json=entry,
            )
        )
    counterfactual = await create_counterfactual_evidence(
        db,
        question=question,
        diagnosis=item,
        reference_rows=reference_rows,
        student_rows=student_rows,
        alignment=alignment,
    )
    await sync_personal_knowledge_links(db, question, analysis, item)
    question.status = "diagnosed"
    await db.commit()
    await db.refresh(item)
    return envelope(
        row_dict(item) | {"evidence": [entry for entry in alignment], "counterfactual": counterfactual}
    )


@app.post("/api/v1/questions/{question_id}/diagnosis/counterfactual")
async def create_counterfactual(question_id: str, db: AsyncSession = Depends(get_db)):
    question = await db.get(Question, question_id)
    diagnosis = (
        await db.scalars(
            select(Diagnosis)
            .where(
                Diagnosis.question_id == question_id,
            )
            .order_by(Diagnosis.created_at.desc())
        )
    ).first()
    analysis = (
        await db.scalars(
            select(ProblemAnalysis).where(
                ProblemAnalysis.question_id == question_id,
            )
        )
    ).first()
    if question is None or diagnosis is None or analysis is None:
        raise HTTPException(404, "题目诊断不存在")
    existing = (
        await db.scalars(
            select(DiagnosisEvidence).where(
                DiagnosisEvidence.diagnosis_id == diagnosis.id,
                DiagnosisEvidence.kind == "counterfactual_validation",
            )
        )
    ).first()
    if existing:
        return envelope(existing.metadata_json)
    reference_rows = list(
        await db.scalars(
            select(ReferenceStep)
            .where(
                ReferenceStep.analysis_id == analysis.id,
            )
            .order_by(ReferenceStep.step_index)
        )
    )
    work = (
        await db.scalars(
            select(StudentWork)
            .where(
                StudentWork.question_id == question_id,
            )
            .order_by(StudentWork.created_at.desc())
        )
    ).first()
    student_rows = (
        list(
            await db.scalars(
                select(StudentStep)
                .where(
                    StudentStep.work_id == work.id,
                )
                .order_by(StudentStep.step_index)
            )
        )
        if work
        else []
    )
    alignment = align_steps(reference_rows, student_rows, question.subject, question.question_text)
    counterfactual = await create_counterfactual_evidence(
        db,
        question=question,
        diagnosis=diagnosis,
        reference_rows=reference_rows,
        student_rows=student_rows,
        alignment=alignment,
    )
    await sync_personal_knowledge_links(db, question, analysis, diagnosis)
    await db.commit()
    return envelope(counterfactual)


@app.get("/api/v1/questions/{question_id}/diagnosis")
async def get_diagnosis(question_id: str, db: AsyncSession = Depends(get_db)):
    item = (
        await db.scalars(
            select(Diagnosis)
            .where(Diagnosis.question_id == question_id)
            .order_by(Diagnosis.created_at.desc())
        )
    ).first()
    evidence = (
        list(await db.scalars(select(DiagnosisEvidence).where(DiagnosisEvidence.diagnosis_id == item.id)))
        if item
        else []
    )
    counterfactual = next((x.metadata_json for x in evidence if x.kind == "counterfactual_validation"), None)
    step_evidence = [row_dict(x) for x in evidence if x.kind == "step_alignment"]
    return envelope(
        (row_dict(item) | {"evidence": step_evidence, "counterfactual": counterfactual}) if item else None
    )


@app.patch("/api/v1/questions/{question_id}/diagnosis")
async def correct_diagnosis(question_id: str, payload: dict = Body(...), db: AsyncSession = Depends(get_db)):
    item = (
        await db.scalars(
            select(Diagnosis)
            .where(Diagnosis.question_id == question_id)
            .order_by(Diagnosis.created_at.desc())
        )
    ).first()
    if item is None:
        raise HTTPException(404, "诊断不存在")
    for field in (
        "first_error_step",
        "first_error_text",
        "error_type",
        "root_misconception",
        "error_location",
        "missing_prerequisites",
        "recommended_strategy",
        "confidence",
    ):
        if field in payload:
            setattr(item, field, payload[field])
    item.user_confirmed = True
    item.correction = payload
    await db.commit()
    return envelope(row_dict(item))


@app.get("/api/v1/jobs/{job_id}")
async def get_job(job_id: str, db: AsyncSession = Depends(get_db)):
    job = await db.get(ProcessingJob, job_id)
    if not job:
        raise HTTPException(404, "任务不存在")
    return envelope(row_dict(job))


@app.post("/api/v1/jobs/{job_id}/retry")
async def retry_job(job_id: str, background: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    job = await db.get(ProcessingJob, job_id)
    if job is None:
        raise HTTPException(404, "任务不存在")
    # All writers lock the question first, then the job, to keep lock order consistent.
    question_id = job.question_id
    question = await lock_recognition_question(db, question_id)
    job = await db.get(ProcessingJob, job_id, with_for_update=True, populate_existing=True)
    if job is None:
        raise HTTPException(404, "任务不存在")
    if job.status != "failed":
        raise HTTPException(409, "任务仍在处理或已完成，请刷新后查看结果")
    existing = await active_recognition_job(db, job.question_id)
    if existing:
        return envelope(row_dict(existing) | {"resumed": True})
    asset = (
        await db.scalars(
            select(QuestionAsset).where(
                QuestionAsset.question_id == job.question_id,
                QuestionAsset.kind == "crop",
            )
        )
    ).first()
    if asset is None and job.kind == "ingest":
        asset = (
            await db.scalars(
                select(QuestionAsset).where(
                    QuestionAsset.question_id == job.question_id,
                    QuestionAsset.kind == "original",
                )
            )
        ).first()
    if asset is None:
        raise HTTPException(422, "缺少识别图片，请重新框选题目")
    job.status = "pending"
    job.progress = 0
    job.error = None
    question.status = "processing"
    await db.commit()
    background.add_task(
        process_question, job.id, job.question_id, asset.path, require_crop=asset.kind == "crop"
    )
    return envelope(row_dict(job))


async def tutor_learning_context(
    session: TutorSession, db: AsyncSession
) -> tuple[Question, ProblemAnalysis | None, list[ReferenceStep]]:
    question = await db.get(Question, session.question_id)
    if question is None:
        raise HTTPException(404, "题目不存在")
    analysis = (
        await db.scalars(select(ProblemAnalysis).where(ProblemAnalysis.question_id == session.question_id))
    ).first()
    references = (
        list(
            await db.scalars(
                select(ReferenceStep)
                .where(ReferenceStep.analysis_id == analysis.id)
                .order_by(ReferenceStep.step_index)
            )
        )
        if analysis
        else []
    )
    return question, analysis, references


def tutor_knowledge_points(question: Question, analysis: ProblemAnalysis | None) -> list[Any]:
    return list((analysis.knowledge_points if analysis else None) or question.knowledge_points or [])


async def create_session_variant(session: TutorSession, transfer: str, db: AsyncSession) -> VariantQuestion:
    question, analysis, _ = await tutor_learning_context(session, db)
    knowledge_points = tutor_knowledge_points(question, analysis)
    diagnosis = (
        await db.scalars(
            select(Diagnosis)
            .where(Diagnosis.question_id == session.question_id)
            .order_by(Diagnosis.created_at.desc())
        )
    ).first()
    context = "；".join(
        filter(
            None,
            [
                question.question_text,
                "、".join(str(item) for item in knowledge_points),
                diagnosis.root_misconception if diagnosis else "",
            ],
        )
    )
    used_variants = list(
        await db.scalars(
            select(VariantQuestion).where(
                VariantQuestion.question_id == session.question_id,
            )
        )
    )
    used_question_texts = {item.question_text for item in used_variants}
    used_dataset_ids = {
        str(reference_id)
        for item in used_variants
        for reference_id in ((item.generation_metadata or {}).get("retrieval_ids") or [])
    }
    retrieval_status = "ok"
    try:
        retrieval = await retrieve_variant_references(
            db,
            subject=question.subject,
            grade=question.grade or "",
            question_type=question.question_type,
            knowledge_points=knowledge_points,
            original_text=question.question_text,
            transfer_type=transfer,
            excluded_question_ids=used_dataset_ids,
        )
    except Exception as exc:
        logger.warning(
            "Tutor retrieval unavailable for session=%s transfer=%s: %s",
            session.id,
            transfer,
            type(exc).__name__,
        )
        retrieval = []
        retrieval_status = "unavailable"
    retrieval = [item for item in retrieval if item.question_text not in used_question_texts]
    generated, verified, generation = await generate_variant(
        provider,
        question.subject,
        transfer,
        context,
        question.question_type,
        knowledge_points=knowledge_points,
        references=retrieval,
    )
    generation_metadata = generation.model_dump() | {
        "retrieval_pipeline": "bge_m3_qdrant_reranker",
        "retrieval_status": retrieval_status,
    }
    item = VariantQuestion(
        question_id=session.question_id,
        session_id=session.id,
        transfer_type=transfer,
        question_text=generated.question_text,
        answer=generated.answer,
        explanation=generated.explanation,
        reference_solution=generated.reference_solution,
        verified=verified,
        generation_metadata=generation_metadata,
    )
    db.add(item)
    await db.flush()
    state = dict(session.state or {})
    state[f"{transfer}_variant_id"] = item.id
    state[f"{transfer}_validated_variant_id"] = item.id if verified else None
    state[f"{transfer}_attempts"] = 0
    state[f"{transfer}_variant_generation"] = generation_metadata
    state[f"{transfer}_variant_options"] = [item.model_dump(mode="json") for item in generated.options]
    state["activity_feedback"] = ""
    session.state = state
    await record_agent_tool(
        db,
        session.id,
        f"{transfer}_transfer_generated",
        "generate_variant",
        {
            "transfer_type": transfer,
            "knowledge_points": knowledge_points,
            "retrieval_pipeline": "bge_m3_qdrant_reranker",
        },
        {"variant_id": item.id, "verified": verified, **generation_metadata},
    )
    return item


async def session_variant_is_aligned(
    item: VariantQuestion | None,
    session: TutorSession,
    db: AsyncSession,
) -> bool:
    if item is None:
        return False
    question, analysis, _ = await tutor_learning_context(session, db)
    result = VariantOutput(
        question_text=item.question_text,
        answer=item.answer,
        explanation=item.explanation,
        reference_solution=list(item.reference_solution or []),
    )
    return verify_variant(result, question.subject) and verify_knowledge_alignment(
        result,
        tutor_knowledge_points(question, analysis),
        question.question_text,
    )


async def reuse_or_create_session_variant(
    session: TutorSession, transfer: str, db: AsyncSession
) -> VariantQuestion:
    state = dict(session.state or {})
    variant_id = state.get(f"{transfer}_variant_id")
    item = await db.get(VariantQuestion, variant_id) if variant_id else None
    if item is not None and await session_variant_is_aligned(item, session, db):
        state[f"{transfer}_validated_variant_id"] = item.id
        session.state = state
        return item
    if item is not None:
        state.setdefault("invalidated_variant_ids", []).append(item.id)
        state[f"{transfer}_variant_id"] = None
        state[f"{transfer}_validated_variant_id"] = None
        session.state = state
    return await create_session_variant(session, transfer, db)


async def ensure_tutor_activity_state(
    session: TutorSession, db: AsyncSession
) -> tuple[Question, ProblemAnalysis | None, list[ReferenceStep]]:
    session.stage = canonical_tutor_stage(session.stage)
    question, analysis, references = await tutor_learning_context(session, db)
    state = {"understanding_passed": False, "assisted": False, **(session.state or {})}
    if state.get("teaching_policy", {}).get("mode") == "compressed" and state.get("teaching_brief"):
        state.setdefault("answer_reveal_acknowledged", False)
        state.setdefault("targeted_check_pending", False)
    elif not state.get("understanding_plan"):
        state["understanding_plan"] = build_understanding_plan(
            question_text=question.question_text,
            subject=question.subject,
            question_type=question.question_type,
            knowledge_points=tutor_knowledge_points(question, analysis),
            reference_steps=[item.text for item in references],
        )
        state["understanding_index"] = 0
        state["activity_attempts"] = {}
    session.state = state
    transfer = (
        "near" if session.stage == "near_transfer" else "far" if session.stage == "far_transfer" else None
    )
    if transfer and not state.get("near_confirmation"):
        await reuse_or_create_session_variant(session, transfer, db)
    return question, analysis, references


async def current_tutor_activity(
    session: TutorSession,
    question: Question,
    analysis: ProblemAnalysis | None,
    references: list[ReferenceStep],
    db: AsyncSession,
) -> dict[str, Any] | None:
    state = session.state or {}
    feedback = str(state.get("activity_feedback", ""))
    if session.stage == "understanding" and not state.get("understanding_passed"):
        if state.get("teaching_policy", {}).get("mode") == "compressed":
            brief = dict(state.get("teaching_brief") or {})
            if not state.get("answer_reveal_acknowledged"):
                return answer_reveal_activity(brief)
            if state.get("targeted_check_pending"):
                source = dict(brief.get("check") or {})
                attempts = dict(state.get("activity_attempts") or {})
                return activity_public(
                    source,
                    attempt=int(attempts.get(source.get("id", "targeted-check"), 0)) + 1,
                    feedback=feedback,
                )
            return None
        plan = list(state.get("understanding_plan") or [])
        index = min(int(state.get("understanding_index", 0)), max(0, len(plan) - 1))
        if not plan:
            return None
        source = plan[index]
        if state.get("understanding_confirmation"):
            item = confirmation_activity(source)
            return activity_public(
                item,
                attempt=1,
                feedback=feedback,
                teaching=str(source.get("teaching", "")),
            )
        attempts = dict(state.get("activity_attempts") or {})
        return activity_public(source, attempt=int(attempts.get(source["id"], 0)) + 1, feedback=feedback)
    if session.stage == "teach_back":
        item = teach_back_activity(
            tutor_knowledge_points(question, analysis), [row.text for row in references]
        )
        return activity_public(item, attempt=int(state.get("teach_back_attempts", 0)) + 1, feedback=feedback)
    if session.stage == "near_transfer" and state.get("near_confirmation"):
        item = dict(state["near_confirmation"])
        return activity_public(item, attempt=1, feedback=feedback, teaching=str(item.get("teaching", "")))
    if session.stage in {"near_transfer", "far_transfer"}:
        transfer = "near" if session.stage == "near_transfer" else "far"
        variant_id = state.get(f"{transfer}_variant_id")
        variant_item = await db.get(VariantQuestion, variant_id) if variant_id else None
        if variant_item is None:
            variant_item = await create_session_variant(session, transfer, db)
        state = dict(session.state or {})
        normalized_type = str(
            (state.get("teaching_policy") or {}).get("question_type") or question.question_type
        )
        variant_options = list(state.get(f"{transfer}_variant_options") or [])
        activity_type = (
            "multiple_choice"
            if normalized_type == "multiple_choice" and variant_options
            else "single_choice"
            if variant_options
            else "short_answer"
            if normalized_type == "fill_blank"
            else "variant"
        )
        activity_input_mode = (
            "multiple_choice"
            if activity_type == "multiple_choice"
            else "choice"
            if activity_type == "single_choice"
            else normalized_type
        )
        public_options = [
            {
                "value": str(option.get("label", "")),
                "label": "  ".join(filter(None, (str(option.get("label", "")), str(option.get("text", ""))))),
            }
            for option in variant_options
            if isinstance(option, dict)
        ]
        raw = {
            "id": f"{transfer}-variant-{variant_item.id}",
            "variant_id": variant_item.id,
            "type": activity_type,
            "title": "相似题练习" if transfer == "near" else "换个场景试一试",
            "question": variant_item.question_text,
            "options": public_options,
            "input_mode": activity_input_mode,
            "teaching": str(state.get("transfer_guidance", "")),
            "teaching_title": "我们一步一步写" if state.get("transfer_guidance") else "",
        }
        return activity_public(
            raw, attempt=int((session.state or {}).get(f"{transfer}_attempts", 0)) + 1, feedback=feedback
        )
    return None


def public_tutor_session(session: TutorSession) -> dict[str, Any]:
    # Only progress is public. Activity plans, marking keys and retrieved solutions
    # remain server-side; intentional lesson explanations have their own fields.
    state = session.state or {}
    progress_fields = (
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
    )
    return row_dict(session) | {"state": {key: state[key] for key in progress_fields if key in state}}


async def tutor_session_payload(session: TutorSession, db: AsyncSession) -> dict[str, Any]:
    question, analysis, references = await ensure_tutor_activity_state(session, db)
    activity = await current_tutor_activity(session, question, analysis, references, db)
    turns = list(
        await db.scalars(
            select(TutorTurn).where(TutorTurn.session_id == session.id).order_by(TutorTurn.created_at)
        )
    )
    figure = (
        await db.scalars(
            select(QuestionAsset)
            .where(
                QuestionAsset.question_id == question.id,
                QuestionAsset.kind == "question_figure",
            )
            .order_by(QuestionAsset.created_at.desc())
        )
    ).first()
    if figure is None:
        figure = (
            await db.scalars(
                select(QuestionAsset)
                .where(
                    QuestionAsset.question_id == question.id,
                    QuestionAsset.kind == "crop",
                )
                .order_by(QuestionAsset.created_at.desc())
            )
        ).first()
    state = session.state or {}
    stage_status = (
        "completed"
        if session.stage == "finished"
        else "passed"
        if session.stage == "understanding" and state.get("understanding_passed")
        else "active"
    )
    return public_tutor_session(session) | {
        "stage_status": stage_status,
        "activity": activity,
        "knowledge_title": " · ".join(str(item) for item in tutor_knowledge_points(question, analysis)[:2])
        or question.title,
        "visualization_available": recommended_visualization(
            question.subject,
            question.question_type,
            tutor_knowledge_points(question, analysis),
        )
        is not None,
        "question": {
            "id": question.id,
            "text": question.question_text,
            "figure_url": sign_media_url("/" + figure.path, settings.auth_secret) if figure else None,
        },
        "assisted": bool(state.get("assisted")),
        "teaching_policy": state.get("teaching_policy", {"mode": "full"}),
        "answer_reveal": state.get("answer_reveal"),
        "completion_summary": state.get("completion_summary", ""),
        "turns": [row_dict(item) for item in turns],
    }


async def complete_tutor_learning(
    session: TutorSession,
    user: User,
    db: AsyncSession,
    *,
    transfer_insufficient: bool,
) -> tuple[MasteryState, MisconceptionState, ReviewPlan]:
    state = dict(session.state or {})
    evidence = {
        "teach_back": state.get("teach_back"),
        "near_transfer": state.get("near_transfer"),
        "far_transfer": state.get("far_transfer"),
        "hint_level": session.hint_level,
        "strategy": "assisted_progression" if state.get("assisted") else "micro_activity",
    }
    question = await db.get(Question, session.question_id)
    analysis = (
        await db.scalars(
            select(ProblemAnalysis).where(
                ProblemAnalysis.question_id == session.question_id,
            )
        )
    ).first()
    diagnosis = (
        await db.scalars(
            select(Diagnosis)
            .where(
                Diagnosis.question_id == session.question_id,
            )
            .order_by(Diagnosis.created_at.desc())
        )
    ).first()
    if question is None:
        raise HTTPException(404, "题目不存在")
    target = cognition_target(
        subject=question.subject,
        question_type=question.question_type,
        title=question.title,
        question_knowledge_points=question.knowledge_points,
        analysis_knowledge_points=analysis.knowledge_points if analysis else None,
        diagnosis_error_type=diagnosis.error_type if diagnosis else None,
        diagnosis_root_misconception=diagnosis.root_misconception if diagnosis else None,
    )
    mastery, misconception = await update_cognition(
        db,
        user.id,
        session.question_id,
        evidence,
        subject=target.subject,
        knowledge_point=target.knowledge_point,
        misconception_code=target.misconception_code,
        misconception_label=target.misconception_label,
    )
    session.stage = "finished"
    session.status = "completed"
    session.mastery_score = mastery.mastery_score
    days = 1 if transfer_insufficient else 3 if state.get("assisted") else 15
    reason = (
        "迁移练习还不稳定，已提高复习优先级" if transfer_insufficient else "本轮学习已完成，按掌握情况复习"
    )
    plan = ReviewPlan(
        user_id=user.id,
        question_id=session.question_id,
        due_at=datetime.now(timezone.utc) + timedelta(days=days),
        interval_days=days,
        reason=reason,
    )
    db.add(plan)
    state["completion_summary"] = (
        "这次换一种题目还不够稳定，我已经把它放到近期优先复习。"
        if transfer_insufficient
        else "本轮已经完成。下一次复习会根据这次是否需要提示来安排。"
    )
    state["mastery_proven"] = not transfer_insufficient and bool(state.get("far_transfer"))
    session.state = state
    await record_agent_tool(
        db,
        session.id,
        "activity_finish",
        "update_cognition",
        evidence,
        {
            "mastery": mastery.mastery_score,
            "interval_days": days,
            "priority": "high" if transfer_insufficient else "normal",
        },
    )
    return mastery, misconception, plan


def activity_answer_text(activity: dict[str, Any], answer: Any) -> str:
    values = answer if isinstance(answer, list) else [answer]
    labels = {str(item.get("value")): str(item.get("label")) for item in activity.get("options", [])}
    return "、".join(labels.get(str(value), str(value)) for value in values)


async def tutor_micro_answer_passed(
    activity: dict[str, Any],
    answer: Any,
    question: Question,
) -> bool:
    expected_values = list(activity.get("correct_answers") or [])
    expected: Any = (
        expected_values
        if activity.get("type") == "multiple_choice"
        else (expected_values[0] if expected_values else "")
    )
    result = await grade_answer(
        provider,
        question=str(activity.get("question") or question.question_text),
        answer=answer,
        expected=expected,
        reference_solution=[],
        subject=question.subject,
        question_type=str(activity.get("type") or question.question_type),
        options=list(activity.get("options") or []),
    )
    return bool(result["correct"] and result["can_update_learning"])


async def answer_handwriting_context(
    *,
    context_type: str,
    context_id: str,
    activity_id: str,
    mistake_id: str,
    mode: str,
    user: User,
    db: AsyncSession,
) -> tuple[str, str]:
    """Validate an answer context and return subject plus the visible question text."""
    if context_type == "tutor":
        session = await db.get(TutorSession, context_id)
        if session is None or session.user_id != user.id:
            raise HTTPException(404, "学习会话不存在")
        question, analysis, references = await ensure_tutor_activity_state(session, db)
        activity = await current_tutor_activity(session, question, analysis, references, db)
        if activity is None or str(activity.get("id", "")) != activity_id:
            raise HTTPException(409, "当前练习已经变化，请刷新后重新上传")
        if activity.get("type") in {"single_choice", "multiple_choice", "explanation", "teach_back"}:
            raise HTTPException(422, "当前练习不需要上传手写过程")
        return question.subject, str(activity.get("question") or question.question_text)

    if context_type == "practice":
        mistake = await db.get(Question, mistake_id)
        practice_question = await db.get(DatasetQuestion, context_id)
        if mistake is None or mistake.user_id != user.id or practice_question is None:
            raise HTTPException(404, "没有找到这道练习题")
        served = (
            await db.scalars(
                select(PracticeRecommendation)
                .where(
                    PracticeRecommendation.user_id == user.id,
                    PracticeRecommendation.mistake_id == mistake.id,
                    PracticeRecommendation.dataset_question_id == practice_question.id,
                    PracticeRecommendation.mode == mode,
                )
                .order_by(PracticeRecommendation.created_at.desc())
            )
        ).first()
        if served is None or (served.retrieval_trace or {}).get(
            "source_question_fingerprint"
        ) != await learning_source_fingerprint(db, mistake):
            raise HTTPException(409, "请先获取推荐题再上传作答")
        if practice_question.options:
            raise HTTPException(422, "选择题请直接选择选项")
        return practice_question.subject, practice_question.question_text

    if context_type == "assignment":
        link = await db.get(AssignmentStudent, context_id)
        if link is None or link.student_id != user.id:
            raise HTTPException(404, "布置任务不存在")
        assignment = await db.get(QuestionAssignment, link.assignment_id)
        if assignment is None:
            raise HTTPException(409, "布置记录已不存在")
        can_repeat = link.status == "completed" and (assignment.settings or {}).get("allow_repeat", False)
        if link.status != "pending" and not can_repeat:
            raise HTTPException(409, "当前任务暂不能再次作答")
        assignment_question = await db.get(Question, assignment.question_id)
        if assignment_question is None:
            raise HTTPException(409, "题目已不存在")
        return assignment_question.subject, assignment_question.question_text

    if context_type == "review":
        plan = await db.get(ReviewPlan, context_id)
        if plan is None or plan.user_id != user.id or plan.status != "pending":
            raise HTTPException(404, "待复习题不存在")
        review_question = await db.get(Question, plan.question_id)
        if review_question is None:
            raise HTTPException(404, "题目不存在")
        if review_question.options:
            raise HTTPException(422, "选择题请直接选择选项")
        return review_question.subject, review_question.question_text

    raise HTTPException(422, "不支持的答题场景")


@app.post("/api/v1/answers/handwriting")
async def upload_answer_handwriting(
    file: UploadFile = File(...),
    context_type: str = Form(...),
    context_id: str = Form(...),
    activity_id: str = Form(""),
    mistake_id: str = Form(""),
    mode: str = Form(""),
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    subject, question_text = await answer_handwriting_context(
        context_type=context_type,
        context_id=context_id,
        activity_id=activity_id,
        mistake_id=mistake_id,
        mode=mode,
        user=user,
        db=db,
    )
    raw = await file.read()
    if not raw:
        raise HTTPException(422, "请选择包含手写过程的照片")
    if len(raw) > 15 * 1024 * 1024:
        raise HTTPException(413, "照片不能超过 15MB")
    folder = settings.upload_dir / "answers" / user.id / context_type / context_id
    target = folder / f"handwriting-{uuid.uuid4().hex}.jpg"
    try:
        save_original(raw, target)
    except (OSError, ValueError) as exc:
        raise HTTPException(422, "仅支持 JPEG、PNG 或 WEBP 图片") from exc
    try:
        recognition = await recognize_handwritten_answer(
            provider,
            target,
            question_text=question_text,
            subject=subject,
        )
    except Exception as exc:
        logger.warning(
            "handwriting recognition failed context=%s error=%s",
            context_type,
            type(exc).__name__,
        )
        raise HTTPException(503, "照片已保留，但暂时无法识别，请稍后重试或使用文字输入") from exc
    relative = target.relative_to(settings.upload_dir).as_posix()
    return envelope(
        {
            "image_url": sign_media_url(f"/uploads/{relative}", settings.auth_secret),
            "recognition": recognition.model_dump(mode="json"),
        }
    )


@app.post("/api/v1/tutor/sessions/{session_id}/activity/answer")
async def answer_tutor_activity(
    session_id: str,
    payload: dict = Body(...),
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await db.get(TutorSession, session_id)
    if session is None or session.user_id != user.id:
        raise HTTPException(404, "会话不存在")
    question, analysis, references = await ensure_tutor_activity_state(session, db)
    activity = await current_tutor_activity(session, question, analysis, references, db)
    if activity is None or str(payload.get("activity_id", "")) != activity.get("id"):
        raise HTTPException(409, "当前小任务已经变化，请刷新后继续")
    answer = payload.get("answer", "")
    working = str(payload.get("working", "")).strip()
    handwriting_image_url, handwriting_recognition = validate_answer_handwriting(
        user_id=user.id,
        context_type="tutor",
        context_id=session.id,
        image_url=str(payload.get("handwriting_image_url", "")),
        recognition=payload.get("handwriting_recognition"),
    )
    unknown = bool(payload.get("unknown")) or answer == "__unknown__"
    state = dict(session.state or {})
    feedback = ""
    passed = False
    grading: dict[str, Any] = {}

    if session.stage == "understanding":
        compressed = state.get("teaching_policy", {}).get("mode") == "compressed"
        if compressed and activity.get("type") == "explanation":
            state["answer_reveal_acknowledged"] = True
            if str(answer) == "need_help":
                state["targeted_check_pending"] = True
                feedback = "只确认一个易错点。"
            else:
                state["understanding_passed"] = True
                state["understood"] = True
                state["near_transfer"] = None
                session.stage = "near_transfer"
                state["next_goal"] = "做一道相似题"
                feedback = "好，直接练一道。"
                session.state = state
                await reuse_or_create_session_variant(session, "near", db)
                state = dict(session.state or {})
            passed = True
        elif compressed and state.get("targeted_check_pending"):
            source = dict((state.get("teaching_brief") or {}).get("check") or {})
            passed = await tutor_micro_answer_passed(source, answer, question) and not unknown
            attempts = dict(state.get("activity_attempts") or {})
            count = int(attempts.get(source.get("id", "targeted-check"), 0)) + 1
            attempts[source.get("id", "targeted-check")] = count
            state["activity_attempts"] = attempts
            if passed or count >= 2 or unknown:
                if not passed:
                    state["assisted"] = True
                state["targeted_check_pending"] = False
                state["understanding_passed"] = True
                state["understood"] = True
                session.stage = "near_transfer"
                state["near_transfer"] = None
                state["next_goal"] = "做一道相似题"
                feedback = "答对了，练一道类似的。" if passed else "记住这个条件，我们直接练一道。"
                session.state = state
                await reuse_or_create_session_variant(session, "near", db)
                state = dict(session.state or {})
            else:
                feedback = str(source.get("hint") or "再用刚才的关键条件判断一次。")[:70]
        else:
            plan = list(state.get("understanding_plan") or [])
            index = int(state.get("understanding_index", 0))
            source = plan[index]
            if state.get("understanding_confirmation"):
                state["assisted"] = True
                state["understanding_confirmation"] = False
                state["understanding_index"] = index + 1
                passed = True
                feedback = "记住这个判断方法，我们继续下一个小问题。"
            else:
                passed = await tutor_micro_answer_passed(source, answer, question) and not unknown
                attempts = dict(state.get("activity_attempts") or {})
                count = int(attempts.get(source["id"], 0)) + 1
                attempts[source["id"]] = count
                state["activity_attempts"] = attempts
                if passed:
                    state["understanding_index"] = index + 1
                    feedback = "答对了，我们继续。"
                elif unknown or count >= 2:
                    state["understanding_confirmation"] = True
                    state["assisted"] = True
                    feedback = "先看一个最短讲解，再确认一次就继续。"
                else:
                    feedback = str(source.get("hint", "再看一眼题目条件，然后试一次。"))[:70]
            if int(state.get("understanding_index", 0)) >= len(plan):
                state["understanding_passed"] = True
                state["understood"] = True
                state["next_goal"] = "用自己的话说一遍"
                feedback = "已经抓住这个关键点。"

    elif session.stage == "teach_back":
        explanation = str(answer).strip()
        assessment = evaluate_teach_back(
            explanation,
            question.subject,
            question.question_type,
            tutor_knowledge_points(question, analysis),
            [item.text for item in references],
        )
        teach_back_attempt_count = int(state.get("teach_back_attempts", 0)) + 1
        state["teach_back_attempts"] = teach_back_attempt_count
        passed = bool(assessment["passed"])
        if passed or teach_back_attempt_count >= 2:
            state["teach_back"] = passed
            state["teach_back_passed"] = passed
            if not passed:
                state["assisted"] = True
            session.stage = "near_transfer"
            state["next_goal"] = "完成一道相似题"
            feedback = (
                "讲清楚了，接着做一道相似题。"
                if passed
                else "这次还少一个关键点，我先记录下来，我们继续练一道相似题。"
            )
            session.state = state
            await reuse_or_create_session_variant(session, "near", db)
            state = dict(session.state or {})
        else:
            feedback = str(assessment["feedback"])

    elif session.stage == "near_transfer" and state.get("near_confirmation"):
        state["near_confirmation"] = None
        state["near_transfer"] = False
        state["assisted"] = True
        if state.get("teaching_policy", {}).get("skip_far_transfer"):
            feedback = "本轮练习完成。"
            passed = True
            session.state = state
            await complete_tutor_learning(session, user, db, transfer_insufficient=True)
            state = dict(session.state or {})
        else:
            session.stage = "far_transfer"
            state["next_goal"] = "换一个场景再试一次"
            feedback = "已经看懂这一步，我们换个场景继续。"
            passed = True
            session.state = state
            await reuse_or_create_session_variant(session, "far", db)
            state = dict(session.state or {})

    elif session.stage in {"near_transfer", "far_transfer"}:
        transfer = "near" if session.stage == "near_transfer" else "far"
        variant_id = state.get(f"{transfer}_variant_id")
        variant_item = await db.get(VariantQuestion, variant_id) if variant_id else None
        if variant_item is None:
            raise HTTPException(409, "练习题已经变化，请刷新后继续")
        if unknown or writing_help_requested(answer):
            guidance = build_writing_guidance(
                list(variant_item.reference_solution or []),
                variant_item.explanation or "",
                variant_item.answer or "",
            )
            state["transfer_guidance"] = guidance
            feedback = "不会写没关系。这次不计作答次数，请先照着下面的步骤组织答案。"
            state["activity_feedback"] = feedback
            state["branch"] = f"activity_{session.stage}_writing_help"
            state["assisted"] = True
            session.state = state
            session.turn_count += 1
            db.add(
                TutorTurn(
                    session_id=session.id,
                    role="user",
                    content="我不会写，请教我",
                    stage=session.stage,
                    metadata_json={
                        "activity_id": activity["id"],
                        "activity_type": activity["type"],
                        "unknown": True,
                        "attempt_consumed": False,
                    },
                )
            )
            db.add(
                TutorTurn(
                    session_id=session.id,
                    role="assistant",
                    content=guidance,
                    stage=session.stage,
                    metadata_json={
                        "activity_id": activity["id"],
                        "branch": "writing_help",
                    },
                )
            )
            await db.commit()
            return envelope(await tutor_session_payload(session, db))
        state.pop("transfer_guidance", None)
        grading = await grade_answer(
            provider,
            question=variant_item.question_text,
            answer=str(answer),
            expected=variant_item.answer,
            reference_solution=list(variant_item.reference_solution or []),
            subject=question.subject,
            question_type=question.question_type,
        )
        if not grading["can_update_learning"]:
            feedback = str(grading["feedback"])
            state["activity_feedback"] = feedback
            state["branch"] = f"activity_{session.stage}_review_required"
            state["last_grading"] = grading
            session.state = state
            session.turn_count += 1
            db.add(
                TutorTurn(
                    session_id=session.id,
                    role="user",
                    content=str(answer),
                    stage=session.stage,
                    metadata_json={
                        "activity_id": activity["id"],
                        "grading": grading,
                        "attempt_consumed": False,
                    },
                )
            )
            db.add(
                TutorTurn(
                    session_id=session.id,
                    role="assistant",
                    content=feedback,
                    stage=session.stage,
                    metadata_json={"activity_id": activity["id"], "grading_verdict": grading["verdict"]},
                )
            )
            await db.commit()
            return envelope(await tutor_session_payload(session, db))
        passed = bool(grading["correct"])
        transfer_attempt_count = int(state.get(f"{transfer}_attempts", 0)) + 1
        state[f"{transfer}_attempts"] = transfer_attempt_count
        db.add(
            VariantAttempt(
                variant_id=variant_item.id,
                user_id=user.id,
                answer=str(answer),
                correct=passed,
                elapsed_seconds=int(payload.get("elapsed_seconds", 0)),
                hint_level=session.hint_level,
            )
        )
        if passed and transfer == "near" and state.get("teaching_policy", {}).get("skip_far_transfer"):
            state["near_transfer"] = True
            state["far_transfer"] = None
            session.state = state
            feedback = "这道相似题做对了，本轮学习完成。"
            await complete_tutor_learning(session, user, db, transfer_insufficient=False)
            state = dict(session.state or {})
        elif passed and transfer == "near":
            state["near_transfer"] = True
            session.stage = "far_transfer"
            feedback = "这道相似题做对了，我们换个场景试一试。"
            session.state = state
            await reuse_or_create_session_variant(session, "far", db)
            state = dict(session.state or {})
        elif passed:
            state["far_transfer"] = True
            session.state = state
            feedback = "迁移题完成，本轮学习结束。"
            await complete_tutor_learning(session, user, db, transfer_insufficient=False)
            state = dict(session.state or {})
        elif transfer_attempt_count == 1:
            feedback = str(grading["feedback"])
        elif transfer == "near" and state.get("teaching_policy", {}).get("skip_far_transfer"):
            state["near_transfer"] = False
            state["assisted"] = True
            state["transfer_insufficient"] = True
            session.state = state
            feedback = "这次还不稳定，我已安排近期复习。"
            await complete_tutor_learning(session, user, db, transfer_insufficient=True)
            state = dict(session.state or {})
        elif transfer == "near":
            state["near_transfer"] = False
            state["assisted"] = True
            state["near_confirmation"] = remediation_confirmation(
                variant_item.id,
                variant_item.explanation or "先对照题目条件，再按顺序完成关键步骤。",
                variant_item.answer,
            )
            feedback = "先看这道题的简短讲解，再完成一个简单确认。"
        else:
            state["far_transfer"] = False
            state["transfer_insufficient"] = True
            state["assisted"] = True
            session.state = state
            feedback = "这次换一种题目还不稳定，本轮先结束，并提高后续复习优先级。"
            await complete_tutor_learning(session, user, db, transfer_insufficient=True)
            state = dict(session.state or {})

    feedback = feedback.strip()
    state["activity_feedback"] = feedback
    state["branch"] = f"activity_{session.stage}_{'pass' if passed else 'continue'}"
    session.state = state
    session.turn_count += 1
    db.add(
        TutorTurn(
            session_id=session.id,
            role="user",
            content=activity_answer_text(activity, answer),
            stage=session.stage,
            metadata_json={
                "activity_id": activity["id"],
                "activity_type": activity["type"],
                "working": working[:500] if working else "",
                "handwriting_image_url": sign_media_url(handwriting_image_url, settings.auth_secret),
                "handwriting_recognition": handwriting_recognition,
                "grading": grading if session.stage in {"near_transfer", "far_transfer", "finished"} else {},
            },
        )
    )
    db.add(
        TutorTurn(
            session_id=session.id,
            role="assistant",
            content=feedback,
            stage=session.stage,
            metadata_json={
                "activity_id": activity["id"],
                "passed": passed,
                "assisted": bool(state.get("assisted")),
            },
        )
    )
    await db.commit()
    return envelope(await tutor_session_payload(session, db))


@app.post("/api/v1/tutor/sessions")
async def start_tutor(
    payload: dict = Body(...), user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    question = await owned_resource(db, Question, str(payload.get("question_id", "")), user)
    analysis = (
        await db.scalars(select(ProblemAnalysis).where(ProblemAnalysis.question_id == question.id))
    ).first()
    if (
        analysis is None
        or not analysis.final_answer.strip()
        or analysis.final_answer.startswith("需要根据完整题目")
    ):
        raise HTTPException(409, "请先完成题目分析，再开始学习")
    references = (
        list(
            await db.scalars(
                select(ReferenceStep)
                .where(ReferenceStep.analysis_id == analysis.id)
                .order_by(ReferenceStep.step_index)
            )
        )
        if analysis
        else []
    )
    work = (
        await db.scalars(
            select(StudentWork)
            .where(
                StudentWork.question_id == question.id,
            )
            .order_by(StudentWork.created_at.desc())
        )
    ).first()
    student_rows = (
        list(
            await db.scalars(
                select(StudentStep)
                .where(
                    StudentStep.work_id == work.id,
                )
                .order_by(StudentStep.step_index)
            )
        )
        if work
        else []
    )
    diagnosis = (
        await db.scalars(
            select(Diagnosis)
            .where(
                Diagnosis.question_id == question.id,
            )
            .order_by(Diagnosis.created_at.desc())
        )
    ).first()
    correct_answer = str(analysis.final_answer if analysis else "").strip()
    policy = adaptive_teaching_policy(
        question.question_type,
        options=question.options,
        student_steps=[item.text for item in student_rows],
        correct_answer=correct_answer,
    )
    brief = None
    plan: list[dict[str, Any]] = []
    if policy["mode"] == "compressed":
        brief = await build_adaptive_teaching_brief(
            provider,
            question_text=question.question_text,
            options=question.options,
            correct_answer=correct_answer,
            student_answer=question.student_answer or "未作答",
            diagnosis=row_dict(diagnosis) if diagnosis else {},
            student_steps=[item.text for item in student_rows],
            knowledge_points=tutor_knowledge_points(question, analysis),
            question_type=policy["question_type"],
        )
    else:
        plan = build_understanding_plan(
            question_text=question.question_text,
            subject=question.subject,
            question_type=question.question_type,
            knowledge_points=tutor_knowledge_points(question, analysis),
            reference_steps=[item.text for item in references],
        )
    answer_reveal = None
    if brief is not None:
        answer_reveal = {
            "topic": brief.topic,
            "student_answer": choice_answer_label(question.student_answer, question.options)
            if policy["question_type"] in {"choice", "multiple_choice"}
            else (question.student_answer or "未作答"),
            "correct_answer": brief.correct_answer,
            "key_explanation": brief.key_explanation,
            "option_explanations": [item.model_dump(mode="json") for item in brief.option_explanations],
        }
    elif correct_answer:
        answer_reveal = {
            "topic": student_facing_topic(tutor_knowledge_points(question, analysis), question.question_type),
            "student_answer": question.student_answer or "未作答",
            "correct_answer": correct_answer,
            "key_explanation": "",
            "option_explanations": [],
        }
    session = TutorSession(
        user_id=user.id,
        question_id=payload["question_id"],
        stage="understanding",
        state={
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
            "understanding_plan": plan,
            "understanding_index": 0,
            "activity_attempts": {},
            "activity_feedback": "",
            "teaching_policy": policy,
            "teaching_brief": brief.model_dump(mode="json") if brief else None,
            "answer_reveal": answer_reveal,
            "answer_reveal_acknowledged": False,
            "targeted_check_pending": False,
            "subject": question.subject,
            "question_type": question.question_type,
            "visualization_type": recommended_visualization(
                question.subject,
                question.question_type,
                question.knowledge_points or [],
            ),
        },
    )
    db.add(session)
    await db.flush()
    opening = (
        "先看清正确答案和刚才选项的关键差别。"
        if policy["mode"] == "compressed"
        else "我们先只解决一个小问题。选出你认为正确的答案就可以。"
    )
    db.add(
        TutorTurn(
            session_id=session.id,
            role="assistant",
            content=opening,
            stage=session.stage,
            metadata_json={"branch": "opening", "next_goal": "解释首错步骤"},
        )
    )
    await record_agent_tool(
        db,
        session.id,
        "opening",
        "diagnosis_lookup",
        {"question_id": session.question_id},
        {"diagnosis_id": diagnosis.id if diagnosis else None},
    )
    await db.commit()
    return envelope(await tutor_session_payload(session, db))


@app.get("/api/v1/tutor/sessions/{session_id}")
async def get_tutor(session_id: str, db: AsyncSession = Depends(get_db)):
    session = await db.get(TutorSession, session_id)
    if not session:
        raise HTTPException(404, "会话不存在")
    payload = await tutor_session_payload(session, db)
    await db.commit()
    return envelope(payload)


@app.post("/api/v1/tutor/sessions/{session_id}/turns")
async def tutor_turn(session_id: str, payload: dict = Body(...), db: AsyncSession = Depends(get_db)):
    session = await db.get(TutorSession, session_id)
    if not session:
        raise HTTPException(404, "会话不存在")
    message = str(payload.get("message", "")).strip()
    if not message:
        raise HTTPException(422, "请输入你的想法")
    session.stage = canonical_tutor_stage(session.stage)
    if session.stage == "finished":
        raise HTTPException(409, "本次学习已经完成")
    state = {"understanding_passed": False, **(session.state or {})}
    repeated = int(state.get("repeated_count", 0)) + 1 if message.strip() == state.get("last_message") else 0
    db.add(
        TutorTurn(
            session_id=session_id,
            role="user",
            content=message,
            stage=session.stage,
            metadata_json={"input_stage": session.stage},
        )
    )
    session.turn_count += 1
    question = await db.get(Question, session.question_id)
    analysis = (
        await db.scalars(select(ProblemAnalysis).where(ProblemAnalysis.question_id == session.question_id))
    ).first()
    references = (
        list(
            await db.scalars(
                select(ReferenceStep)
                .where(ReferenceStep.analysis_id == analysis.id)
                .order_by(ReferenceStep.step_index)
            )
        )
        if analysis
        else []
    )
    graph_result = run_tutor_step(
        session.turn_count,
        message,
        session.hint_level,
        repeated,
        {
            "subject": question.subject if question else "数学",
            "question_type": question.question_type if question else "综合题",
            "question_text": question.question_text if question else "",
            "final_answer": analysis.final_answer if analysis else "",
            "reference_steps": [item.text for item in references],
        },
    )
    memory = await load_long_term_memory(
        db,
        session.user_id,
        question.subject if question else "数学",
        session.question_id,
    )
    agent_result = await run_agent_turn(
        db,
        provider,
        dict(graph_result),
        AgentToolContext(
            subject=question.subject if question else "数学",
            question_type=question.question_type if question else "综合题",
            question_text=question.question_text if question else "",
            final_answer=analysis.final_answer if analysis else "",
            reference_steps=[item.text for item in references],
            student_message=message,
            turn_count=session.turn_count,
            knowledge_points=list(question.knowledge_points or []) if question else [],
            memory=memory,
        ),
    )
    work = (
        await db.scalars(
            select(StudentWork)
            .where(
                StudentWork.question_id == session.question_id,
            )
            .order_by(StudentWork.created_at.desc())
        )
    ).first()
    student_rows = (
        list(
            await db.scalars(
                select(StudentStep)
                .where(
                    StudentStep.work_id == work.id,
                )
                .order_by(StudentStep.step_index)
            )
        )
        if work
        else []
    )
    recent_rows = list(
        await db.scalars(
            select(TutorTurn)
            .where(
                TutorTurn.session_id == session_id,
            )
            .order_by(TutorTurn.created_at.desc())
            .limit(8)
        )
    )
    recent_rows.reverse()
    recent_dialogue = [{"role": row.role, "content": row.content} for row in recent_rows]
    if not recent_dialogue or recent_dialogue[-1] != {"role": "user", "content": message}:
        recent_dialogue.append({"role": "user", "content": message})
    grounded_draft = ground_reply_with_tool(graph_result["reply"], agent_result.tool)
    reply = await generate_tutor_guidance(
        provider,
        visual_paths=await question_visual_paths(session.question_id, db),
        question_text=question.question_text if question else "",
        student_answer=question.student_answer if question else None,
        student_steps=[row.text for row in student_rows],
        subject=question.subject if question else "数学",
        question_type=question.question_type if question else "综合题",
        draft_reply=grounded_draft,
        student_message=message,
        recent_turns=recent_dialogue,
    )
    reply = ensure_fresh_tutor_reply(
        reply,
        grounded_draft,
        [row.content for row in recent_rows if row.role == "assistant"],
        subject=question.subject if question else "数学",
        branch=graph_result["branch"],
        turn_count=session.turn_count,
    )
    reply = ground_reply_with_tool(reply, agent_result.tool)
    reply = reply if len(reply) <= 120 else reply[:119].rstrip("，。；：") + "。"
    session.hint_level = graph_result["hint_level"]
    # LangGraph chooses a dialogue branch only. A normal chat turn must never
    # advance (or replace) the explicit teaching stage.
    session.state = {
        **state,
        "last_message": message.strip(),
        "repeated_count": repeated,
        "branch": graph_result["branch"],
        "strategy": graph_result["strategy"],
        "next_goal": graph_result["next_goal"],
        "mastery_proven": graph_result["mastery_proven"],
        "dialogue_stage": graph_result["stage"],
        "agent_verification": agent_result.verification.status,
        "agent_memory_refs": agent_result.plan.memory_source_ids,
    }
    if agent_result.plan.tool_name == "visualization":
        session.state = {
            **session.state,
            "visualization_type": agent_result.tool.evidence.get("visualization_type"),
        }
    metadata = {key: graph_result[key] for key in ("branch", "strategy", "next_goal", "mastery_proven")}
    metadata.update(
        {
            "tool_name": agent_result.plan.tool_name,
            "decision_verified": agent_result.verification.status,
            "planner_status": agent_result.planner_status,
        }
    )
    assistant_turn = TutorTurn(
        session_id=session_id,
        role="assistant",
        content=reply,
        stage=session.stage,
        metadata_json=metadata,
    )
    db.add(assistant_turn)
    tool_input = agent_result.tool.consumed_input
    tool_output: dict[str, Any] = {
        "stage": session.stage,
        "next_goal": graph_result["next_goal"],
        **agent_result.tool.evidence,
        "executed": agent_result.tool.executed,
    }
    await record_agent_tool(
        db,
        session_id,
        graph_result["branch"],
        agent_result.plan.tool_name,
        tool_input,
        tool_output,
        run_result={
            "observation": agent_result.observation,
            "plan": agent_result.plan.model_dump(mode="json"),
            "verification": agent_result.verification.model_dump(mode="json"),
            "planner_status": agent_result.planner_status,
        },
    )
    await db.commit()
    return envelope({"message": reply, "stage": session.stage, "hint_level": session.hint_level, **metadata})




@app.post("/api/v1/tutor/sessions/{session_id}/advance")
async def advance_tutor_stage(session_id: str, payload: dict = Body(...), db: AsyncSession = Depends(get_db)):
    session = await db.get(TutorSession, session_id)
    if session is None:
        raise HTTPException(404, "会话不存在")
    target = str(payload.get("target_stage", ""))
    if target != "teach_back":
        raise HTTPException(422, "只支持进入讲清阶段")
    try:
        session.stage = transition_tutor_stage(session.stage, "understanding_advance", session.state or {})
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    session.state = {
        **(session.state or {}),
        "branch": "understanding_advance",
        "next_goal": "用自己的话说明规则、依据和结论",
    }
    message = "现在请用自己的话讲一遍：用了什么规则，为什么能用，又怎样得到结论。"
    db.add(
        TutorTurn(
            session_id=session.id,
            role="assistant",
            content=message,
            stage=session.stage,
            metadata_json={"branch": "understanding_advance", "explicit_transition": True},
        )
    )
    await record_agent_tool(
        db,
        session.id,
        "understanding_advance",
        "transition_tutor_stage",
        {"from": "understanding", "event": "understanding_advance"},
        {"to": session.stage},
    )
    await db.commit()
    return envelope({"stage": session.stage, "message": message, "next_goal": session.state["next_goal"]})


@app.post("/api/v1/tutor/sessions/{session_id}/rewind")
async def rewind_tutor_stage(session_id: str, db: AsyncSession = Depends(get_db)):
    session = await db.get(TutorSession, session_id)
    if session is None:
        raise HTTPException(404, "会话不存在")
    current = canonical_tutor_stage(session.stage)
    state = dict(session.state or {})
    compressed = state.get("teaching_policy", {}).get("mode") == "compressed"
    try:
        target = (
            "understanding" if compressed and current == "near_transfer" else previous_tutor_stage(current)
        )
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    if current == "teach_back":
        state.update(
            {
                "understanding_passed": True,
                "understood": True,
                "teach_back": None,
                "teach_back_passed": None,
                "teach_back_attempts": 0,
                "next_goal": "回顾已经理解的关键点",
            }
        )
    elif current == "near_transfer":
        state.update(
            {
                "teach_back": None,
                "teach_back_passed": None,
                "teach_back_attempts": 0,
                "near_transfer": None,
                "near_attempts": 0,
                "near_confirmation": None,
                "far_transfer": None,
                "far_attempts": 0,
                "next_goal": "重新用自己的话说清关键判断",
            }
        )
        if compressed:
            state.update(
                {
                    "understanding_passed": False,
                    "understood": False,
                    "answer_reveal_acknowledged": False,
                    "targeted_check_pending": False,
                    "next_goal": "重新查看答案讲解",
                }
            )
    else:
        state.update(
            {
                "near_transfer": None,
                "near_attempts": 0,
                "near_confirmation": None,
                "far_transfer": None,
                "far_attempts": 0,
                "next_goal": "重新完成一道相似题",
            }
        )
    target_label = {"understanding": "理解", "teach_back": "讲清", "near_transfer": "练习"}[target]
    state["activity_feedback"] = f"已返回“{target_label}”。"
    state["branch"] = f"rewind_{current}_to_{target}"
    session.stage = target
    session.state = state
    await record_agent_tool(
        db,
        session.id,
        state["branch"],
        "rewind_tutor_stage",
        {"from": current},
        {"to": target},
    )
    await db.commit()
    return envelope(await tutor_session_payload(session, db))


@app.post("/api/v1/tutor/sessions/{session_id}/teach-back")
async def teach_back(session_id: str, payload: dict = Body(...), db: AsyncSession = Depends(get_db)):
    session = await db.get(TutorSession, session_id)
    if session is None:
        raise HTTPException(404, "会话不存在")
    session.stage = canonical_tutor_stage(session.stage)
    if session.stage != "teach_back":
        raise HTTPException(409, "请先完成理解检查并进入讲清阶段")
    explanation = payload.get("explanation", "")
    question = await db.get(Question, session.question_id)
    analysis = (
        await db.scalars(select(ProblemAnalysis).where(ProblemAnalysis.question_id == session.question_id))
    ).first()
    references = (
        list(
            await db.scalars(
                select(ReferenceStep)
                .where(ReferenceStep.analysis_id == analysis.id)
                .order_by(ReferenceStep.step_index)
            )
        )
        if analysis
        else []
    )
    assessment = evaluate_teach_back(
        explanation,
        question.subject if question else "数学",
        question.question_type if question else "综合题",
        (analysis.knowledge_points if analysis else (question.knowledge_points if question else [])),
        [item.text for item in references],
    )
    passed = bool(assessment["passed"])
    branch = "teach_back_pass" if passed else "teach_back_fail"
    feedback = str(assessment["feedback"])
    state = dict(session.state or {})
    attempts = int(state.get("teach_back_attempts", 0)) + 1
    assisted = not passed and attempts >= 2
    state.update(
        {
            "teach_back": passed,
            "teach_back_passed": passed,
            "teach_back_attempts": attempts,
            "branch": branch,
            "next_goal": "完成一道相似题" if passed or assisted else "补充一个关键理由",
        }
    )
    if assisted:
        state["assisted"] = True
    session.state = state
    if passed or assisted:
        session.stage = "near_transfer"
        await create_session_variant(session, "near", db)
        feedback = feedback if passed else "这次还少一个关键点，我先记录下来，我们继续练一道相似题。"
    db.add(
        TutorTurn(
            session_id=session_id,
            role="user",
            content=explanation,
            stage="teach_back",
            metadata_json={"branch": branch},
        )
    )
    db.add(
        TutorTurn(
            session_id=session_id,
            role="assistant",
            content=feedback,
            stage=session.stage,
            metadata_json={"branch": branch, "passed": passed},
        )
    )
    await record_agent_tool(
        db,
        session_id,
        branch,
        "evaluate_teach_back",
        {"explanation": explanation, "subject": question.subject if question else ""},
        {"passed": passed, "stage": session.stage, "matched_concepts": assessment["matched_concepts"]},
    )
    await db.commit()
    return envelope(
        {
            "passed": passed,
            "assisted": assisted,
            "branch": branch,
            "stage": session.stage,
            "feedback": feedback,
            "next_goal": session.state["next_goal"],
        }
    )


async def visualization_context(
    session_id: str, db: AsyncSession
) -> tuple[TutorSession, Question, dict[str, Any]]:
    session = await db.get(TutorSession, session_id)
    if session is None:
        raise HTTPException(404, "会话不存在")
    question, analysis, _ = await tutor_learning_context(session, db)
    kind = recommended_visualization(
        question.subject, question.question_type, tutor_knowledge_points(question, analysis)
    )
    if kind is None:
        raise HTTPException(404, "这道题暂时没有匹配的互动演示")
    return session, question, visualization_spec(kind)


@app.get("/api/v1/tutor/sessions/{session_id}/visualization")
async def recommended_session_visualization(session_id: str, db: AsyncSession = Depends(get_db)):
    _, question, spec = await visualization_context(session_id, db)
    return envelope(
        {
            "question": {"id": question.id, "title": question.title, "question_text": question.question_text},
            "spec": spec,
        }
    )


@app.post("/api/v1/tutor/sessions/{session_id}/visualization")
async def visualization(
    session_id: str,
    payload: dict = Body(default={}),
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    session, _, raw_spec = await visualization_context(session_id, db)
    values = payload.get("values", {})
    raw_spec["parameters"] = {**raw_spec["parameters"], **values}
    spec = VisualizationPayload.model_validate(raw_spec)
    item = VisualizationSpec(session_id=session_id, type=spec.type, title=spec.title, spec=spec.model_dump())
    db.add(item)
    await db.flush()
    if payload.get("observation"):
        interaction = VisualizationInteraction(
            visualization_id=item.id, user_id=user.id, values=values, observation=payload["observation"]
        )
        db.add(interaction)
        await db.flush()
        await record_agent_tool(
            db,
            session_id,
            "visualization_evidence",
            "observe_visualization",
            {"type": spec.type, "values": values},
            {
                "interaction_id": interaction.id,
                "observation": payload["observation"],
                "expected_observation": spec.expected_observation,
            },
        )
    await db.commit()
    return envelope(row_dict(item))


@app.get("/api/v1/visualizations/types")
async def visualization_types():
    return envelope(visualization_catalog())


@app.get("/api/v1/visualizations/{visualization_id}")
async def get_visualization(visualization_id: str, db: AsyncSession = Depends(get_db)):
    item = await db.get(VisualizationSpec, visualization_id)
    if item is None:
        raise HTTPException(404, "可视化不存在")
    interactions = list(
        await db.scalars(
            select(VisualizationInteraction)
            .where(VisualizationInteraction.visualization_id == visualization_id)
            .order_by(VisualizationInteraction.created_at)
        )
    )
    return envelope(row_dict(item) | {"interactions": [row_dict(value) for value in interactions]})


@app.post("/api/v1/tutor/sessions/{session_id}/variant")
async def variant(session_id: str, payload: dict = Body(default={}), db: AsyncSession = Depends(get_db)):
    session = await db.get(TutorSession, session_id)
    if session is None:
        raise HTTPException(404, "会话不存在")
    transfer = payload.get("transfer_type", "near")
    session.stage = canonical_tutor_stage(session.stage)
    expected_stages = {"near_transfer"} if transfer == "near" else {"far_transfer"}
    if transfer not in {"near", "far"}:
        raise HTTPException(422, "迁移类型必须是 near 或 far")
    if session.stage not in expected_stages:
        raise HTTPException(409, "当前教学阶段不能生成这类练习")
    state = dict(session.state or {})
    existing_id = state.get(f"{transfer}_variant_id")
    item = await db.get(VariantQuestion, existing_id) if existing_id else None
    if item is None:
        item = await create_session_variant(session, transfer, db)
    await db.commit()
    public_fields = (
        "id",
        "question_id",
        "session_id",
        "transfer_type",
        "question_text",
        "verified",
        "created_at",
        "updated_at",
    )
    item_fields = row_dict(item)
    return envelope({key: item_fields[key] for key in public_fields if key in item_fields})


@app.post("/api/v1/variants/{variant_id}/attempt")
async def attempt_variant(
    variant_id: str,
    payload: dict = Body(...),
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    variant_item = await db.get(VariantQuestion, variant_id)
    if variant_item is None:
        raise HTTPException(404, "迁移题不存在")
    session = await db.get(TutorSession, variant_item.session_id)
    question = await db.get(Question, variant_item.question_id)
    if session is None:
        raise HTTPException(404, "会话不存在")
    session.stage = canonical_tutor_stage(session.stage)
    expected_stages = {"near_transfer"} if variant_item.transfer_type == "near" else {"far_transfer"}
    if session.stage not in expected_stages:
        raise HTTPException(409, "这道练习与当前教学阶段不匹配")
    answer = str(payload.get("answer", ""))
    grading = await grade_answer(
        provider,
        question=variant_item.question_text,
        answer=answer,
        expected=variant_item.answer,
        reference_solution=list(variant_item.reference_solution or []),
        subject=question.subject if question else "数学",
        question_type=question.question_type if question else "综合题",
    )
    if not grading["can_update_learning"]:
        feedback = str(grading["feedback"])
        branch = f"{variant_item.transfer_type}_transfer_review_required"
        db.add(
            TutorTurn(
                session_id=session.id,
                role="user",
                content=answer,
                stage=variant_item.transfer_type + "_transfer",
                metadata_json={
                    "branch": branch,
                    "variant_id": variant_id,
                    "grading": grading,
                    "attempt_consumed": False,
                },
            )
        )
        db.add(
            TutorTurn(
                session_id=session.id,
                role="assistant",
                content=feedback,
                stage=session.stage,
                metadata_json={"branch": branch, "grading_verdict": grading["verdict"]},
            )
        )
        await db.commit()
        return envelope(
            {
                "attempt": None,
                "correct": None,
                "branch": branch,
                "stage": session.stage,
                "feedback": feedback,
                "grading": grading,
                "mastery": None,
                "misconception": None,
            }
        )
    correct = bool(grading["correct"])
    attempt = VariantAttempt(
        variant_id=variant_id,
        user_id=user.id,
        answer=answer,
        correct=correct,
        elapsed_seconds=int(payload.get("elapsed_seconds", 0)),
        hint_level=int(payload.get("hint_level", session.hint_level)),
    )
    db.add(attempt)
    transfer = variant_item.transfer_type
    branch = f"{transfer}_transfer_{'pass' if correct else 'fail'}"
    state = {**(session.state or {}), "branch": branch}
    attempts = int(state.get(f"{transfer}_attempts", 0)) + 1
    state[f"{transfer}_attempts"] = attempts
    feedback = str(grading["feedback"])
    if transfer == "near" and correct:
        state["near_transfer"] = True
        session.stage = "far_transfer"
        session.state = state
        await create_session_variant(session, "far", db)
        state = dict(session.state or {})
    elif transfer == "near" and attempts >= 2:
        state["near_transfer"] = False
        state["assisted"] = True
        state["near_confirmation"] = remediation_confirmation(
            variant_item.id,
            variant_item.explanation or "先对照题目条件，再按顺序完成关键步骤。",
            variant_item.answer,
        )
        feedback = "先看这道题的简短讲解，再完成一个简单确认。"
    elif transfer == "near":
        feedback = str(grading["feedback"])
    elif correct:
        state["far_transfer"] = True
        session.state = state
        await complete_tutor_learning(session, user, db, transfer_insufficient=False)
        state = dict(session.state or {})
    elif attempts >= 2:
        state["far_transfer"] = False
        state["transfer_insufficient"] = True
        state["assisted"] = True
        session.state = state
        await complete_tutor_learning(session, user, db, transfer_insufficient=True)
        state = dict(session.state or {})
        feedback = "这次换一种题目还不稳定，本轮先结束，并提高后续复习优先级。"
    else:
        feedback = str(grading["feedback"])
    session.state = state
    db.add(
        TutorTurn(
            session_id=session.id,
            role="user",
            content=answer,
            stage=transfer + "_transfer",
            metadata_json={"branch": branch, "variant_id": variant_id},
        )
    )
    db.add(
        TutorTurn(
            session_id=session.id,
            role="assistant",
            content=feedback,
            stage=session.stage,
            metadata_json={"branch": branch, "correct": correct},
        )
    )
    await record_agent_tool(
        db,
        session.id,
        branch,
        "grade_answer",
        {"variant_id": variant_id, "answer": answer},
        {"correct": correct, "stage": session.stage},
    )
    mastery = (
        await db.scalars(
            select(MasteryState)
            .where(
                MasteryState.user_id == user.id,
            )
            .order_by(MasteryState.updated_at.desc())
        )
    ).first()
    misconception = (
        await db.scalars(
            select(MisconceptionState)
            .where(
                MisconceptionState.user_id == user.id,
            )
            .order_by(MisconceptionState.updated_at.desc())
        )
    ).first()
    await db.commit()
    return envelope(
        {
            "attempt": row_dict(attempt),
            "correct": correct,
            "branch": branch,
            "stage": session.stage,
            "feedback": feedback,
            "grading": grading,
            "mastery": row_dict(mastery) if mastery else None,
            "misconception": row_dict(misconception) if misconception else None,
        }
    )


@app.post("/api/v1/tutor/sessions/{session_id}/finish")
async def finish_tutor(
    session_id: str,
    payload: dict = Body(default={}),
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await db.get(TutorSession, session_id)
    if session is None:
        raise HTTPException(404, "会话不存在")
    session.stage = canonical_tutor_stage(session.stage)
    if session.stage != "finished":
        raise HTTPException(409, "请先完成讲清、相似题和综合应用")
    if session.status == "completed":
        plan = (
            await db.scalars(
                select(ReviewPlan)
                .where(
                    ReviewPlan.user_id == user.id,
                    ReviewPlan.question_id == session.question_id,
                )
                .order_by(ReviewPlan.created_at.desc())
            )
        ).first()
        return envelope(
            {
                "session": public_tutor_session(session),
                "mastery": None,
                "review": row_dict(plan) if plan else None,
            }
        )
    state = dict(session.state or {})
    mastery, _, plan = await complete_tutor_learning(
        session,
        user,
        db,
        transfer_insufficient=bool(state.get("transfer_insufficient") or state.get("far_transfer") is False),
    )
    await db.commit()
    return envelope(
        {"session": public_tutor_session(session), "mastery": row_dict(mastery), "review": row_dict(plan)}
    )


@app.get("/api/v1/reviews/today")
async def today_reviews(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    end_of_today = (
        datetime.now(timezone(timedelta(hours=8)))
        .replace(
            hour=23,
            minute=59,
            second=59,
            microsecond=999999,
        )
        .astimezone(timezone.utc)
    )
    items = list(
        await db.scalars(
            select(ReviewPlan)
            .where(
                ReviewPlan.user_id == user.id,
                ReviewPlan.status == "pending",
                ReviewPlan.due_at <= end_of_today,
            )
            .order_by(ReviewPlan.due_at)
        )
    )
    result = []
    seen_questions: set[str] = set()
    for item in items:
        question = await db.get(Question, item.question_id)
        if question and question.status == "archived":
            continue
        if question:
            key = question_display_key(question)
            if key in seen_questions:
                continue
            seen_questions.add(key)
        reason = item.reason
        if "again" in reason.casefold():
            reason = "本次作答需要重做，安排 1 天后再次复习"
        visible_question = None
        if question:
            figures = await db.scalars(
                select(QuestionAsset)
                .where(
                    QuestionAsset.question_id == question.id,
                    QuestionAsset.kind == "question_figure",
                )
                .order_by(QuestionAsset.created_at)
            )
            visible_question = row_dict(question)
            visible_question.pop("student_answer", None)
            visible_question["question_figures"] = [
                row_dict(figure) | {"url": sign_media_url("/" + figure.path, settings.auth_secret)}
                for figure in figures
            ]
        result.append(row_dict(item) | {"reason": reason, "question": visible_question})
    return envelope(result)


@app.post("/api/v1/reviews/{plan_id}/attempt")
async def attempt_review(
    plan_id: str,
    payload: dict = Body(...),
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    plan = await db.get(ReviewPlan, plan_id)
    if plan is None or plan.user_id != user.id or plan.status != "pending":
        raise HTTPException(404, "待复习题不存在")
    question = await db.get(Question, plan.question_id)
    analysis = (
        await db.scalars(select(ProblemAnalysis).where(ProblemAnalysis.question_id == plan.question_id))
    ).first()
    if question is None:
        raise HTTPException(404, "题目不存在")
    expected = analysis.final_answer if analysis else ""
    if not expected:
        raise HTTPException(422, "这道题还没有标准答案，请先在题目详情中完成分析")
    answer = str(payload.get("answer", "")).strip()
    handwriting_image_url, handwriting_recognition = validate_answer_handwriting(
        user_id=user.id,
        context_type="review",
        context_id=plan.id,
        image_url=str(payload.get("handwriting_image_url", "")),
        recognition=payload.get("handwriting_recognition"),
    )
    references = (
        list(
            await db.scalars(
                select(ReferenceStep)
                .where(
                    ReferenceStep.analysis_id == analysis.id,
                )
                .order_by(ReferenceStep.step_index)
            )
        )
        if analysis
        else []
    )
    assessment = await grade_answer(
        provider,
        question=question.question_text,
        answer=answer,
        expected=expected,
        reference_solution=[item.text for item in references],
        subject=question.subject,
        question_type=question.question_type,
        options=question.options,
    )
    record = ReviewRecord(
        plan_id=plan.id,
        grade="pending",
        correct=bool(assessment["correct"]),
        student_answer=answer,
        expected_answer=expected,
        feedback=str(assessment["feedback"]),
        score=int(assessment["score"]),
        grading_details={
            **assessment,
            "handwriting_image_url": sign_media_url(handwriting_image_url, settings.auth_secret),
            "handwriting_recognition": handwriting_recognition,
        },
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return envelope(
        {
            "attempt_id": record.id,
            "correct": record.correct if assessment["can_update_learning"] else None,
            "score": record.score,
            "feedback": record.feedback,
            "expected_answer": expected,
            "matched_points": assessment["matched_points"],
            "grading": assessment,
            "can_update_learning": assessment["can_update_learning"],
            "handwriting_image_url": sign_media_url(handwriting_image_url, settings.auth_secret),
            "handwriting_recognition": handwriting_recognition,
        }
    )


@app.post("/api/v1/reviews/{plan_id}/grade")
async def grade_review(
    plan_id: str,
    payload: dict = Body(...),
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    plan = await db.get(ReviewPlan, plan_id, with_for_update=True, populate_existing=True)
    if plan is None or plan.user_id != user.id:
        raise HTTPException(404, "复习计划不存在")
    if plan.status != "pending":
        raise HTTPException(409, "这次复习已完成，请刷新复习列表")
    attempt_id = payload.get("attempt_id")
    record = await db.get(ReviewRecord, attempt_id) if attempt_id else None
    if record is None or record.plan_id != plan_id or record.grade != "pending":
        raise HTTPException(422, "请先提交答案并完成系统判定")
    if not (record.grading_details or {}).get("can_update_learning", True):
        raise HTTPException(409, "这次判题仍需核对，不能据此更新复习计划")
    grade = payload.get("grade", "good")
    if grade not in {"again", "hard", "good", "easy"}:
        raise HTTPException(422, "请选择有效的复习反馈")
    correct = record.correct
    days = (
        {"again": 1, "hard": 1, "good": 2, "easy": 4}.get(grade, 1)
        if not correct
        else {"again": 1, "hard": 2, "good": 7, "easy": 15}.get(grade, 4)
    )
    plan.status = "completed"
    record.grade = grade
    await db.flush()
    grade_label = {"again": "还没想起来", "hard": "有点困难", "good": "已经掌握", "easy": "很轻松"}.get(
        grade, "已完成"
    )
    next_plan = ReviewPlan(
        user_id=user.id,
        question_id=plan.question_id,
        due_at=datetime.now(timezone.utc) + timedelta(days=days),
        interval_days=days,
        reason=f"上次作答{'正确' if correct else '有误'}，随后选择了“{grade_label}”",
    )
    db.add(next_plan)
    await db.commit()
    return envelope({"record": row_dict(record), "next_plan": row_dict(next_plan)})


@app.get("/api/v1/reviews/history")
async def review_history(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    rows = (
        await db.execute(
            select(ReviewRecord, ReviewPlan)
            .join(ReviewPlan, ReviewPlan.id == ReviewRecord.plan_id)
            .where(ReviewPlan.user_id == user.id, ReviewRecord.grade != "pending")
            .order_by(ReviewRecord.created_at.desc())
        )
    ).all()
    result = []
    for record, plan in rows:
        question = await db.get(Question, plan.question_id)
        result.append(
            row_dict(record) | {"plan": row_dict(plan), "question": row_dict(question) if question else None}
        )
    return envelope(result)


@app.get("/api/v1/knowledge/cards")
async def knowledge_cards(
    q: str = Query(default=""),
    subject: str | None = Query(default=None),
    grade: str | None = Query(default=None),
    misconception: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    cards = await search_knowledge_cards(
        db,
        query=q,
        subject=subject,
        grade=grade,
        misconception=misconception,
        limit=50,
    )
    return envelope([row_dict(card) for card in cards])


@app.get("/api/v1/knowledge/cards/{code}")
async def knowledge_card(code: str, db: AsyncSession = Depends(get_db)):
    card = (await db.scalars(select(KnowledgePoint).where(KnowledgePoint.code == code))).first()
    if card is None:
        raise HTTPException(404, "知识卡不存在")
    prerequisite_rows = (
        await db.execute(
            select(KnowledgeRelation, KnowledgePoint)
            .join(KnowledgePoint, KnowledgePoint.id == KnowledgeRelation.target_id)
            .where(KnowledgeRelation.source_id == card.id)
        )
    ).all()
    next_rows = (
        await db.execute(
            select(KnowledgeRelation, KnowledgePoint)
            .join(KnowledgePoint, KnowledgePoint.id == KnowledgeRelation.source_id)
            .where(KnowledgeRelation.target_id == card.id)
        )
    ).all()
    return envelope(
        row_dict(card)
        | {
            "prerequisites": [row_dict(point) for _, point in prerequisite_rows],
            "next_knowledge": [row_dict(point) for _, point in next_rows],
        }
    )


@app.get("/api/v1/analytics/overview")
async def analytics(
    days: int = Query(default=14, ge=1, le=365),
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    mastery_rows = list(
        await db.scalars(
            select(MasteryState)
            .where(
                MasteryState.user_id == user.id,
            )
            .order_by(MasteryState.updated_at.desc())
        )
    )
    mastery_by_point: dict[tuple[str, str], MasteryState] = {}
    for mastery_item in mastery_rows:
        mastery_by_point.setdefault(
            (mastery_item.subject, mastery_item.knowledge_point),
            mastery_item,
        )
    mastery = [row_dict(item) for item in mastery_by_point.values()]
    misconception_rows = list(
        await db.scalars(
            select(MisconceptionState)
            .where(
                MisconceptionState.user_id == user.id,
            )
            .order_by(MisconceptionState.probability.desc())
        )
    )
    misconception_by_label: dict[tuple[str, str], MisconceptionState] = {}
    for misconception_item in misconception_rows:
        label = canonical_misconception_label(misconception_item.label)
        misconception_by_label.setdefault(
            (misconception_item.subject, label),
            misconception_item,
        )
    mistakes = [
        row_dict(item)
        | {
            "label": label,
            "successful_strategy": learning_method_label(item.successful_strategy)
            if item.successful_strategy
            else "",
            "failed_strategy": learning_method_label(item.failed_strategy) if item.failed_strategy else "",
        }
        for (_, label), item in misconception_by_label.items()
    ]
    since = datetime.now(timezone.utc) - timedelta(days=days - 1)
    updates = list(
        await db.scalars(
            select(CognitiveUpdate)
            .where(
                CognitiveUpdate.user_id == user.id,
                CognitiveUpdate.entity_type == "mastery",
                CognitiveUpdate.created_at >= since,
            )
            .order_by(CognitiveUpdate.created_at)
        )
    )
    by_date: dict[str, list[float]] = {}
    for update in updates:
        by_date.setdefault(update.created_at.date().isoformat(), []).append(update.new_value)
    trend = [
        {"date": key, "score": round(sum(values) / len(values) * 100, 1), "evidence_count": len(values)}
        for key, values in sorted(by_date.items())
    ]
    return envelope(
        {
            "mastery": mastery,
            "misconceptions": mistakes,
            "trend": trend,
            "summary": {
                "knowledge_count": len(mastery),
                "misconception_count": len(mistakes),
                "evidence_count": len(updates),
            },
        }
    )


@app.get("/api/v1/analytics/cognition-graph")
async def cognition_graph(
    subject: str | None = Query(default=None),
    days: int = Query(default=90, ge=1, le=3650),
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    mastery_rows = list(await db.scalars(select(MasteryState).where(MasteryState.user_id == user.id)))
    misconception_rows = list(
        await db.scalars(
            select(MisconceptionState)
            .where(
                MisconceptionState.user_id == user.id,
            )
            .order_by(MisconceptionState.probability.desc())
        )
    )
    since = datetime.now(timezone.utc) - timedelta(days=days)
    update_rows = list(
        await db.scalars(
            select(CognitiveUpdate).where(
                CognitiveUpdate.user_id == user.id,
                CognitiveUpdate.created_at >= since,
                CognitiveUpdate.entity_type != "note_evidence",
            )
        )
    )
    personal_links = list(
        await db.scalars(
            select(UserQuestionKnowledgeLink).where(
                UserQuestionKnowledgeLink.user_id == user.id,
                UserQuestionKnowledgeLink.created_at >= since,
            )
        )
    )
    question_ids = {item.question_id for item in update_rows if item.question_id}
    question_ids.update(item.question_id for item in personal_links)
    questions = (
        list(
            await db.scalars(
                select(Question).where(
                    Question.id.in_(question_ids),
                    Question.status != "archived",
                )
            )
        )
        if question_ids
        else []
    )
    clean_questions: list[Question] = []
    seen_questions: set[str] = set()
    for question in sorted(questions, key=lambda item: item.updated_at, reverse=True):
        key = question_display_key(question)
        if key in seen_questions:
            continue
        seen_questions.add(key)
        clean_questions.append(question)
    questions = clean_questions
    allowed_question_ids = {item.id for item in questions}
    update_rows = [
        item for item in update_rows if not item.question_id or item.question_id in allowed_question_ids
    ]
    if subject:
        mastery_rows = [item for item in mastery_rows if item.subject == subject]
        misconception_rows = [item for item in misconception_rows if item.subject == subject]
        questions = [question for question in questions if question.subject == subject]
        allowed_ids = {question.id for question in questions}
        update_rows = [
            item for item in update_rows if not item.question_id or item.question_id in allowed_ids
        ]
        personal_links = [item for item in personal_links if item.question_id in allowed_ids]
    cards_statement = select(KnowledgePoint)
    if subject:
        cards_statement = cards_statement.where(KnowledgePoint.subject == subject)
    cards = list(await db.scalars(cards_statement))
    card_by_name = {(card.subject, card.name): card for card in cards}
    card_by_code = {(card.subject, card.code): card for card in cards}
    card_by_id = {card.id: card for card in cards}
    nodes: dict[str, dict[str, Any]] = {}
    links: list[dict[str, Any]] = []
    misconception_node_by_key: dict[tuple[str, str], str] = {}
    question_topic_by_id: dict[str, str] = {}
    for update in update_rows:
        if update.question_id and update.entity_type == "mastery" and update.entity_key:
            question_topic_by_id.setdefault(update.question_id, update.entity_key)
    for mapping in personal_links:
        card = card_by_id.get(mapping.knowledge_point_id)
        if card and mapping.role == "primary":
            question_topic_by_id[mapping.question_id] = card.name
        elif card:
            question_topic_by_id.setdefault(mapping.question_id, card.name)
    for mastery in mastery_rows:
        card = card_by_name.get((mastery.subject, mastery.knowledge_point)) or card_by_code.get(
            (mastery.subject, mastery.knowledge_point)
        )
        if subject and card is None:
            continue
        node_id = f"knowledge:{mastery.subject}:{card.code if card else mastery.knowledge_point}"
        nodes[node_id] = {
            "id": node_id,
            "name": mastery.knowledge_point,
            "category": "knowledge",
            "value": round(mastery.mastery_score * 100),
            "confidence": mastery.confidence,
            "detail": learner_text(mastery.update_reason),
            "subject": mastery.subject,
        }
    for mistake in misconception_rows:
        label = canonical_misconception_label(mistake.label)
        node_id = f"misconception:{mistake.subject}:{label}"
        misconception_node_by_key[(mistake.subject, mistake.code)] = node_id
        if node_id in nodes:
            continue
        nodes[node_id] = {
            "id": node_id,
            "name": label,
            "category": "misconception",
            "value": round(mistake.probability * 100),
            "status": mistake.status,
            "detail": f"已参考 {mistake.evidence_count} 次学习记录；有效方法：{learning_method_label(mistake.successful_strategy)}",
            "subject": mistake.subject,
        }
        for strategy in {value for value in (mistake.successful_strategy, mistake.failed_strategy) if value}:
            strategy_id = f"strategy:{strategy}"
            nodes[strategy_id] = {
                "id": strategy_id,
                "name": learning_method_label(strategy),
                "category": "strategy",
                "value": 35,
                "detail": "学习过程中使用过的方法",
            }
            links.append(
                {
                    "source": node_id,
                    "target": strategy_id,
                    "relation": "有效策略" if strategy == mistake.successful_strategy else "待改进策略",
                }
            )
    for question in questions:
        node_id = f"question:{question.id}"
        topic = question_topic_by_id.get(question.id) or student_facing_topic(
            question.knowledge_points,
            question.question_type,
        )
        question_name = "相关错题" if topic in {"错题学习", "其他题型"} else f"{topic}相关错题"
        nodes[node_id] = {
            "id": node_id,
            "name": question_name,
            "category": "question",
            "value": 28,
            "subject": question.subject,
            "detail": question.question_text[:120],
            "question_id": question.id,
        }
    for mapping in personal_links:
        card = card_by_id.get(mapping.knowledge_point_id)
        question_node = f"question:{mapping.question_id}"
        if card is None or question_node not in nodes:
            continue
        knowledge_node = f"knowledge:{card.subject}:{card.code}"
        nodes.setdefault(
            knowledge_node,
            {
                "id": knowledge_node,
                "name": card.name,
                "category": "knowledge",
                "value": 45,
                "confidence": mapping.confidence,
                "detail": f"由你的错题映射到共享知识点；依据：{mapping.evidence_text}",
                "subject": card.subject,
            },
        )
        links.append(
            {
                "source": question_node,
                "target": knowledge_node,
                "relation": "涉及知识点" if mapping.role == "primary" else "需要先修",
            }
        )
    grouped: dict[str, dict[str, list[CognitiveUpdate]]] = {}
    for update in update_rows:
        if update.question_id:
            grouped.setdefault(update.question_id, {}).setdefault(update.entity_type, []).append(update)
    for question_id, evidence in grouped.items():
        question_node = f"question:{question_id}"
        if question_node not in nodes:
            continue
        for item in evidence.get("mastery", []):
            question_subject = nodes[question_node].get("subject", "")
            candidates = [
                key
                for key, node in nodes.items()
                if node["category"] == "knowledge"
                and node["subject"] == question_subject
                and node["name"] == item.entity_key
            ]
            if candidates:
                links.append({"source": question_node, "target": candidates[0], "relation": "提供掌握证据"})
        for item in evidence.get("misconception", []):
            question_subject = nodes[question_node].get("subject", "")
            target = misconception_node_by_key.get((question_subject, item.entity_key))
            if target and target in nodes:
                links.append({"source": question_node, "target": target, "relation": "暴露错因"})
    visible_card_ids = {
        card.id: f"knowledge:{card.subject}:{card.code}"
        for card in cards
        if f"knowledge:{card.subject}:{card.code}" in nodes
    }
    if visible_card_ids:
        relations = list(
            await db.scalars(
                select(KnowledgeRelation).where(
                    KnowledgeRelation.source_id.in_(visible_card_ids),
                    KnowledgeRelation.target_id.in_(visible_card_ids),
                )
            )
        )
        links.extend(
            {
                "source": visible_card_ids[item.source_id],
                "target": visible_card_ids[item.target_id],
                "relation": item.relation_type,
            }
            for item in relations
        )
    ordered_by_category = {
        category: sorted(
            (item for item in nodes.values() if item["category"] == category),
            key=lambda item: (-float(item.get("value", 0)), item["name"]),
        )
        for category in ("knowledge", "question", "misconception", "strategy")
    }
    visible_nodes = (
        ordered_by_category["knowledge"][:8]
        + ordered_by_category["question"][:4]
        + ordered_by_category["misconception"][:2]
        + ordered_by_category["strategy"][:2]
    )
    visible_ids = {item["id"] for item in visible_nodes}
    visible_links = [
        item for item in links if item["source"] in visible_ids and item["target"] in visible_ids
    ]
    return envelope(
        {
            "nodes": visible_nodes,
            "links": visible_links,
            "categories": ["knowledge", "misconception", "question", "strategy"],
            "filters": {"subject": subject, "days": days},
            "evidence_count": len(update_rows),
            "personal_mapping_count": len(personal_links),
            "mapped_question_count": len({item.question_id for item in personal_links}),
        }
    )


@app.post("/api/v1/papers")
async def create_paper(
    payload: dict = Body(...), user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    payload = validated_payload(PaperCreateRequest, payload)
    filters = payload.get("filters", {})
    paper = Paper(user_id=user.id, title=payload.get("title", "我的错题练习"), filters=filters)
    db.add(paper)
    await db.flush()
    candidates = await paper_candidates_data(user.id, filters, db)
    ids = payload.get("question_ids") or [item["id"] for item in candidates[: int(payload.get("limit", 10))]]
    for question_id in ids:
        await owned_resource(db, Question, str(question_id), user)
    score_map = {
        str(item.get("question_id")): int(item.get("score", 10)) for item in payload.get("items", [])
    }
    for pos, question_id in enumerate(ids):
        db.add(
            PaperItem(
                paper_id=paper.id,
                question_id=question_id,
                position=pos,
                score=score_map.get(str(question_id), int(payload.get("default_score", 10))),
            )
        )
    await db.commit()
    return envelope(row_dict(paper))


async def paper_candidates_data(
    user_id: str, filters: dict[str, Any], db: AsyncSession
) -> list[dict[str, Any]]:
    statement = (
        select(Question)
        .where(
            Question.user_id == user_id,
            Question.status != "archived",
        )
        .order_by(Question.created_at.desc())
    )
    if filters.get("subject"):
        statement = statement.where(Question.subject == filters["subject"])
    questions = list(await db.scalars(statement))
    seen_questions: set[str] = set()
    result: list[dict[str, Any]] = []
    for question in questions:
        key = question_display_key(question)
        if key in seen_questions:
            continue
        seen_questions.add(key)
        if filters.get("date_from") and question.created_at.date().isoformat() < filters["date_from"]:
            continue
        if filters.get("date_to") and question.created_at.date().isoformat() > filters["date_to"]:
            continue
        analysis = (
            await db.scalars(select(ProblemAnalysis).where(ProblemAnalysis.question_id == question.id))
        ).first()
        diagnosis = (
            await db.scalars(
                select(Diagnosis)
                .where(Diagnosis.question_id == question.id)
                .order_by(Diagnosis.created_at.desc())
            )
        ).first()
        knowledge = list(question.knowledge_points or (analysis.knowledge_points if analysis else []))
        if filters.get("knowledge_point") and not any(
            filters["knowledge_point"] in str(value) for value in knowledge
        ):
            continue
        if filters.get("error_type") and (not diagnosis or filters["error_type"] not in diagnosis.error_type):
            continue
        mastery = (
            await db.scalars(
                select(MasteryState)
                .where(
                    MasteryState.user_id == user_id,
                    MasteryState.subject == question.subject,
                    MasteryState.knowledge_point.in_(knowledge or ["__none__"]),
                )
                .order_by(MasteryState.updated_at.desc())
            )
        ).first()
        mastery_score = mastery.mastery_score if mastery else 0.0
        if mastery_score < float(filters.get("mastery_min", 0)) or mastery_score > float(
            filters.get("mastery_max", 1)
        ):
            continue
        review = (
            await db.scalars(
                select(ReviewPlan)
                .where(
                    ReviewPlan.user_id == user_id,
                    ReviewPlan.question_id == question.id,
                )
                .order_by(ReviewPlan.due_at.desc())
            )
        ).first()
        if filters.get("due_review") and (review is None or review.status != "pending"):
            continue
        result.append(
            row_dict(question)
            | {
                "knowledge_points": knowledge,
                "error_type": diagnosis.error_type if diagnosis else "未诊断",
                "root_misconception": diagnosis.root_misconception if diagnosis else "",
                "mastery_score": mastery_score,
                "review_due_at": iso_timestamp(review.due_at) if review else None,
            }
        )
    return result


@app.get("/api/v1/papers/candidates")
async def paper_candidates(
    subject: str | None = Query(default=None),
    knowledge_point: str | None = Query(default=None),
    error_type: str | None = Query(default=None),
    mastery_min: float = Query(default=0, ge=0, le=1),
    mastery_max: float = Query(default=1, ge=0, le=1),
    due_review: bool = Query(default=False),
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    filters = {
        "subject": subject,
        "knowledge_point": knowledge_point,
        "error_type": error_type,
        "mastery_min": mastery_min,
        "mastery_max": mastery_max,
        "due_review": due_review,
    }
    return envelope(await paper_candidates_data(user.id, filters, db))


@app.get("/api/v1/papers")
async def list_papers(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    return envelope([row_dict(x) for x in await db.scalars(select(Paper).where(Paper.user_id == user.id))])


@app.get("/api/v1/papers/{paper_id}")
async def get_paper(paper_id: str, db: AsyncSession = Depends(get_db)):
    paper = await db.get(Paper, paper_id)
    if paper is None:
        raise HTTPException(404, "试卷不存在")
    items = list(
        await db.scalars(select(PaperItem).where(PaperItem.paper_id == paper_id).order_by(PaperItem.position))
    )
    item_rows = []
    for item in items:
        question = await db.get(Question, item.question_id)
        item_rows.append(row_dict(item) | {"question": row_dict(question) if question else None})
    exports = list(
        await db.scalars(
            select(ExportJob).where(ExportJob.paper_id == paper_id).order_by(ExportJob.created_at.desc())
        )
    )
    return envelope(
        row_dict(paper)
        | {
            "items": item_rows,
            "exports": [
                row_dict(item) | {"url": sign_media_url("/" + item.path, settings.auth_secret)}
                for item in exports
            ],
        }
    )


@app.patch("/api/v1/papers/{paper_id}")
async def patch_paper(
    paper_id: str,
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(current_user),
):
    payload = validated_payload(PaperUpdateRequest, payload)
    paper = await db.get(Paper, paper_id)
    if paper is None:
        raise HTTPException(404, "试卷不存在")
    if "title" in payload:
        paper.title = payload["title"]
    if "filters" in payload:
        paper.filters = payload["filters"]
    if "items" in payload:
        for value in payload["items"]:
            await owned_resource(db, Question, str(value.get("question_id", "")), user)
        await db.execute(delete(PaperItem).where(PaperItem.paper_id == paper_id))
        for position, value in enumerate(payload["items"]):
            db.add(
                PaperItem(
                    paper_id=paper_id,
                    question_id=value["question_id"],
                    position=position,
                    score=int(value.get("score", 10)),
                )
            )
    await db.commit()
    return await get_paper(paper_id, db)


@app.delete("/api/v1/papers/{paper_id}")
async def delete_paper(paper_id: str, db: AsyncSession = Depends(get_db)):
    paper = await db.get(Paper, paper_id)
    if paper is None:
        return envelope({"deleted": False})
    await db.execute(delete(ExportJob).where(ExportJob.paper_id == paper_id))
    await db.execute(delete(PaperItem).where(PaperItem.paper_id == paper_id))
    await db.delete(paper)
    await db.commit()
    return envelope({"deleted": True})


@app.post("/api/v1/papers/{paper_id}/export")
async def export_paper(paper_id: str, payload: dict = Body(default={}), db: AsyncSession = Depends(get_db)):
    kind = payload.get("kind", "question")
    if kind not in {"question", "answer", "excel"}:
        raise HTTPException(422, "不支持的导出格式")
    paper = await db.get(Paper, paper_id)
    if paper is None:
        raise HTTPException(404, "试卷不存在")
    items = list(
        await db.scalars(select(PaperItem).where(PaperItem.paper_id == paper_id).order_by(PaperItem.position))
    )
    questions = []
    for item in items:
        q = await db.get(Question, item.question_id)
        if q is None:
            continue
        analysis = (
            await db.scalars(select(ProblemAnalysis).where(ProblemAnalysis.question_id == q.id))
        ).first()
        diagnosis = (
            await db.scalars(
                select(Diagnosis).where(Diagnosis.question_id == q.id).order_by(Diagnosis.created_at.desc())
            )
        ).first()
        figures = list(
            await db.scalars(
                select(QuestionAsset).where(
                    QuestionAsset.question_id == q.id, QuestionAsset.kind == "question_figure"
                )
            )
        )
        references = (
            list(
                await db.scalars(
                    select(ReferenceStep)
                    .where(
                        ReferenceStep.analysis_id == analysis.id,
                    )
                    .order_by(ReferenceStep.step_index)
                )
            )
            if analysis
            else []
        )
        questions.append(
            {
                "question_text": q.question_text,
                "answer": analysis.final_answer if analysis else "",
                "explanation": "\n".join(row.text for row in references),
                "subject": q.subject,
                "score": item.score,
                "formula": "；".join(str(value) for value in q.formulas),
                "options": q.options or [],
                "figure_paths": [figure.path for figure in figures],
                "misconception": diagnosis.root_misconception if diagnosis else "",
            }
        )
    kind = payload.get("kind", "question")
    suffix = "xlsx" if kind == "excel" else "pdf"
    path = Path("reports") / f"{paper_id}-{kind}.{suffix}"
    if kind == "excel":
        build_excel(
            path,
            [
                {
                    "question": q["question_text"],
                    "subject": q["subject"],
                    "misconception": q["misconception"],
                    "mastery": "",
                    "review": "",
                }
                for q in questions
            ],
        )
    else:
        build_pdf(
            path, paper.title + ("-答案解析" if kind == "answer" else ""), questions, answers=kind == "answer"
        )
    job = ExportJob(paper_id=paper_id, kind=kind, path=str(path))
    db.add(job)
    await db.commit()
    return envelope(row_dict(job) | {"url": sign_media_url("/" + str(path), settings.auth_secret)})


@app.get("/api/v1/papers/{paper_id}/download")
async def download_paper(paper_id: str, kind: str = Query("question"), db: AsyncSession = Depends(get_db)):
    job = (
        await db.scalars(
            select(ExportJob)
            .where(ExportJob.paper_id == paper_id, ExportJob.kind == kind)
            .order_by(ExportJob.created_at.desc())
        )
    ).first()
    if not job or not Path(job.path).exists():
        raise HTTPException(404, "请先生成导出文件")
    return FileResponse(job.path, filename=Path(job.path).name)


@app.post("/api/v1/voice/transcribe")
async def transcribe_voice(
    file: UploadFile = File(...),
    question_id: str | None = Query(default=None),
    work_id: str | None = Query(default=None),
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    raw = await file.read()
    if not raw:
        raise HTTPException(400, "音频文件为空")
    suffix = Path(file.filename or "voice.webm").suffix.lower()
    if suffix not in {".webm", ".wav", ".mp3", ".m4a", ".ogg", ".mp4"}:
        suffix = ".webm"
    folder = settings.upload_dir / "voice" / user.id
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{uuid.uuid4().hex}{suffix}"
    path.write_bytes(raw)
    try:
        text, metadata = await voice_provider.transcribe(path)
    except Exception as exc:
        record = VoiceRecord(
            user_id=user.id,
            question_id=question_id,
            work_id=work_id,
            kind="stt",
            audio_path=str(path),
            transcript="",
            model_name=voice_provider.model_name,
            status="failed",
            duration_ms=0,
        )
        db.add(record)
        await db.commit()
        raise HTTPException(502, f"语音转写失败：{type(exc).__name__}") from exc
    record = VoiceRecord(
        user_id=user.id,
        question_id=question_id,
        work_id=work_id,
        kind="stt",
        audio_path=str(path),
        transcript=text,
        model_name=metadata["model"],
        duration_ms=metadata["duration_ms"],
    )
    db.add(record)
    if work_id:
        work = await db.get(StudentWork, work_id)
        if work:
            work.explanation = text
    await db.commit()
    await db.refresh(record)
    return envelope(
        row_dict(record)
        | {
            "text": text,
            "bytes": len(raw),
            "editable": True,
            "metadata": metadata,
            "audio_url": sign_media_url("/" + str(path), settings.auth_secret),
        }
    )


@app.post("/api/v1/voice/synthesize")
async def synthesize_voice(
    payload: dict = Body(...),
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    text = str(payload.get("text", "")).strip()
    if not text:
        raise HTTPException(400, "朗读文本不能为空")
    folder = settings.upload_dir / "voice" / user.id
    path = folder / f"tts-{uuid.uuid4().hex}.mp3"
    try:
        metadata = await voice_provider.synthesize(text, path, payload.get("voice", "zh-CN-XiaoxiaoNeural"))
    except Exception as exc:
        raise HTTPException(502, f"语音合成失败：{type(exc).__name__}") from exc
    record = VoiceRecord(
        user_id=user.id,
        question_id=payload.get("question_id"),
        kind="tts",
        audio_path=str(path),
        transcript=text,
        model_name=metadata["model"],
        duration_ms=metadata["duration_ms"],
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return envelope(
        row_dict(record)
        | {
            "text": text,
            "browser_fallback": False,
            "audio_url": sign_media_url("/" + str(path), settings.auth_secret),
            "metadata": metadata,
        }
    )


@app.get("/api/v1/guardians/students")
async def guardian_students(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    if user.role != "guardian":
        raise HTTPException(status_code=403, detail="请使用家长账号登录")
    links = list(
        await db.scalars(select(GuardianStudentLink).where(GuardianStudentLink.guardian_id == user.id))
    )
    students = [await db.get(User, link.student_id) for link in links]
    result = []
    for student in students:
        if student:
            pending = int(
                await db.scalar(
                    select(func.count())
                    .select_from(ReviewPlan)
                    .where(ReviewPlan.user_id == student.id, ReviewPlan.status == "pending")
                )
                or 0
            )
            mastery = list(await db.scalars(select(MasteryState).where(MasteryState.user_id == student.id)))
            result.append(
                user_dict(student)
                | {
                    "pending_reviews": pending,
                    "average_mastery": round(sum(item.mastery_score for item in mastery) / len(mastery), 3)
                    if mastery
                    else 0,
                }
            )
    return envelope(result)


@app.get("/api/v1/guardians/students/{student_id}/overview")
@app.get("/api/v1/teachers/students/{student_id}/report")
async def student_report(
    student_id: str, account: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    if account.role == "guardian":
        allowed = await db.scalar(
            select(func.count())
            .select_from(GuardianStudentLink)
            .where(
                GuardianStudentLink.guardian_id == account.id,
                GuardianStudentLink.student_id == student_id,
            )
        )
    elif account.role == "teacher":
        allowed = await db.scalar(
            select(func.count())
            .select_from(TeacherClassStudent)
            .join(
                TeacherClass,
                TeacherClass.id == TeacherClassStudent.class_id,
            )
            .where(TeacherClass.teacher_id == account.id, TeacherClassStudent.student_id == student_id)
        )
    else:
        raise HTTPException(status_code=403, detail="请使用家长或教师账号登录")
    if not allowed:
        raise HTTPException(status_code=403, detail="该学生未关联到当前账号")
    student = await db.get(User, student_id)
    if student is None:
        raise HTTPException(404, "学生不存在")
    mastery = [
        row_dict(x) for x in await db.scalars(select(MasteryState).where(MasteryState.user_id == student_id))
    ]
    mistakes = [
        row_dict(x)
        for x in await db.scalars(select(MisconceptionState).where(MisconceptionState.user_id == student_id))
    ]
    question_count = int(
        await db.scalar(select(func.count()).select_from(Question).where(Question.user_id == student_id)) or 0
    )
    completed_sessions = int(
        await db.scalar(
            select(func.count())
            .select_from(TutorSession)
            .where(TutorSession.user_id == student_id, TutorSession.status == "completed")
        )
        or 0
    )
    reviews = int(
        await db.scalar(
            select(func.count())
            .select_from(ReviewRecord)
            .join(ReviewPlan, ReviewPlan.id == ReviewRecord.plan_id)
            .where(ReviewPlan.user_id == student_id)
        )
        or 0
    )
    recent = [
        row_dict(item)
        for item in await db.scalars(
            select(CognitiveUpdate)
            .where(CognitiveUpdate.user_id == student_id)
            .order_by(CognitiveUpdate.created_at.desc())
            .limit(10)
        )
    ]
    weak = sorted(mastery, key=lambda item: item["mastery_score"])[:3]
    suggestion = (
        f"建议先巩固{weak[0]['knowledge_point']}，再用自己的话讲一遍解题方法。"
        if weak
        else "先完成一道错题学习，系统会给出更具体的建议。"
    )
    return envelope(
        {
            "student": user_dict(student),
            "mastery": mastery,
            "misconceptions": mistakes,
            "summary": {
                "questions": question_count,
                "completed_sessions": completed_sessions,
                "review_records": reviews,
            },
            "recent_updates": recent,
            "suggestion": suggestion,
        }
    )


@app.get("/api/v1/teachers/classes")
async def teacher_classes(user: User = Depends(require_roles("teacher")), db: AsyncSession = Depends(get_db)):
    result = []
    for item in await db.scalars(select(TeacherClass).where(TeacherClass.teacher_id == user.id)):
        count = int(
            await db.scalar(
                select(func.count())
                .select_from(TeacherClassStudent)
                .where(TeacherClassStudent.class_id == item.id)
            )
            or 0
        )
        result.append(row_dict(item) | {"student_count": count})
    return envelope(result)


@app.get("/api/v1/teachers/classes/{class_id}")
async def teacher_class(
    class_id: str, user: User = Depends(require_roles("teacher")), db: AsyncSession = Depends(get_db)
):
    item = await db.get(TeacherClass, class_id)
    if item is None or item.teacher_id != user.id:
        raise HTTPException(status_code=404, detail="没有找到这个班级")
    links = list(
        await db.scalars(select(TeacherClassStudent).where(TeacherClassStudent.class_id == class_id))
    )
    students = []
    for link in links:
        student = await db.get(User, link.student_id)
        if student:
            mastery = list(await db.scalars(select(MasteryState).where(MasteryState.user_id == student.id)))
            active = list(
                await db.scalars(
                    select(MisconceptionState).where(
                        MisconceptionState.user_id == student.id, MisconceptionState.status != "resolved"
                    )
                )
            )
            students.append(
                user_dict(student)
                | {
                    "average_mastery": round(sum(value.mastery_score for value in mastery) / len(mastery), 3)
                    if mastery
                    else 0,
                    "active_misconceptions": len(active),
                }
            )
    return envelope(row_dict(item) | {"students": students})


def _practice_grade_band(grade: str) -> str:
    return "高中" if grade.startswith("高") or grade == "高中" else "初中"


async def _practice_knowledge(
    db: AsyncSession, question: Question, analysis: ProblemAnalysis | None
) -> list[KnowledgePoint]:
    names = [
        str(item) for item in (analysis.knowledge_points if analysis else question.knowledge_points or [])
    ]
    cards = list(await db.scalars(select(KnowledgePoint).where(KnowledgePoint.subject == question.subject)))
    text = " ".join(names + [question.question_text, question.title]).lower()
    ranked = sorted(
        cards,
        key=lambda card: (
            -(10 if card.name.lower() in text else 0)
            - sum(2 for word in names if len(word) >= 2 and word in str(card.content)),
            card.code,
        ),
    )
    return ranked[:3]


def _practice_recommendation_payload(
    item: DatasetQuestion,
    mode: str,
    trace: dict[str, Any],
    knowledge_points: list[Any],
) -> dict[str, Any]:
    error_pattern = str(trace.get("error_match", "unknown"))
    knowledge_names = list(trace.get("knowledge_match") or [])
    return {
        "question_id": item.id,
        "subject": item.subject,
        "grade": item.grade,
        "stem": item.question_text,
        "images": [
            sign_media_url(f"/api/v1/practice/questions/{item.id}/images/{index}", settings.auth_secret)
            for index, _ in enumerate(item.image_paths)
        ],
        "options": normalize_choice_options(item.options),
        "question_type": item.question_type,
        "knowledge_points": knowledge_points,
        "recommendation": (
            "这道题和你刚才漏掉的边界情况有关。"
            if error_pattern == "boundary_omission"
            else f"这道题会继续检查你刚才需要加强的{knowledge_names[0] if knowledge_names else '关键方法'}。"
        ),
        "mode": mode,
    }


@app.post("/api/v1/practice/recommend")
async def recommend_practice(
    payload: PracticeRecommendRequest,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    mistake = await db.get(Question, payload.mistake_id)
    if mistake is None or mistake.user_id != user.id or mistake.status == "archived":
        raise HTTPException(status_code=404, detail="没有找到这道错题")
    source_fingerprint = await learning_source_fingerprint(db, mistake)
    diagnosis = (
        await db.scalars(
            select(Diagnosis)
            .where(
                Diagnosis.question_id == mistake.id,
            )
            .order_by(Diagnosis.created_at.desc())
        )
    ).first()
    analysis = (
        await db.scalars(select(ProblemAnalysis).where(ProblemAnalysis.question_id == mistake.id))
    ).first()
    cards = await _practice_knowledge(db, mistake, analysis)
    knowledge_names = [card.name for card in cards]
    if not payload.force_new:
        latest = (
            await db.scalars(
                select(PracticeRecommendation)
                .where(
                    PracticeRecommendation.user_id == user.id,
                    PracticeRecommendation.mistake_id == mistake.id,
                    PracticeRecommendation.mode == payload.mode,
                )
                .order_by(PracticeRecommendation.created_at.desc())
            )
        ).first()
        if (
            latest is not None
            and (latest.retrieval_trace or {}).get("source_question_fingerprint") == source_fingerprint
        ):
            attempted = await db.scalar(
                select(func.count())
                .select_from(DatasetPracticeAttempt)
                .where(
                    DatasetPracticeAttempt.user_id == user.id,
                    DatasetPracticeAttempt.mistake_id == mistake.id,
                    DatasetPracticeAttempt.dataset_question_id == latest.dataset_question_id,
                    DatasetPracticeAttempt.mode == payload.mode,
                )
            )
            previous = await db.get(DatasetQuestion, latest.dataset_question_id)
            if not attempted and previous is not None:
                current = await db.get(Question, mistake.id, with_for_update=True, populate_existing=True)
                if (
                    current is None
                    or current.status == "archived"
                    or await learning_source_fingerprint(db, current, current_read=True) != source_fingerprint
                ):
                    raise HTTPException(409, "题目已修改，请重新获取推荐题")
                result = _practice_recommendation_payload(
                    previous,
                    payload.mode,
                    latest.retrieval_trace or {},
                    previous.knowledge_points or [],
                )
                if payload.debug:
                    result["debug"] = latest.retrieval_trace or {}
                return envelope(result)
    target_skill = "；".join(
        filter(
            None,
            (
                diagnosis.first_error_text if diagnosis else "",
                diagnosis.root_misconception if diagnosis else "",
                "、".join(diagnosis.missing_prerequisites) if diagnosis else "",
            ),
        )
    ) or (knowledge_names[0] if knowledge_names else mistake.title)
    error_pattern = diagnosis.error_type if diagnosis else "unknown"
    query_text = "\n".join(
        filter(
            None,
            (
                f"学科：{mistake.subject}",
                f"年级：{mistake.grade}",
                mistake.question_text,
                "知识点：" + "、".join(knowledge_names),
                f"目标技能：{target_skill}",
                f"错误模式：{error_pattern}",
                "要求：保持核心知识和难度"
                if payload.mode == "reinforce"
                else "要求：改变题型或情境但检验同一错误模式",
            ),
        )
    )
    try:
        fused, dense_ranks, sparse_ranks = await hybrid_ids(
            query_text,
            mistake.subject,
            mistake.grade or "",
            _practice_grade_band(mistake.grade or ""),
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail="真实题库检索服务尚未就绪") from exc
    candidates = await load_candidates(db, fused, dense_ranks, sparse_ranks)
    attempted_ids = set(
        await db.scalars(
            select(DatasetPracticeAttempt.dataset_question_id).where(
                DatasetPracticeAttempt.user_id == user.id,
                DatasetPracticeAttempt.mistake_id == mistake.id,
            )
        )
    )
    served_ids = set(
        await db.scalars(
            select(PracticeRecommendation.dataset_question_id).where(
                PracticeRecommendation.user_id == user.id,
                PracticeRecommendation.mistake_id == mistake.id,
            )
        )
    )
    original_text = "".join(character.lower() for character in mistake.question_text if character.isalnum())
    filtered = []
    for item in candidates:
        candidate_text = "".join(
            character.lower() for character in item.question.question_text if character.isalnum()
        )
        similarity = SequenceMatcher(None, original_text, candidate_text).ratio()
        threshold = 0.90 if payload.mode == "variation" else 0.96
        if item.question.id in attempted_ids | served_ids or similarity >= threshold:
            continue
        filtered.append(item)
    if not filtered:
        raise HTTPException(status_code=404, detail="暂时没有找到合适且未做过的真实题目")
    try:
        ranked = await rerank_candidates(
            query_text,
            mistake.question_text,
            mistake.question_type,
            payload.mode,
            filtered,
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail="真实题库重排服务尚未就绪，请稍后重试") from exc
    if not ranked:
        raise HTTPException(status_code=404, detail="暂时没有找到合适的真实题目")
    current = await db.get(Question, mistake.id, with_for_update=True, populate_existing=True)
    if (
        current is None
        or current.status == "archived"
        or await learning_source_fingerprint(db, current, current_read=True) != source_fingerprint
    ):
        raise HTTPException(409, "题目已修改，请重新获取推荐题")
    selected = ranked[0]
    trace = {
        "source_question_fingerprint": source_fingerprint,
        "knowledge_match": knowledge_names,
        "target_knowledge_id": cards[0].id if cards else None,
        "target_knowledge_name": cards[0].name if cards else None,
        "error_match": error_pattern,
        "target_skill": target_skill,
        "difficulty_match": selected.question.difficulty or "同年级",
        "question_type_difference": selected.question.question_type != mistake.question_type,
        "structure_similarity": round(selected.structure_similarity, 5),
        "dense_rank": selected.dense_rank,
        "sparse_rank": selected.sparse_rank,
        "fusion_rank": selected.fusion_rank,
        "reranker_score": round(selected.reranker_score, 5),
        "mode_score": round(selected.mode_score, 5),
    }
    db.add(
        PracticeRecommendation(
            user_id=user.id,
            mistake_id=mistake.id,
            dataset_question_id=selected.question.id,
            mode=payload.mode,
            retrieval_rank=selected.fusion_rank,
            retrieval_trace=trace,
        )
    )
    await db.commit()
    result = _practice_recommendation_payload(
        selected.question, payload.mode, trace, selected.knowledge_points
    )
    if payload.debug:
        result["debug"] = trace
    return envelope(result)


@app.get("/api/v1/practice/questions/{question_id}/images/{image_index}")
async def practice_image(question_id: str, image_index: int, db: AsyncSession = Depends(get_db)):
    question = await db.get(DatasetQuestion, question_id)
    paths = question.image_paths if question else []
    if question is None or image_index < 0 or image_index >= len(paths):
        raise HTTPException(status_code=404, detail="图片不存在")
    path = Path(paths[image_index]).resolve()
    allowed_root = Path("data/question_bank_assets").resolve()
    if not path.is_relative_to(allowed_root) or not path.is_file():
        raise HTTPException(status_code=404, detail="图片不存在")
    return FileResponse(path)


@app.post("/api/v1/practice/attempt")
async def attempt_practice(
    payload: PracticeAttemptRequest,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    # A locking read serializes attempts for this source mistake, including
    # requests whose authentication query started an older MySQL snapshot.
    mistake = await db.get(Question, payload.mistake_id, with_for_update=True, populate_existing=True)
    question = await db.get(DatasetQuestion, payload.question_id)
    if mistake is None or mistake.user_id != user.id or mistake.status == "archived":
        raise HTTPException(status_code=404, detail="没有找到这道错题")
    if question is None or not question.usable_for_auto_grade:
        raise HTTPException(status_code=422, detail="这道题不能自动判分")
    previous_attempt = (
        await db.scalars(
            select(DatasetPracticeAttempt)
            .where(
                DatasetPracticeAttempt.user_id == user.id,
                DatasetPracticeAttempt.mistake_id == mistake.id,
                DatasetPracticeAttempt.dataset_question_id == question.id,
                DatasetPracticeAttempt.mode == payload.mode,
            )
            .with_for_update()
        )
    ).first()
    if previous_attempt is not None:
        raise HTTPException(409, "这道练习已经完成，请换一道题继续练习")
    handwriting_image_url, handwriting_recognition = validate_answer_handwriting(
        user_id=user.id,
        context_type="practice",
        context_id=question.id,
        image_url=payload.handwriting_image_url,
        recognition=payload.handwriting_recognition,
    )
    served = (
        await db.scalars(
            select(PracticeRecommendation)
            .where(
                PracticeRecommendation.user_id == user.id,
                PracticeRecommendation.mistake_id == mistake.id,
                PracticeRecommendation.dataset_question_id == question.id,
                PracticeRecommendation.mode == payload.mode,
            )
            .order_by(PracticeRecommendation.created_at.desc())
            .with_for_update()
        )
    ).first()
    if not served or (served.retrieval_trace or {}).get(
        "source_question_fingerprint"
    ) != await learning_source_fingerprint(db, mistake, current_read=True):
        raise HTTPException(status_code=409, detail="题目或推荐已更新，请重新获取推荐题再提交")
    grading = await grade_answer(
        provider,
        question=question.question_text,
        answer=payload.student_answer,
        expected=question.answer,
        reference_solution=[
            line.strip() for line in str(question.solution or "").splitlines() if line.strip()
        ],
        subject=question.subject,
        question_type=question.question_type,
        options=question.options,
    )
    correct = bool(grading["correct"])
    grading_method = str(grading["method"])
    source = await db.get(DatasetSource, question.dataset_source_id)
    primary = (
        await db.execute(
            select(QuestionKnowledgeLink, KnowledgePoint)
            .join(KnowledgePoint, KnowledgePoint.id == QuestionKnowledgeLink.knowledge_point_id)
            .where(
                QuestionKnowledgeLink.dataset_question_id == question.id,
                QuestionKnowledgeLink.role == "primary",
            )
        )
    ).first()
    _, recommended_knowledge = primary if primary else (None, None)
    target_knowledge_id = served.retrieval_trace.get("target_knowledge_id") if served else None
    knowledge = (
        await db.get(KnowledgePoint, target_knowledge_id) if target_knowledge_id else recommended_knowledge
    )
    if grading["can_update_learning"]:
        db.add(
            DatasetPracticeAttempt(
                user_id=user.id,
                mistake_id=mistake.id,
                dataset_question_id=question.id,
                source_dataset=source.key if source else "unknown",
                knowledge_id=knowledge.id if knowledge else None,
                mode=payload.mode,
                student_answer=payload.student_answer,
                correct=correct,
                duration_seconds=payload.duration_seconds,
                grading_details={
                    **grading,
                    "method": grading_method,
                    "independent_answer": True,
                    "handwriting_image_url": sign_media_url(handwriting_image_url, settings.auth_secret),
                    "handwriting_recognition": handwriting_recognition,
                },
            )
        )
    diagnosis = (
        await db.scalars(
            select(Diagnosis)
            .where(
                Diagnosis.question_id == mistake.id,
            )
            .order_by(Diagnosis.created_at.desc())
        )
    ).first()
    evidence_key = "near_transfer" if payload.mode == "reinforce" else "far_transfer"
    target = cognition_target(
        subject=mistake.subject,
        question_type=mistake.question_type,
        title=mistake.title,
        question_knowledge_points=mistake.knowledge_points,
        analysis_knowledge_points=None,
        diagnosis_error_type=diagnosis.error_type if diagnosis else None,
        diagnosis_root_misconception=diagnosis.root_misconception if diagnosis else None,
        preferred_knowledge_point=knowledge.name if knowledge else None,
    )
    mastery_before = (
        await db.scalar(
            select(MasteryState.mastery_score).where(
                MasteryState.user_id == user.id,
                MasteryState.subject == target.subject,
                MasteryState.knowledge_point == target.knowledge_point,
            )
        )
        or 0.0
    )
    mastery = None
    if grading["can_update_learning"]:
        mastery, _ = await update_cognition(
            db,
            user.id,
            mistake.id,
            {
                evidence_key: correct,
                "hint_level": 0,
                "strategy": "independent_dataset_practice",
                "dataset_question_id": question.id,
            },
            subject=target.subject,
            knowledge_point=target.knowledge_point,
            misconception_code=target.misconception_code,
            misconception_label=target.misconception_label,
        )
    await db.commit()
    return envelope(
        {
            "correct": correct if grading["can_update_learning"] else None,
            "verdict": grading["verdict"],
            "can_update_learning": grading["can_update_learning"],
            "confidence": grading["confidence"],
            "evidence": grading["evidence"],
            "answer": question.answer,
            "solution": question.solution,
            "feedback": grading["feedback"],
            "mastery_before": mastery_before,
            "mastery": mastery.mastery_score if mastery else None,
            "grading_method": grading_method,
        }
    )


app.include_router(create_learning_router(current_user))
