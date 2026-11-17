"""Learning journey from persisted facts; no grading or mastery computation."""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Request

from .learning_evidence import stamp_compact
from .lessons import digest
from .protocol import ApiError, envelope
from .question_data import rows, select_rows
from .task_records import self_check_public
from .task_sources import fingerprint_fields, load_snapshot, validate_version

router = APIRouter(prefix="/api/v1/questions")


def instant(value):
    value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return (value if value.tzinfo else value.replace(tzinfo=timezone.utc)).astimezone(
        timezone.utc
    )


def stamp(value):
    return instant(value).isoformat()


def event(events, id, time, title, detail):
    events.append({"id": id, "time": stamp(time), "title": title, "detail": detail})


def recent(events):
    return sorted(events, key=lambda value: instant(value["time"]), reverse=True)[:30]


def action(kind, qid, target=""):
    values = {
        "crop": (
            "继续框选题目",
            "/pages/crop/crop?id=" + qid,
            "框选要学习的题目，再开始识别。",
        ),
        "processing": (
            "查看识别进度",
            "/pages/ocr/ocr?id=" + qid + "&job=" + target,
            "识别仍在处理中，完成后核对题干和答案。",
        ),
        "confirm": (
            "核对题目信息",
            "/pages/ocr/ocr?id=" + qid + ("&job=" + target if target else ""),
            "确认题干和自己的作答，避免识别偏差影响诊断。",
        ),
        "diagnose": (
            "开始错因诊断",
            "/pages/diagnosis/diagnosis?id=" + qid,
            "根据确认后的题目与步骤寻找错误原因。",
        ),
        "resume": (
            "继续上次辅导",
            "/pages/tutor/tutor?id=" + target,
            "从已保存的学习阶段继续。",
        ),
        "review": (
            "完成到期复习",
            "/pages/review/review?plan=" + target,
            "先独立回忆，再根据判题结果安排下次复习。",
        ),
        "learn": (
            "查看诊断并学习",
            "/pages/diagnosis/diagnosis?id=" + qid,
            "理解首错原因，再练习验证。",
        ),
        "practice": (
            "练一道相似题",
            "/pages/practice/practice?id=" + qid,
            "用独立作答检验理解。",
        ),
    }
    label, url, reason = values[kind]
    return {"label": label, "url": url, "reason": reason}


def trusted(item):
    details = item.get("grading_details") or {}
    return (
        details.get("can_update_learning") is True
        and details.get("question_changed") is not True
    )


