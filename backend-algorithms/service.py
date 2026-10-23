"""Internal computation only: no database, accounts, task state or business proxy."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import os
import secrets
import time
from contextlib import asynccontextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Annotated, Literal

from fastapi import FastAPI, HTTPException, Request
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    ValidationError,
    model_validator,
)

from adaptive_practice import AdaptivePracticeInput, select_practice
from diagnosis_compute import StepRecord, compute_diagnosis
from dialogue_compute import DialogueContext, finish_dialogue, prepare_dialogue
from grading_compute import UnavailableGradingProvider, grade_answer
from inequality_compute import format_solution, solution_set, source_inequality
from knowledge_lesson_compute import explain_knowledge
from learning_core.providers.api_pool import ApiPoolProvider, ApiPoolUnavailable
from learning_core.schemas import (
    AnalysisOutput,
    HandwrittenAnswerRecognition,
    VariantOutput,
    VisualizationPayload,
)
from learning_core.services.ai_pipeline import analyze_question
from learning_core.services.cognition_rules import compute_cognition
from learning_core.services.diagnosis import equation_equivalent
from learning_core.services.handwritten_answer import recognize_handwritten_answer
from learning_core.services.image_recognition import recognize_cropped_question
from learning_core.services.math_tools import (
    compare_equivalence,
    solve_text_equation,
)
from learning_core.services.pedagogy import evaluate_teach_back
from learning_core.services.question_bank_import import normalize_choice_options
from learning_core.services.tutor_activities import build_adaptive_teaching_brief
from learning_core.services.vision import (
    MAX_UPLOAD_BYTES,
    crop_image,
    persist_recognition_regions,
    preprocess_image,
    save_original,
)
from learning_core.services.visualizations import (
    recommended_visualization,
    visualization_catalog,
    visualization_spec,
)
from learning_core.services.voice import VoiceProvider
from learning_task_compute import Checkpoint, TaskAction, TaskContext
from learning_workflow import run_learning_workflow
from mastery_tracker import compute_aemt_cognition
from paper_export_compute import ExportQuestion, render_paper
from practice_alignment import align_practice
from practice_generation import UnavailablePracticeProvider, generate_practice
from retrieval_compute import prepare_query, rank_snapshots, search_index
from variant_compute import (
    VariantReference,
    generate_variant,
    verify_knowledge_alignment,
    verify_variant,
)
from voice_compute import VoiceComputeError, synthesize_audio, transcribe_audio

PROJECT = Path(__file__).resolve().parents[1]
MAX_REQUEST_BYTES = 22 * 1024 * 1024


class ComputeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    operation: Literal[
        "learning_task",
        "knowledge_lesson",
        "normalize",
        "crop",
        "preprocess",
        "recognize",
        "math_compare",
        "math_solve",
        "analyze",
        "diagnose",
        "counterfactual",
        "teaching_brief",
        "generate_variant",
        "generate_practice",
        "grade_answer",
        "recognize_handwriting",
        "validate_handwriting",
        "cognition_update",
        "evaluate_teach_back",
        "visualization_config",
        "render_paper",
        "system_state",
        "voice_transcribe",
        "voice_synthesize",
        "tutor_dialogue_prepare",
        "tutor_dialogue_finish",
        "adaptive_practice",
        "retrieval_prepare",
        "retrieval_search",
        "retrieval_rank",
        "practice_alignment",
        "normalize_options",
        "validate_variant",
    ]
    image_base64: str | None = Field(default=None, max_length=20 * 1024 * 1024)
    box: list[float] | None = Field(default=None, min_length=4, max_length=4)
    left: str = Field(default="", max_length=12000)
    right: str = Field(default="", max_length=12000)
    text: str = Field(default="", max_length=12000)

    subject: str = Field(default="数学", min_length=1, max_length=30)
    grade: str = Field(default="", max_length=30)
    question_type: str = Field(default="综合题", max_length=50)
    student_answer: str | None = Field(default=None, max_length=12000)
    student_steps: list[Annotated[str, Field(max_length=12000)]] = Field(
        default_factory=list, max_length=100
    )
    options: list[dict[str, str]] = Field(default_factory=list, max_length=26)
    images_base64: list[Annotated[str, Field(max_length=20 * 1024 * 1024)]] = Field(
        default_factory=list, max_length=32
    )

    reference_steps: list[StepRecord] = Field(default_factory=list, max_length=100)
    student_records: list[StepRecord] = Field(default_factory=list, max_length=100)

    correct_answer: str = Field(default="", max_length=12000)
    knowledge_points: list[Annotated[str, Field(max_length=12000)]] = Field(
        default_factory=list, max_length=100
    )
    diagnosis: dict[str, JsonValue] = Field(default_factory=dict)
    diagnostic_cards: list[dict[str, JsonValue]] = Field(default_factory=list, max_length=8)

    transfer_type: Literal["near", "far"] = "near"
    variant_references: list[VariantReference] = Field(
        default_factory=list, max_length=20
    )

    retrieval_query: str = Field(default="", max_length=80000)
    retrieval_source: dict[str, JsonValue] = Field(default_factory=dict)
    retrieval_target: dict[str, JsonValue] = Field(default_factory=dict)
    retrieval_analysis: dict[str, JsonValue] | None = None
    retrieval_diagnosis: dict[str, JsonValue] = Field(default_factory=dict)
    retrieval_cards: list[dict[str, JsonValue]] = Field(
        default_factory=list, max_length=5000
    )
    retrieval_candidates: list[dict[str, JsonValue]] = Field(
        default_factory=list, max_length=50
    )
    retrieval_excluded_ids: list[str] = Field(default_factory=list, max_length=10000)
    retrieval_kind: Literal["practice", "variant"] = "practice"
    retrieval_mode: Literal["reinforce", "variation"] = "reinforce"
    grade_band: str = Field(default="初中", max_length=30)
    raw_options: JsonValue = None
    variant_candidate: VariantOutput | None = None

    task_budget_ms: int = Field(default=38000, ge=1, le=38000, strict=True)
    task_context: TaskContext | None = None
    task_checkpoint: Checkpoint = Field(default_factory=Checkpoint)
    task_action: TaskAction = Field(default_factory=TaskAction)
    dialogue_context: DialogueContext | None = None
    dialogue_memory_rows: dict[str, list[dict[str, JsonValue]]] = Field(
        default_factory=dict
    )
    dialogue_preparation: dict[str, JsonValue] = Field(default_factory=dict)
    dialogue_cards: list[dict[str, JsonValue]] = Field(
        default_factory=list, max_length=8
    )
    knowledge_history: list[dict[str, JsonValue]] = Field(default_factory=list, max_length=3)
    adaptive_practice: AdaptivePracticeInput | None = None
    probe_provider: bool = False
    audio_base64: str = Field(default="", max_length=20 * 1024 * 1024)
    audio_suffix: Literal[".webm", ".wav", ".mp3", ".m4a", ".ogg", ".mp4"] = ".webm"
    voice: str = Field(default="zh-CN-XiaoxiaoNeural", max_length=100)
    paper_title: str = Field(default="专项练习", max_length=255)
    paper_kind: Literal["question", "answer", "excel"] = "question"
    paper_questions: list[ExportQuestion] = Field(default_factory=list, max_length=200)
    visualization_values: dict[str, JsonValue] = Field(default_factory=dict)
    teach_back_points: list[JsonValue] = Field(default_factory=list, max_length=100)
    mastery_values: dict[str, JsonValue] = Field(default_factory=dict)
    misconception_values: dict[str, JsonValue] = Field(default_factory=dict)
    learning_evidence: dict[str, JsonValue] = Field(default_factory=dict)
    misconception_label: str = Field(default="", max_length=150)
    recognition: dict[str, JsonValue] = Field(default_factory=dict)
    answer: JsonValue = ""
    expected: JsonValue = None
    reference_solution: list[Annotated[str, Field(max_length=12000)]] = Field(
        default_factory=list, max_length=100
    )

    @model_validator(mode="after")
    def required_inputs(self):
        if (
            self.operation
            in {"normalize", "crop", "preprocess", "recognize", "recognize_handwriting"}
            and not self.image_base64
        ):
            raise ValueError("image required")
        if (
            self.operation
            in {
                "analyze",
                "diagnose",
                "counterfactual",
                "teaching_brief",
                "generate_variant",
                "generate_practice",
            }
            and not self.text.strip()
        ):
            raise ValueError("question required")
        if self.operation == "grade_answer" and (
            not self.text.strip() or self.expected is None
        ):
            raise ValueError("question and expected answer required")
        if self.operation == "teaching_brief" and not self.correct_answer.strip():
            raise ValueError("correct answer required")
        if self.operation == "crop":
            if self.box is None:
                raise ValueError("crop required")
            x, y, width, height = self.box
            if not (
                0 <= x < 1
                and 0 <= y < 1
                and 0 < width <= 1
                and 0 < height <= 1
                and x + width <= 1.000001
                and y + height <= 1.000001
            ):
                raise ValueError("invalid crop")
        return self


class ImageResult(BaseModel):
    kind: str
    image_base64: str
    sha256: str


def image_result(path: Path, kind: str) -> dict:
    data = path.read_bytes()
    return ImageResult(
        kind=kind,
        image_base64=base64.b64encode(data).decode(),
        sha256=hashlib.sha256(data).hexdigest(),
    ).model_dump()


def decode_image(value: str) -> bytes:
    data = base64.b64decode(value, validate=True)
    if not data or len(data) > MAX_UPLOAD_BYTES:
        raise ValueError("invalid image size")
    return data


def create_app(*, secret: str | None = None, pool_path: Path | None = None) -> FastAPI:
    token = (
        secret if secret is not None else os.environ.get("CANGJIE_ALGORITHM_SECRET", "")
    )
    if len(token) < 32:
        raise ValueError("CANGJIE_ALGORITHM_SECRET 至少需要 32 字符")
    pool = pool_path or Path(
        os.environ.get(
            "CANGJIE_API_POOL_PATH", str(PROJECT / "config/api_pool.json")
        )
    )

    def configured_model():
        if app.state.provider is not None and hasattr(app.state.provider, "logical_model"):
            return app.state.provider.logical_model
        try:
            config = json.loads(pool.read_text())
            def models(value):
                if isinstance(value, dict):
                    if value.get("disabled") is True:
                        return []
                    if isinstance(value.get("model"), str):
                        return [value["model"]]
                    return [m for child in value.values() for m in models(child)]
                if isinstance(value, list):
                    return [m for child in value for m in models(child)]
                return []
            active = models(config)
            return active[0] if active else "unconfigured"
        except (OSError, ValueError):
            return "unconfigured"

    trust_env_proxy = os.environ.get("CANGJIE_AI_USE_ENV_PROXY", "true").lower() != "false"

    @asynccontextmanager
    async def lifespan(app):
        yield
        if app.state.provider is not None:
            await app.state.provider.close()

    app = FastAPI(
        title="仓颉内部算法服务",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.provider = None
    app.state.voice_provider = VoiceProvider()

    @app.get("/livez")
    async def livez():
        return {
            "service": "zhiwei-algorithms",
            "database": False,
            "logical_model": configured_model(),
        }

    @app.post("/v1/compute")
    async def compute(request: Request):
        authorization = request.headers.get("authorization", "")
        supplied = authorization.removeprefix("Bearer ")
        if not authorization.startswith("Bearer ") or not secrets.compare_digest(
            supplied.encode(), token.encode()
        ):
            raise HTTPException(401, "内部计算认证失败")
        chunks, size = [], 0
        async for chunk in request.stream():
            size += len(chunk)
            if size > MAX_REQUEST_BYTES:
                raise HTTPException(413, "计算输入过大")
            chunks.append(chunk)
        try:
            data = ComputeRequest.model_validate_json(b"".join(chunks))
        except ValidationError:
            raise HTTPException(422, "计算输入格式不正确") from None
        try:
            if data.operation == "knowledge_lesson":
                if app.state.provider is None:
                    try:
                        app.state.provider = ApiPoolProvider(pool, trust_env=trust_env_proxy)
                    except (OSError, ValueError):
                        pass
                result = await explain_knowledge(
                    app.state.provider or UnavailableGradingProvider(),
                    data.dialogue_cards, data.subject, data.grade, data.text, data.knowledge_history,
                )
            elif data.operation == "learning_task":
                if data.task_context is None:
                    raise ValueError("task context required")
                if app.state.provider is None:
                    try:
                        app.state.provider = ApiPoolProvider(pool, trust_env=trust_env_proxy)
                    except (OSError, ValueError):
                        pass
                async with asyncio.timeout(data.task_budget_ms / 1000):
                    task_result = await run_learning_workflow(
                        app.state.provider or UnavailableGradingProvider(),
                        data.task_context,
                        data.task_checkpoint,
                        data.task_action,
                    )
                result = task_result.model_dump(mode="json")
            elif data.operation in {"tutor_dialogue_prepare", "tutor_dialogue_finish"}:
                if data.dialogue_context is None:
                    raise ValueError("dialogue context required")
                if app.state.provider is None:
                    try:
                        app.state.provider = ApiPoolProvider(pool, trust_env=trust_env_proxy)
                    except (OSError, ValueError):
                        pass
                dialogue_provider = app.state.provider or UnavailableGradingProvider()
                if data.operation == "tutor_dialogue_prepare":
                    result = await prepare_dialogue(
                        dialogue_provider,
                        data.dialogue_context,
                        data.dialogue_memory_rows,
                    )
                else:
                    result = await finish_dialogue(
                        dialogue_provider,
                        data.dialogue_context,
                        data.dialogue_preparation,
                        data.dialogue_cards,
                        [decode_image(item) for item in data.images_base64],
                    )
            elif data.operation == "adaptive_practice":
                if data.adaptive_practice is None:
                    raise ValueError("adaptive practice input required")
                result = select_practice(data.adaptive_practice)
            elif data.operation == "system_state":
                if app.state.provider is None:
                    try:
                        app.state.provider = ApiPoolProvider(pool, trust_env=trust_env_proxy)
                    except (OSError, ValueError):
                        if data.probe_provider:
                            raise ApiPoolUnavailable("模型池尚未就绪") from None
                if app.state.provider is None:
                    health = {
                        "logical_model": configured_model(),
                        "actual_models": [],
                        "total_entries": 0,
                        "unique_keys": 0,
                        "text_entries": 0,
                        "vision_entries": 0,
                        "global_index": 0,
                        "text_index": 0,
                        "vision_index": 0,
                        "last_entry": None,
                        "last_status": "unavailable",
                        "recent_rotation": [],
                    }
                else:
                    health = (
                        await app.state.provider.probe()
                        if data.probe_provider
                        else app.state.provider.health_check()
                    )
                result = {
                    "provider": health,
                    "voice": app.state.voice_provider.health_check(),
                }
            elif data.operation == "voice_transcribe":
                result = await transcribe_audio(
                    app.state.voice_provider, data.audio_base64, data.audio_suffix
                )
            elif data.operation == "voice_synthesize":
                result = await synthesize_audio(
                    app.state.voice_provider, data.text, data.voice
                )
            elif data.operation == "render_paper":
                result = await asyncio.to_thread(
                    render_paper,
                    data.paper_title,
                    data.paper_kind,
                    data.paper_questions,
                )
            elif data.operation == "visualization_config":
                kind = recommended_visualization(
                    data.subject, data.question_type, data.teach_back_points
                )
                spec = None
                if kind is not None:
                    raw = visualization_spec(kind)
                    raw["parameters"].update(data.visualization_values)
                    spec = VisualizationPayload.model_validate(raw).model_dump(
                        mode="json"
                    )
                result = {
                    "catalog": visualization_catalog(),
                    "kind": kind,
                    "spec": spec,
                }
            elif data.operation == "evaluate_teach_back":
                result = evaluate_teach_back(
                    data.text,
                    data.subject,
                    data.question_type,
                    data.teach_back_points,
                    data.reference_solution,
                )
            elif data.operation == "cognition_update":
                compute = compute_aemt_cognition if "aemt_event" in data.learning_evidence else compute_cognition
                mastery, misconception = compute(
                    data.mastery_values,
                    data.misconception_values,
                    data.learning_evidence,
                    data.misconception_label,
                )
                result = {"mastery": mastery, "misconception": misconception}
            elif data.operation == "analyze":
                if app.state.provider is None:
                    try:
                        app.state.provider = ApiPoolProvider(pool, trust_env=trust_env_proxy)
                    except (OSError, ValueError):
                        raise ApiPoolUnavailable("模型池尚未就绪") from None
                with TemporaryDirectory(prefix="zhiwei-analysis-") as directory:
                    paths = []
                    for index, encoded in enumerate(data.images_base64):
                        path = Path(directory) / f"figure-{index}.jpg"
                        await asyncio.to_thread(
                            save_original, decode_image(encoded), path
                        )
                        paths.append(path)
                    source = (
                        await asyncio.to_thread(source_inequality, data.text)
                        if data.subject == "数学" and not data.options
                        else None
                    )
                    try:
                        analysis = await analyze_question(
                            app.state.provider,
                            data.text,
                            data.subject,
                            data.grade,
                            data.question_type,
                            paths,
                            data.student_answer,
                            data.student_steps,
                            options=data.options,
                        )
                    except ApiPoolUnavailable:
                        if source is None:
                            raise
                        analysis = AnalysisOutput(
                            subject="数学",
                            problem_type=data.question_type,
                            known_conditions=[source.text],
                            goal="解不等式",
                            knowledge_points=["一元不等式"],
                            prerequisites=["实数大小与区间"],
                            reference_steps=[source.text, format_solution(source)],
                            final_answer=format_solution(source),
                            answer_verified=True,
                        )
                    if source is not None:
                        analysis.final_answer = format_solution(source)
                        analysis.answer_verified = True

                    def reference_valid(step):
                        if source is not None:
                            try:
                                return (
                                    solution_set(step, source.variable)
                                    == source.solutions
                                )
                            except Exception:  # noqa: BLE001 - prose is not symbolic proof
                                return False
                        return bool(
                            analysis.answer_verified
                            and data.subject == "数学"
                            and equation_equivalent(
                                step, analysis.final_answer, require_symbolic=True
                            )
                        )

                    valid_steps = await asyncio.to_thread(
                        lambda: [
                            reference_valid(step) for step in analysis.reference_steps
                        ]
                    )
                    result = {
                        "analysis": analysis.model_dump(mode="json"),
                        "reference_math_valid": valid_steps,
                        "logical_model": configured_model(),
                    }
            elif data.operation == "grade_answer":
                if app.state.provider is None:
                    try:
                        app.state.provider = ApiPoolProvider(pool, trust_env=trust_env_proxy)
                    except (OSError, ValueError):
                        pass
                result = await grade_answer(
                    app.state.provider or UnavailableGradingProvider(),
                    question=data.text,
                    answer=data.answer,
                    expected=data.expected,
                    reference_solution=data.reference_solution,
                    subject=data.subject,
                    question_type=data.question_type,
                    options=data.options,
                )
            elif data.operation == "retrieval_prepare":
                result = prepare_query(
                    data.retrieval_source,
                    data.retrieval_analysis,
                    data.retrieval_diagnosis,
                    data.retrieval_cards,
                    data.retrieval_kind,
                    data.retrieval_mode,
                )
            elif data.operation == "retrieval_search":
                try:
                    result = await search_index(
                        data.retrieval_query, data.subject, data.grade, data.grade_band
                    )
                except Exception:  # noqa: BLE001 - preserve index failure isolation without leaking provider errors
                    raise HTTPException(503, "真实题库检索服务尚未就绪") from None
            elif data.operation == "retrieval_rank":
                try:
                    result = await rank_snapshots(
                        data.retrieval_query,
                        data.text,
                        data.question_type,
                        data.retrieval_mode,
                        data.retrieval_candidates,
                        data.retrieval_excluded_ids,
                        data.retrieval_kind,
                    )
                except Exception:  # noqa: BLE001 - preserve index failure isolation without leaking provider errors
                    raise HTTPException(503, "真实题库重排服务尚未就绪") from None
            elif data.operation == "practice_alignment":
                if app.state.provider is None:
                    try:
                        app.state.provider = ApiPoolProvider(pool, trust_env=trust_env_proxy)
                    except (OSError, ValueError):
                        pass
                result = await align_practice(
                    app.state.provider,
                    data.retrieval_source,
                    data.retrieval_target,
                    data.retrieval_candidates,
                )
            elif data.operation == "normalize_options":
                result = {"options": normalize_choice_options(data.raw_options)}
            elif data.operation == "validate_variant":
                if data.variant_candidate is None:
                    raise HTTPException(422, "缺少待校验练习")
                result = {
                    "valid": verify_variant(data.variant_candidate, data.subject)
                    and verify_knowledge_alignment(
                        data.variant_candidate, data.knowledge_points, data.text
                    )
                }
            elif data.operation in {"generate_variant", "generate_practice"}:
                if app.state.provider is None:
                    try:
                        app.state.provider = ApiPoolProvider(pool, trust_env=trust_env_proxy)
                    except (OSError, ValueError):
                        if data.operation != "generate_practice":
                            raise ApiPoolUnavailable("模型池尚未就绪") from None
                if data.operation == "generate_practice":
                    return {"operation": data.operation, "result": await generate_practice(
                        app.state.provider or UnavailablePracticeProvider(), data.subject,
                        data.transfer_type, data.text, data.question_type, data.knowledge_points)}
                generated, verified, metadata = await generate_variant(
                    app.state.provider,
                    data.subject,
                    data.transfer_type,
                    data.text,
                    data.question_type,
                    knowledge_points=data.knowledge_points,
                    references=data.variant_references,
                )
                result = {
                    "variant": generated.model_dump(mode="json"),
                    "verified": verified,
                    "generation": metadata.model_dump(),
                    "logical_model": configured_model(),
                }
            elif data.operation == "teaching_brief":
                if app.state.provider is None:
                    try:
                        app.state.provider = ApiPoolProvider(pool, trust_env=trust_env_proxy)
                    except (OSError, ValueError):
                        raise ApiPoolUnavailable("模型池尚未就绪") from None
                brief = await build_adaptive_teaching_brief(
                    app.state.provider,
                    question_text=data.text,
                    options=data.options,
                    correct_answer=data.correct_answer.strip(),
                    student_answer=data.student_answer or "未作答",
                    diagnosis=data.diagnosis,
                    student_steps=data.student_steps,
                    knowledge_points=data.knowledge_points,
                    question_type=data.question_type,
                )
                result = {
                    "brief": brief.model_dump(mode="json"),
                    "logical_model": configured_model(),
                }
            elif data.operation in {"diagnose", "counterfactual"}:
                if app.state.provider is None:
                    try:
                        app.state.provider = ApiPoolProvider(pool, trust_env=trust_env_proxy)
                    except (OSError, ValueError):
                        raise ApiPoolUnavailable("模型池尚未就绪") from None
                with TemporaryDirectory(prefix="zhiwei-diagnosis-") as directory:
                    paths = []
                    for index, encoded in enumerate(data.images_base64):
                        path = Path(directory) / f"figure-{index}.jpg"
                        await asyncio.to_thread(
                            save_original, decode_image(encoded), path
                        )
                        paths.append(path)
                    result = await compute_diagnosis(
                        app.state.provider,
                        text=data.text,
                        subject=data.subject,
                        question_type=data.question_type,
                        student_answer=data.student_answer,
                        options=data.options,
                        references=data.reference_steps,
                        students=data.student_records,
                        images=paths,
                        counterfactual_only=data.operation == "counterfactual",
                        knowledge_cards=data.diagnostic_cards,
                        grade=data.grade,
                    )
            elif data.operation == "validate_handwriting":
                result = HandwrittenAnswerRecognition.model_validate(
                    data.recognition
                ).model_dump(mode="json")
            elif data.operation == "math_compare":
                equivalent, verified = await asyncio.to_thread(
                    compare_equivalence, data.left, data.right
                )
                result = {"equivalent": equivalent, "verified": verified}
            elif data.operation == "math_solve":
                answer, verified = await asyncio.to_thread(
                    solve_text_equation, data.text
                )
                result = {"answer": answer, "verified": verified}
            else:
                raw = decode_image(data.image_base64 or "")
                with TemporaryDirectory(prefix="zhiwei-algorithm-") as directory:
                    root = Path(directory)
                    original = root / "original.jpg"
                    await asyncio.to_thread(save_original, raw, original)
                    if data.operation == "normalize":
                        result = image_result(original, "original")
                    elif data.operation == "crop":
                        target = root / "crop.jpg"
                        geometry = await asyncio.to_thread(
                            crop_image, original, target, data.box
                        )
                        result = {**image_result(target, "crop"), "geometry": geometry}
                    elif data.operation == "preprocess":
                        paths = [
                            root / "clean.jpg",
                            root / "red_mask.png",
                            root / "overlay.jpg",
                        ]
                        metrics = await asyncio.to_thread(
                            preprocess_image, original, *paths
                        )
                        result = {
                            "metrics": metrics,
                            "assets": [
                                image_result(path, kind)
                                for path, kind in zip(
                                    paths, ("clean", "red_mask", "overlay"), strict=True
                                )
                            ],
                        }
                    else:
                        if app.state.provider is None:
                            try:
                                app.state.provider = ApiPoolProvider(pool, trust_env=trust_env_proxy)
                            except (OSError, ValueError):
                                raise ApiPoolUnavailable("模型池尚未就绪") from None
                        started = time.perf_counter()
                        if data.operation == "recognize_handwriting":
                            recognition = await recognize_handwritten_answer(
                                app.state.provider,
                                original,
                                question_text=data.text,
                                subject=data.subject,
                            )
                            return {
                                "operation": data.operation,
                                "result": {
                                    "recognition": recognition.model_dump(mode="json"),
                                    "logical_model": configured_model(),
                                },
                            }
                        recognition = await recognize_cropped_question(
                            app.state.provider, original
                        )
                        duration = round((time.perf_counter() - started) * 1000)
                        regions = await asyncio.to_thread(
                            persist_recognition_regions, original, root, recognition
                        )
                        result = {
                            "recognition": recognition.model_dump(mode="json"),
                            "logical_model": configured_model(),
                            "duration_ms": duration,
                            "assets": [
                                {
                                    **{
                                        key: value
                                        for key, value in region.items()
                                        if key not in {"path", "sha256"}
                                    },
                                    **image_result(
                                        Path(region["path"]), region["kind"]
                                    ),
                                }
                                for region in regions
                            ],
                        }
            return {"operation": data.operation, "result": result}
        except VoiceComputeError:
            raise HTTPException(502, "语音计算暂时不可用") from None
        except ApiPoolUnavailable:
            raise HTTPException(503, "模型计算暂时不可用") from None
        except (ValueError, ValidationError):
            raise HTTPException(422, "图片或计算数据无效") from None
        except Exception:  # noqa: BLE001 -- Internal boundary must not expose upstream credentials.
            # Never propagate upstream messages, request payloads or provider credentials.
            raise HTTPException(503, "计算暂时不可用") from None

    return app
