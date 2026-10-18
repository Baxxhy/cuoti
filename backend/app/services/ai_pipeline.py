from __future__ import annotations

import json
from pathlib import Path

from app.providers.api_pool import ApiPoolProvider, ApiPoolUnavailable
from app.schemas import AnalysisOutput, DiagnosisOutput, TutorGuidanceOutput
from app.services.math_tools import solve_text_equation
from app.services.pedagogy import SUBJECT_PEDAGOGY, pedagogy_for


async def analyze_question(
    provider: ApiPoolProvider,
    question_text: str,
    subject: str = "数学",
    grade: str = "初二",
    question_type: str = "综合题",
    visual_paths: list[Path] | None = None,
    student_answer: str | None = None,
    student_steps: list[str] | None = None,
    options: list[dict] | None = None,
) -> AnalysisOutput:
    answer, verified = (
        solve_text_equation(question_text) if subject == "数学" and not options else ("", False)
    )
    context = json.dumps(
        {
            "question_text": question_text,
            "options": options or [],
            "student_answer": student_answer,
            "student_steps": student_steps or [],
        },
        ensure_ascii=False,
    )
    instruction = (
        f"你是{grade}{subject}老师。按{subject}{question_type}的学科规范分析题目，生成简洁、可验证的参考步骤。"
        "必须同时依据所附裁剪题目图片/原题题图与结构化文字；图表、几何关系、函数图像和物理示意不得仅按OCR文字猜测。"
        "不要套用其他学科的公式或术语；开放题的参考答案必须包含评分要点。上下文：" + context
    )
    try:
        paths = [path for path in (visual_paths or []) if path.is_file()]
        result = (
            await provider.generate_multimodal(
                instruction,
                [path.read_bytes() for path in paths],
                AnalysisOutput,
                system="你是中学题目分析器。必须结合图片和文字，只返回合法JSON。/no_think",
            )
            if paths
            else await provider.generate_structured(instruction, AnalysisOutput)
        )
        result.subject = subject
        result.problem_type = question_type or result.problem_type
        result.answer_verified = verified
        if verified:
            result.final_answer = answer
        if not result.final_answer.strip():
            raise ValueError("分析结果缺少标准答案")
        return result
    except (ApiPoolUnavailable, ValueError) as exc:
        if not verified:
            raise ApiPoolUnavailable("题目分析暂时不可用，尚未生成可靠的标准答案，请稍后重试") from exc
        return AnalysisOutput(
            subject=subject,
            problem_type=question_type,
            known_conditions=[question_text],
            goal="解方程",
            knowledge_points=["方程求解"],
            prerequisites=["等式的性质"],
            reference_steps=[f"方程的实数解为：{answer}"],
            final_answer=answer,
            answer_verified=verified,
        )


