"""Question analysis persistence around the existing database-free compute API."""

import base64

from fastapi import APIRouter, Request
from learning_core.schemas import AnalysisOutput, DiagnosisOutput

from .protocol import ApiError, envelope
from .question_data import TYPES, insert, invalidate, owned, select_rows, update

router = APIRouter(prefix="/api/v1/questions")


def snapshot(service, db, id, owner):
    question = owned(db, id, owner, lock=True)
    if question["status"] == "archived":
        raise ApiError(404, "题目不存在或已归档")
    if not question["confirmed"] or not question["question_text"].strip():
        raise ApiError(409, "请先核对并确认题目文字，再开始分析")
    # Detail includes current steps, references and existing evidence. Comparing it
    # also guards concurrent re-analysis and user corrections during computation.
    detail = service.detail(db, id, owner)
    for asset in detail["assets"]:
        asset.pop("url", None)
    return detail


def input_for(service, value):
    payload = {
        "text": value["question_text"],
        "subject": value["subject"],
        "grade": value["grade"] or "",
        "question_type": value["question_type"],
        "student_answer": value["student_answer"],
        "options": value["options"],
        "student_steps": [s["text"] for s in value["student_steps"]],
        "student_records": [
            {"id": s["id"], "text": s["text"]} for s in value["student_steps"]
        ],
        "reference_steps": [
            {"id": s["id"], "text": s["text"]} for s in value["reference_steps"]
        ],
        "images_base64": [
            base64.b64encode(service.media.read(path)).decode()
            for path in dict.fromkeys(
                a["path"]
                for a in value["assets"]
                if a["kind"] in ["crop", "question_figure"]
            )
        ],
    }
    return payload


def evidence(db, diagnosis_id, value, result):
    refs = {r["id"] for r in value["reference_steps"]}
    steps = {s["id"] for s in value["student_steps"]}
    for entry in result["alignment"]:
        if (
            entry.get("reference_step_id") is not None
            and entry["reference_step_id"] not in refs
        ) or (
            entry.get("student_step_id") is not None
            and entry["student_step_id"] not in steps
        ):
            raise ApiError(503, "诊断证据不属于当前作答")
        fields = {
            key: entry.get(key)
            for key in [
                "reference_step_id",
                "student_step_id",
                "alignment",
                "equivalent",
                "uses_condition",
                "is_first_error",
                "propagated",
                "math_valid",
            ]
        }
        insert(
            db,
            "diagnosis_evidence",
            diagnosis_id=diagnosis_id,
            kind="step_alignment",
            content=str(entry.get("student_text", "")),
            metadata_json=entry,
            **fields,
        )
    for kind, item in [
        ("counterfactual_validation", result["counterfactual"]),
        ("eced_assessment", result.get("evidence_diagnosis")),
    ]:
        if item:
            insert(
                db,
                "diagnosis_evidence",
                diagnosis_id=diagnosis_id,
                kind=kind,
                content=item.get("conclusion", item.get("reason", "")),
                metadata_json=item,
                reference_step_id=None,
                student_step_id=None,
                alignment=item.get("status", "evidence_assessment"),
                equivalent=bool(item.get("root_cause_confirmed", False)),
                uses_condition=False,
                is_first_error=False,
                propagated=False,
                math_valid=bool(item.get("root_cause_confirmed", False)),
            )


def run(request, id, operation):
    service = request.app.state.questions
    with service.database.session() as db, db.begin():
        owner = service.user(request, db).id
        before = snapshot(service, db, id, owner)
    if operation == "diagnose" and not before["analysis"]:
        run(request, id, "analyze")
        with service.database.session() as db, db.begin():
            before = snapshot(service, db, id, owner)
    if request.app.state.compute is None:
        raise ApiError(503, "内部算法服务未配置")
    result = request.app.state.compute.compute(operation, **input_for(service, before))
    if operation == "analyze":
        analysis = AnalysisOutput.model_validate(result["analysis"]).model_dump()
        if not analysis["final_answer"].strip() or len(
            result["reference_math_valid"]
        ) != len(analysis["reference_steps"]):
            raise ApiError(503, "分析结果不完整")
    else:
        diagnosis = DiagnosisOutput.model_validate(result["diagnosis"]).model_dump()
    with service.database.session() as db, db.begin():
        if snapshot(service, db, id, owner) != before:
            raise ApiError(409, "题目、作答或分析已变化，请重新诊断")
        if operation == "analyze":
            invalidate(db, id)
            aid = insert(
                db,
                "problem_analyses",
                question_id=id,
                subject=analysis["subject"],
                problem_type=analysis["problem_type"],
                known_conditions=analysis["known_conditions"],
                goal=analysis["goal"],
                knowledge_points=analysis["knowledge_points"],
                prerequisites=analysis["prerequisites"],
                final_answer=analysis["final_answer"],
                verified=analysis["answer_verified"],
                raw_result=analysis,
            )
            for index, content in enumerate(analysis["reference_steps"]):
                insert(
                    db,
                    "reference_steps",
                    analysis_id=aid,
                    step_index=index,
                    text=content,
                    expression=content if "=" in content else None,
                    explanation="由题目条件进行等价变形"
                    if "=" in content
                    else "推理步骤",
                    math_valid=result["reference_math_valid"][index],
                    uses_condition=index == 0,
                )
            update(db, "questions", id, status="analyzed")
            saved = select_rows(
                db,
                "problem_analyses",
                "SELECT * FROM problem_analyses WHERE id=?",
                [aid],
            )[0]
            saved["reference_steps"] = analysis["reference_steps"]
            return saved
        fields = {
            key: diagnosis[key]
            for key in TYPES["diagnoses"]
            if key in diagnosis
            and key not in ["id", "question_id", "created_at", "updated_at"]
        }
        did = insert(
            db,
            "diagnoses",
            question_id=id,
            user_confirmed=False,
            correction={},
            **fields,
        )
        evidence(db, did, before, result)
        update(db, "questions", id, status="diagnosed")
        return service.detail(db, id, owner)["diagnosis"]


@router.post("/{id}/analyze")
def analyze(request: Request, id: str):
    return envelope(request, run(request, id, "analyze"))


@router.post("/{id}/diagnose")
def diagnose(request: Request, id: str):
    return envelope(request, run(request, id, "diagnose"))


@router.get("/{id}/diagnosis")
def get_diagnosis(request: Request, id: str):
    service = request.app.state.questions
    with service.database.session() as db, db.begin():
        owner = service.user(request, db).id
        return envelope(request, service.detail(db, id, owner)["diagnosis"])


@router.get("/{id}/diagnosis/history")
def diagnosis_history(request: Request, id: str):
    service = request.app.state.questions
    with service.database.session() as db, db.begin():
        owner = service.user(request, db).id
        owned(db, id, owner)
        records = select_rows(
            db,
            "diagnoses",
            "SELECT * FROM diagnoses WHERE question_id=? ORDER BY created_at DESC,id DESC",
            [id],
        )
        for record in records:
            record["evidence"] = select_rows(
                db,
                "diagnosis_evidence",
                "SELECT * FROM diagnosis_evidence WHERE diagnosis_id=? ORDER BY created_at,id",
                [record["id"]],
            )
        return envelope(request, records)
