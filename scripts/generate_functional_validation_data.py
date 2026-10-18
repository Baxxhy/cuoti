#!/usr/bin/env python3
from __future__ import annotations

import json
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "data/functional_validation"
FONT = ROOT / "frontend/src/assets/fonts/NotoSansSC.ttf"

QUESTIONS = [
    ("数学", "解方程：2x + 3 = 11", ["2x+3=11"], "x=7", ["2x=11+3", "x=7"], "移项要变号"),
    ("数学", "化简：3(x-2)-2(x+1)", ["3(x-2)-2(x+1)"], "x-4", ["3x-6-2x+2", "x-4"], "负号未分配"),
    ("数学", "已知直角边3和4，求斜边", ["a²+b²=c²"], "7", ["c=3+4", "c=7"], "勾股不是边长相加"),
    ("数学", "函数 y=2x-1，当x=3时求y", ["y=2x-1"], "5", ["y=2×3+1", "y=7"], "常数项符号"),
    ("数学", "抛物线 y=(x-2)²+1 的顶点", ["y=(x-2)²+1"], "(-2,1)", ["h=-2", "顶点(-2,1)"], "平移方向相反"),
    ("数学", "圆半径为3，求周长", ["C=2πr"], "6π", ["C=πr²", "C=9π"], "公式选择错误"),
    ("数学", "求不等式 2x-1>5 的解集", ["2x-1>5"], "x>2", ["2x>4", "x>2"], "计算检查"),
    ("数学", "因式分解：x²-9", ["a²-b²=(a-b)(a+b)"], "(x-3)²", ["x²-9=(x-3)²"], "平方差结构"),
    ("数学", "计算 √16 + √9", ["√16+√9"], "√25=5", ["√16+√9=√25", "=5"], "根式不能直接合并"),
    ("数学", "相似三角形对应边比为2:3，小边4求大边", ["4/x=2/3"], "x=6", ["x=4×2/3", "x=8/3"], "对应关系颠倒"),
    ("数学", "概率：袋中3红2蓝，随机取红球", ["P=3/5"], "2/5", ["P=2/5"], "分子取错"),
    ("数学", "平均数：2、4、9", ["x̄=(2+4+9)/3"], "5", ["x̄=15/3", "=5"], "正确"),
    ("数学", "坐标A(-2,1)、B(4,3)，求中点", ["M=((x₁+x₂)/2,(y₁+y₂)/2)"], "(1,2)", ["M=(2,4)"], "忘记除以2"),
    ("数学", "解方程：x/3=4", ["x/3=4"], "x=1.3", ["x=4/3"], "等式两边同乘3"),
    ("数学", "三角形两边2和3，第三边范围", ["|a-b|<c<a+b"], "c<5", ["c<5"], "遗漏下界"),
    ("数学", "证明平行线内错角相等", ["a∥b⇒内错角相等"], "直接写相等", ["∠1=∠2"], "缺少平行条件"),
    ("物理", "汽车5m/s行驶6s，求路程", ["s=vt"], "30m/s", ["s=5×6", "s=30m/s"], "路程单位错误"),
    ("物理", "质量2kg受力6N，求加速度", ["F=ma"], "12m/s²", ["a=Fm", "a=12"], "公式变形错误"),
    ("物理", "静止木块画受力图", ["ΣF=0"], "只有重力", ["G=mg"], "漏画支持力"),
    ("物理", "10N力推动2m，求功", ["W=Fs"], "5J", ["W=F/s", "W=5J"], "公式选择错误"),
    ("物理", "物体浸入水中，说明浮力变化", ["F浮=ρgV排"], "与深度成正比", ["F浮=ρgh"], "混淆压强与浮力"),
    ("历史", "比较工业革命与法国大革命的时间", [], "法国大革命更早", ["法国大革命先发生"], "时间线顺序错误"),
    ("历史", "分析鸦片战争爆发的直接与根本原因", [], "把直接原因当根本原因", ["直接原因就是根本原因"], "因果层级混淆"),
    ("历史", "评价一项改革的影响", [], "只写积极影响", ["改革完全成功"], "缺少时代条件和双面评价"),
]


