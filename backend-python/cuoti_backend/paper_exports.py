"""Original PDF/XLSX rendering with checked bytes and owner-only downloads."""

import base64
import hashlib
from uuid import uuid4

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response
from starlette.concurrency import run_in_threadpool

from .papers import owned, question
from .protocol import ApiError, envelope
from .question_data import insert, rows, select_rows
from .question_routes import body
from .retrieval import answer_text

router = APIRouter(prefix="/api/v1/papers")


def questions(service, db, paper, include_images):
    result = []
    for item in select_rows(
        db,
        "paper_items",
        "SELECT * FROM paper_items WHERE paper_id=? ORDER BY position,id",
        [paper["id"]],
    ):
        q = question(db, item["question_id"], paper["user_id"])
        analyses = select_rows(
            db,
            "problem_analyses",
            "SELECT * FROM problem_analyses WHERE question_id=? ORDER BY created_at DESC,id DESC LIMIT 1",
            [q["id"]],
        )
        diagnoses = select_rows(
            db,
            "diagnoses",
            "SELECT * FROM diagnoses WHERE question_id=? ORDER BY created_at DESC,id DESC LIMIT 1",
            [q["id"]],
        )
        references = (
            rows(
                db,
                "SELECT text FROM reference_steps WHERE analysis_id=? ORDER BY step_index",
                [analyses[0]["id"]],
            )
            if analyses
            else []
        )
        images = []
        if include_images:
            for figure in rows(
                db,
                "SELECT path FROM question_assets WHERE question_id=? AND kind='question_figure' ORDER BY created_at,id",
                [q["id"]],
            ):
                try:
                    images.append(
                        base64.b64encode(service.media.read(figure["path"])).decode(
                            "ascii"
                        )
                    )
                except ApiError as error:
                    if error.status != 404:
                        raise
        result.append(
            {
                "question_text": q["question_text"],
                "answer": analyses[0]["final_answer"] if analyses else "",
                "explanation": "\n".join(row["text"] for row in references),
                "subject": q["subject"],
                "score": item["score"],
                "formula": "；".join(
                    answer_text(value) for value in q.get("formulas") or []
                ),
                "options": q["options"],
                "misconception": diagnoses[0]["root_misconception"]
                if diagnoses
                else "",
                "figure_images": images,
            }
        )
    return result


@router.post("/{id}/export")
async def export_route(request: Request, id: str):
    return envelope(
        request,
        await run_in_threadpool(export, request, id, await body(request, empty=True)),
    )


def export(request, id, value):
    kind = value.get("kind", "question")
    if kind not in ["question", "answer", "excel"]:
        raise ApiError(422, "不支持的导出格式")
    service = request.app.state.questions
    written = ""
    try:
        with service.database.session() as db, db.begin():
            owner = service.user(request, db).id
            paper = owned(db, id, owner)
            content = questions(service, db, paper, kind != "excel")
            if kind == "answer":
                for index, item in enumerate(content, 1):
                    if not item["answer"].strip() or not item["explanation"].strip():
                        raise ApiError(
                            409,
                            f"第{index}题缺少答案或解析，请先补齐分析后再导出答案 PDF",
                        )
            if service.compute is None:
                raise ApiError(503, "内部算法服务未配置")
            rendered = service.compute.compute(
                "render_paper",
                paper_title=paper["title"],
                paper_kind=kind,
                paper_questions=content,
            )
            try:
                data = base64.b64decode(rendered["file_base64"], validate=True)
                if (
                    not data
                    or len(data) > 64 * 1024 * 1024
                    or hashlib.sha256(data).hexdigest() != rendered["sha256"]
                ):
                    raise ValueError("invalid export")
            except (ValueError, KeyError, TypeError):
                raise ApiError(503, "导出文件校验失败") from None
            job_id = str(uuid4())
            path = f"reports/{id}-{kind}-{job_id}." + (
                "xlsx" if kind == "excel" else "pdf"
            )
            service.media.write(path, data)
            written = path
            insert(
                db,
                "export_jobs",
                timestamp_microseconds=False,
                id=job_id,
                paper_id=id,
                kind=kind,
                status="completed",
                path=path,
            )
            result = select_rows(
                db, "export_jobs", "SELECT * FROM export_jobs WHERE id=?", [job_id]
            )[0]
            result["url"] = service.media.url("/" + path)
        return result
    except BaseException:
        if written:
            service.media.remove(written)
        raise


@router.get("/{id}/download")
def download(request: Request, id: str):
    try:
        service = request.app.state.questions
        kind = request.query_params.get("kind", "") or "question"
        with service.database.session() as db:
            owner = service.user(request, db).id
            owned(db, id, owner)
            jobs = rows(
                db,
                "SELECT * FROM export_jobs WHERE paper_id=? AND kind=? ORDER BY created_at DESC,id DESC LIMIT 1",
                [id, kind],
            )
            if not jobs:
                raise ApiError(404, "请先生成导出文件")
            data = service.media.read(jobs[0]["path"])
        suffix = "xlsx" if kind == "excel" else "pdf"
        mime = (
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            if kind == "excel"
            else "application/pdf"
        )
        return Response(
            data,
            media_type=mime,
            headers={
                "Content-Disposition": f'attachment; filename="{id}-{kind}.{suffix}"',
                "Content-Length": str(len(data)),
            },
        )
    except ApiError as error:
        return JSONResponse({"detail": error.message}, status_code=error.status)
    except Exception:  # noqa: BLE001 -- Preserve download errors without exposing storage paths.
        return JSONResponse({"detail": "导出文件暂时不可用"}, status_code=500)
