from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

CAPABILITIES = ("text", "ocr", "retrieval", "embedding", "rerank", "asr", "tts")
CAPABILITY_LABELS = {"retrieval": "案例检索", "text": "文字指导", "ocr": "题图识别", "embedding": "文本向量", "rerank": "材料重排", "asr": "语音转写", "tts": "讲解音频"}


class StrictResult(BaseModel):
    model_config = ConfigDict(extra="forbid")


ResponseType = Literal['short_answer','single_choice','multiple_choice','true_false','fill_blank','essay','calculation','proof','reading','writing','translation','experiment','programming']
GradingMode = Literal['manual','exact','math']


class ChoiceOption(StrictResult):
    id: str = Field(min_length=1, max_length=40)
    text: str = Field(min_length=1, max_length=2000)


class OCRResult(StrictResult):
    text: str = Field(min_length=1)
    equation: str = ""
    studentAnswer: str = ""
    uncertainties: list[str] = Field(default_factory=list)


class MathClaim(StrictResult):
    left: str
    right: str


class GuidanceResult(StrictResult):
    title: str = Field(min_length=1)
    hint: str = Field(min_length=1)
    steps: list[str] = Field(min_length=1, max_length=12)
    question: str = ""
    mathClaims: list[MathClaim] = Field(default_factory=list, max_length=12)


class RankedCandidate(StrictResult):
    id: str
    score: float = Field(strict=True, ge=0, le=1, allow_inf_nan=False)


class RankingResult(StrictResult):
    ranking: list[RankedCandidate] = Field(min_length=1, max_length=32)


class JobInput(BaseModel):
    capability: Literal["text", "ocr", "retrieval", "embedding", "rerank", "asr", "tts", "lesson_agent"]
    requestKey: str = Field(min_length=8, max_length=80)
    recordId: str | None = None
    fileId: str | None = None
    data: dict = Field(default_factory=dict)


class DocumentOCRResult(StrictResult):
    text: str = Field(min_length=1)
    uncertainties: list[str] = Field(default_factory=list)


class Evidence(StrictResult):
    field: str = Field(default='content', pattern=r'^(content|goal|studentBase|difficulty|diagnosis|strategy|effectCheck|introduction|adjustment|boundary|knowledgePoints\.\d+|steps\.\d+|questions\.\d+|responses\.\d+)$')
    unitId: str
    quote: str = Field(min_length=1)


class ExperienceResult(StrictResult):
    title: str = Field(min_length=1, max_length=240)
    content: str = Field(min_length=1)
    grade: str = ''
    subject: str = ''
    knowledgePoints: list[str] = Field(default_factory=list)
    goal: str = ''
    studentBase: str = ''
    difficulty: str = ''
    diagnosis: str = ''
    strategy: str = ''
    effectCheck: str = ''
    introduction: str = ''
    steps: list[str] = Field(default_factory=list)
    questions: list[str] = Field(default_factory=list)
    responses: list[str] = Field(default_factory=list)
    adjustment: str = ''
    boundary: str = ''
    suggestions: list[str] = Field(default_factory=list)
    references: list[Evidence] = Field(min_length=1)
    mathClaims: list[MathClaim] = Field(default_factory=list, max_length=12)


Scenario = Literal['concept_explanation','misconception_correction','activity_design','questioning','assessment','differentiated_support','other']


class RetrievalFilters(StrictResult):
    grade: str = Field(default='',max_length=40)
    subject: str = Field(default='',max_length=80)
    knowledgeIds: list[str] = Field(default_factory=list,max_length=16)
    scenario: Scenario = 'other'


class RetrievalContext(StrictResult):
    grade: str = Field(default='',max_length=80)
    subject: str = Field(default='',max_length=80)
    knowledgeIds: list[str] = Field(default_factory=list,max_length=16)
    prerequisiteIds: list[str] = Field(default_factory=list,max_length=32)
    goal: str = Field(default='',max_length=2000)
    questionText: str = Field(default='',max_length=3000)
    equation: str = Field(default='',max_length=1000)
    studentObservation: str = Field(default='',max_length=4000)
    recognizedText: str = Field(default='',max_length=12000)


class RetrievalRequest(StrictResult):
    query: str = Field(default='',max_length=2000)
    filters: RetrievalFilters = Field(default_factory=RetrievalFilters)
    context: RetrievalContext = Field(default_factory=RetrievalContext)
    includePrerequisites: bool = True
    rerank: bool = False
    limit: int = Field(default=8,ge=1,le=20,strict=True)
