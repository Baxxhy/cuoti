from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class RecognitionOption(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = Field(min_length=1, max_length=8)
    text: str = Field(min_length=1)


class RecognizedStudentStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    index: int = Field(ge=1)
    text: str = Field(min_length=1)


class TeacherAnnotation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1)
    type: Literal["check", "cross", "correction", "comment", "other"]


class NormalizedVisualRegion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bbox: list[float] = Field(min_length=4, max_length=4)
    description: str = Field(min_length=1)

    @field_validator("bbox")
    @classmethod
    def valid_normalized_bbox(cls, value: list[float]) -> list[float]:
        coordinates = [float(item) for item in value]
        if any(item < 0 or item > 1 for item in coordinates):
            raise ValueError("bbox必须使用0~1归一化坐标")
        x1, y1, x2, y2 = coordinates
        if x2 <= x1 or y2 <= y1:
            raise ValueError("bbox必须满足x2>x1且y2>y1")
        return coordinates


class QuestionFigureRegion(NormalizedVisualRegion):
    role: Literal["question_figure", "table", "chart", "diagram"]


class StudentWorkingFigureRegion(NormalizedVisualRegion):
    role: Literal["student_working_figure"]


class TeacherAnnotationRegion(NormalizedVisualRegion):
    role: Literal["teacher_annotation_region"]


class RawVisualRegion(BaseModel):
    """兼容视觉模型常见的0~1000 bbox；进入业务层前会归一化。"""

    model_config = ConfigDict(extra="forbid")
    bbox: list[float] = Field(min_length=4, max_length=4)
    description: str = Field(min_length=1)

    @field_validator("bbox")
    @classmethod
    def valid_ordered_bbox(cls, value: list[float]) -> list[float]:
        coordinates = [float(item) for item in value]
        x1, y1, x2, y2 = coordinates
        if min(coordinates) < 0 or x2 <= x1 or y2 <= y1:
            raise ValueError("bbox坐标无效")
        return coordinates


class RawQuestionFigureRegion(RawVisualRegion):
    role: Literal["question_figure", "table", "chart", "diagram"]


class RawStudentWorkingFigureRegion(RawVisualRegion):
    role: Literal["student_working_figure"]


class RawTeacherAnnotationRegion(RawVisualRegion):
    role: Literal["teacher_annotation_region"]


class CroppedQuestionRecognition(BaseModel):
    """Qwen对单张裁剪题目图片的严格结构化识别结果。"""

    model_config = ConfigDict(extra="forbid")

    subject: str = Field(min_length=1)
    grade: str | None = None
    question_type: Literal[
        "choice",
        "multiple_choice",
        "fill_blank",
        "calculation",
        "proof",
        "subjective",
        "other",
    ]
    question_text: str = Field(min_length=1)
    options: list[RecognitionOption] = Field(default_factory=list)
    student_answer: str | None = None
    student_steps: list[RecognizedStudentStep] = Field(default_factory=list)
    teacher_annotations: list[TeacherAnnotation] = Field(default_factory=list)
    question_figures: list[QuestionFigureRegion] = Field(default_factory=list)
    student_working_figures: list[StudentWorkingFigureRegion] = Field(default_factory=list)
    teacher_annotation_regions: list[TeacherAnnotationRegion] = Field(default_factory=list)
    printed_irrelevant: list[str] = Field(default_factory=list)
    has_answer: bool
    has_working: bool
    has_teacher_annotation: bool
    recognition_confidence: float = Field(ge=0, le=1)
    uncertain_fields: list[str] = Field(default_factory=list)

    @field_validator("subject", mode="before")
    @classmethod
    def canonical_subject(cls, value: object) -> str:
        text = str(value).strip()
        aliases = {
            "math": "数学",
            "mathematics": "数学",
            "physics": "物理",
            "chemistry": "化学",
            "biology": "生物",
            "english": "英语",
            "chinese": "语文",
            "history": "历史",
            "geography": "地理",
            "politics": "思想政治",
        }
        return aliases.get(text.casefold(), text)

    @model_validator(mode="after")
    def validate_presence_flags(self) -> "CroppedQuestionRecognition":
        has_answer_value = bool(self.student_answer and self.student_answer.strip())
        if self.has_answer != has_answer_value:
            raise ValueError("has_answer必须与student_answer保持一致")
        if self.has_working != bool(self.student_steps):
            raise ValueError("has_working必须与student_steps保持一致")
        if self.has_teacher_annotation != bool(self.teacher_annotations):
            raise ValueError("has_teacher_annotation必须与teacher_annotations保持一致")
        if [item.index for item in self.student_steps] != list(range(1, len(self.student_steps) + 1)):
            raise ValueError("student_steps.index必须从1开始连续编号")
        return self


