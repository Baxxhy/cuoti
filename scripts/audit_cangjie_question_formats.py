"""Audit public questions and optionally quarantine malformed content via Cangjie."""

import argparse
import json
from pathlib import Path

from prepare_cangjie_question_bank import native
from question_format_audit import audit_formats, format_reviews


def export_all():
    rows = []
    after = ""
    while batch := native({"operation": "audit-export", "after": after}):
        rows.extend(batch)
        after = batch[-1]["id"]
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = export_all()
    report = audit_formats(rows)
    reviews = format_reviews(report)
    changed = 0
    if args.apply:
        for start in range(0, len(reviews), 100):
            result = native(
                {"operation": "review-format", "questions": reviews[start : start + 100]}
            )
            changed += result["changed"]
        # Re-read the authoritative flags; Python never writes MySQL.
        rows = export_all()
    eligible = [r for r in rows if r["usable_for_practice"] and r["usable_for_auto_grade"]]
    served = audit_formats(eligible)
    report.update(
        quarantined_questions=len(reviews),
        changed=changed,
        eligible_questions=len(eligible),
        eligible_unresolved_fields=len(served["findings"]),
        applied=args.apply,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k != "findings"}))
    return 1 if served["findings"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
