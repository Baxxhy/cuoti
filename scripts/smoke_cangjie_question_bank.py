"""Real native command/MySQL checks for repeatable, atomic local data preparation."""

import copy
import json
import subprocess
from pathlib import Path
from uuid import uuid4


def question_bank(env, query):
    project = Path(__file__).resolve().parents[1]

    def native(payload, code=0, command_env=None):
        done = subprocess.run(
            ["bash", "scripts/cangjie.sh", "question-bank-built"],
            input=json.dumps(payload, ensure_ascii=False) + "\n",
            cwd=project,
            env=command_env or env,
            text=True,
            capture_output=True,
            check=False,
        )
        assert done.returncode == code, "native question-bank exit mismatch"
        assert env["CANGJIE_DB_PASSWORD"] not in done.stdout + done.stderr
        return json.loads(done.stdout)

    source = {
        "key": "cmmu",
        "name": "隔离题源",
        "version": "native-test",
        "homepage": "",
        "license": "test-only",
        "local_path": "test",
    }
    prefix = uuid4().hex
    row = {
        "source_item_id": prefix,
        "split": "test",
        "subject": "数学",
        "grade": "初中",
        "grade_band": "初中",
        "title": "导入测试",
        "question_text": "解方程 3x+1=10",
        "question_type": "填空题",
        "options": [],
        "answer": "x=3",
        "solution": "3x=9，所以x=3",
        "knowledge_points": [],
        "image_paths": [],
        "difficulty": "",
        "content_hash": "a" * 64,
        "source_metadata": {"test": True},
        "has_answer": True,
        "has_solution": True,
        "answer_verified": False,
        "quality_status": "usable",
        "usable_for_practice": True,
        "usable_for_auto_grade": True,
        "links": [],
    }
    payload = {"operation": "import", "source": source, "questions": [row]}
    before_users = query(env, "SELECT COUNT(*) FROM users")
    before = int(query(env, "SELECT COUNT(*) FROM dataset_questions"))
    native(payload)
    saved = query(
        env, f"SELECT id FROM dataset_questions WHERE source_item_id='{prefix}'"
    )
    assert (
        saved
        and int(query(env, "SELECT COUNT(*) FROM dataset_questions")) == before + 1
    )
    version = query(env, f"SELECT updated_at FROM dataset_questions WHERE id='{saved}'")
    native(payload)
    assert (
        query(env, f"SELECT updated_at FROM dataset_questions WHERE id='{saved}'")
        == version
    )
    assert (
        query(env, f"SELECT id FROM dataset_questions WHERE source_item_id='{prefix}'")
        == saved
    )
    assert int(query(env, "SELECT COUNT(*) FROM dataset_questions")) == before + 1
    changed = copy.deepcopy(payload)
    changed["questions"][0].update(answer="x=4", content_hash="b" * 64)
    native(changed)
    assert (
        query(
            env,
            f"SELECT JSON_UNQUOTE(answer) FROM dataset_questions WHERE id='{saved}'",
        )
        == "x=4"
    )
    exported = native({"operation": "export", "source": "cmmu"})
    assert any(item["id"] == saved and item["answer"] == "x=4" for item in exported)
    assert native({"operation": "export", "source": "cmmu", "after": "z" * 36}) == []
    cards = native({"operation": "cards"})
    assert isinstance(cards, list)
    rollback = copy.deepcopy(payload)
    second = copy.deepcopy(row)
    second["source_item_id"] = prefix + "-new"
    second["links"] = [{"code": "missing-card-" + prefix, "role": "primary"}]
    rollback["questions"] = [row, second]
    assert native(rollback, 1)["code"] == 422
    # The first row changed before the second row's invalid link: both roll back.
    assert (
        query(
            env,
            f"SELECT JSON_UNQUOTE(answer) FROM dataset_questions WHERE id='{saved}'",
        )
        == "x=4"
    )
    assert (
        query(
            env,
            f"SELECT COUNT(*) FROM dataset_questions WHERE source_item_id='{prefix}-new'",
        )
        == "0"
    )
    for delta in [
        {"usable_for_practice": True, "has_answer": False},
        {"content_hash": "z" * 64},
        {"image_paths": ["../../secret"]},
        {"usable_for_practice": "true"},
    ]:
        invalid = copy.deepcopy(payload)
        invalid["questions"][0].update(delta)
        assert native(invalid, 1)["code"] == 422
    assert native({**payload, "questions": [row, row]}, 1)["code"] == 422
    assert native({"operation": "unknown"}, 1)["code"] == 422
    assert native(payload, 1, {**env, "CANGJIE_DB_NAME": ""})["code"] == 422
    assert query(env, "SELECT COUNT(*) FROM users") == before_users
    # Avoid changing later retrieval fixtures or leaving isolated test content active.
    query(
        env,
        f"UPDATE dataset_questions SET usable_for_practice=0,usable_for_auto_grade=0 WHERE id='{saved}'",
    )
    print(
        "Cangjie question bank passed: native import/export, stable IDs, content update, validation, atomic batch rollback and no user mutation"
    )
