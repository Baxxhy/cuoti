"""Rebuild bounded learner memory from owned, current source records."""

import json
from datetime import datetime

from .learning_evidence import question_version, stamp_compact
from .lessons import digest
from .question_data import rows, select_rows
from .question_validation import short_title


def first(db, table, sql, params):
    values = select_rows(db, table, sql, params)
    return values[0] if values else None


def task_fingerprint(db, id, owner):
    q = first(
        db, "questions", "SELECT * FROM questions WHERE id=? AND user_id=?", [id, owner]
    )
    if not q:
        return ""
    work = first(
        db,
        "student_works",
        "SELECT * FROM student_works WHERE question_id=? ORDER BY created_at DESC,id DESC LIMIT 1",
        [id],
    )
    steps = select_rows(
        db,
        "student_steps",
        "SELECT * FROM student_steps WHERE work_id=(SELECT id FROM student_works WHERE question_id=? ORDER BY created_at DESC,id DESC LIMIT 1) ORDER BY step_index,id",
        [id],
    )
    assets = select_rows(
        db,
        "question_assets",
        "SELECT * FROM question_assets WHERE question_id=? AND kind IN ('crop','question_figure') ORDER BY created_at,id",
        [id],
    )
    analysis = first(
        db,
        "problem_analyses",
        "SELECT * FROM problem_analyses WHERE question_id=?",
        [id],
    )
    refs = select_rows(
        db,
        "reference_steps",
        "SELECT r.* FROM reference_steps r JOIN problem_analyses a ON a.id=r.analysis_id WHERE a.question_id=? ORDER BY r.step_index,r.id",
        [id],
    )
    diagnosis = first(
        db,
        "diagnoses",
        "SELECT * FROM diagnoses WHERE question_id=? ORDER BY created_at DESC,id DESC LIMIT 1",
        [id],
    )
    source = [
        q[key]
        for key in [
            "question_text",
            "subject",
            "grade",
            "question_type",
            "student_answer",
            "options",
            "knowledge_points",
            "confirmed",
            "status",
        ]
    ]
    return digest(
        stamp_compact([*source, work, steps, assets, analysis, refs, diagnosis])
    )


def sorted_json(value):
    return json.dumps(
        json.loads(stamp_compact(value)),
        ensure_ascii=False,
        sort_keys=True,
        allow_nan=False,
    )


def practice_context(db, q, target_id, candidate):
    id = q["id"]
    source = {
        key: q[key]
        for key in [
            "question_text",
            "student_answer",
            "subject",
            "grade",
            "title",
            "formulas",
            "options",
            "question_type",
            "knowledge_points",
        ]
    }
    source["student_work_revisions"] = [
        r["id"]
        for r in rows(
            db, "SELECT id FROM student_works WHERE question_id=? ORDER BY id", [id]
        )
    ]
    analysis = first(
        db,
        "problem_analyses",
        "SELECT * FROM problem_analyses WHERE question_id=? ORDER BY created_at DESC,id DESC LIMIT 1",
        [id],
    )
    diagnosis = first(
        db,
        "diagnoses",
        "SELECT * FROM diagnoses WHERE question_id=? ORDER BY created_at DESC,id DESC LIMIT 1",
        [id],
    )
    version = digest(
        sorted_json(
            {
                "question": digest(sorted_json(source)),
                "analysis": analysis,
                "diagnosis": diagnosis,
            }
        )
    )
    target = first(
        db,
        "knowledge_points",
        "SELECT * FROM knowledge_points WHERE id=? AND subject=?",
        [target_id, q["subject"]],
    )
    return {
        "policy": 1,
        "source": version,
        "candidate": digest(sorted_json(candidate)),
        "target": digest(sorted_json(target)) if target else "",
    }


