"""Question analysis persistence around the existing database-free compute API."""

import base64

from fastapi import APIRouter, Request
from learning_core.schemas import AnalysisOutput, DiagnosisOutput

from .knowledge_mapping import dialogue_cards, sync_links
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
    detail["diagnostic_cards"] = dialogue_cards(
        db, detail["question_text"], detail["subject"], detail["grade"] or ""
    )
    return detail


def input_for(service, value):
    payload = {
        "text": value["question_text"],
        "subject": value["subject"],
        "grade": value["grade"] or "",
        "question_type": value["question_type"],
        "student_answer": value["student_answer"],
        "options": value["options"],
        "diagnostic_cards": value.get("diagnostic_cards", []),
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


def evidence(db, diagnosis_id, value, result, include_alignment=True):
    refs = {r["id"] for r in value["reference_steps"]}
    steps = {s["id"] for s in value["student_steps"]}
    for entry in result["alignment"] if include_alignment else []:
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
            sync_links(db, before, analysis)
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
        sync_links(db, before, before["analysis"]["raw_result"], diagnosis)
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


@router.patch("/{id}/diagnosis")
async def correct_diagnosis_route(request: Request, id: str):
    from starlette.concurrency import run_in_threadpool

    from .question_routes import body

    value = await body(request, maximum=2 * 1024 * 1024)
    return envelope(
        request, await run_in_threadpool(correct_diagnosis, request, id, value)
    )


def correct_diagnosis(request, id, value):
    import json
    from pathlib import Path

    from .question_validation import array, number, text_value

    codes = json.loads(
        (Path(__file__).parent / "resources/diagnosis_error_codes.json").read_text()
    )
    changes = {}
    for key, item in value.items():
        if key == "first_error_step":
            if item is not None and (
                type(item) is not int or not 0 <= item <= 2147483647
            ):
                raise ApiError(422, "错误步骤序号必须为非负整数或空值")
            changes[key] = item
        elif key in [
            "first_error_text",
            "root_misconception",
            "error_location",
            "recommended_strategy",
        ]:
            changes[key] = text_value(item, 12000)
        elif key == "error_type":
            if text_value(item, 60) not in codes:
                raise ApiError(422, "请选择支持的错误类型")
            changes[key] = item
        elif key == "confidence":
            score = number(item)
            if not 0 <= score <= 1:
                raise ApiError(422, "置信度超出范围")
            changes[key] = score
        elif key == "missing_prerequisites":
            changes[key] = [
                text_value(entry, 12000) for entry in array(value, key, 100)
            ]
    service = request.app.state.questions
    with service.database.session() as db, db.begin():
        owner = service.user(request, db).id
        question = owned(db, id, owner, lock=True)
        if question["status"] == "archived":
            raise ApiError(409, "题目已归档，不能修正诊断")
        records = select_rows(
            db,
            "diagnoses",
            "SELECT * FROM diagnoses WHERE question_id=? ORDER BY created_at DESC,id DESC LIMIT 1 FOR UPDATE",
            [id],
        )
        if not records:
            raise ApiError(404, "诊断不存在")
        if not changes:
            raise ApiError(422, "请提供需要修正的诊断内容")
        if "first_error_step" in changes:
            steps = service.detail(db, id, owner)["student_steps"]
            index = changes["first_error_step"]
            if index is not None and index >= len(steps):
                raise ApiError(422, "错误步骤不在当前作答中，请重新核对")
            changes["first_error_text"] = (
                steps[index]["text"] if index is not None else ""
            )
        if changes.get("error_type", records[0]["error_type"]) in [
            "exact",
            "equivalent",
        ]:
            if changes.get("first_error_step") is not None:
                raise ApiError(422, "未发现错误时不能同时指定出错步骤")
            changes.update(first_error_step=None, first_error_text="")
        update(
            db,
            "diagnoses",
            records[0]["id"],
            user_confirmed=True,
            correction=value,
            **changes,
        )
        return select_rows(
            db, "diagnoses", "SELECT * FROM diagnoses WHERE id=?", [records[0]["id"]]
        )[0]


@router.post("/{id}/diagnosis/counterfactual")
def counterfactual_route(request: Request, id: str):
    service = request.app.state.questions
    with service.database.session() as db, db.begin():
        owner = service.user(request, db).id
        before = snapshot(service, db, id, owner)
        if not before["analysis"] or not before["diagnosis"]:
            raise ApiError(404, "题目诊断不存在")
        cached = before["diagnosis"].get("counterfactual")
        if cached is not None:
            return envelope(request, cached)
    if request.app.state.compute is None:
        raise ApiError(503, "内部算法服务未配置")
    payload = input_for(service, before)
    payload["images_base64"] = []
    result = request.app.state.compute.compute("counterfactual", **payload)
    with service.database.session() as db, db.begin():
        current = snapshot(service, db, id, owner)
        if current != before:
            raise ApiError(409, "题目或诊断已变化，请重新验证")
        evidence(
            db, current["diagnosis"]["id"], current, result, include_alignment=False
        )
        sync_links(db, current, current["analysis"]["raw_result"], current["diagnosis"])
        return envelope(
            request, service.detail(db, id, owner)["diagnosis"]["counterfactual"]
        )
