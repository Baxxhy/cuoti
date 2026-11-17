import copy
import os
from uuid import uuid4

import pytest
from cuoti_backend import question_bank
from cuoti_backend.protocol import ApiError
from cuoti_backend.question_data import execute, rows
from test_questions_mysql import (
    question_app as question_app,  # noqa: PLC0414 -- Export a shared pytest fixture.
)

pytestmark = [
    pytest.mark.mysql,
    pytest.mark.skipif(
        os.environ.get("CUOTI_TEST_MYSQL") != "1",
        reason="local MySQL check not enabled",
    ),
]


def test_import_quarantine_snapshot_history_and_rollback(question_app, monkeypatch):
    app, _, _, _ = question_app
    database, settings = app.state.database, app.state.settings
    key = "migration-" + str(uuid4())
    monkeypatch.setattr(question_bank, "SOURCES", {*question_bank.SOURCES, key})
    source = {
        "key": key,
        "name": "迁移测试",
        "version": "1",
        "homepage": "",
        "license": "test",
        "local_path": "",
    }

    def command(**body):
        return question_bank.command(database, settings, body)

    try:
        cards = command(operation="cards")
        assert cards
        card = cards[0]
        item = {
            "source_item_id": "test-1",
            "split": "test",
            "subject": card["subject"],
            "grade": "初一",
            "grade_band": "初中",
            "title": "题库迁移验证",
            "question_text": "2x=4，求x",
            "question_type": "calculation",
            "solution": "两边同除2",
            "difficulty": "",
            "content_hash": "a" * 64,
            "quality_status": "usable",
            "options": [],
            "answer": "2",
            "knowledge_points": [card["name"]],
            "image_paths": [],
            "source_metadata": {},
            "has_answer": True,
            "has_solution": True,
            "answer_verified": True,
            "usable_for_practice": True,
            "usable_for_auto_grade": True,
            "links": [
                {
                    "code": card["code"],
                    "role": "primary",
                    "confidence": 0.8,
                    "method": "offline_rules",
                }
            ],
        }
        result = command(operation="import", source=source, questions=[item])
        assert result == {"stored": "1", "source": key}
        first = command(operation="export", source=key)[0]
        id = first["id"]
        assert first["answer"] == "2"
        command(operation="import", source=source, questions=[item])
        assert command(operation="export", source=key)[0] == first
        with database.session() as db:
            assert (
                len(
                    rows(
                        db,
                        "SELECT * FROM question_knowledge_links WHERE dataset_question_id=?",
                        [id],
                    )
                )
                == 1
            )
        review = {
            "id": id,
            "content_hash": item["content_hash"],
            "fields": ["question", "option.A"],
        }
        assert command(operation="review-format", questions=[review]) == {"changed": 1}
        assert command(operation="review-format", questions=[review]) == {"changed": 0}
        assert command(operation="export", source=key) == []
        command(operation="import", source=source, questions=[item])
        assert command(operation="export", source=key) == []
        changed = copy.deepcopy(item)
        changed.update(content_hash="b" * 64, question_text="3x=6，求x")
        command(operation="import", source=source, questions=[changed])
        updated = command(operation="export", source=key)[0]
        assert (
            updated["id"] == id and updated["question_text"] == changed["question_text"]
        )
        assert updated["source_metadata"]["format_review_history"] == [
            {"content_hash": item["content_hash"], "fields": review["fields"]}
        ]
        with pytest.raises(ApiError, match="重新核验"):
            command(operation="review-format", questions=[review])
        invalid = copy.deepcopy(changed)
        invalid.update(
            source_item_id="bad-link",
            links=[{**item["links"][0], "code": "no-such-card-" + uuid4().hex}],
        )
        with pytest.raises(ApiError, match="知识卡不存在"):
            command(operation="import", source=source, questions=[changed, invalid])
        assert len(command(operation="export", source=key)) == 1
        with pytest.raises(ApiError, match="重复"):
            command(operation="import", source=source, questions=[item, item])
        with pytest.raises(ApiError, match="已配置"):
            command(
                operation="import",
                source={**source, "key": "unsupported"},
                questions=[item],
            )
        exported = command(operation="audit-export", after="")
        assert len(exported) <= 100
    finally:
        with database.session() as db, db.begin():
            execute(
                db,
                "DELETE l FROM question_knowledge_links l JOIN dataset_questions q ON l.dataset_question_id=q.id JOIN dataset_sources s ON q.dataset_source_id=s.id WHERE s.`key`=?",
                [key],
            )
            execute(
                db,
                "DELETE q FROM dataset_questions q JOIN dataset_sources s ON q.dataset_source_id=s.id WHERE s.`key`=?",
                [key],
            )
            execute(db, "DELETE FROM dataset_sources WHERE `key`=?", [key])