def update_valid(db, record, owner, subject):
    if record.get("user_id") != owner:
        return False
    evidence = record.get("evidence") or {}
    source = evidence.get("memory_source") or {}
    if source.get("rule_version") != "learning-memory-v1":
        return False
    q = first(
        db,
        "questions",
        "SELECT * FROM questions WHERE id=? AND subject=? AND status<>'archived' AND confirmed=1",
        [record.get("question_id"), subject],
    )
    if (
        not q
        or q["user_id"] != owner
        or source.get("question_version") != question_version(db, q)
    ):
        return False
    strategy = evidence.get("strategy")
    if strategy == "aemt_assistance_aware":
        matches = rows(
            db,
            "SELECT a.result,t.input_fingerprint FROM learning_task_actions a JOIN learning_tasks t ON t.id=a.task_id WHERE t.id=? AND t.user_id=? AND t.question_id=? AND a.request_id=? AND a.status='applied'",
            [
                evidence.get("learning_task_id", ""),
                owner,
                q["id"],
                evidence.get("action_request_id", ""),
            ],
        )
        if not matches or matches[0]["input_fingerprint"] != task_fingerprint(
            db, q["id"], owner
        ):
            return False
        result = (
            json.loads(matches[0]["result"])
            if isinstance(matches[0]["result"], str)
            else matches[0]["result"]
        )
        attempt = result.get("attempt") or {}
        event = evidence.get("aemt_event") or {}
        verdict = attempt.get("verdict")
        return (
            verdict in ["confirmed_correct", "confirmed_incorrect"]
            and event.get("verdict") == verdict
            and (attempt.get("grading") or {}).get("can_update_learning") is True
            and event.get("solution_seen") is not True
            and event.get("scope") in ["original_question", "contrast_question"]
        )
    if strategy == "verified_condition_contrast":
        task = first(
            db,
            "learning_tasks",
            "SELECT * FROM learning_tasks WHERE id=? AND user_id=? AND question_id=? AND status='completed' AND learning_applied=1",
            [evidence.get("learning_task_id", ""), owner, q["id"]],
        )
        return bool(
            task and task["input_fingerprint"] == task_fingerprint(db, q["id"], owner)
        )
    if strategy == "independent_dataset_practice":
        dataset = first(
            db,
            "dataset_questions",
            "SELECT * FROM dataset_questions WHERE id=? AND usable_for_auto_grade=1",
            [evidence.get("dataset_question_id", "")],
        )
        if not dataset or source.get("dataset_version") != digest(
            stamp_compact(dataset)
        ):
            return False
        attempt = first(
            db,
            "dataset_practice_attempts",
            "SELECT * FROM dataset_practice_attempts WHERE id=? AND user_id=? AND mistake_id=? AND dataset_question_id=?",
            [evidence.get("practice_attempt_id", ""), owner, q["id"], dataset["id"]],
        )
        if not attempt:
            return False
        details = attempt["grading_details"] or {}
        proof = details.get("alignment_proof") or {}
        return (
            details.get("can_update_learning") is True
            and proof.get("method") in ["symbolic_linear", "qwen_grounded_concept"]
            and proof.get("context")
            == practice_context(db, q, attempt["knowledge_id"], dataset)
        )
    if strategy in ["micro_activity", "assisted_progression"]:
        return bool(
            rows(
                db,
                "SELECT id FROM tutor_sessions WHERE id=? AND user_id=? AND question_id=? AND status='completed'",
                [evidence.get("tutor_session_id", ""), owner, q["id"]],
            )
        )
    return False


def estimate_current(db, record, kind, owner, subject):
    key, source_key = (
        ("knowledge_point", "mastery_id")
        if kind == "mastery"
        else ("code", "misconception_id")
    )
    update = first(
        db,
        "cognitive_updates",
        f"SELECT u.* FROM cognitive_updates u WHERE u.user_id=? AND u.entity_type=? AND u.entity_key=? AND (JSON_UNQUOTE(JSON_EXTRACT(u.evidence,'$.memory_source.{source_key}'))=? OR JSON_EXTRACT(u.evidence,'$.memory_source') IS NULL) ORDER BY u.created_at DESC,u.id DESC LIMIT 1",
        [owner, kind, record[key], record["id"]],
    )
    return (
        not update
        or not (update.get("evidence") or {}).get("memory_source")
        or update_valid(db, update, owner, subject)
    )


def entry(
    kind,
    record,
    qid,
    classification,
    summary,
    days,
    version,
    refs,
    independence="not_applicable",
    outcome="unknown",
):
    observed = int(datetime.fromisoformat(record["updated_at"]).timestamp())
    return {
        "ref": kind + ":" + record["id"],
        "kind": kind,
        "classification": classification,
        "question_id": qid,
        "source_refs": refs,
        "observed_at": observed,
        "expires_at": observed + days * 86400,
        "summary": short_title(summary, 400),
        "version": digest(stamp_compact([record, version])),
        "independence": independence,
        "outcome": outcome,
    }


