"""Local-only public question import, snapshots and format quarantine."""

import copy
import json
import re
import sys

from sqlalchemy.exc import SQLAlchemyError

from .config import Settings
from .database import Database
from .protocol import ApiError
from .question_data import execute, insert, rows, select_rows, update
from .question_validation import boolean, number, text_value

FIELDS = {
    "source_item_id": 190,
    "split": 30,
    "subject": 30,
    "grade": 30,
    "grade_band": 30,
    "title": 255,
    "question_text": 200000,
    "question_type": 60,
    "solution": 200000,
    "difficulty": 30,
    "content_hash": 64,
    "quality_status": 30,
}
ARRAYS = ["options", "knowledge_points", "image_paths", "links"]
FLAGS = [
    "has_answer",
    "has_solution",
    "answer_verified",
    "usable_for_practice",
    "usable_for_auto_grade",
]
COLUMNS = [
    *FIELDS,
    "options",
    "answer",
    "knowledge_points",
    "image_paths",
    "source_metadata",
    *FLAGS,
]
SOURCES = {"cmmu", "cmm-math", "gaokao", "race", "tal"}


def string(value, field, maximum, required=False):
    return text_value(value.get(field, ""), maximum, minimum=int(required))


def fingerprint(value):
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ApiError(422, "内容指纹无效")


def batch(body, maximum):
    values = body.get("questions")
    if (
        not isinstance(values, list)
        or not 1 <= len(values) <= maximum
        or any(not isinstance(value, dict) for value in values)
    ):
        raise ApiError(422, f"每批需要1至{maximum}道题")
    return values


def import_questions(db, body):
    source = body.get("source")
    if not isinstance(source, dict):
        raise ApiError(422, "题目来源无效")
    key = string(source, "key", 80, True)
    if key not in SOURCES:
        raise ApiError(422, "仅支持已配置的公开题源")
    items = copy.deepcopy(batch(body, 500))
    seen = set()
    for item in items:
        for field, maximum in FIELDS.items():
            item[field] = string(
                item,
                field,
                maximum,
                field in ["source_item_id", "subject", "question_text", "content_hash"],
            )
        if item["source_item_id"] in seen:
            raise ApiError(422, "批次包含重复题目")
        seen.add(item["source_item_id"])
        fingerprint(item["content_hash"])
        for field in ARRAYS:
            if not isinstance(item.get(field), list):
                raise ApiError(422, "题目集合字段无效")
        if not isinstance(item.get("source_metadata"), dict) or "answer" not in item:
            raise ApiError(422, "题目来源或答案无效")
        for field in FLAGS:
            item[field] = boolean(item.get(field))
        if item["usable_for_practice"] and (
            not item["has_answer"] or item["quality_status"] != "usable"
        ):
            raise ApiError(422, "未通过质量检查的题目不能用于练习")
        if item["usable_for_auto_grade"] and not item["usable_for_practice"]:
            raise ApiError(422, "判题资格无效")
        if any(
            not isinstance(path, str) or ".." in path for path in item["image_paths"]
        ):
            raise ApiError(422, "题目图片路径无效")
    metadata = {
        field: string(source, field, maximum, field in ["name", "version"])
        for field, maximum in [
            ("name", 160),
            ("version", 100),
            ("homepage", 500),
            ("license", 100),
            ("local_path", 500),
        ]
    }
    with db.begin():
        existing = rows(
            db, "SELECT id FROM dataset_sources WHERE `key`=? FOR UPDATE", [key]
        )
        if existing:
            source_id = existing[0]["id"]
            # Original source metadata refresh does not change its row timestamp here.
            execute(
                db,
                "UPDATE dataset_sources SET name=?,version=?,homepage=?,license=?,local_path=? WHERE id=?",
                [*metadata.values(), source_id],
            )
        else:
            source_id = insert(
                db,
                "dataset_sources",
                key=key,
                **metadata,
                total_items=0,
                imported_items=0,
                source_metadata={},
            )
        for item in items:
            previous = select_rows(
                db,
                "dataset_questions",
                "SELECT * FROM dataset_questions WHERE dataset_source_id=? AND source_item_id=?",
                [source_id, item["source_item_id"]],
            )
            if previous:
                saved = previous[0]
                saved_metadata = saved["source_metadata"] or {}
                review = saved_metadata.get("format_review") or {}
                history = saved_metadata.get("format_review_history") or []
                if (
                    saved["content_hash"] != item["content_hash"]
                    and review.get("fields")
                    and not any(
                        entry.get("content_hash") == review.get("content_hash")
                        for entry in history
                    )
                ):
                    history.append(review)
                if history:
                    item["source_metadata"]["format_review_history"] = history
                if saved["content_hash"] == item["content_hash"] and review.get(
                    "fields"
                ):
                    item["source_metadata"]["format_review"] = review
                    item.update(
                        quality_status="format_review",
                        usable_for_practice=False,
                        usable_for_auto_grade=False,
                    )
            values = {field: item[field] for field in COLUMNS}
            if not previous:
                id = insert(
                    db, "dataset_questions", dataset_source_id=source_id, **values
                )
            else:
                id = previous[0]["id"]
                if any(previous[0][field] != value for field, value in values.items()):
                    update(db, "dataset_questions", id, **values)
            execute(
                db,
                "DELETE FROM question_knowledge_links WHERE dataset_question_id=?",
                [id],
            )
            for link in item["links"]:
                if not isinstance(link, dict):
                    raise ApiError(422, "知识映射无效")
                code = string(link, "code", 100, True)
                cards = rows(
                    db,
                    "SELECT id FROM knowledge_points WHERE code=? AND subject=?",
                    [code, item["subject"]],
                )
                if not cards:
                    raise ApiError(422, "知识卡不存在或学科不匹配")
                role, method = (
                    string(link, "role", 30, True),
                    string(link, "method", 50, True),
                )
                confidence = number(link.get("confidence"))
                if role not in ["primary", "secondary"]:
                    raise ApiError(422, "知识映射角色无效")
                if not 0 <= confidence <= 1 or method not in [
                    "offline_rules",
                    "subject_grade_fallback",
                ]:
                    raise ApiError(422, "知识映射依据无效")
                insert(
                    db,
                    "question_knowledge_links",
                    dataset_question_id=id,
                    knowledge_point_id=cards[0]["id"],
                    role=role,
                    confidence=confidence,
                    mapping_method=method,
                )
        count = rows(
            db,
            "SELECT COUNT(*) AS count FROM dataset_questions WHERE dataset_source_id=?",
            [source_id],
        )[0]["count"]
        execute(
            db,
            "UPDATE dataset_sources SET total_items=?,imported_items=?,last_imported_at=UTC_TIMESTAMP(6),updated_at=UTC_TIMESTAMP(6) WHERE id=?",
            [count, count, source_id],
        )
        return {"stored": str(count), "source": key}


