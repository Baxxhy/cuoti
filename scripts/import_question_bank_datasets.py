#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import shutil
import subprocess
import sys
import tarfile
import zipfile
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.dialects.mysql import insert as mysql_insert

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.db import SessionLocal
from app.models import DatasetQuestion, DatasetSource, utcnow, uuid4
from app.services.question_bank_import import (
    NormalizedDatasetQuestion,
    build_asset_index,
    iter_cmm_math,
    iter_cmmu,
    iter_m3ke,
)

SOURCE_ROOT = ROOT / "data/question_bank_sources"
ASSET_ROOT = ROOT / "data/question_bank_assets"

SOURCES = {
    "cmm-math": {
        "name": "CMM-Math",
        "version": "5b227e818a47ebfd0090b4fdcaac38cbf8cb7aa3",
        "homepage": "https://hf-mirror.com/datasets/ecnu-icalk/cmm-math",
        "license": "BSD-3-Clause",
        "data_url": "https://hf-mirror.com/datasets/ecnu-icalk/cmm-math/resolve/main/all_data.jsonl",
        "asset_url": "https://hf-mirror.com/datasets/ecnu-icalk/cmm-math/resolve/main/images.zip",
    },
    "m3ke": {
        "name": "M3KE",
        "version": "b370aae92167610791c34d16ef1b5a3e41805e62",
        "homepage": "https://github.com/tjunlp-lab/M3KE",
        "license": "未在仓库中声明",
        "data_url": "https://gh-proxy.com/https://raw.githubusercontent.com/tjunlp-lab/M3KE/main/data/M3KE.zip",
    },
    "cmmu": {
        "name": "CMMU",
        "version": "b3b65566fa083636713bca7b117e48c67720a074",
        "homepage": "https://hf-mirror.com/datasets/BAAI/CMMU",
        "license": "Apache-2.0",
        "asset_url": "https://hf-mirror.com/datasets/BAAI/CMMU/resolve/main/val/images.tar",
    },
}
CMMU_SUBJECTS = ("biology", "chemistry", "geography", "history", "math", "physics", "politics")


def download(url: str, target: Path) -> None:
    if target.exists() and target.stat().st_size:
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_name(f"{target.name}.part")
    partial.unlink(missing_ok=True)
    try:
        subprocess.run([
            "curl", "-fsSL", "--retry", "5", "--connect-timeout", "20", url,
            "-o", str(partial),
        ], check=True)
        if not partial.stat().st_size:
            raise RuntimeError(f"下载内容为空: {url}")
        partial.replace(target)
    finally:
        partial.unlink(missing_ok=True)


def safe_target(root: Path, member: str) -> Path:
    target = (root / member).resolve()
    if not target.is_relative_to(root.resolve()):
        raise ValueError(f"非法归档路径: {member}")
    return target


def extract_zip(archive_path: Path, target_root: Path) -> None:
    marker = target_root / ".extracted"
    if marker.exists():
        return
    target_root.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive_path) as archive:
        for member in archive.infolist():
            if member.is_dir():
                continue
            target = safe_target(target_root, member.filename)
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as source, target.open("wb") as output:
                shutil.copyfileobj(source, output)
    marker.touch()


def extract_tar(archive_path: Path, target_root: Path) -> None:
    marker = target_root / ".extracted"
    if marker.exists():
        return
    target_root.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive_path) as archive:
        for member in archive.getmembers():
            if not member.isfile():
                continue
            target = safe_target(target_root, member.name)
            target.parent.mkdir(parents=True, exist_ok=True)
            source = archive.extractfile(member)
            if source is None:
                continue
            with source, target.open("wb") as output:
                shutil.copyfileobj(source, output)
    marker.touch()


