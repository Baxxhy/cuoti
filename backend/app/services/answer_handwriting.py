"""Validate original answer images against their owner and learning context."""

import re
from typing import Any
from urllib.parse import urlsplit

from fastapi import HTTPException

from app.config import settings
from app.schemas import HandwrittenAnswerRecognition


def validate_answer_handwriting(
    *,
    user_id: str,
    context_type: str,
    context_id: str,
    image_url: str,
    recognition: Any,
) -> tuple[str, dict[str, Any] | None]:
    image_url = urlsplit(image_url.strip()).path
    if not image_url:
        if recognition:
            raise HTTPException(422, "手写识别结果缺少对应原图")
        return "", None
    prefix = f"/uploads/answers/{user_id}/{context_type}/{context_id}/"
    pattern = rf"{re.escape(prefix)}handwriting-[0-9a-f]{{32}}\.jpg"
    relative_path = image_url.removeprefix("/uploads/")
    if re.fullmatch(pattern, image_url) is None or not (settings.upload_dir / relative_path).is_file():
        raise HTTPException(422, "手写作答图片无效")
    try:
        raw_recognition = (
            recognition.model_dump(mode="json") if hasattr(recognition, "model_dump") else recognition
        )
        parsed = HandwrittenAnswerRecognition.model_validate(raw_recognition or {})
    except ValueError as exc:
        raise HTTPException(422, "手写作答识别结果无效") from exc
    return image_url, parsed.model_dump(mode="json")