def build(data, now):
    question = data["question"]
    qid = question["id"]
    diagnosis, analysis, job, ocr = (
        data.get(key) or {} for key in ["diagnosis", "analysis", "job", "ocr"]
    )
    events = []
    latest, active_time, active = None, None, ""
    understanding = independent = False
    event(
        events,
        "question:" + qid,
        question["created_at"],
        "记录错题",
        question["subject"] + " · " + question["question_type"],
    )
    if ocr:
        event(
            events,
            "ocr:" + ocr["id"],
            ocr["created_at"],
            "图片识别",
            "识别完成，请以人工核对后的内容为准。",
        )
    if diagnosis:
        event(
            events,
            "diagnosis:" + diagnosis["id"],
            diagnosis["created_at"],
            "错因诊断",
            diagnosis.get("root_misconception") or "可在诊断页查看具体证据。",
        )
    for session in data.get("sessions", []):
        flags = session.get("state") or {}
        time = instant(session["created_at"])
        if flags.get("question_changed") is not True:
            latest = max(latest, time) if latest else time
            if session["status"] == "active" and (
                not active_time or time > active_time
            ):
                active, active_time = session["id"], time
            understanding |= (
                flags.get("understanding_passed") is True
                and flags.get("teach_back_passed") is True
            )
            independent |= (
                flags.get("near_transfer") is True
                and flags.get("far_transfer") is True
                and flags.get("assisted") is not True
                and flags.get("transfer_insufficient") is not True
            )
        detail = (
            "本轮已结束，后续仍需独立练习和复习。"
            if session["status"] == "completed"
            else "学习进度已保存，可继续。"
        )
        if flags.get("question_changed") is True:
            detail = "题目信息已修改，本次记录保留为历史，不计入当前进度。"
        elif (
            flags.get("assisted") is True or flags.get("transfer_insufficient") is True
        ):
            detail = "本轮使用了辅助或迁移尚不稳定，仍需巩固。"
        event(
            events,
            "session:" + session["id"],
            session["updated_at"],
            "辅导记录",
            detail,
        )
    attempts = verified = correct = waiting = 0
    for item in data.get("practices", []):
        attempts += 1
        valid = trusted(item)
        details = item.get("grading_details") or {}
        changed = details.get("question_changed") is True
        if valid:
            verified += 1
            correct += item.get("correct") is True
        if details.get("can_update_learning") is not True and not changed:
            waiting += 1
        detail = (
            ("独立练习作答正确" if item.get("correct") is True else "本次作答仍需巩固")
            if valid
            else "本次结果待核对，未作为掌握证据"
        )
        if changed:
            detail = "题目信息已修改，此次练习作为历史记录保留。"
        event(events, "practice:" + item["id"], item["created_at"], "题库练习", detail)
    completed, review_correct = 0, False
    for item in data.get("reviews", []):
        valid = trusted(item) and item["grade"] != "pending"
        if valid:
            completed += 1
            review_correct |= item.get("correct") is True
        detail = (
            ("复习作答正确" if item.get("correct") is True else "复习仍需巩固")
            if valid
            else "等待完成判定和难度反馈"
        )
        if (item.get("grading_details") or {}).get("question_changed") is True:
            detail = "题目信息已修改，此次复习作为历史记录保留。"
        event(events, "review:" + item["id"], item["created_at"], "复习作答", detail)
    local = instant(now).astimezone(timezone(timedelta(hours=8)))
    end_day = (local + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    due, next_time, next_id = 0, None, ""
    for plan in data.get("plans", []):
        if plan["status"] != "pending":
            continue
        time = instant(plan["due_at"])
        if next_time is None or time < instant(next_time):
            next_time, next_id = plan["due_at"], plan["id"]
        due += time < end_day
    kind, target = "practice", ""
    if question["status"] == "awaiting_crop":
        kind = "crop"
    elif job.get("status") in ["pending", "running"]:
        kind, target = "processing", job["id"]
    elif question.get("confirmed") is not True:
        kind = "confirm"
        if job.get("status") == "failed":
            target = job["id"]
    elif not diagnosis:
        kind = "diagnose"
    elif active:
        kind, target = "resume", active
    elif due > 0:
        kind, target = "review", next_id
    elif latest is None:
        kind = "learn"
    stages = [
        (
            "confirmed",
            "核对题目",
            question.get("confirmed") is True,
            "题干与作答已确认"
            if question.get("confirmed") is True
            else "等待核对识别内容",
        ),
        (
            "diagnosed",
            "找到错因",
            bool(diagnosis),
            "已有诊断证据，可查看和纠正" if diagnosis else "等待完成诊断",
        ),
        (
            "understanding",
            "理解并讲清",
            understanding,
            "理解检查与教回均通过" if understanding else "以实际检查与教回结果为准",
        ),
        (
            "transfer",
            "独立迁移",
            independent,
            "相似题和综合应用均独立通过" if independent else "尚无完整的独立迁移证据",
        ),
        (
            "review",
            "间隔复习",
            review_correct,
            f"完成 {completed} 次有效复习" if completed else "等待复习验证长期保持",
        ),
    ]
    return {
        **{key: question[key] for key in ["title", "question_text", "subject"]},
        "question_id": qid,
        "generated_at": stamp(now),
        "stages": [
            {"key": key, "label": label, "completed": done, "detail": detail}
            for key, label, done, detail in stages
        ],
        "next_action": action(kind, qid, target),
        "summary": "曾有独立迁移证据，继续用复习检验保持。"
        if independent
        else "按记录逐步巩固，完成辅导不等于已经掌握。",
        "verification": {
            "label": "已完成规则校验"
            if analysis.get("verified") is True
            else "尚未通过规则校验",
            "verified": analysis.get("verified") is True,
            "diagnosis_confirmed": diagnosis.get("user_confirmed") is True,
        },
        "practice": {
            "attempts": attempts,
            "verified_attempts": verified,
            "correct": correct,
            "pending": waiting,
        },
        "review": {
            "completed": completed,
            "due": due,
            "next_due_at": stamp(next_time) if next_time else None,
        },
        "events": recent(events),
        "history_limit": 50,
    }


def add_tasks(db, result, owner, qid):
    tasks = select_rows(
        db,
        "learning_tasks",
        "SELECT * FROM learning_tasks WHERE user_id=? AND question_id=? ORDER BY updated_at DESC,id DESC LIMIT 50",
        [owner, qid],
    )
    if not tasks:
        return result
    snapshot = load_snapshot(db, qid, owner)
    items, events = [], list(result["events"])
    active = ""
    repair = original = near = finished = False
    for task in tasks:
        current = validate_version(db, task, snapshot)
        status, flags = task["status"], task.get("checkpoint") or {}
        assistance = flags.get("assistance") or {}
        if current:
            repair |= flags.get("repair_passed") is True
            original |= (
                flags.get("independent_passed") is True
                and assistance.get("independent") is not True
            )
            near |= task.get("learning_applied") is True
            finished |= status == "completed"
            if not active and status in [
                "queued",
                "running",
                "waiting_student",
                "needs_review",
                "failed",
            ]:
                active = task["id"]
        items.append(
            {
                **{
                    key: task[key]
                    for key in ["id", "status", "updated_at", "learning_applied"]
                },
                "source_current": current,
            }
        )
        detail = (
            "原题已更新，本次过程保留为历史。"
            if not current
            else (
                "本次对照已独立完成，仍需间隔复习检验保持。"
                if task.get("learning_applied") is True
                else "本轮学习已结束，未新增独立迁移证据。"
            )
            if status == "completed"
            else "本次已结束，回答与订正记录保留。"
            if status == "cancelled"
            else "已保存当前步骤，可回任务继续查看。"
        )
        event(events, "task:" + task["id"], task["updated_at"], "订正学习", detail)
    result["learning_tasks"] = {
        "items": items,
        "repair_verified": repair,
        "original_independent": original,
        "near_transfer": near,
    }
    url = result["next_action"]["url"]
    question = snapshot["question"]
    if (
        active
        and question.get("confirmed") is True
        and question["status"] != "awaiting_crop"
        and not url.startswith("/pages/ocr/")
    ):
        result["next_action"] = {
            "label": "继续订正学习",
            "url": "/pages/task/task?id=" + active,
            "reason": "从已保存的当前步骤继续，不必重新开始。",
        }
    elif finished and url.startswith("/pages/diagnosis/"):
        result["next_action"] = action("practice", qid)
    if near:
        result["summary"] = "已有本次单条件对照的独立证据，继续用间隔复习检验保持。"
    notes = []
    fingerprint = digest(stamp_compact(fingerprint_fields(snapshot)))
    for note in select_rows(
        db,
        "learning_self_checks",
        "SELECT * FROM learning_self_checks WHERE user_id=? AND question_id=? AND deleted=0 ORDER BY updated_at DESC,id DESC LIMIT 50",
        [owner, qid],
    ):
        task = next((value for value in tasks if value["id"] == note["task_id"]), None)
        if task is None:
            task = select_rows(
                db,
                "learning_tasks",
                "SELECT * FROM learning_tasks WHERE id=? AND user_id=?",
                [note["task_id"], owner],
            )[0]
        current = (
            note["input_fingerprint"] == fingerprint
            and task["status"] != "stale"
            and question["status"] != "archived"
        )
        view = self_check_public(note, current, False)["note"]
        view["source_current"] = current
        notes.append(view)
        event(
            events,
            "selfcheck:" + note["id"],
            note["updated_at"],
            "保存自检要点",
            "学生确认的提醒，不作为掌握证明。"
            if current
            else "原题已更新，这条要点保留为历史提醒。",
        )
    result.update(self_checks=notes, events=recent(events))
    return result


@router.get("/{id}/journey")
def journey(request: Request, id: str):
    service = request.app.state.questions
    with service.database.session() as db, db.begin():
        owner = service.user(request, db).id
        questions = select_rows(
            db,
            "questions",
            "SELECT * FROM questions WHERE id=? AND user_id=? AND status<>'archived'",
            [id, owner],
        )
        if not questions:
            raise ApiError(404, "题目不存在")
        data = {"question": questions[0]}
        for key, table in [
            ("analysis", "problem_analyses"),
            ("diagnosis", "diagnoses"),
            ("job", "processing_jobs"),
            ("ocr", "ocr_runs"),
        ]:
            found = select_rows(
                db,
                table,
                f"SELECT * FROM {table} WHERE question_id=? ORDER BY created_at DESC,id DESC LIMIT 1",
                [id],
            )
            data[key] = found[0] if found else None
        for key, table, column in [
            ("sessions", "tutor_sessions", "question_id"),
            ("practices", "dataset_practice_attempts", "mistake_id"),
            ("plans", "review_plans", "question_id"),
        ]:
            suffix = (
                " AND status='pending' ORDER BY due_at,id"
                if key == "plans"
                else " ORDER BY created_at DESC,id DESC"
            )
            data[key] = select_rows(
                db,
                table,
                f"SELECT * FROM {table} WHERE {column}=? AND user_id=?"
                + suffix
                + " LIMIT 50",
                [id, owner],
            )
        data["reviews"] = select_rows(
            db,
            "review_records",
            "SELECT r.* FROM review_records r JOIN review_plans p ON p.id=r.plan_id WHERE p.question_id=? AND p.user_id=? ORDER BY r.created_at DESC,r.id DESC LIMIT 50",
            [id, owner],
        )
        now = (
            rows(db, "SELECT UTC_TIMESTAMP(6) AS now")[0]["now"]
            .replace(tzinfo=timezone.utc)
            .isoformat()
        )
        return envelope(request, add_tasks(db, build(data, now), owner, id))
