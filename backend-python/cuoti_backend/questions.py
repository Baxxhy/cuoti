import hashlib
import json
from pathlib import Path

from . import reference_input
from .account_schemas import text_field
from .accounts import current_user
from .protocol import ApiError
from .question_data import execute, insert, invalidate, owned, rows, select_rows, update
from .question_validation import (
    array,
    edits,
    inferred_choice,
    number,
    step_object,
    step_text,
    text_value,
)

TAXONOMY = json.loads(
    (Path(__file__).parent / "resources/error_taxonomy.json").read_text()
)
LEARNING_FIELDS = [
    "question_text",
    "student_answer",
    "subject",
    "grade",
    "formulas",
    "options",
    "question_type",
    "knowledge_points",
]


class Questions:
    def __init__(self, database, media, settings):
        self.database = database
        self.media = media
        self.settings = settings
        self.compute = None

    def user(self, request, db):
        return current_user(request, db)

    def detail(self, db, id, owner):
        result = owned(db, id, owner)
        assets = select_rows(
            db,
            "question_assets",
            "SELECT * FROM question_assets WHERE question_id=?",
            [id],
        )
        for asset in assets:
            asset["url"] = self.media.url("/" + asset["path"])
        result.update(
            assets=assets,
            question_figures=[a for a in assets if a["kind"] == "question_figure"],
            student_working_figures=[
                a for a in assets if a["kind"] == "student_working_figure"
            ],
            teacher_annotation_regions=[
                a for a in assets if a["kind"] == "teacher_annotation_region"
            ],
            crop_box=None,
        )
        for asset in assets:
            if asset["kind"] == "crop":
                box = asset["bbox"]
                if (
                    isinstance(box, list)
                    and len(box) == 4
                    and 0 <= box[0] < box[2] <= 1
                    and 0 <= box[1] < box[3] <= 1
                ):
                    result["crop_box"] = [
                        box[0],
                        box[1],
                        box[2] - box[0],
                        box[3] - box[1],
                    ]
                break
        ocr = select_rows(
            db,
            "ocr_runs",
            "SELECT * FROM ocr_runs WHERE question_id=? ORDER BY created_at DESC",
            [id],
        )
        result["ocr_runs"] = ocr
        current_ocr = [
            value for value in ocr if not value["stream"].startswith("previous_")
        ]
        result["ocr"] = next(
            (value for value in current_ocr if value["stream"] == "qwen_crop"),
            current_ocr[0] if current_ocr else None,
        )
        analyses = select_rows(
            db,
            "problem_analyses",
            "SELECT * FROM problem_analyses WHERE question_id=? LIMIT 1",
            [id],
        )
        result["analysis"] = analyses[0] if analyses else None
        result["reference_steps"] = (
            select_rows(
                db,
                "reference_steps",
                "SELECT * FROM reference_steps WHERE analysis_id=? ORDER BY step_index",
                [analyses[0]["id"]],
            )
            if analyses
            else []
        )
        diagnoses = select_rows(
            db,
            "diagnoses",
            "SELECT * FROM diagnoses WHERE question_id=? ORDER BY created_at DESC,id DESC LIMIT 1",
            [id],
        )
        diagnosis = diagnoses[0] if diagnoses else None
        if diagnosis:
            evidence = select_rows(
                db,
                "diagnosis_evidence",
                "SELECT * FROM diagnosis_evidence WHERE diagnosis_id=? ORDER BY COALESCE(CAST(JSON_UNQUOTE(JSON_EXTRACT(metadata_json,'$.index')) AS UNSIGNED),10000),created_at,id",
                [diagnosis["id"]],
            )
            diagnosis["evidence"] = [
                value for value in evidence if value["kind"] == "step_alignment"
            ]
            counter = next(
                (
                    value["metadata_json"]
                    for value in evidence
                    if value["kind"] == "counterfactual_validation"
                ),
                None,
            )
            if isinstance(counter, dict):
                if (
                    counter.get("verification_method")
                    in ["qwen_proposal_sympy_check", "reference_repair_sympy_check"]
                    and not counter.get("validation_scope")
                    and "preserved_prefix" not in counter
                ):
                    counter.update(
                        verification_method="legacy_reference_alignment",
                        legacy_review_required=True,
                    )
                    if counter.get("root_cause_confirmed"):
                        counter.update(
                            root_cause_confirmed=False,
                            status="partial",
                            confidence=0.5,
                            conclusion="这是历史参考过程的修复建议，尚未经过当前规则核验，请结合原题核对。",
                        )
                if (
                    diagnosis.get("user_confirmed")
                    and counter.get("status") != "not_needed"
                    and (
                        "suspected_step" not in counter
                        or counter["suspected_step"]
                        != diagnosis.get("first_error_step")
                    )
                ):
                    counter.update(
                        root_cause_confirmed=False,
                        status="partial",
                        stale_after_correction=True,
                        confidence=0.5,
                        verification_method="previous_diagnosis_evidence",
                        conclusion="你已调整出错步骤，原有修复建议需要重新核对。",
                    )
            diagnosis["counterfactual"] = counter
            for value in evidence:
                if value["kind"] == "eced_assessment":
                    diagnosis["evidence_diagnosis"] = value["metadata_json"]
        result["diagnosis"] = diagnosis
        result["student_steps"] = select_rows(
            db,
            "student_steps",
            "SELECT s.* FROM student_steps s WHERE s.work_id=(SELECT id FROM student_works WHERE question_id=? ORDER BY created_at DESC,id DESC LIMIT 1) ORDER BY s.step_index",
            [id],
        )
        result["teacher_marks"] = select_rows(
            db, "teacher_marks", "SELECT * FROM teacher_marks WHERE question_id=?", [id]
        )
        jobs = select_rows(
            db,
            "processing_jobs",
            "SELECT * FROM processing_jobs WHERE question_id=? AND kind IN ('ingest','crop','ocr','reprocess') AND status IN ('pending','running') ORDER BY created_at DESC LIMIT 1",
            [id],
        )
        result["processing_job"] = jobs[0] if jobs else None
        reference = reference_input.display(result["analysis"])
        if reference is not None:
            result["reference_information"] = reference
        history = select_rows(
            db,
            "agent_runs",
            "SELECT result FROM agent_runs WHERE agent_name='question_revision' AND JSON_UNQUOTE(JSON_EXTRACT(result,'$.question_id'))=? ORDER BY created_at DESC,id DESC",
            [id],
        )
        if history:
            result["reference_history"] = [item["result"] for item in history]
        return result

    def list(self, request):
        query = request.query_params
        with self.database.session() as db, db.begin():
            owner = self.user(request, db).id
            sql = (
                "SELECT q.* FROM questions q WHERE q.user_id=? AND q.status<>'archived'"
            )
            params = [owner]
            for key in ["subject", "grade", "question_type"]:
                if query.get(key):
                    sql += f" AND q.{key}=?"
                    params.append(query[key])
            if query.get("knowledge_point"):
                sql += " AND JSON_CONTAINS(q.knowledge_points,JSON_QUOTE(?))"
                params.append(query["knowledge_point"])
            search = query.get("search", "")
            if search:
                sql += " AND (q.question_text LIKE ? OR q.title LIKE ? OR CAST(q.knowledge_points AS CHAR) LIKE ? OR CAST(q.tags AS CHAR) LIKE ? OR EXISTS (SELECT 1 FROM diagnoses d WHERE d.question_id=q.id AND (d.root_misconception LIKE ? OR d.error_type LIKE ? OR d.first_error_text LIKE ?"
                params.extend(["%" + search + "%"] * 7)
                for code, label in TAXONOMY:
                    if search in label or label in search:
                        sql += " OR d.error_type=?"
                        params.append(code)
                sql += ")))"
            order = {
                "created_at": "q.created_at DESC",
                "updated_at": "q.updated_at DESC",
                "oldest": "q.created_at ASC",
            }
            sql += " ORDER BY " + order.get(
                query.get("sort", "created_at"), "q.created_at DESC"
            )
            result = []
            seen = set()
            for item in select_rows(db, "questions", sql, params):
                content = item.get("question_text") or ""
                key = (
                    "".join(
                        c for c in content if not c.isspace() and c not in "，。？?：:"
                    ).lower()
                    if content.strip()
                    else "pending:" + item["id"]
                )
                if key in seen:
                    continue
                seen.add(key)
                result.append(item)
            # Legacy callers receive the full array. Optional paging preserves that shape.
            if "page" in query or "page_size" in query:
                try:
                    page = int(query.get("page", "1"))
                    size = int(query.get("page_size", "20"))
                    if page < 1 or not 1 <= size <= 200:
                        raise ValueError
                except ValueError:
                    raise ApiError(422, "分页参数不正确") from None
                result = result[(page - 1) * size : page * size]
            self.enrich_list(db, owner, result)
            return result

    def enrich_list(self, db, owner, items):
        if not items:
            return
        ids = [item["id"] for item in items]
        placeholders = ",".join("?" for _ in ids)
        diagnoses = {}
        for row in rows(
            db,
            f"SELECT question_id,root_misconception FROM diagnoses WHERE question_id IN ({placeholders}) ORDER BY created_at DESC",
            ids,
        ):
            diagnoses.setdefault(row["question_id"], row["root_misconception"])
        reviews = {
            row["question_id"]: row["due_at"]
            for row in select_rows(
                db,
                "review_plans",
                f"SELECT question_id,MIN(due_at) AS due_at FROM review_plans WHERE user_id=? AND status='pending' AND question_id IN ({placeholders}) GROUP BY question_id",
                [owner, *ids],
            )
        }
        scores = rows(
            db,
            "SELECT subject,knowledge_point,mastery_score FROM mastery_states WHERE user_id=? ORDER BY updated_at DESC",
            [owner],
        )
        assets = {}
        for row in rows(
            db,
            f"SELECT question_id,path FROM question_assets WHERE question_id IN ({placeholders}) AND kind IN ('crop','original') ORDER BY created_at DESC",
            ids,
        ):
            assets.setdefault(row["question_id"], row["path"])
        jobs = {}
        for row in rows(
            db,
            f"SELECT question_id,id,status FROM processing_jobs WHERE question_id IN ({placeholders}) ORDER BY created_at DESC",
            ids,
        ):
            jobs.setdefault(row["question_id"], row)
        for item in items:
            id = item["id"]
            knowledge = item["knowledge_points"] or ["__none__"]
            score = next(
                (
                    float(row["mastery_score"])
                    for row in scores
                    if row["subject"] == item["subject"]
                    and row["knowledge_point"] in knowledge
                ),
                0.0,
            )
            job = jobs.get(id, {})
            item.update(
                diagnosis_summary=diagnoses.get(id, "等待完成错因诊断"),
                review_due_at=reviews.get(id),
                mastery_score=score,
                mastery_status="基本稳定"
                if score >= 0.75
                else "继续巩固"
                if score >= 0.5
                else "需要巩固",
                thumbnail_url=self.media.url("/" + assets[id])
                if id in assets
                else None,
                latest_job_id=job.get("id"),
                latest_job_status=job.get("status"),
            )

    def work(
        self,
        db,
        id,
        owner,
        answer,
        steps,
        *,
        confirmed=True,
        source="user",
        confidence=1,
    ):
        work = insert(
            db,
            "student_works",
            question_id=id,
            user_id=owner,
            answer=answer or "",
            explanation="",
        )
        for index, value in enumerate(steps):
            item = step_object(value)
            text = step_text(item)
            insert(
                db,
                "student_steps",
                work_id=work,
                step_index=index,
                text=text,
                bbox=[number(v) for v in item.get("bbox", [])],
                raw_text=item.get("raw_text", text),
                normalized_text=" ".join(text.split()),
                formula=text if "=" in text else "",
                confidence=number(item.get("confidence", confidence)),
                source=item.get("source", source),
                user_confirmed=confirmed,
            )

    def manual(self, request, body):
        copied = []
        try:
            with self.database.session() as db, db.begin():
                user = self.user(request, db)
                if user.role != "student":
                    raise ApiError(403, "请使用学生账号记录错题")
                source = self.study_source(db, user.id, body)
                content = text_field(body, "question_text", 12000)
                subject = text_field(body, "subject", 30, default="数学")
                kind = text_field(body, "question_type", 50, default="综合题")
                if kind not in ["综合题", "单选题", "多选题"]:
                    raise ApiError(422, "题目类型不正确")
                grade = text_value(body.get("grade"), 30, nullable=True)
                answer = text_value(body.get("student_answer", ""), 6000).strip()
                options = array(body, "options", 8)
                if (kind == "综合题" and options) or (
                    kind != "综合题" and len(options) < 2
                ):
                    raise ApiError(422, "题目类型和选项数量不匹配")
                cleaned = []
                for value in options:
                    if not isinstance(value, dict):
                        raise ApiError(422, "选项格式不正确")
                    label = text_field(value, "label", 1, trim=False)
                    if label not in "ABCDEFGH" or any(
                        o["label"] == label for o in cleaned
                    ):
                        raise ApiError(422, "选项标记无效或重复")
                    cleaned.append(
                        {"label": label, "text": text_field(value, "text", 12000)}
                    )
                steps = [
                    text_value(value, 12000, minimum=1, trim=True)
                    for value in array(body, "student_steps", 30)
                ]
                if source:
                    previous = rows(
                        db,
                        "SELECT id FROM questions WHERE user_id=? AND status<>'archived' AND JSON_CONTAINS(tags,JSON_QUOTE(?)) LIMIT 1",
                        [user.id, "study-item:" + body["study_item_id"]],
                    )
                    if previous:
                        return {"id": previous[0]["id"], "status": "confirmed"}
                id = insert(
                    db,
                    "questions",
                    user_id=user.id,
                    subject=subject,
                    grade=grade,
                    title=content[:80],
                    question_text=content,
                    student_answer=answer or None,
                    status="confirmed",
                    confirmed=True,
                    favorite=False,
                    tags=["study-item:" + body["study_item_id"]] if source else [],
                    formulas=[],
                    options=cleaned,
                    question_type=kind,
                    knowledge_points=source.get("knowledge_points", [])
                    if source
                    else [],
                )
                self.work(db, id, user.id, answer, steps)
                optional = edits(body)
                extras = {
                    key: optional[key]
                    for key in ["knowledge_points", "formulas", "tags"]
                    if key in optional
                }
                if source:
                    extras.pop("knowledge_points", None)
                    if "tags" in extras:
                        extras["tags"] = list(
                            dict.fromkeys(
                                ["study-item:" + body["study_item_id"], *extras["tags"]]
                            )
                        )
                if extras:
                    update(db, "questions", id, **extras)
                reference = reference_input.changes(db, id, body)
                if reference is not None:
                    question = owned(db, id, user.id)
                    reference_input.save(db, question, reference)
                if source:
                    self.study_figures(db, id, source, copied)
            return {"id": id, "status": "confirmed"}
        except BaseException:
            for path in copied:
                self.media.remove(path)
            raise

    def edit(self, request, id, body, confirm=None):
        validated = edits(body)
        with self.database.session() as db, db.begin():
            owner = self.user(request, db).id
            question = owned(db, id, owner, lock=True)
            if question["status"] == "archived":
                raise ApiError(409, "题目已归档，不能修改")
            reference = reference_input.changes(db, id, body)
            if confirm is None:
                kind = validated.get("question_type", question["question_type"])
                if (
                    kind in ["单选题", "多选题"]
                    and len(validated.get("options", question["options"])) < 2
                ):
                    raise ApiError(422, "选择题至少需要两个不同选项")
                changed = any(question[k] != v for k, v in validated.items())
                content_changed = any(
                    k in LEARNING_FIELDS and question[k] != v
                    for k, v in validated.items()
                )
                if content_changed or reference is not None:
                    invalidate(db, id)
                    validated.setdefault(
                        "status",
                        "confirmed" if question["confirmed"] else "needs_confirmation",
                    )
                if reference is not None:
                    execute(
                        db,
                        "UPDATE processing_jobs SET status='cancelled',error='参考资料已人工更新',updated_at=UTC_TIMESTAMP() WHERE question_id=? AND status IN ('pending','running')",
                        [id],
                    )
                if "status" in body:
                    status = body["status"]
                    if status not in [
                        "confirmed",
                        "needs_confirmation",
                        "ocr_draft",
                        "archived",
                    ]:
                        raise ApiError(422, "题目状态不允许直接修改")
                    if (
                        status == "confirmed"
                        and not validated.get(
                            "question_text", question["question_text"]
                        ).strip()
                    ):
                        raise ApiError(422, "请先补充题目文字再确认")
                    validated["status"] = status
                    if status != "archived":
                        validated["confirmed"] = status == "confirmed"
                    execute(
                        db,
                        "UPDATE processing_jobs SET status='cancelled',error='题目状态已人工更新',updated_at=UTC_TIMESTAMP() WHERE question_id=? AND status IN ('pending','running')",
                        [id],
                    )
                    if status == "archived":
                        execute(
                            db,
                            "UPDATE review_plans SET status='cancelled',updated_at=UTC_TIMESTAMP() WHERE question_id=? AND status='pending'",
                            [id],
                        )
                    changed = True
                if changed or reference is not None:
                    update(db, "questions", id, **validated)
                result = owned(db, id, owner)
                if reference is not None:
                    result["reference_information"] = reference_input.save(
                        db, result, reference
                    )
                return result
            selected = {k: v for k, v in validated.items() if k in LEARNING_FIELDS}
            steps = array(body, "student_steps", 100)
            answer = (selected.get("student_answer") or "").strip()
            kind = selected.get("question_type", question["question_type"])
            if not answer and any(
                name in kind.lower() for name in ["选择", "choice", "multiple"]
            ):
                inferred = inferred_choice(
                    steps, selected.get("options", question["options"])
                )
                if inferred:
                    answer = inferred
                    steps = []
            if "student_answer" in selected:
                selected["student_answer"] = answer or None
            if "grade" in selected:
                selected["grade"] = (selected["grade"] or "").strip() or None
            changed = any(question[k] != v for k, v in selected.items())
            if "student_steps" in body:
                previous = rows(
                    db,
                    "SELECT s.text FROM student_steps s WHERE s.work_id=(SELECT id FROM student_works WHERE question_id=? ORDER BY created_at DESC,id DESC LIMIT 1) ORDER BY step_index",
                    [id],
                )
                changed = changed or [v["text"] for v in previous] != [
                    step_text(v) for v in steps
                ]
                self.work(
                    db,
                    id,
                    owner,
                    selected.get("student_answer", question["student_answer"]),
                    steps,
                )
            if "teacher_marks" in body:
                execute(db, "DELETE FROM teacher_marks WHERE question_id=?", [id])
                for value in array(body, "teacher_marks", 100):
                    item = step_object(value, True)
                    insert(
                        db,
                        "teacher_marks",
                        question_id=id,
                        mark_type=item.get("mark_type", "comment"),
                        comment=item.get("comment", ""),
                        bbox=[number(v) for v in item.get("bbox", [])],
                        confidence=number(item.get("confidence", 1)),
                        source="user",
                    )
            if (
                confirm
                and not selected.get("question_text", question["question_text"]).strip()
            ):
                raise ApiError(422, "请先补充题目文字再确认")
            execute(
                db,
                "UPDATE processing_jobs SET status='cancelled',error='题目已人工核对，旧识别结果未应用',updated_at=UTC_TIMESTAMP() WHERE question_id=? AND kind IN ('ingest','crop','ocr','reprocess') AND status IN ('pending','running')",
                [id],
            )
            if changed or reference is not None:
                invalidate(db, id)
            selected["status"] = "confirmed" if confirm else "ocr_draft"
            if confirm:
                selected["confirmed"] = True
            update(db, "questions", id, **selected)
            if reference is not None:
                reference_input.save(db, owned(db, id, owner), reference)
            return self.detail(db, id, owner)

    def archive(self, request, id):
        with self.database.session() as db, db.begin():
            owner = self.user(request, db).id
            owned(db, id, owner, lock=True)
            update(db, "questions", id, status="archived")
            execute(
                db,
                "UPDATE review_plans SET status='cancelled',updated_at=UTC_TIMESTAMP() WHERE question_id=? AND status='pending'",
                [id],
            )
        return {"deleted": True}

    def study_source(self, db, owner, body):
        session_id = body.get("study_session_id", "")
        item_id = body.get("study_item_id", "")
        if not session_id and not item_id:
            return {}
        if (
            not isinstance(session_id, str)
            or not isinstance(item_id, str)
            or max(len(session_id), len(item_id)) > 36
        ):
            raise ApiError(422, "练习来源格式不正确")
        sessions = rows(
            db,
            "SELECT * FROM study_sessions WHERE id=? AND user_id=? FOR UPDATE",
            [session_id, owner],
        )
        if not sessions:
            raise ApiError(404, "练习记录不存在或无权访问")
        if sessions[0]["status"] != "submitted":
            raise ApiError(409, "请先交卷再加入错题本")
        items = rows(
            db,
            "SELECT * FROM study_session_items WHERE id=? AND session_id=?",
            [item_id, session_id],
        )
        if not items:
            raise ApiError(404, "没有找到这道练习题")
        item = items[0]
        grading = (
            json.loads(item["grading"])
            if isinstance(item["grading"], str)
            else item["grading"]
        )
        if not isinstance(grading, dict) or grading.get("correct") is not False:
            raise ApiError(422, "此题尚未判错")
        source = (
            json.loads(item["snapshot"])
            if isinstance(item["snapshot"], str)
            else item["snapshot"]
        )
        current = select_rows(
            db,
            "dataset_questions",
            "SELECT * FROM dataset_questions WHERE id=?",
            [source["id"]],
        )
        histories = (
            (current[0].get("source_metadata") or {}).get("format_review_history", [])
            if current
            else []
        )
        if (
            source.get("quality_status") == "format_review"
            or (current and current[0]["quality_status"] == "format_review")
            or any(
                v.get("content_hash") == source.get("content_hash") for v in histories
            )
        ):
            raise ApiError(409, "此题已暂停使用")
        options = []
        for i, value in enumerate(source.get("options") or []):
            value = dict(value) if isinstance(value, dict) else {"text": str(value)}
            label = value.get("label") or value.get("key") or chr(65 + i)
            options.append(
                {
                    "label": label,
                    "text": value.get(
                        "text", value.get("content", value.get("value", ""))
                    )
                    or f"见选项{label}配图",
                }
            )
        kind = source.get("question_type", "")
        answer = (
            json.loads(item["student_answer"])
            if isinstance(item["student_answer"], str)
            else item["student_answer"]
        )
        body.update(
            question_text=source.get("question_text"),
            subject=source.get("subject"),
            grade=source.get("grade"),
            options=options,
            question_type="综合题"
            if not options
            else "多选题"
            if "多" in kind
            or kind
            in [
                "multiple_choice",
                "multiple-response",
                "multiple_response",
                "multi_choice",
                "multi-select",
            ]
            else "单选题",
            student_answer="、".join(str(v) for v in answer)
            if isinstance(answer, list)
            else str(answer or ""),
            student_steps=[],
        )
        return source

    def study_figures(self, db, id, source, copied):
        paths = source.get("image_paths") or []
        public = source.get("question_text", "").count("<ImageHere>")
        public += sum(
            str(
                v.get("text", v.get("content", "")) if isinstance(v, dict) else v
            ).count("<ImageHere>")
            for v in source.get("options", [])
        )
        total = (
            public
            + str(source.get("answer", "")).count("<ImageHere>")
            + str(source.get("solution", "")).count("<ImageHere>")
        )
        has_visual = (source.get("source_metadata") or {}).get("has_visual", False)
        if total != len(paths) and (total or has_visual):
            raise ApiError(409, "此题已暂停使用")
        if total == 0 and not has_visual:
            public = len(paths)
        from .media import MediaStore

        bank = MediaStore(self.settings.question_bank_root, self.media.secret)
        for index in range(min(public, len(paths))):
            path = Path(paths[index])
            absolute = (
                path if path.is_absolute() else Path(self.settings.project_root) / path
            )
            try:
                relative = absolute.relative_to(
                    Path(self.settings.question_bank_root)
                ).as_posix()
            except ValueError:
                raise ApiError(422, "题库配图路径无效") from None
            data = bank.read(relative)
            import io

            from PIL import Image

            with Image.open(io.BytesIO(data)) as image:
                suffix = {"PNG": "png", "JPEG": "jpg", "WEBP": "webp"}.get(
                    image.format, "bin"
                )
            stored = f"uploads/{id}/bank-{index}.{suffix}"
            self.media.write(stored, data)
            copied.append(stored)
            insert(
                db,
                "question_assets",
                question_id=id,
                kind="question_figure",
                path=stored,
                sha256=hashlib.sha256(data).hexdigest(),
                bbox=[],
                description="题库配图",
            )