async def diagnose_steps(
    provider: ApiPoolProvider,
    question_text: str,
    reference: list[str],
    student: list[str],
    subject: str = "数学",
    question_type: str = "综合题",
    visual_paths: list[Path] | None = None,
    student_answer: str | None = None,
    options: list[dict] | None = None,
) -> DiagnosisOutput:
    prompt = json.dumps(
        {
            "question_text": question_text,
            "student_answer": student_answer,
            "options": options or [],
            "reference_steps": reference,
            "student_steps": student,
        },
        ensure_ascii=False,
    )
    mode_hint = (
        "这是选择题，只核对选中、漏选和错选的选项。"
        if "选择" in question_type or "choice" in question_type.lower()
        else "这是填空题，只核对学生答案与标准答案的关键差异。"
        if "填空" in question_type or "fill" in question_type.lower()
        else "这是计算题，重点指出最早出错的计算、公式或变形步骤。"
        if "计算" in question_type or "calculation" in question_type.lower()
        else "这是综合题，重点指出影响最终结论的关键条件或推理步骤。"
    )
    try:
        instruction = (
            f"你是中学{subject}老师。{mode_hint}按{subject}{question_type}的错因体系分析。"
            "必须同时检查所附裁剪题目图片/原题题图、题干、学生答案和学生步骤，尤其不能忽略图形条件。"
            "不要使用其他学科的模板。所有说明直接写给学生看，使用简短、自然的中文，"
            "不要出现‘首错点’‘误差传播’‘认知证据’等产品或工程术语。"
            "root_misconception 只写 1～2 句、总字数不超过 80 字；必须包含本题的具体条件或数字，"
            "不要重复题干，不要写泛泛的学习建议；数学表达式统一用 LaTeX 并用 $...$ 包裹，"
            "例如 $\\frac{4}{6}=\\frac{2}{3}$，不要输出裸的 LaTeX 命令；"
            "recommended_strategy 只写 1 句：告诉学生这一处应如何判断：" + prompt
        )
        instruction += (
            "参考解析与学生步骤不一定同序、同长，不能按行号或措辞差异判错。"
            "first_error_step必须是学生实际步骤从0开始的下标，first_error_text原样引用该步。"
            "先检查学生每一步在题目条件下是否成立，再定位首次实质错误。"
            "答案和路径都正确时error_type填exact，first_error_step填null，root_misconception留空。"
            "缺条件时明确指出条件不足，不补造条件；无法定位时下标填null且error_type填unknown。"
        )
        instruction += "error_type优先从本学科类别中选取：" + json.dumps(
            {"exact": "作答和路径正确", "unknown": "证据不足", **pedagogy_for(subject).error_taxonomy},
            ensure_ascii=False,
        )
        if student_answer and not student:
            instruction += (
                "学生只提交了选择答案，没有提交解题步骤。不要虚构‘第几步’或学生的推理过程；"
                "必须围绕学生实际选出的第一个错误选项说明：该选项内容、题目中的对应条件、二者为何冲突，"
                "并在recommended_strategy中给出判断这个选项的正确方法。"
            )
        paths = [path for path in (visual_paths or []) if path.is_file()]
        result = (
            await provider.generate_multimodal(
                instruction,
                [path.read_bytes() for path in paths],
                DiagnosisOutput,
                system="你是中学生错因分析器。必须结合图片和结构化作答，只返回合法JSON。/no_think",
            )
            if paths
            else await provider.generate_structured(instruction, DiagnosisOutput)
        )
        aliases = {
            "missing_verification": "condition_omission",
            "missing_condition_check": "condition_omission",
            "incomplete_solution": "condition_omission",
            "invalid_assumption": "reasoning_gap",
            "unit_mismatch": "unit_error",
            "conceptual_error": "concept_error",
        }
        result.error_type = aliases.get(result.error_type, result.error_type)
        allowed = {
            "exact",
            "equivalent",
            "branch_solution",
            "necessary_condition",
            "extra_step",
            "unknown",
            "formula_selection",
        }
        allowed.update(code for profile in SUBJECT_PEDAGOGY.values() for code in profile.error_taxonomy)
        if result.error_type not in allowed:
            result.error_type = "unknown"
        if result.error_type in {"exact", "equivalent"}:
            result.root_misconception = ""
            result.missing_prerequisites = []
        index = result.first_error_step
        if (
            not student
            or result.error_type in {"exact", "equivalent"}
            or not isinstance(index, int)
            or isinstance(index, bool)
            or not 0 <= index < len(student)
        ):
            result.first_error_step = None
            result.first_error_text = ""
            result.error_location = ""
        else:
            result.first_error_text = student[index]
            result.error_location = f"学生路径第 {index + 1} 步"
        return result
    except (ApiPoolUnavailable, ValueError) as exc:
        raise ApiPoolUnavailable("错因分析暂时不可用，尚未形成可靠诊断，请稍后重试") from exc


async def generate_tutor_guidance(
    provider: ApiPoolProvider,
    *,
    visual_paths: list[Path],
    question_text: str,
    student_answer: str | None,
    student_steps: list[str],
    subject: str,
    question_type: str,
    draft_reply: str,
    student_message: str = "",
    recent_turns: list[dict[str, str]] | None = None,
) -> str:
    """让教学回复始终能看到题目图、题干、答案和真实步骤。"""
    paths = [path for path in visual_paths if path.is_file()]
    if not paths:
        return draft_reply
    prompt = json.dumps(
        {
            "question_text": question_text,
            "student_answer": student_answer,
            "student_steps": student_steps,
            "student_message": student_message,
            "teaching_strategy_draft": draft_reply,
            "recent_dialogue": (recent_turns or [])[-6:],
            "subject": subject,
            "question_type": question_type,
        },
        ensure_ascii=False,
    )
    try:
        result = await provider.generate_multimodal(
            "结合图片中的原题图和学生作答，把既定教学策略改写成一句到三句循序引导。"
            "不要虚构图中不存在的条件，不要泄露完整答案，不要使用工程术语。"
            "必须承接最近对话推进一个小步骤，禁止重复最近教师已经说过的话。上下文：" + prompt,
            [path.read_bytes() for path in paths],
            TutorGuidanceOutput,
            system="你是中学个性化教师。结合题目视觉信息进行引导，只返回合法JSON。/no_think",
        )
        return result.reply
    except (ApiPoolUnavailable, ValueError):
        return draft_reply
