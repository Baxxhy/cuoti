from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi import BackgroundTasks, HTTPException
from PIL import Image

from app.config import settings
from app.main import crop_question
from app.models import ProcessingJob, Question, QuestionAsset


class Rows(list):
    def first(self):
        return self[0] if self else None


class CropDB:
    def __init__(self, question, original):
        self.rows = [question, original]
        self.added = []
        self.get_options = []

    async def get(self, model, key, **kwargs):
        self.get_options.append((model, kwargs))
        return next((row for row in self.rows if isinstance(row, model) and row.id == key), None)

    async def scalars(self, statement):
        model = statement.column_descriptions[0]["entity"]
        rows = [row for row in self.rows if isinstance(row, model)]
        values = list(statement.compile().params.values())
        if model is QuestionAsset:
            kind = next((value for value in values if value in ("original", "crop")), None)
            if kind:
                rows = [row for row in rows if row.kind == kind]
        if model is ProcessingJob:
            rows = [row for row in rows if row.status in ("pending", "running")]
        return Rows(rows)

    async def scalar(self, statement):
        return (await self.scalars(statement)).first()

    def add(self, row):
        self.rows.append(row)
        self.added.append(row)

    async def flush(self):
        for index, row in enumerate(self.added):
            if row.id is None:
                row.id = f"created-{index}"
            if row.created_at is None:
                row.created_at = datetime.now(timezone.utc)

    async def commit(self):
        await self.flush()

    async def rollback(self):
        pass


def fixture(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "upload_dir", tmp_path)
    original = tmp_path / "original.png"
    Image.new("RGB", (500, 300), "white").save(original)
    question = Question(id="question", user_id="student", status="awaiting_crop")
    asset = QuestionAsset(id="original", question_id=question.id, kind="original", path=str(original))
    return question, original, CropDB(question, asset)


@pytest.mark.asyncio
async def test_repeated_crop_reuses_one_pending_job_without_rescheduling_or_replacing_image(
    monkeypatch, tmp_path
):
    question, original, db = fixture(monkeypatch, tmp_path)
    background = BackgroundTasks()
    payload = {"box": [0.1, 0.1, 0.5, 0.5]}
    first = await crop_question(question.id, background, payload, db)
    before = Path(first["data"]["path"]).read_bytes()
    second = await crop_question(question.id, background, payload, db)
    assert first["data"]["job_id"] == second["data"]["job_id"]
    assert len(background.tasks) == 1
    assert len([row for row in db.added if isinstance(row, ProcessingJob)]) == 1
    assert Path(first["data"]["path"]).read_bytes() == before
    assert next(row for row in db.rows if isinstance(row, QuestionAsset) and row.kind == "crop").bbox == [
        0.1,
        0.1,
        0.6,
        0.6,
    ]
    assert (Question, {"with_for_update": True, "populate_existing": True}) in db.get_options
    assert original.is_file()


@pytest.mark.asyncio
async def test_new_crop_range_cannot_overwrite_image_being_recognized(monkeypatch, tmp_path):
    question, original, db = fixture(monkeypatch, tmp_path)
    background = BackgroundTasks()
    first = await crop_question(question.id, background, {"box": [0, 0, 0.5, 0.5]}, db)
    before = Path(first["data"]["path"]).read_bytes()
    with pytest.raises(HTTPException) as caught:
        await crop_question(question.id, background, {"box": [0, 0, 1, 1]}, db)
    assert caught.value.status_code == 409
    assert Path(first["data"]["path"]).read_bytes() == before
    assert len(background.tasks) == 1 and original.is_file()


@pytest.mark.asyncio
async def test_archived_question_cannot_be_reopened_by_stale_crop_page(monkeypatch, tmp_path):
    question, original, db = fixture(monkeypatch, tmp_path)
    question.status = "archived"
    original_bytes = original.read_bytes()
    background = BackgroundTasks()
    with pytest.raises(HTTPException) as caught:
        await crop_question(question.id, background, {"box": [0, 0, 1, 1]}, db)
    assert caught.value.status_code == 404
    assert question.status == "archived" and not background.tasks
    assert original.read_bytes() == original_bytes


@pytest.mark.asyncio
async def test_reprocess_uses_existing_active_job_instead_of_scheduling_again(monkeypatch, tmp_path):
    from app.main import reprocess

    question, _, db = fixture(monkeypatch, tmp_path)
    background = BackgroundTasks()
    first = await crop_question(question.id, background, {"box": [0, 0, 1, 1]}, db)
    result = await reprocess(question.id, background, db)
    assert result["data"]["job_id"] == first["data"]["job_id"]
    assert len(background.tasks) == 1


@pytest.mark.asyncio
async def test_retry_of_an_old_failure_uses_current_task(monkeypatch, tmp_path):
    from app.main import retry_job

    question, _, db = fixture(monkeypatch, tmp_path)
    failed = ProcessingJob(id="old", question_id=question.id, kind="crop", status="failed")
    db.rows.append(failed)
    background = BackgroundTasks()
    first = await crop_question(question.id, background, {"box": [0, 0, 1, 1]}, db)
    result = await retry_job(failed.id, background, db)
    assert result["data"]["id"] == first["data"]["job_id"]
    assert result["data"]["resumed"] is True and failed.status == "failed"
    assert len(background.tasks) == 1


@pytest.mark.asyncio
async def test_all_reprocessing_entry_points_reject_archived_question(monkeypatch, tmp_path):
    from app.main import reprocess, retry_job, run_question_ocr

    question, _, db = fixture(monkeypatch, tmp_path)
    question.status = "archived"
    failed = ProcessingJob(id="old", question_id=question.id, kind="crop", status="failed")
    db.rows.append(failed)
    background = BackgroundTasks()
    for action in (
        lambda: reprocess(question.id, background, db),
        lambda: retry_job(failed.id, background, db),
        lambda: run_question_ocr(question.id, db),
    ):
        with pytest.raises(HTTPException) as caught:
            await action()
        assert caught.value.status_code == 404
    assert not background.tasks and question.status == "archived" and failed.status == "failed"
