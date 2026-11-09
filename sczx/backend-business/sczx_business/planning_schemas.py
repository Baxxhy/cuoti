"""Structured teaching plans; no model-selected executable tools."""
from typing import Literal,Annotated
from pydantic import BaseModel,ConfigDict,Field,StringConstraints
from .ai_schemas import MathClaim
Text=Annotated[str,StringConstraints(strict=True,strip_whitespace=True,min_length=1)]
class StrictModel(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
class PlanningInput(StrictModel):
    lessonId: Text=Field(max_length=80)
    task: Text=Field(max_length=3000)
    taskType: Literal['auto','activity','misconception','foundation']='auto'
    constraints: str=Field(default='',max_length=1500)
    parentJobId: str|None=None
    regenerateBlockId: str|None=None
class PlanBlock(StrictModel):
    id: Text=Field(max_length=80)
    title: Text=Field(max_length=200)
    content: Text=Field(max_length=6000)
    evidenceIds: list[Text]=Field(min_length=1,max_length=6)
class GeneratedPlan(StrictModel):
    title: Text=Field(max_length=200)
    goal: Text=Field(max_length=2000)
    rationale: list[Text]=Field(min_length=1,max_length=6)
    blocks: list[PlanBlock]=Field(min_length=1,max_length=12)
    mathClaims: list[MathClaim]=Field(default_factory=list,max_length=12)
class AgentConfirmation(StrictModel):
    expectedDraftHash: Text=Field(max_length=64)
    confirmed: Literal[True]
