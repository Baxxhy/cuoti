"""Development-only lesson text snapshot and Python parity fixtures; no runtime Python."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.schemas import TutorActivityDefinition
from app.services.pedagogy import SUBJECT_PEDAGOGY
from app.services.question_mapping import QUESTION_TYPE_LABELS
from app.services.tutor_activities import activity_public, build_understanding_plan


def write(path, value):
    if path.endswith("teaching_parity.json"):
        content = (
            "[\n"
            + ",\n".join(json.dumps(item, ensure_ascii=False) for item in value)
            + "\n]"
        )
    else:
        content = json.dumps(value, ensure_ascii=False, indent=2)
    (ROOT / path).write_text(content + "\n")


def main():
    # These are fixed lesson texts/defaults, not executable rules or live model output.
    write(
        "backend-cangjie/schema/teaching_templates.json",
        {
            "guided_prompts": {k: v.guided_prompt for k, v in SUBJECT_PEDAGOGY.items()},
            "question_type_labels": QUESTION_TYPE_LABELS,
            "activity_defaults": TutorActivityDefinition(
                id="", type="single_choice", title="", question=""
            ).model_dump(mode="json"),
            "cube_plan": build_understanding_plan(
                question_text="正方体展开图",
                subject="数学",
                question_type="other",
                knowledge_points=[],
                reference_steps=[],
            ),
        },
    )
    cases = []
    for subject in [*SUBJECT_PEDAGOGY, "未知学科"]:
        for points, references, text, kind in [
            ([], [], "普通题目", "proof"),
            (["　", "有效知识点"], ["\t", "根据条件推导🙂" * 10], "普通题目", "other"),
            (["相对面"], [], "正方体", "calculation"),
            ([], ["正方体展开图"], "普通题目", "other"),
            ([], [], "正方体体积", "custom"),
        ]:
            args = {
                "question_text": text,
                "subject": subject,
                "question_type": kind,
                "knowledge_points": points,
                "reference_steps": references,
            }
            expected = build_understanding_plan(**args)
            cases.append(
                {
                    "input": args,
                    "plan": expected,
                    "public": [
                        activity_public(x, attempt=2, feedback="再试一次")
                        for x in expected
                    ],
                }
            )
    write("backend-cangjie/tests/teaching_parity.json", cases)


if __name__ == "__main__":
    main()