class RawCroppedQuestionRecognition(CroppedQuestionRecognition):
    question_figures: list[RawQuestionFigureRegion] = Field(default_factory=list)  # type: ignore[assignment]
    student_working_figures: list[RawStudentWorkingFigureRegion] = Field(default_factory=list)  # type: ignore[assignment]
    teacher_annotation_regions: list[RawTeacherAnnotationRegion] = Field(default_factory=list)  # type: ignore[assignment]


class AnalysisOutput(BaseModel):
    subject: str = "数学"
    problem_type: str = "综合题"
    known_conditions: list[str] = Field(default_factory=list)
    goal: str = ""
    knowledge_points: list[str] = Field(default_factory=list)
    prerequisites: list[str] = Field(default_factory=list)
    reference_steps: list[str] = Field(default_factory=list)
    final_answer: str = ""
    answer_verified: bool = False


class DiagnosisOutput(BaseModel):
    first_error_step: int | None = None
    first_error_text: str = ""
    error_type: str = "unknown"
    root_misconception: str = ""
    propagated_errors: list[str] = Field(default_factory=list)
    strategy_candidates: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0, le=1, allow_inf_nan=False, strict=True)
    error_location: str = ""
    missing_prerequisites: list[str] = Field(default_factory=list)
    recommended_strategy: str = ""


class CounterfactualRepairProposal(BaseModel):
    """A minimal repair proposed by the logical model and verified by local rules."""

    model_config = ConfigDict(extra="forbid")

    corrected_first_step: str = Field(min_length=1, max_length=1000)
    repaired_steps: list[str] = Field(default_factory=list, max_length=30)
    independent_error_steps: list[int] = Field(default_factory=list, max_length=10)
    reasoning: str = Field(default="", max_length=500)
    confidence: float = Field(default=0.5, ge=0, le=1)


class TutorGuidanceOutput(BaseModel):
    reply: str = Field(min_length=1)


class HandwrittenAnswerRecognition(BaseModel):
    """Only transcribe student work that is actually visible in an uploaded image."""

    model_config = ConfigDict(extra="forbid")

    final_answer: str = Field(default="", max_length=500)
    steps: list[str] = Field(default_factory=list, max_length=30)
    transcription: str = Field(default="", max_length=4000)
    confidence: float = Field(default=0.0, ge=0, le=1)
    uncertain: bool = False


class TutorActivityOption(BaseModel):
    value: str
    label: str


class TutorActivityDefinition(BaseModel):
    id: str
    type: Literal["explanation", "single_choice", "multiple_choice", "short_answer", "teach_back", "variant"]
    title: str
    question: str
    options: list[TutorActivityOption] = Field(default_factory=list)
    correct_answers: list[str] = Field(default_factory=list)
    hint: str = ""
    teaching: str = ""
    sentence_starter: str = ""
    keywords: list[str] = Field(default_factory=list)
    visual: dict[str, Any] = Field(default_factory=dict)


class TutorOptionExplanation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = Field(min_length=1, max_length=8)
    text: str = Field(min_length=1, max_length=35)
    correct: bool = False


class AdaptiveTeachingBrief(BaseModel):
    """短流程题目的答案讲解与唯一一次针对性检查。"""

    model_config = ConfigDict(extra="forbid")

    topic: str = Field(min_length=1, max_length=24)
    correct_answer: str = Field(min_length=1, max_length=80)
    key_explanation: str = Field(min_length=1, max_length=120)
    option_explanations: list[TutorOptionExplanation] = Field(default_factory=list, max_length=8)
    check: TutorActivityDefinition


class TutorActivityPlan(BaseModel):
    activities: list[TutorActivityDefinition] = Field(min_length=1, max_length=3)






class VisualizationPayload(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    type: str
    title: str
    teaching_goal: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    interactive_variables: list[dict[str, Any]] = Field(default_factory=list)
    highlights: list[Any] = Field(default_factory=list)
    annotations: list[Any] = Field(default_factory=list)
    student_task: str
    expected_observation: str


class VariantOutput(BaseModel):
    question_text: str
    answer: str
    reference_solution: list[str] = Field(default_factory=list)
    explanation: str = ""
    options: list[RecognitionOption] = Field(default_factory=list)


class AnswerGradeOutput(BaseModel):
    """Qwen 对任意学生作答的结构化判定。"""

    model_config = ConfigDict(extra="forbid")

    correct: bool
    score: int = Field(ge=0, le=100)
    recognized_final_answer: str = Field(default="", max_length=200)
    reason: str = Field(min_length=1, max_length=160)
    matched_key_steps: list[str] = Field(default_factory=list, max_length=6)
    error_points: list[str] = Field(default_factory=list, max_length=4)
    confidence: float = Field(ge=0, le=1)
