from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
MAX_UPLOAD_BYTES = 15 * 1024 * 1024
MAX_IMAGE_PIXELS = 25_000_000
# 手机照片保留原件；仅把后续识别副本缩到适合 CPU OCR 的尺寸。
# 与 PP-OCR 检测器的输入上限一致；原图仍完整保留，仅缩小识别副本。
OCR_WORKING_MAX_SIDE = 1536
VISUAL_REGION_KINDS = {
    "question_figures": "question_figure",
    "student_working_figures": "student_working_figure",
    "teacher_annotation_regions": "teacher_annotation_region",
}


def save_original(raw: bytes, target: Path) -> str:
    if not raw:
        raise ValueError("图片为空，请重新选择图片")
    if len(raw) > MAX_UPLOAD_BYTES:
        raise ValueError("图片不能超过 15 MB")
    try:
        with Image.open(__import__("io").BytesIO(raw)) as opened:
            if opened.format not in ALLOWED_FORMATS:
                raise ValueError("仅支持 JPEG、PNG、WEBP 图片")
            if opened.width * opened.height > MAX_IMAGE_PIXELS:
                raise ValueError("图片像素过大，请压缩到 2500 万像素以内")
            image = ImageOps.exif_transpose(opened).convert("RGB")
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ValueError("图片无法读取，请上传有效的 JPEG、PNG 或 WEBP 图片") from exc
    target.parent.mkdir(parents=True, exist_ok=True)
    image.save(target, format="JPEG", quality=94)
    return hashlib.sha256(target.read_bytes()).hexdigest()


def preprocess_image(original: Path, clean: Path, mask_path: Path, overlay: Path) -> dict[str, float]:
    image = cv2.imread(str(original))
    if image is None:
        raise ValueError("图片无法读取")
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    enhanced = cv2.cvtColor(cv2.merge((cv2.createCLAHE(2.0, (8, 8)).apply(l), a, b)), cv2.COLOR_LAB2BGR)
    hsv = cv2.cvtColor(enhanced, cv2.COLOR_BGR2HSV)
    lower1 = cv2.inRange(hsv, np.array([0, 55, 45]), np.array([12, 255, 255]))
    lower2 = cv2.inRange(hsv, np.array([165, 55, 45]), np.array([180, 255, 255]))
    mask = cv2.bitwise_or(lower1, lower2)
    kernel = np.ones((3, 3), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    cleaned = cv2.inpaint(enhanced, mask, 3, cv2.INPAINT_TELEA)
    marked = enhanced.copy()
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(marked, contours, -1, (0, 200, 255), 2)
    for path in (clean, mask_path, overlay):
        path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(clean), cleaned)
    cv2.imwrite(str(mask_path), mask)
    cv2.imwrite(str(overlay), marked)
    ratio = float(np.count_nonzero(mask)) / float(mask.size)
    return {"red_ratio": round(ratio, 4), "width": image.shape[1], "height": image.shape[0]}


def crop_image(original: Path, target: Path, box: list[float]) -> dict[str, int | bool]:
    if len(box) != 4:
        raise ValueError("裁剪框必须包含 x、y、width、height")
    image = Image.open(original).convert("RGB")
    width, height = image.size
    x, y, crop_width, crop_height = (max(0.0, min(1.0, float(value))) for value in box)
    left, top = round(x * width), round(y * height)
    right = max(left + 1, min(width, round((x + crop_width) * width)))
    bottom = max(top + 1, min(height, round((y + crop_height) * height)))
    target.parent.mkdir(parents=True, exist_ok=True)
    cropped = image.crop((left, top, right, bottom))
    source_width, source_height = cropped.size
    resized_for_ocr = max(source_width, source_height) > OCR_WORKING_MAX_SIDE
    if resized_for_ocr:
        scale = OCR_WORKING_MAX_SIDE / max(source_width, source_height)
        cropped = cropped.resize(
            (max(1, round(source_width * scale)), max(1, round(source_height * scale))),
            Image.Resampling.LANCZOS,
        )
    cropped.save(target, "JPEG", quality=94)
    return {
        "left": left,
        "top": top,
        "right": right,
        "bottom": bottom,
        "source_width": source_width,
        "source_height": source_height,
        "width": cropped.width,
        "height": cropped.height,
        "resized_for_ocr": resized_for_ocr,
    }


def crop_normalized_region(source: Path, target: Path, bbox: list[float]) -> dict[str, int]:
    """从已纠正方向的crop图片裁出0~1归一化区域。"""
    if len(bbox) != 4:
        raise ValueError("视觉区域bbox必须包含4个坐标")
    x1, y1, x2, y2 = (float(value) for value in bbox)
    if not (0 <= x1 < x2 <= 1 and 0 <= y1 < y2 <= 1):
        raise ValueError("视觉区域bbox必须是有效的0~1归一化坐标")
    with Image.open(source) as opened:
        image = opened.convert("RGB")
        width, height = image.size
        left = max(0, min(width - 1, round(x1 * width)))
        top = max(0, min(height - 1, round(y1 * height)))
        right = max(left + 1, min(width, round(x2 * width)))
        bottom = max(top + 1, min(height, round(y2 * height)))
        region = image.crop((left, top, right, bottom))
        target.parent.mkdir(parents=True, exist_ok=True)
        region.save(target, "JPEG", quality=94)
    return {
        "left": left,
        "top": top,
        "right": right,
        "bottom": bottom,
        "width": right - left,
        "height": bottom - top,
    }


def red_ink_ratio(source: Path, bbox: list[float]) -> float:
    """计算归一化区域中的真实红色墨迹占比，用于拒绝灰色透印伪批注。"""
    image = cv2.imread(str(source))
    if image is None or len(bbox) != 4:
        return 0.0
    height, width = image.shape[:2]
    x1, y1, x2, y2 = (float(value) for value in bbox)
    left = max(0, min(width - 1, round(x1 * width)))
    top = max(0, min(height - 1, round(y1 * height)))
    right = max(left + 1, min(width, round(x2 * width)))
    bottom = max(top + 1, min(height, round(y2 * height)))
    region = image[top:bottom, left:right]
    if region.size == 0:
        return 0.0
    hsv = cv2.cvtColor(region, cv2.COLOR_BGR2HSV)
    red_low = cv2.inRange(hsv, np.array([0, 55, 35]), np.array([12, 255, 255]))
    red_high = cv2.inRange(hsv, np.array([165, 55, 35]), np.array([180, 255, 255]))
    mask = cv2.bitwise_or(red_low, red_high)
    return float(np.count_nonzero(mask)) / float(mask.size)


def persist_recognition_regions(crop_path: Path, root: Path, recognition: Any) -> list[dict[str, Any]]:
    """把Qwen区分出的原题图、学生草图和教师批注区域分别持久化。"""
    saved: list[dict[str, Any]] = []
    figure_root = root / "figures"
    for field, kind in VISUAL_REGION_KINDS.items():
        regions = getattr(recognition, field, []) or []
        for index, region in enumerate(regions, start=1):
            target = figure_root / f"{kind}_{index}.jpg"
            geometry = crop_normalized_region(crop_path, target, list(region.bbox))
            saved.append(
                {
                    "kind": kind,
                    "role": region.role,
                    "bbox": list(region.bbox),
                    "description": region.description,
                    "path": str(target),
                    "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
                    "geometry": geometry,
                }
            )
    return saved
