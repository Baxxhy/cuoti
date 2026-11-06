"""Bayesian knowledge tracing and expected-information-gain batch selection.

Parameters are transparent cold-start defaults, not a fitted student model. Only
confirmed, unaided submitted answers are observations; selection never awards mastery.
"""

import math
from collections import Counter

from pydantic import BaseModel, ConfigDict, Field


class PracticeCandidate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(min_length=1, max_length=36)
    subject: str = Field(min_length=1, max_length=30)
    question_type: str = Field(default="", max_length=100)
    grade_band: str = Field(default="", max_length=30)
    knowledge_points: list[str | dict] = Field(default_factory=list, max_length=100)
    options: list[dict | str] = Field(default_factory=list, max_length=26)


class PracticeObservation(PracticeCandidate):
    correct: bool
    independent: bool = True
    confirmed: bool = True


class AdaptivePracticeInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    candidates: list[PracticeCandidate] = Field(max_length=200)
    observations: list[PracticeObservation] = Field(default_factory=list, max_length=400)
    count: int = Field(ge=1, le=20, strict=True)


def skills(item):
    labels = []
    for value in item.knowledge_points:
        text = str(value.get("code") or value.get("name") or "") if isinstance(value, dict) else value
        if text.strip():
            labels.append(item.subject + ":" + text.strip())
    if labels:
        return list(dict.fromkeys(labels)), "knowledge"
    # Do not invent concept labels when the bank lacks curriculum annotation.
    return [f"{item.subject}:{item.grade_band}:{item.question_type}"], "question_type"


def posterior(prior, correct, guess, weight=1.0):
    known = ((0.9 if correct else 0.1) ** weight)
    unknown = ((guess if correct else 1 - guess) ** weight)
    updated = prior * known / (prior * known + (1 - prior) * unknown)
    return min(1 - 1e-6, max(1e-6, updated))


def entropy(p):
    p = min(1 - 1e-10, max(1e-10, p))
    return -p * math.log2(p) - (1 - p) * math.log2(1 - p)


def information_gain(prior, guess):
    correct_probability = prior * 0.9 + (1 - prior) * guess
    expected = (correct_probability * entropy(posterior(prior, True, guess))
                + (1 - correct_probability) * entropy(posterior(prior, False, guess)))
    return max(0.0, entropy(prior) - expected)


def select_practice(data: AdaptivePracticeInput):
    mastery, exposures, evidence = {}, Counter(), Counter()
    for item in data.observations:
        if not item.confirmed or not item.independent:
            continue
        keys, _ = skills(item)
        guess = 1 / max(2, len(item.options)) if item.options else 0.05
        exposures[item.id] += 1
        for key in keys:
            old = mastery.get(key, 0.35)
            post = posterior(old, item.correct, guess, 1 / len(keys))
            mastery[key] = post + (1 - post) * 0.08 / len(keys)
            evidence[key] += 1
    candidates = {item.id: item for item in data.candidates}
    selected, trace, used_skills = [], [], Counter()
    while candidates and len(selected) < data.count:
        ranked = []
        for item in candidates.values():
            keys, basis = skills(item)
            guess = 1 / max(2, len(item.options)) if item.options else 0.05
            prior = sum(mastery.get(key, 0.35) for key in keys) / len(keys)
            gain = sum(information_gain(mastery.get(key, 0.35), guess) for key in keys) / len(keys)
            diversity = sum(used_skills[key] for key in keys) / len(keys)
            score = gain + 0.3 * (1 - prior) - 0.3 * exposures[item.id] - 0.08 * diversity
            ranked.append((score, item.id, prior, gain, basis, keys))
        ranked.sort(key=lambda x: (-x[0], x[1]))
        _, qid, prior, gain, basis, keys = ranked[0]
        selected.append(qid)
        trace.append({"question_id": qid, "prior": round(prior, 6),
                      "information_gain": round(gain, 6), "basis": basis,
                      "evidence_count": sum(evidence[key] for key in keys)})
        used_skills.update(keys)
        candidates.pop(qid)
    return {"question_ids": selected, "trace": trace,
            "strategy": "bkt_information_gain_v1", "calibration": "cold_start_defaults"}