def transform(image: Image.Image, index: int, kind: str) -> Image.Image:
    if kind != "degraded":
        return image
    mode = index % 4
    if mode == 0:
        return image.rotate(5, expand=True, fillcolor="white").resize(image.size)
    if mode == 1:
        return ImageEnhance.Contrast(image).enhance(0.42)
    if mode == 2:
        return image.filter(ImageFilter.GaussianBlur(1.7))
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0)); draw = ImageDraw.Draw(overlay)
    draw.polygon([(0, 0), (image.width, 0), (image.width, image.height // 2), (0, image.height)], fill=(20, 20, 20, 95))
    return Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB")


def generate_images() -> list[dict[str, object]]:
    image_dir = TARGET / "images"; image_dir.mkdir(parents=True, exist_ok=True)
    font = ImageFont.truetype(str(FONT), 35); small = ImageFont.truetype(str(FONT), 29)
    manifest = []
    for index, (subject, question, formulas, answer, steps, teacher) in enumerate(QUESTIONS):
        kind = "clear" if index < 8 else "annotated" if index < 16 else "degraded"
        image = Image.new("RGB", (1100, 620), "white"); draw = ImageDraw.Draw(image)
        draw.text((45, 35), f"{subject} · {question}", font=font, fill="#111")
        if formulas:
            draw.text((55, 115), "公式：" + "；".join(formulas), font=small, fill="#222")
        draw.text((65, 225), "学生答案：" + answer, font=small, fill="#173b67")
        for step_index, step in enumerate(steps):
            draw.text((75, 300 + step_index * 62), f"{step_index + 1}. {step}", font=small, fill="#173b67")
        if kind == "annotated" or (kind == "degraded" and index % 2 == 0):
            draw.text((650, 230), "老师：" + teacher, font=small, fill="#cc2020")
            draw.line((610, 285, 1020, 285), fill="#d02020", width=5)
            draw.ellipse((920, 340, 980, 400), outline="#d02020", width=5)
        image = transform(image, index, kind)
        path = image_dir / f"case-{index + 1:02d}.jpg"; image.save(path, quality=92)
        manifest.append({"case_id": f"image-{index + 1:02d}", "image": str(path.relative_to(ROOT)),
                         "question": question, "formulas": formulas, "student_answer": answer,
                         "student_steps": steps, "teacher_comment": teacher, "subject": subject,
                         "interference": kind, "original_synthetic": True})
    return manifest


def diagnosis_cases() -> list[dict[str, object]]:
    patterns = [
        ("移项符号", "数学", ["2x=11-3", "x=4"], ["2x=11+3", "x=7"], 0, "sign_error"),
        ("去括号", "数学", ["3*(x+2)=3x+6"], ["3x+2=3x+6"], 0, "formula_error"),
        ("算术计算", "数学", ["x=11-3", "x=8"], ["x=11-3", "x=9"], 1, "calculation_error"),
        ("公式选择", "数学", ["(3+4)*2"], ["3+4"], 0, "formula_error"),
        ("条件遗漏", "数学", ["三角形任意两边之和大于第三边"], ["两边之和"], 0, "condition_omission"),
        ("不等价变换", "数学", ["2x=8"], ["3x=8"], 0, "invalid_transformation"),
        ("推理跳步", "数学", ["2x=8", "x=4"], ["2x=8"], 1, "missing_step"),
        ("函数图像", "数学", ["顶点=(2,1)"], ["顶点=(-2,1)"], 0, "calculation_error"),
        ("单位", "物理", ["s=30m"], ["s=30m/s"], 0, "unit_error"),
        ("物理概念", "物理", ["支持力与重力平衡"], ["只有重力"], 0, "concept_error"),
        ("历史因果", "历史", ["根本原因是生产方式变化"], ["直接原因就是根本原因"], 0, "causality_confusion"),
        ("历史评价", "历史", ["结合时代评价积极与局限"], ["改革完全成功"], 0, "concept_error"),
    ]
    cases = []
    for repeat in range(2):
        for index, (topic, subject, refs, students, step, error) in enumerate(patterns):
            cases.append({"case_id": f"diagnosis-{repeat * 12 + index + 1:02d}", "coverage": topic,
                          "question": f"{topic}验收题（变体{repeat + 1}）", "subject": subject,
                          "reference_steps": refs, "student_steps": students,
                          "gold_first_error_step": step, "gold_error_type": error,
                          "root_reason": f"{topic}的核心规则未正确使用",
                          "recommended_strategy": f"使用{topic}对比与反例重新讲解"})
    return cases


def main() -> int:
    random.seed(20260807); TARGET.mkdir(parents=True, exist_ok=True)
    images = generate_images(); diagnoses = diagnosis_cases()
    agent = [{"case_id": f"agent-{index + 1:02d}", "name": name, "expected_branch": branch}
             for index, (name, branch) in enumerate([
                 ("完全不会", "completely_unknown"), ("部分正确", "partial_correct"),
                 ("重复相同错误", "repeated_error"), ("出现新错误", "new_error"),
                 ("直接索要答案", "answer_requested"), ("答案正确但解释错误", "correct_but_unclear"),
                 ("教回失败", "teach_back_fail"), ("教回通过", "teach_back_pass"),
                 ("近迁移失败", "near_transfer_fail"), ("近迁移通过", "near_transfer_pass"),
                 ("远迁移失败", "far_transfer_fail"), ("远迁移通过", "far_transfer_pass")])]
    demos = [
        ("一元方程移项符号错误", "数学", "equation_balance"),
        ("二次函数平移方向错误", "数学", "quadratic_function"),
        ("勾股定理误用", "数学", "right_triangle"),
        ("匀加速公式选择错误", "物理", "uniform_acceleration"),
        ("牛顿第二定律概念错误", "物理", "force_diagram"),
        ("历史事件因果混淆", "历史", "history_timeline"),
    ]
    e2e = [{"case_id": f"e2e-{i + 1:02d}", "name": name, "subject": subject,
            "image_case_id": f"image-{[1,5,3,18,19,23][i]:02d}", "visualization": visual,
            "expected_pipeline": ["upload", "opencv", "qwen_vision", "qwen_text", "mysql",
                                  "diagnosis", "tutor", "visualization", "teach_back", "near", "far", "export"]}
           for i, (name, subject, visual) in enumerate(demos)]
    for name, value in (("images.json", images), ("diagnosis_cases.json", diagnoses),
                        ("agent_cases.json", agent), ("e2e_cases.json", e2e)):
        (TARGET / name).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    (TARGET / "README.md").write_text("# MindTrace-Functional-Validation-v1\n\n24张原创合成图片、24个首错点案例、12个Agent分支和6个端到端案例。\n", encoding="utf-8")
    print(json.dumps({"images": len(images), "diagnoses": len(diagnoses), "agent": len(agent), "e2e": len(e2e)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
