"""Prepare local public files via Cangjie snapshots; never connect Python to MySQL."""

import argparse
import hashlib
import json
import os
import subprocess
import sys
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "backend"))
sys.path.insert(0, str(PROJECT / "backend-algorithms"))

from app.services.question_bank_import import (
    build_asset_index,
    iter_cmm_math,
    iter_cmmu,
)
from app.services.question_mapping import map_question, normalized_grade
from app.services.question_quality import quality_flags

SOURCES = {
    "cmmu": {
        "key": "cmmu",
        "name": "CMMU",
        "version": "b3b65566fa083636713bca7b117e48c67720a074",
        "homepage": "https://huggingface.co/datasets/BAAI/CMMU",
        "license": "Apache-2.0",
        "local_path": "data/question_bank_sources/cmmu",
    },
    "cmm-math": {
        "key": "cmm-math",
        "name": "CMM-Math",
        "version": "5b227e818a47ebfd0090b4fdcaac38cbf8cb7aa3",
        "homepage": "https://huggingface.co/datasets/ecnu-icalk/cmm-math",
        "license": "BSD-3-Clause",
        "local_path": "data/question_bank_sources/cmm_math",
    },
}


def native(payload):
    done = subprocess.run(
        ["bash", "scripts/cangjie.sh", "question-bank-built"],
        input=json.dumps(payload, ensure_ascii=False) + "\n",
        cwd=PROJECT,
        text=True,
        capture_output=True,
        check=False,
    )
    if done.returncode:
        raise RuntimeError(
            "仓颉题库命令未完成，当前批次未提交；请检查独立库、版本或输入"
        )
    return json.loads(done.stdout)


def normalized_records(source):
    folder = source.replace("-", "_")
    directory = PROJECT / "data/question_bank_sources" / folder
    assets = build_asset_index(PROJECT / "data/question_bank_assets" / folder, PROJECT)
    if source == "cmmu":
        if not list(directory.glob("*.jsonl")):
            raise RuntimeError("本地CMMU文件不存在；工具不会自动下载")
        return iter_cmmu(directory, assets)
    return iter_cmm_math(directory / "all_data.jsonl", assets)


def import_records(source, contains=""):
    cards = [SimpleNamespace(**item) for item in native({"operation": "cards"})]
    by_id = {card.id: card for card in cards}
    counts = Counter()
    batch = []

    def flush():
        result = native(
            {"operation": "import", "source": SOURCES[source], "questions": batch}
        )
        print(json.dumps({"stage": "import", **result}, ensure_ascii=False), flush=True)
        batch.clear()

    for item in normalized_records(source):
        if contains and contains not in item.question_text + item.solution:
            continue
        if contains:
            item.source_metadata["selection_text"] = contains
            item.finalize()
        flags = quality_flags(item, PROJECT)
        flags.pop("image_missing")
        matches = map_question(
            item, [card for card in cards if card.subject == item.subject]
        )
        row = {**asdict(item), **flags}
        row["links"] = [
            {
                "code": by_id[match.knowledge_id].code,
                "role": match.role,
                "confidence": match.confidence,
                "method": match.method,
            }
            for match in matches
        ]
        batch.append(row)
        counts[flags["quality_status"]] += 1
        if len(batch) == 50:
            flush()
    if batch:
        flush()
    print(
        json.dumps(
            {"stage": "quality", "source": source, "counts": dict(counts)},
            ensure_ascii=False,
        ),
        flush=True,
    )


