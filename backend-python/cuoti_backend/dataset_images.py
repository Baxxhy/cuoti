"""Keep dataset figure indices and separate public figures from answer images."""

import re
from copy import deepcopy
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from .media import MediaStore, file_response
from .protocol import ApiError
from .question_data import select_rows
from .retrieval import answer_text

router = APIRouter(prefix="/api/v1/practice/questions")


def options(question):
    result = []
    for item in question.get("options") or []:
        value = (
            deepcopy(item) if isinstance(item, dict) else {"text": answer_text(item)}
        )
        if "text" not in value:
            value["text"] = value.get("content", value.get("value", ""))
        result.append(value)
    return result


def layout(question):
    count = len(question.get("image_paths") or [])
    stem = (question.get("question_text") or "").count("<ImageHere>")
    option_counts = [
        (item.get("text") if isinstance(item.get("text"), str) else "").count(
            "<ImageHere>"
        )
        for item in options(question)
    ]
    answer = answer_text(question.get("answer")).count("<ImageHere>")
    solution = (question.get("solution") or "").count("<ImageHere>")
    total = stem + sum(option_counts) + answer + solution
    visual = (question.get("source_metadata") or {}).get("has_visual") is True
    output = {"review": total != count and (total > 0 or visual)}
    index = 0

    def indices(amount):
        nonlocal index
        values = list(range(index, min(index + amount, count)))
        index += amount
        return values

    output["stem"] = indices(count if total == 0 and not visual else stem)
    output["options"] = [indices(amount) for amount in option_counts]
    output["answer"] = indices(answer)
    output["solution"] = indices(solution)
    return output


def urls(media, question, indices):
    return [
        media.url(f"/api/v1/practice/questions/{question['id']}/images/{index}")
        for index in indices
    ]


def question_images(media, question):
    positions = layout(question)
    images = [] if positions["review"] else urls(media, question, positions["stem"])
    previews, shown = list(images), options(question)
    for item, indices in zip(shown, positions["options"], strict=True):
        images_for_option = (
            [] if positions["review"] else urls(media, question, indices)
        )
        if images_for_option:
            item["image_urls"] = images_for_option
        previews.extend(images_for_option)
    return {
        "image_urls": images,
        "preview_image_urls": previews,
        "options": shown,
        "image_layout_review": positions["review"],
    }


def solution_images(media, question):
    positions = layout(question)
    return {
        "answer_image_urls": urls(media, question, positions["answer"]),
        "solution_image_urls": urls(media, question, positions["solution"]),
    }


@router.get("/{id}/images/{index}")
@router.head("/{id}/images/{index}")
def serve(request: Request, id: str, index: str):
    try:
        media = request.app.state.media
        if not media.valid(
            request.url.path,
            request.query_params.get("expires"),
            request.query_params.get("signature", ""),
        ):
            raise ApiError(403, "资源链接已失效，请返回页面刷新")
        if not re.fullmatch(r"[+-]?[0-9]+", index):
            raise ApiError(422, "图片序号无效")
        position = int(index)
        with request.app.state.database.session() as db:
            found = select_rows(
                db,
                "dataset_questions",
                "SELECT * FROM dataset_questions WHERE id=?",
                [id],
            )
        paths = found[0].get("image_paths") or [] if found else []
        if position < 0 or position >= len(paths):
            raise ApiError(404, "图片不存在")
        settings = request.app.state.settings
        root = Path(settings.question_bank_root)
        path = Path(paths[position])
        if not path.is_absolute():
            path = Path(settings.project_root) / path
        try:
            # Lexical containment followed by MediaStore's no-symlink open.
            relative = path.relative_to(root).as_posix()
        except ValueError:
            raise ApiError(404, "图片不存在") from None
        bank = MediaStore(root, media.secret)
        return file_response(request, bank, relative)
    except ApiError as error:
        return JSONResponse({"detail": error.message}, status_code=error.status)
    except Exception:  # noqa: BLE001 -- Match the existing media error contract without exposing storage paths.
        return JSONResponse({"detail": "图片暂时不可用"}, status_code=503)


@router.api_route(
    "/{id}/images/{index}",
    methods=["POST", "PUT", "PATCH", "DELETE", "OPTIONS", "TRACE", "CONNECT"],
    include_in_schema=False,
)
def unsupported_method(id: str, index: str):
    return JSONResponse(
        {"detail": "请求方法不支持"}, status_code=405, headers={"Allow": "GET, HEAD"}
    )
