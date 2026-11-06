from __future__ import annotations

from pathlib import Path

from learning_core.providers.api_pool import ApiPoolProvider
from learning_core.schemas import HandwrittenAnswerRecognition

HANDWRITING_SYSTEM_PROMPT = """你是中学生手写作答转写器。
只识别图片中学生实际写出的最终答案、公式和分步过程，不解题、不纠错、不补全缺失步骤。
保留数学含义，公式优先使用 LaTeX。看不清的内容不要猜测，并把 uncertain 设为 true。
输出必须通过给定 JSON Schema 校验，只返回合法 JSON。/no_think"""


async def recognize_handwritten_answer(
    provider: ApiPoolProvider,
    image_path: Path,
    *,
    question_text: str,
    subject: str,
) -> HandwrittenAnswerRecognition:
    if not image_path.is_file():
        raise FileNotFoundError(f"手写作答图片不存在: {image_path}")
    prompt = (
        f"学科：{subject}\n"
        f"当前题目：{question_text}\n"
        "请只转写照片中的学生作答。final_answer 放明确写出的最终结论；"
        "steps 按书写顺序记录过程；transcription 保留完整可见内容。"
    )
    return await provider.generate_multimodal(
        prompt,
        [image_path.read_bytes()],
        HandwrittenAnswerRecognition,
        system=HANDWRITING_SYSTEM_PROMPT,
    )
