"""Development-only schema snapshot; the Cangjie runtime does not import Python."""

import json
import sys
from pathlib import Path

from sqlalchemy import JSON, Boolean, DateTime, Float, Integer

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "backend"))
from app.models import Base
from app.services.pedagogy import SUBJECT_PEDAGOGY


def main():
    types = [
        (JSON, "json"),
        (Boolean, "bool"),
        (DateTime, "datetime"),
        (Float, "float"),
        (Integer, "int"),
    ]
    columns = {
        table.name: {
            column.name: next(
                (name for kind, name in types if isinstance(column.type, kind)),
                "string",
            )
            for column in table.columns
        }
        for table in Base.metadata.sorted_tables
    }
    defaults = {}
    for name in (
        "question_assets",
        "ocr_runs",
        "problem_analyses",
        "reference_steps",
        "diagnoses",
        "diagnosis_evidence",
        "teacher_marks",
        "processing_jobs",
        "mastery_states",
        "review_plans",
        "questions",
        "tutor_sessions",
        "tutor_turns",
        "variant_questions",
        "agent_runs",
        "agent_tool_calls",
        "knowledge_points",
        "user_question_knowledge_links",
        "dataset_questions",
        "dataset_sources",
        "dataset_practice_attempts",
        "practice_recommendations",
        "review_records",
        "assignment_attempts",
        "teacher_questions",
        "teacher_audit_logs",
        "teacher_class_students",
        "guardian_student_links",
        "assignment_students",
        "question_assignments",
        "teacher_review_results",
        "teacher_review_tasks",
        "teacher_classes",
        "cognitive_updates",
        "misconception_states",
        "knowledge_relations",
    ):
        row = {}
        for column in Base.metadata.tables[name].columns:
            if column.name in ("id", "created_at", "updated_at"):
                continue
            if column.default is not None:
                value = column.default.arg
                row[column.name] = value(None) if callable(value) else value
            elif column.nullable:
                row[column.name] = None
        defaults[name] = row
    for filename, data in (
        ("schema/column_types.json", columns),
        (
            "schema/school_defaults.json",
            {
                name: defaults[name]
                for name in (
                    "questions",
                    "teacher_questions",
                    "question_assignments",
                    "assignment_students",
                    "assignment_attempts",
                    "teacher_review_tasks",
                    "teacher_review_results",
                )
            },
        ),
        ("tests/detail_defaults.json", defaults),
        (
            "schema/error_taxonomy.json",
            sorted(
                {
                    (code, label)
                    for profile in SUBJECT_PEDAGOGY.values()
                    for code, label in profile.error_taxonomy.items()
                }
            ),
        ),
    ):
        (PROJECT / "backend-cangjie" / filename).write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n"
        )


if __name__ == "__main__":
    main()
