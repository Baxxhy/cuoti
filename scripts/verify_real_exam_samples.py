#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pyarrow.parquet as pq
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data/real_exam_validation/cache"
GENERATED = ROOT / "data/real_exam_validation/generated"
REPORT = ROOT / "reports/verification/real_exam_validation.json"
FONT = ROOT / "frontend/src/assets/fonts/NotoSansSC.ttf"
BASE = "https://huggingface.co/datasets/ceval/ceval-exam/resolve/main"
GAOKAO_BASE = "https://raw.githubusercontent.com/OpenLMLab/GAOKAO-Bench/main/Data/Subjective_Questions"

CASES = {
    "middle_school_mathematics": ("数学", "初中"), "middle_school_physics": ("物理", "初中"),
    "middle_school_chemistry": ("化学", "初中"), "middle_school_biology": ("生物", "初中"),
    "middle_school_history": ("历史", "初中"), "middle_school_geography": ("地理", "初中"),
    "middle_school_politics": ("道德与法治", "初中"), "high_school_chinese": ("语文", "高中"),
    "high_school_mathematics": ("数学", "高中"), "high_school_physics": ("物理", "高中"),
    "high_school_chemistry": ("化学", "高中"), "high_school_biology": ("生物", "高中"),
    "high_school_history": ("历史", "高中"), "high_school_geography": ("地理", "高中"),
    "high_school_politics": ("思想政治", "高中"),
}

GAOKAO_CASES = {
    "2010-2022_Math_I_Open-ended_Questions.json": ("数学", "解答题"),
    "2010-2022_Math_I_Fill-in-the-Blank.json": ("数学", "填空题"),
    "2010-2022_Physics_Open-ended_Questions.json": ("物理", "解答题"),
    "2010-2022_Chemistry_Open-ended_Questions.json": ("化学", "解答题"),
    "2010-2022_Biology_Open-ended_Questions.json": ("生物", "材料题"),
    "2010-2022_History_Open-ended_Questions.json": ("历史", "材料题"),
    "2010-2022_Geography_Open-ended_Questions.json": ("地理", "材料题"),
    "2010-2022_Political_Science_Open-ended_Questions.json": ("思想政治", "材料题"),
    "2010-2022_Chinese_Language_Famous_Passages_and_Sentences_Dictation.json": ("语文", "默写题"),
    "2012-2022_English_Language_Error_Correction.json": ("英语", "改错题"),
}


def download(config: str) -> Path:
    CACHE.mkdir(parents=True, exist_ok=True)
    target = CACHE / f"{config}.parquet"
    if not target.exists():
        url = f"{BASE}/{config}/val-00000-of-00001.parquet"
        subprocess.run([
            "curl", "-fsSL", "--retry", "5", "--max-time", "120",
            "-A", "MindDimension-local-validation/1.0", url, "-o", str(target),
        ], check=True)
    return target


def curl_download(url: str, target: Path) -> Path:
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([
            "curl", "-fsSL", "--retry", "5", "--max-time", "120",
            "-A", "MindDimension-local-validation/1.0", url, "-o", str(target),
        ], check=True)
    return target


def wrap(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, width: int) -> list[str]:
    lines, current = [], ""
    for char in text.replace("\r", " ").replace("\n", " "):
        candidate = current + char
        if draw.textlength(candidate, font=font) > width and current:
            lines.append(current); current = char
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def render_case(config: str, subject: str, grade: str, row: dict[str, object]) -> Path:
    GENERATED.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (1400, 1050), "#fffdf7")
    draw = ImageDraw.Draw(image)
    title_font = ImageFont.truetype(str(FONT), 34)
    body_font = ImageFont.truetype(str(FONT), 30)
    answer_font = ImageFont.truetype(str(FONT), 35)
    draw.text((70, 55), f"{grade} · {subject} · 公开考试题样本", fill="#1a2c25", font=title_font)
    y = 135
    for line in wrap(draw, str(row["question"]), body_font, 1250):
        draw.text((70, y), line, fill="#17231f", font=body_font); y += 48
    for option in "ABCD":
        value = str(row.get(option, ""))
        if value:
            for line in wrap(draw, f"{option}. {value}", body_font, 1200):
                draw.text((95, y), line, fill="#263a33", font=body_font); y += 44
            y += 8
    has_options = any(str(row.get(option, "")) for option in "ABCD")
    student_answer = next(option for option in "ABCD" if option != str(row["answer"])) if has_options else "先写结论，理由和步骤稍后补充"
    layer = Image.new("RGBA", image.size, (0, 0, 0, 0)); handwriting = ImageDraw.Draw(layer)
    handwriting.text((110, min(850, y + 35)), f"我的答案：{student_answer}，因为……", fill="#275aa8", font=answer_font)
    layer = layer.rotate(-1.2, resample=Image.Resampling.BICUBIC)
    image = Image.alpha_composite(image.convert("RGBA"), layer).convert("RGB")
    red = ImageDraw.Draw(image)
    red_y = min(960, y + 115)
    red.ellipse((95, red_y - 18, 150, red_y + 38), outline="#d83232", width=6)
    teacher_text = f"再检查依据，正确选项是 {row['answer']}" if has_options else "结论不能代替过程，请补充依据和关键步骤"
    red.text((170, red_y - 15), teacher_text, fill="#d83232", font=answer_font)
    target = GENERATED / f"{config}.jpg"
    image.save(target, quality=92)
    return target


