"""Validated, bounded source memory. Data here never grants learning credit."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class LearningMemoryEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ref: str = Field(min_length=1, max_length=90)
    kind: Literal[
        "mastery", "misconception", "cognitive", "review_record", "self_check", "review"
    ]
    classification: Literal[
        "estimate", "candidate", "verified_event", "student_self_report", "reminder"
    ]
    question_id: str = Field(default="", max_length=36)
    source_refs: list[str] = Field(min_length=1, max_length=6)
    version: str = Field(pattern=r"^[a-f0-9]{64}$")
    observed_at: int = Field(ge=0, strict=True)
    expires_at: int = Field(ge=0, strict=True)
    summary: str = Field(min_length=1, max_length=400)
    independence: Literal["independent", "assisted", "unknown", "not_applicable"] = (
        "not_applicable"
    )
    outcome: Literal["correct", "incorrect", "unknown"] = "unknown"

    @model_validator(mode="after")
    def validate_scope(self):
        classification = {
            "mastery": "estimate",
            "misconception": "candidate",
            "cognitive": "verified_event",
            "review_record": "verified_event",
            "self_check": "student_self_report",
            "review": "reminder",
        }[self.kind]
        if (
            self.classification != classification
            or not self.ref.startswith(self.kind + ":")
            or self.ref not in self.source_refs
        ):
            raise ValueError("memory classification or source does not match")
        maximum_days = 30 if self.kind in {"mastery", "misconception"} else 90
        if not 0 < self.expires_at - self.observed_at <= maximum_days * 86400:
            raise ValueError("memory expiration must follow observation")
        if self.classification != "verified_event" and (
            self.outcome != "unknown" or self.independence != "not_applicable"
        ):
            raise ValueError("estimate or self-report is not verified performance")
        if any(not 1 <= len(ref) <= 90 for ref in self.source_refs):
            raise ValueError("memory source reference length invalid")
        return self


class LearningMemorySnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rule_version: Literal["learning-memory-v1"] = "learning-memory-v1"
    entries: list[LearningMemoryEntry] = Field(default_factory=list, max_length=18)

    @model_validator(mode="after")
    def unique_sources(self):
        if len(set(self.refs)) != len(self.entries):
            raise ValueError("duplicate memory source")
        limits = {
            "mastery": 3,
            "misconception": 3,
            "cognitive": 4,
            "review_record": 3,
            "self_check": 3,
            "review": 2,
        }
        if any(
            sum(entry.kind == kind for entry in self.entries) > limit
            for kind, limit in limits.items()
        ):
            raise ValueError("memory category limit exceeded")
        return self

    @property
    def refs(self):
        return [entry.ref for entry in self.entries]

    @property
    def versions(self):
        return {entry.ref: entry.version for entry in self.entries}

    @property
    def summary(self):
        parts = []
        for entry in self.entries:
            if len("；".join([*parts, entry.summary])) <= 1800:
                parts.append(entry.summary)
        return "；".join(parts) or "暂无有效的长期记录，不推断学生已掌握"