def review_format(db, body):
    items, seen = batch(body, 100), set()
    for item in items:
        id = string(item, "id", 36, True)
        if id in seen:
            raise ApiError(422, "核验记录重复")
        seen.add(id)
        fingerprint(item.get("content_hash"))
        fields = item.get("fields")
        if (
            not isinstance(fields, list)
            or not 1 <= len(fields) <= 20
            or any(
                not isinstance(field, str)
                or re.fullmatch(r"question|solution|option\.[A-H]", field) is None
                for field in fields
            )
        ):
            raise ApiError(422, "核验字段无效")
    with db.begin():
        changed = 0
        for item in items:
            saved = select_rows(
                db,
                "dataset_questions",
                "SELECT * FROM dataset_questions WHERE id=? FOR UPDATE",
                [item["id"]],
            )
            if not saved:
                raise ApiError(404, "题目不存在")
            value = saved[0]
            if value["content_hash"] != item["content_hash"]:
                raise ApiError(409, "题目已更新，请重新核验")
            metadata = value["source_metadata"] or {}
            review = {"content_hash": item["content_hash"], "fields": item["fields"]}
            if (
                metadata.get("format_review") != review
                or value["quality_status"] != "format_review"
                or value["usable_for_practice"]
                or value["usable_for_auto_grade"]
            ):
                metadata["format_review"] = review
                update(
                    db,
                    "dataset_questions",
                    item["id"],
                    source_metadata=metadata,
                    quality_status="format_review",
                    usable_for_practice=False,
                    usable_for_auto_grade=False,
                )
                changed += 1
        return {"changed": changed}


def command(database, settings, body):
    if not settings.db_name:
        raise ApiError(422, "必须显式配置数据库")
    if not isinstance(body, dict):
        raise ApiError(422, "题库命令输入无效")
    with database.session() as db:
        if not rows(
            db,
            "SELECT version FROM cangjie_schema_versions WHERE version='009_task_sources'",
        ):
            raise ApiError(409, "请先初始化或升级数据库")
        db.rollback()
        operation = string(body, "operation", 30, True)
        if operation == "import":
            return import_questions(db, body)
        if operation == "review-format":
            return review_format(db, body)
        if operation == "cards":
            return select_rows(
                db, "knowledge_points", "SELECT * FROM knowledge_points ORDER BY code"
            )
        after = string(body, "after", 36)
        if operation == "audit-export":
            return select_rows(
                db,
                "dataset_questions",
                "SELECT * FROM dataset_questions WHERE id>? ORDER BY id LIMIT 100",
                [after],
            )
        if operation == "export":
            source = string(body, "source", 80, True)
            return select_rows(
                db,
                "dataset_questions",
                "SELECT q.* FROM dataset_questions q JOIN dataset_sources s ON s.id=q.dataset_source_id WHERE s.`key`=? AND q.id>? AND q.usable_for_practice=1 ORDER BY q.id LIMIT 100",
                [source, after],
            )
        raise ApiError(422, "未知题库操作")


def main():
    database = None
    try:
        raw = sys.stdin.buffer.readline(16000002)
        if not raw or len(raw) > 16000000:
            raise ApiError(422, "题库命令输入无效或过大")
        body = json.loads(raw)
        settings = Settings.load()
        database = Database(settings)
        print(
            json.dumps(
                command(database, settings, body), ensure_ascii=False, allow_nan=False
            )
        )
    except (ApiError, SQLAlchemyError, ValueError, TypeError, KeyError):
        error = sys.exception()
        print(
            json.dumps(
                {
                    "code": error.status if isinstance(error, ApiError) else 503,
                    "message": error.message
                    if isinstance(error, ApiError)
                    else "题库操作未完成，请检查输入及数据库环境；当前批次未提交",
                },
                ensure_ascii=False,
            )
        )
        raise SystemExit(1) from None
    finally:
        if database is not None:
            database.close()


if __name__ == "__main__":
    main()
