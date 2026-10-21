from __future__ import annotations

from pathlib import Path

from pydantic import ValidationError

from learning_core.providers.api_pool import ApiPoolProvider
from learning_core.schemas import CroppedQuestionRecognition, RawCroppedQuestionRecognition
from learning_core.services.vision import red_ink_ratio

CROPPED_RECOGNITION_SYSTEM_PROMPT = """你是学生错题图片结构化识别器。
只能依据当前这一张【裁剪后的题目图片】返回 JSON。

规则：
1. 不补全图片中不存在的内容。
2. 不猜测学生没写出的解题过程。
3. 不把印刷题干当学生答案。
4. 不把教师红笔订正当学生步骤。
5. 不把页码、广告、联系电话、页脚或裁剪区域内偶然出现的其他题目当题目或学生作答；将它们放入 printed_irrelevant。
6. 学生没有过程时 student_steps=[]，has_working=false。
7. 学生没有答案时 student_answer=null，has_answer=false。
8. 无法确定时返回 null/[] 并加入 uncertain_fields，禁止臆测。
9. 保留数学公式语义，公式优先使用 LaTeX。
10. 此阶段只识别和划分内容角色，禁止分析错因、评价正误或生成参考解法。
11. 严禁输出 JSON Schema 以外的字段。
12. 只返回合法 JSON，不返回 Markdown、解释或前后缀文字。
13. 填在横线、括号或答题区域内的学生手写结果属于 student_answer；多个小题答案合并为一个字符串。只要该字符串非空，has_answer 必须为 true；为 null 时必须为 false。
14. 原题印刷内容自带的几何图、函数图、表格、统计图、物理示意图分别放入 question_figures，role只能为 question_figure、table、chart、diagram。
15. 学生自己画的草图、辅助线或受力标记只放入 student_working_figures，role固定为 student_working_figure，禁止放入 question_figures。
16. 教师红笔圈画、勾叉和订正所在区域只放入 teacher_annotation_regions，role固定为 teacher_annotation_region，禁止放入前两类。
17. 三类视觉区域的 bbox 均为相对于当前裁剪图片宽高的 [x1,y1,x2,y2]，坐标必须归一化到0~1且框住对应内容；description只做客观描述，不推断答案。
18. 只有图片中清楚可见的红色教师墨迹才能进入 teacher_annotations 和 teacher_annotation_regions；纸张背面透印、灰色残影、印刷字、题号圈和学生黑蓝笔迹都不是教师批注。
/no_think"""

CROPPED_RECOGNITION_PROMPT = """识别这张已经由学生框选的单题图片。
以框选区域内的主要题目为 question_text，严格区分印刷题干、学生真实书写和教师批注。
识别并分别定位原题自带图、学生草图/辅助线、教师批注区域；不要因为题干文字已经识别就省略原题图。
其他题号、其他题目、页码、出版社、广告和联系电话必须放入 printed_irrelevant，不得混入学生答案或步骤。"""


async def recognize_cropped_question(
    provider: ApiPoolProvider,
    cropped_path: Path,
) -> CroppedQuestionRecognition:
    """只读取持久化裁剪图并由 Qwen 完成一次结构化识别；Schema 失败最多重试一次。"""
    if not cropped_path.is_file():
        raise FileNotFoundError(f"裁剪图片不存在: {cropped_path}")
    image_bytes = cropped_path.read_bytes()
    last_error: ValueError | None = None
    for attempt in range(2):
        prompt = CROPPED_RECOGNITION_PROMPT
        if attempt:
            prompt += "\n上一次输出未通过JSON Schema校验，请逐字段检查类型、布尔标志和步骤序号后重新输出。"
        try:
            raw_result = await provider.generate_multimodal(
                prompt,
                [image_bytes],
                RawCroppedQuestionRecognition,
                system=CROPPED_RECOGNITION_SYSTEM_PROMPT,
            )
            normalized = normalize_visual_bboxes(raw_result)
            return filter_teacher_annotations_by_red_evidence(normalized, cropped_path)
        except (ValidationError, ValueError) as exc:
            last_error = exc
    assert last_error is not None
    raise last_error


def normalize_visual_bboxes(result: RawCroppedQuestionRecognition) -> CroppedQuestionRecognition:
    """把 Qwen 常见的 0~1000 坐标转换为业务层唯一的 0~1 坐标。"""
    payload = result.model_dump(mode="json")
    for field in ("question_figures", "student_working_figures", "teacher_annotation_regions"):
        for region in payload.get(field, []):
            bbox = [float(value) for value in region["bbox"]]
            if max(bbox) > 1:
                if max(bbox) > 1000:
                    raise ValueError("模型返回的视觉区域bbox超出0~1000范围")
                bbox = [value / 1000 for value in bbox]
            region["bbox"] = bbox
    return CroppedQuestionRecognition.model_validate(payload)


def filter_teacher_annotations_by_red_evidence(
    result: CroppedQuestionRecognition,
    cropped_path: Path,
    minimum_ratio: float = 0.002,
) -> CroppedQuestionRecognition:
    """教师批注必须同时满足 Qwen 语义判断和红色像素证据。"""
    payload = result.model_dump(mode="json")
    verified_regions = [
        region
        for region in payload.get("teacher_annotation_regions", [])
        if red_ink_ratio(cropped_path, region["bbox"]) >= minimum_ratio
    ]
    payload["teacher_annotation_regions"] = verified_regions
    if verified_regions:
        payload["teacher_annotations"] = payload.get("teacher_annotations", [])[: len(verified_regions)]
    else:
        payload["teacher_annotations"] = []
        uncertain = list(payload.get("uncertain_fields", []))
        if result.teacher_annotations and "teacher_annotations" not in uncertain:
            uncertain.append("teacher_annotations")
        payload["uncertain_fields"] = uncertain
    payload["has_teacher_annotation"] = bool(payload["teacher_annotations"])
    return CroppedQuestionRecognition.model_validate(payload)
