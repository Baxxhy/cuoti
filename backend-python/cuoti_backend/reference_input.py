"""User-entered reference material in existing analysis tables; no AI generation."""

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .protocol import ApiError
from .question_data import insert, select_rows


class ReferenceInput(BaseModel):
    model_config = ConfigDict(strict=True)
    correct_answer: str | None = Field(default=None, max_length=12000)
    explanation: str | None = Field(default=None, max_length=12000)
    source_info: str | None = Field(default=None, max_length=2000)


def changes(db, id, body):
    supplied = {key: body[key] for key in ReferenceInput.model_fields if key in body}
    if not supplied:
        return None
    try:
        value = ReferenceInput.model_validate(supplied).model_dump(exclude_unset=True)
    except ValidationError:
        raise ApiError(422, "参考答案、解析或来源格式不正确") from None
    analyses = select_rows(
        db,
        "problem_analyses",
        "SELECT * FROM problem_analyses WHERE question_id=?",
        [id],
    )
    current = {"correct_answer": "", "explanation": "", "source_info": ""}
    if analyses:
        analysis = analyses[0]
        steps = select_rows(
            db,
            "reference_steps",
            "SELECT * FROM reference_steps WHERE analysis_id=? ORDER BY step_index",
            [analysis["id"]],
        )
        raw = analysis["raw_result"] if isinstance(analysis["raw_result"], dict) else {}
        current.update(
            correct_answer=analysis["final_answer"],
            explanation=raw.get(
                "manual_explanation", "\n".join(step["text"] for step in steps)
            ),
            source_info=raw.get("source_info", ""),
        )
    changed = {key: item or "" for key, item in value.items()}
    if all(current[key] == item for key, item in changed.items()):
        return None
    return {**current, **changed}


def save(db, question, value):
    from learning_core.schemas import AnalysisOutput

    payload = AnalysisOutput(
        subject=question["subject"],
        problem_type=question["question_type"],
        knowledge_points=question["knowledge_points"] or [],
        final_answer=value["correct_answer"],
        reference_steps=[value["explanation"]] if value["explanation"] else [],
        answer_verified=False,
    ).model_dump()
    payload.update(
        manual_reference=True,
        manual_explanation=value["explanation"],
        source_info=value["source_info"],
    )
    id = insert(
        db,
        "problem_analyses",
        question_id=question["id"],
        subject=question["subject"],
        problem_type=question["question_type"],
        known_conditions=[],
        goal="",
        knowledge_points=question["knowledge_points"] or [],
        prerequisites=[],
        final_answer=value["correct_answer"],
        verified=False,
        raw_result=payload,
    )
    if value["explanation"]:
        insert(
            db,
            "reference_steps",
            analysis_id=id,
            step_index=0,
            text=value["explanation"],
            expression="",
            explanation="",
            math_valid=False,
            uses_condition=False,
        )
    return display({"final_answer": value["correct_answer"], "raw_result": payload})


def display(analysis):
    if (
        not analysis
        or not isinstance(analysis["raw_result"], dict)
        or not analysis["raw_result"].get("manual_reference")
    ):
        return None
    raw = analysis["raw_result"]
    return {
        "correct_answer": analysis["final_answer"],
        "explanation": raw.get("manual_explanation", ""),
        "source_info": raw.get("source_info", ""),
        "verified": False,
    }