def index_records(source):
    from qdrant_client import QdrantClient, models
    from retrieval_compute import bge_runtime, retrieval_text, settings

    database = os.environ.get("CANGJIE_DB_NAME", "")
    collection = os.environ.get("CANGJIE_QDRANT_COLLECTION", "")
    if not database or not collection.startswith(database + "_"):
        raise RuntimeError(
            "请显式配置以独立仓颉库名加下划线开头的CANGJIE_QDRANT_COLLECTION，防止混用旧库索引"
        )
    settings.qdrant_collection = collection
    after = ""
    indexed = skipped = 0
    client = QdrantClient(url=settings.qdrant_url, timeout=120)
    try:
        while True:
            rows = native({"operation": "export", "source": source, "after": after})
            if not rows:
                break
            after = rows[-1]["id"]
            for start in range(0, len(rows), 16):
                page = rows[start : start + 16]
                texts = [
                    retrieval_text(SimpleNamespace(**row), row["knowledge_points"])
                    for row in page
                ]
                hashes = {
                    row["id"]: hashlib.sha256(
                        (text + row["content_hash"]).encode()
                    ).hexdigest()
                    for row, text in zip(page, texts, strict=True)
                }
                exists = client.collection_exists(collection)
                saved = (
                    client.retrieve(
                        collection,
                        [row["id"] for row in page],
                        with_payload=True,
                        with_vectors=False,
                    )
                    if exists
                    else []
                )
                current = {
                    str(point.id): point.payload.get("content_hash") for point in saved
                }
                pending = [
                    (row, text)
                    for row, text in zip(page, texts, strict=True)
                    if current.get(row["id"]) != hashes[row["id"]]
                ]
                skipped += len(page) - len(pending)
                if not pending:
                    continue
                dense, sparse = bge_runtime.embed([text for _, text in pending])
                if not exists:
                    client.create_collection(
                        collection,
                        vectors_config={
                            "dense": models.VectorParams(
                                size=len(dense[0]), distance=models.Distance.COSINE
                            )
                        },
                        sparse_vectors_config={"sparse": models.SparseVectorParams()},
                    )
                points = []
                for (row, _), vector, weights in zip(
                    pending, dense, sparse, strict=True
                ):
                    ordered = sorted(weights.items())
                    points.append(
                        models.PointStruct(
                            id=row["id"],
                            vector={
                                "dense": vector,
                                "sparse": models.SparseVector(
                                    indices=[key for key, _ in ordered],
                                    values=[value for _, value in ordered],
                                ),
                            },
                            payload={
                                "question_id": row["id"],
                                "source_dataset": source,
                                "subject": row["subject"],
                                "grade": normalized_grade(
                                    row["grade"], row["grade_band"]
                                ),
                                "grade_band": row["grade_band"],
                                "usable_for_practice": row["usable_for_practice"],
                                "content_hash": hashes[row["id"]],
                            },
                        )
                    )
                client.upsert(collection, points, wait=True)
                indexed += len(points)
                print(
                    json.dumps(
                        {"stage": "index", "indexed": indexed, "skipped": skipped}
                    ),
                    flush=True,
                )
        print(
            json.dumps(
                {
                    "stage": "indexed",
                    "source": source,
                    "indexed": indexed,
                    "skipped": skipped,
                    "collection_count": client.count(collection, exact=True).count
                    if client.collection_exists(collection)
                    else 0,
                }
            ),
            flush=True,
        )
    finally:
        client.close()


def main():
    parser = argparse.ArgumentParser(
        description="仓颉入库、Python清洗/BGE索引；仅使用本地公开题源"
    )
    parser.add_argument("--source", choices=SOURCES, default="cmmu")
    parser.add_argument("--index-only", action="store_true")
    parser.add_argument("--skip-index", action="store_true")
    parser.add_argument(
        "--contains",
        default="",
        help="仅导入题干或解答包含该文字的本地题目；不代表相关性已验证",
    )
    args = parser.parse_args()
    if not args.index_only:
        import_records(args.source, args.contains)
    if not args.skip_index:
        index_records(args.source)


if __name__ == "__main__":
    try:
        main()
    except Exception:  # noqa: BLE001 - deployment boundary must not print upstream credentials
        print(
            "题库准备未完成；已提交批次保留，可修复配置后重复执行。未输出连接凭据。",
            file=sys.stderr,
        )
        raise SystemExit(1) from None