def ensure_files(source: str, include_assets: bool) -> None:
    if source == "cmm-math":
        root = SOURCE_ROOT / "cmm_math"
        download(SOURCES[source]["data_url"], root / "all_data.jsonl")
        if include_assets:
            download(SOURCES[source]["asset_url"], root / "images.zip")
            extract_zip(root / "images.zip", ASSET_ROOT / "cmm_math")
    elif source == "m3ke":
        root = SOURCE_ROOT / "m3ke"
        download(SOURCES[source]["data_url"], root / "M3KE.zip")
    else:
        root = SOURCE_ROOT / "cmmu"
        for subject in CMMU_SUBJECTS:
            download(
                f"https://hf-mirror.com/datasets/BAAI/CMMU/resolve/main/val/{subject}.jsonl",
                root / f"{subject}.jsonl",
            )
        if include_assets:
            download(SOURCES[source]["asset_url"], root / "images.tar")
            extract_tar(root / "images.tar", ASSET_ROOT / "cmmu")


def records(source: str) -> list[NormalizedDatasetQuestion]:
    if source == "cmm-math":
        assets = build_asset_index(ASSET_ROOT / "cmm_math", ROOT)
        return list(iter_cmm_math(SOURCE_ROOT / "cmm_math/all_data.jsonl", assets))
    if source == "m3ke":
        return list(iter_m3ke(SOURCE_ROOT / "m3ke/M3KE.zip"))
    assets = build_asset_index(ASSET_ROOT / "cmmu", ROOT)
    return list(iter_cmmu(SOURCE_ROOT / "cmmu", assets))


async def ensure_source(db, key: str) -> DatasetSource:
    source = (await db.scalars(select(DatasetSource).where(DatasetSource.key == key))).first()
    meta = SOURCES[key]
    local_path = str((SOURCE_ROOT / key.replace("-", "_")).relative_to(ROOT))
    if source is None:
        source = DatasetSource(
            key=key, name=meta["name"], version=meta["version"], homepage=meta["homepage"],
            license=meta["license"], local_path=local_path,
            source_metadata={"scope": "初中与高中", "importer": "scripts/import_question_bank_datasets.py"},
        )
        db.add(source)
        await db.flush()
    else:
        source.version, source.homepage, source.license, source.local_path = (
            meta["version"], meta["homepage"], meta["license"], local_path
        )
    return source


async def import_source(key: str, include_assets: bool, batch_size: int) -> dict[str, int | str]:
    ensure_files(key, include_assets)
    normalized = records(key)
    async with SessionLocal() as db:
        source = await ensure_source(db, key)
        source.total_items = len(normalized)
        table = DatasetQuestion.__table__
        for offset in range(0, len(normalized), batch_size):
            now = utcnow()
            values = []
            for item in normalized[offset:offset + batch_size]:
                values.append({
                    "id": uuid4(), "created_at": now, "updated_at": now,
                    "dataset_source_id": source.id, **asdict(item),
                })
            statement = mysql_insert(table).values(values)
            update_columns = {
                column.name: statement.inserted[column.name]
                for column in table.columns
                if column.name not in {"id", "created_at", "dataset_source_id", "source_item_id"}
            }
            await db.execute(statement.on_duplicate_key_update(**update_columns))
            await db.commit()
        imported = await db.scalar(
            select(func.count()).select_from(DatasetQuestion).where(DatasetQuestion.dataset_source_id == source.id)
        )
        source.imported_items = int(imported or 0)
        source.last_imported_at = datetime.now(timezone.utc)
        await db.commit()
        return {"source": key, "parsed": len(normalized), "stored": source.imported_items}


async def main() -> None:
    parser = argparse.ArgumentParser(description="导入 CMM-Math、M3KE、CMMU 中学题目到 MySQL")
    parser.add_argument("--source", choices=["all", *SOURCES], default="all")
    parser.add_argument("--skip-assets", action="store_true", help="只导入题目文本，不下载图片归档")
    parser.add_argument("--batch-size", type=int, default=500)
    args = parser.parse_args()
    selected = list(SOURCES) if args.source == "all" else [args.source]
    for key in selected:
        result = await import_source(key, not args.skip_assets, args.batch_size)
        print(" ".join(f"{name}={value}" for name, value in result.items()))


if __name__ == "__main__":
    asyncio.run(main())
