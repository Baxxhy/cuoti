#!/usr/bin/env python3
"""Check recognition transaction races in real MySQL; never execute captured AI tasks."""

from __future__ import annotations

import asyncio
import hashlib
import json
import shutil
import sys
import uuid
from pathlib import Path

from fastapi import BackgroundTasks, HTTPException
from PIL import Image
from sqlalchemy import delete, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.auth import hash_password
from app.config import settings
from app.db import SessionLocal, engine
from app.main import crop_question, provider, question_payload
from app.models import ProcessingJob, Question, QuestionAsset, User


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


async def verify() -> dict:
    actor_id = str(uuid.uuid4())
    # New high-sorting IDs exercise an empty range of the question/job index.
    question_ids = [
        "z0" + uuid.uuid4().hex[:30],
        *("zz" + uuid.uuid4().hex[:30] for _ in range(2)),
    ]
    created_folders = []
    original_hashes = {}
    try:
        async with SessionLocal() as db:
            db.add(
                User(
                    id=actor_id,
                    email=f"qa-concurrency-{uuid.uuid4().hex}@minddimension.local",
                    name="并发事务验收",
                    role="student",
                    password_hash=hash_password(uuid.uuid4().hex),
                )
            )
            await db.flush()
            for question_id in question_ids:
                db.add(
                    Question(
                        id=question_id,
                        user_id=actor_id,
                        subject="数学",
                        status="awaiting_crop",
                    )
                )
            await db.flush()
            for question_id in question_ids:
                folder = settings.upload_dir / question_id
                folder.mkdir(parents=True)
                created_folders.append(folder)
                original = folder / "original.png"
                Image.new("RGB", (400, 300), "white").save(original)
                original_hashes[question_id] = digest(original)
                db.add(
                    QuestionAsset(
                        question_id=question_id,
                        kind="original",
                        path=str(original),
                        sha256=original_hashes[question_id],
                    )
                )
            await db.commit()

        async def submit(question_id: str, sessions=SessionLocal):
            async with sessions() as db:
                background = BackgroundTasks()
                response = await crop_question(
                    question_id, background, {"box": [0, 0, 1, 1]}, db
                )
                return response["data"]["job_id"], len(background.tasks)

        same = await asyncio.gather(
            submit(question_ids[0]), submit(question_ids[0]), return_exceptions=True
        )
        for result in same:
            if isinstance(result, BaseException):
                raise result
        assert same[0][0] == same[1][0] and sum(count for _, count in same) == 1

        entered = 0
        release = asyncio.Event()

        class InterleavedSession(AsyncSession):
            async def get(self, model, key, **kwargs):
                nonlocal entered
                row = await super().get(model, key, **kwargs)
                if model is Question and kwargs.get("with_for_update"):
                    entered += 1
                    if entered == 2:
                        release.set()
                    await asyncio.wait_for(release.wait(), 10)
                return row

        sessions = async_sessionmaker(
            engine, class_=InterleavedSession, expire_on_commit=False
        )
        different = await asyncio.gather(
            *(submit(qid, sessions) for qid in question_ids[1:]), return_exceptions=True
        )
        for result in different:
            if isinstance(result, BaseException):
                raise result
        assert (
            different[0][0] != different[1][0]
            and sum(count for _, count in different) == 2
        )

        async with SessionLocal() as db:
            jobs = list(
                await db.scalars(
                    select(ProcessingJob).where(
                        ProcessingJob.question_id.in_(question_ids)
                    )
                )
            )
            assert len(jobs) == 3
            snapshot = await question_payload(question_ids[0], db)
            assert snapshot["processing_job"]["id"] == same[0][0] and snapshot[
                "crop_box"
            ] == [0, 0, 1, 1]
            crop = next(item for item in snapshot["assets"] if item["kind"] == "crop")
            before = digest(Path(crop["path"]))
            try:
                await crop_question(
                    question_ids[0], BackgroundTasks(), {"box": [0, 0, 0.5, 0.5]}, db
                )
            except HTTPException as error:
                assert error.status_code == 409
            else:
                raise AssertionError("active crop replaced")
            assert digest(Path(crop["path"])) == before
        for question_id, expected in original_hashes.items():
            assert (
                digest(settings.upload_dir / question_id / "original.png") == expected
            )
        return {
            "same_question_jobs": 1,
            "different_question_jobs": 2,
            "workers_scheduled": 3,
            "conflicting_range": 409,
            "originals_preserved": True,
            "ai_calls": 0,
        }
    finally:
        # These exact IDs were created above and cannot refer to existing users/data.
        async with SessionLocal() as db:
            await db.execute(
                delete(ProcessingJob).where(ProcessingJob.question_id.in_(question_ids))
            )
            await db.execute(
                delete(QuestionAsset).where(QuestionAsset.question_id.in_(question_ids))
            )
            await db.execute(
                delete(Question).where(
                    Question.id.in_(question_ids), Question.user_id == actor_id
                )
            )
            await db.execute(delete(User).where(User.id == actor_id))
            await db.commit()
        for folder in created_folders:
            shutil.rmtree(folder)
        await provider.close()
        await engine.dispose()


def main() -> int:
    try:
        print(json.dumps(asyncio.run(verify())))
    except (SQLAlchemyError, AssertionError, OSError, TimeoutError) as error:
        code = getattr(getattr(error, "orig", None), "args", (None,))[0]
        print(
            json.dumps(
                {
                    "concurrency": "failed",
                    "error_type": type(error).__name__,
                    "mysql_code": code if isinstance(code, int) else None,
                }
            )
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