def red_pixel_count(path: Path) -> int:
    image = Image.open(path).convert("RGB").resize((300, 300))
    pixels = image.get_flattened_data() if hasattr(image, "get_flattened_data") else image.getdata()
    return sum(1 for r, g, b in pixels if r > 140 and r > g * 1.45 and r > b * 1.35)


def main() -> int:
    if not FONT.exists():
        raise FileNotFoundError(FONT)
    results = []
    for config, (subject, grade) in CASES.items():
        rows = pq.read_table(download(config)).to_pylist()
        if not rows:
            raise AssertionError(f"{config}没有验证题")
        row = rows[0]
        target = render_case(config, subject, grade, row)
        red_pixels = red_pixel_count(target)
        assert red_pixels > 20
        results.append({
            "config": config, "subject": subject, "grade_band": grade, "question_type": "选择题",
            "source": f"{BASE}/{config}/val-00000-of-00001.parquet", "source_id": row["id"],
            "generated_image": str(target.relative_to(ROOT)), "red_annotation_pixels": red_pixels,
            "question_is_public_exam_data": True, "handwriting_is_simulated": True,
        })
    for filename, (subject, question_type) in GAOKAO_CASES.items():
        source = f"{GAOKAO_BASE}/{filename}"
        payload = json.loads(curl_download(source, CACHE / filename).read_text(encoding="utf-8"))
        row = payload["example"][0]
        target = render_case("gaokao_" + filename.removesuffix(".json"), subject, "高中", row)
        red_pixels = red_pixel_count(target)
        assert red_pixels > 20 and row.get("question") and row.get("answer")
        results.append({
            "config": filename, "subject": subject, "grade_band": "高中", "question_type": question_type,
            "source": source, "source_id": row.get("year", 0), "generated_image": str(target.relative_to(ROOT)),
            "red_annotation_pixels": red_pixels, "question_is_public_exam_data": True,
            "handwriting_is_simulated": True,
        })
    upload_images = [path for path in (ROOT / "uploads").rglob("*") if path.suffix.lower() in {".jpg", ".jpeg", ".png"} and path.is_file()]
    red_uploads = 0
    for path in upload_images:
        try:
            red_uploads += int(red_pixel_count(path) > 20)
        except OSError:
            pass
    report = {
        "passed": len(results) == len(CASES) + len(GAOKAO_CASES), "dataset": "C-Eval + GAOKAO-Bench school subsets",
        "licenses": ["C-Eval: CC BY-NC-SA 4.0", "GAOKAO-Bench: Apache-2.0"],
        "source_repositories": ["https://github.com/hkust-nlp/ceval", "https://github.com/OpenLMLab/GAOKAO-Bench"],
        "case_count": len(results), "subjects": sorted({item["subject"] for item in results}),
        "grade_bands": sorted({item["grade_band"] for item in results}), "question_types": sorted({item["question_type"] for item in results}),
        "real_question_simulated_annotation_cases": len(results), "existing_upload_images": len(upload_images),
        "existing_uploads_with_red_pixels": red_uploads,
        "manual_handwriting_confirmation_required": True, "cases": results,
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("passed", "case_count", "subjects", "grade_bands", "existing_upload_images", "existing_uploads_with_red_pixels")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ModuleNotFoundError as exc:
        print(f"需要在可用的conda环境安装pyarrow和Pillow：{exc}", file=sys.stderr)
        raise