def memory(db, owner, q):
    subject, qid = q["subject"], q["id"]
    entries, legacy = (
        [],
        {key: [] for key in ["mastery", "misconceptions", "updates", "reviews"]},
    )
    for table, key, kind in [
        ("mastery_states", "mastery", "mastery"),
        ("misconception_states", "misconceptions", "misconception"),
    ]:
        sql = (
            f"SELECT * FROM {table} WHERE user_id=? AND subject=?"
            + (" AND status='active'" if kind == "misconception" else "")
            + " AND updated_at<=UTC_TIMESTAMP(6) AND updated_at>UTC_TIMESTAMP(6)-INTERVAL 30 DAY ORDER BY updated_at DESC,id DESC LIMIT 12"
        )
        for record in select_rows(db, table, sql, [owner, subject]):
            if len(legacy[key]) >= 3:
                break
            if not estimate_current(db, record, kind, owner, subject):
                continue
            legacy[key].append(record)
            summary = (
                record["knowledge_point"]
                + "：历史掌握估计 "
                + stamp_compact(record["mastery_score"])
                + "，不是掌握证明"
                if kind == "mastery"
                else record["label"] + "：待核对误区候选，不能对学生定性"
            )
            entries.append(
                entry(
                    kind,
                    record,
                    "",
                    "estimate" if kind == "mastery" else "candidate",
                    summary,
                    30,
                    "",
                    [kind + ":" + record["id"]],
                )
            )
    for record in select_rows(
        db,
        "cognitive_updates",
        "SELECT u.* FROM cognitive_updates u JOIN questions q ON q.id=u.question_id WHERE u.user_id=? AND q.subject=? AND u.entity_type='mastery' AND u.updated_at<=UTC_TIMESTAMP(6) AND u.updated_at>UTC_TIMESTAMP(6)-INTERVAL 90 DAY ORDER BY u.updated_at DESC,u.id DESC LIMIT 30",
        [owner, subject],
    ):
        if len(legacy["updates"]) >= 4:
            break
        if not update_valid(db, record, owner, subject):
            continue
        evidence = record["evidence"] or {}
        strategy = evidence.get("strategy", "")
        event = evidence.get("aemt_event") or {}
        correct = (
            evidence.get("near_transfer") is True
            or evidence.get("far_transfer") is True
            or (
                strategy == "aemt_assistance_aware"
                and event.get("verdict") == "confirmed_correct"
            )
        )
        outcome = (
            "correct"
            if correct
            else "incorrect"
            if strategy == "independent_dataset_practice"
            or (
                strategy == "aemt_assistance_aware"
                and event.get("verdict") == "confirmed_incorrect"
            )
            else "unknown"
        )
        independence = (
            "assisted"
            if strategy == "assisted_progression" or evidence.get("hint_level", 0) > 0
            else "independent"
        )
        refs = ["cognitive:" + record["id"], "question:" + record["question_id"]]
        refs += [
            prefix + evidence[key]
            for key, prefix in [
                ("learning_task_id", "task:"),
                ("practice_attempt_id", "practice:"),
                ("tutor_session_id", "tutor:"),
            ]
            if evidence.get(key)
        ]
        scope = (
            "本次原题作答"
            if strategy == "aemt_assistance_aware"
            and event.get("scope") == "original_question"
            else "本次迁移作答"
        )
        outcome_text = (
            (
                scope + "正确"
                if strategy == "aemt_assistance_aware"
                else "本次迁移判定正确"
            )
            if outcome == "correct"
            else (
                scope + "有误"
                if strategy == "aemt_assistance_aware"
                else "本次迁移作答有误"
            )
            if outcome == "incorrect"
            else "结果尚不充分"
        )
        entries.append(
            entry(
                "cognitive",
                record,
                record["question_id"],
                "verified_event",
                record["entity_key"]
                + "：历史学习事件，"
                + outcome_text
                + "；不代表整个知识点掌握",
                90,
                (evidence.get("memory_source") or {}).get("question_version", ""),
                refs,
                independence,
                outcome,
            )
        )
        legacy["updates"].append(record)
    reviewed = 0
    for record in select_rows(
        db,
        "review_records",
        "SELECT r.* FROM review_records r JOIN review_plans p ON p.id=r.plan_id JOIN questions q ON q.id=p.question_id WHERE p.user_id=? AND q.user_id=? AND q.subject=? AND q.status<>'archived' AND q.confirmed=1 AND r.grade<>'pending' AND r.updated_at<=UTC_TIMESTAMP(6) AND r.updated_at>UTC_TIMESTAMP(6)-INTERVAL 90 DAY ORDER BY r.updated_at DESC,r.id DESC LIMIT 20",
        [owner, owner, subject],
    ):
        if reviewed >= 3:
            break
        details = record["grading_details"] or {}
        if details.get("can_update_learning") is not True or details.get(
            "verdict"
        ) not in ["confirmed_correct", "confirmed_incorrect"]:
            continue
        plan = first(
            db,
            "review_plans",
            "SELECT question_id FROM review_plans WHERE id=? AND user_id=?",
            [record["plan_id"], owner],
        )
        source = (
            first(
                db,
                "questions",
                "SELECT * FROM questions WHERE id=? AND subject=? AND status<>'archived' AND confirmed=1",
                [plan["question_id"], subject],
            )
            if plan
            else None
        )
        if not source:
            continue
        version = question_version(db, source)
        if details.get("memory_question_version") != version:
            continue
        outcome = "correct" if record["correct"] else "incorrect"
        entries.append(
            entry(
                "review_record",
                record,
                source["id"],
                "verified_event",
                "本次复习系统判定"
                + (
                    "正确；难度自评不等于掌握"
                    if outcome == "correct"
                    else "有误；不以学生的难度自评改为正确"
                ),
                90,
                version,
                ["review_record:" + record["id"], "review:" + record["plan_id"]],
                "unknown",
                outcome,
            )
        )
        reviewed += 1
    notes = 0
    for record in select_rows(
        db,
        "learning_self_checks",
        "SELECT n.* FROM learning_self_checks n JOIN learning_tasks t ON t.id=n.task_id JOIN questions q ON q.id=n.question_id WHERE n.user_id=? AND q.user_id=? AND q.subject=? AND q.status<>'archived' AND q.confirmed=1 AND n.deleted=0 AND t.status='completed' AND n.updated_at<=UTC_TIMESTAMP(6) AND n.updated_at>UTC_TIMESTAMP(6)-INTERVAL 90 DAY ORDER BY n.updated_at DESC,n.id DESC LIMIT 20",
        [owner, owner, subject],
    ):
        if notes >= 3:
            break
        version = task_fingerprint(db, record["question_id"], owner)
        if version != record["input_fingerprint"]:
            continue
        entries.append(
            entry(
                "self_check",
                record,
                record["question_id"],
                "student_self_report",
                "学生确认的自述（未证明掌握）：" + record["text"],
                90,
                version,
                ["self_check:" + record["id"], "task:" + record["task_id"]],
            )
        )
        notes += 1
    for record in select_rows(
        db,
        "review_plans",
        "SELECT p.* FROM review_plans p JOIN questions q ON q.id=p.question_id WHERE p.user_id=? AND q.user_id=? AND q.id=? AND q.subject=? AND q.status<>'archived' AND q.confirmed=1 AND p.status='pending' AND p.updated_at<=UTC_TIMESTAMP(6) AND p.updated_at>UTC_TIMESTAMP(6)-INTERVAL 90 DAY ORDER BY p.due_at,p.id LIMIT 2",
        [owner, owner, qid, subject],
    ):
        version = question_version(db, q)
        legacy["reviews"].append(record)
        entries.append(
            entry(
                "review",
                record,
                qid,
                "reminder",
                "当前题有待复习安排，到期时间："
                + record["due_at"]
                + "；安排不证明学会",
                90,
                version,
                ["review:" + record["id"], "question:" + qid],
            )
        )
    return {
        "snapshot": {"rule_version": "learning-memory-v1", "entries": entries},
        "legacy_rows": legacy,
    }


def audit_manifest(snapshot):
    return [
        {
            key: entry[key]
            for key in [
                "ref",
                "version",
                "classification",
                "observed_at",
                "expires_at",
                "question_id",
                "source_refs",
            ]
        }
        for entry in snapshot.get("entries", [])
    ]
