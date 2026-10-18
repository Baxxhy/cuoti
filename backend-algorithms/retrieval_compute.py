"""Original BGE/Qdrant/reranker algorithms, supplied native MySQL snapshots only."""

from __future__ import annotations

import asyncio
import json
import math
import os
from dataclasses import asdict, dataclass
from difflib import SequenceMatcher
from threading import Lock
from types import SimpleNamespace
from typing import Any

import httpx
from app.services.question_mapping import normalized_grade
from qdrant_client import QdrantClient, models

settings = SimpleNamespace(
    retrieval_inference_url=os.environ.get(
        "CANGJIE_RETRIEVAL_INFERENCE_URL", "http://127.0.0.1:8011"
    ),
    qdrant_url=os.environ.get("CANGJIE_QDRANT_URL", "http://127.0.0.1:6333"),
    qdrant_collection=os.environ.get(
        "CANGJIE_QDRANT_COLLECTION", "minddimension_questions_v1"
    ),
    retrieval_candidate_limit=50,
    retrieval_result_limit=10,
)


def answer_text(value: Any) -> str:
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return value.strip('"')
        return answer_text(parsed)
    if isinstance(value, list):
        return "、".join(answer_text(item) for item in value)
    if isinstance(value, dict):
        return "；".join(f"{key}：{answer_text(item)}" for key, item in value.items())
    return str(value or "")


def question_with_options(question: Any) -> str:
    options = "\n".join(
        f"{item.get('key') or item.get('label', '')}. {item.get('text', '')}"
        for item in (question.options or [])
        if isinstance(item, dict)
    )
    return "\n".join(filter(None, (question.question_text, options)))


@dataclass(slots=True)
class VariantReference:
    id: str
    question_text: str
    answer: str
    solution: str
    question_type: str
    knowledge_points: list[Any]
    score: float


def retrieval_text(question: Any, knowledge_names: list[str]) -> str:
    options = " ".join(
        f"{item.get('key', '')}. {item.get('text', '')}"
        for item in (question.options or [])
    )
    return "\n".join(
        filter(
            None,
            (
                f"学科：{question.subject}",
                f"年级：{normalized_grade(question.grade, question.grade_band)}",
                question.question_text,
                options,
                "知识点：" + "、".join(knowledge_names),
            ),
        )
    )


def normalize_stem(text: str) -> str:
    return "".join(character.lower() for character in text if character.isalnum())


@dataclass(slots=True)
class RetrievalCandidate:
    question: Any
    source_dataset: str
    knowledge_points: list[dict[str, str]]
    dense_rank: int | None
    sparse_rank: int | None
    fusion_rank: int
    fusion_score: float
    reranker_score: float = 0.0
    mode_score: float = 0.0
    similarity_to_original: float = 0.0
    structure_similarity: float = 0.0


class BGERuntime:
    def __init__(self) -> None:
        self._lock = Lock()

    def embed(
        self, texts: list[str]
    ) -> tuple[list[list[float]], list[dict[int, float]]]:
        with self._lock:
            response = httpx.post(
                f"{settings.retrieval_inference_url}/embed",
                json={"texts": texts},
                timeout=300,
            )
            response.raise_for_status()
            output = response.json()
        return output["dense"], [
            {int(key): float(value) for key, value in row.items()}
            for row in output["sparse"]
        ]

    def rerank(self, query: str, documents: list[str]) -> list[float]:
        with self._lock:
            response = httpx.post(
                f"{settings.retrieval_inference_url}/rerank",
                json={"query": query, "documents": documents},
                timeout=300,
            )
            response.raise_for_status()
            return [float(score) for score in response.json()["scores"]]


bge_runtime = BGERuntime()

STRUCTURE_MARKERS = {
    "piecewise": ("分段", "begin{array}", "cases"),
    "quadratic": ("二次函数", "抛物线", "x^{2}", "x²"),
    "interval": ("区间", "取值范围", "范围"),
    "monotonicity": ("单调", "递增", "递减"),
    "extrema": ("最大值", "最小值", "最值"),
    "existence": ("存在", "\\exists", "任意", "恒成立"),
    "graph": ("如图", "图像", "图所示"),
    "experiment": ("实验", "测量", "装置"),
    "proof": ("证明", "说明理由"),
    "calculation": ("计算", "求解", "求出"),
    "material": ("材料", "阅读下列", "根据材料"),
}


def structure_features(text: str) -> set[str]:
    lowered = text.lower()
    return {
        name
        for name, markers in STRUCTURE_MARKERS.items()
        if any(marker in lowered for marker in markers)
    }


def structure_similarity(left: str, right: str) -> float:
    left_features, right_features = structure_features(left), structure_features(right)
    if not left_features and not right_features:
        return 0.5
    return len(left_features & right_features) / max(
        1, len(left_features | right_features)
    )


def _sparse_vector(weights: dict[int, float]) -> models.SparseVector:
    ordered = sorted(weights.items())
    return models.SparseVector(
        indices=[item[0] for item in ordered], values=[item[1] for item in ordered]
    )


def _filter(subject: str, grade: str, grade_band: str) -> models.Filter:
    grade_values = {normalized_grade(grade, grade_band), grade_band}
    return models.Filter(
        must=[
            models.FieldCondition(
                key="subject", match=models.MatchValue(value=subject)
            ),
            models.FieldCondition(
                key="usable_for_practice", match=models.MatchValue(value=True)
            ),
        ],
        min_should=models.MinShould(
            conditions=[
                models.FieldCondition(key="grade", match=models.MatchValue(value=value))
                for value in grade_values
            ],
            min_count=1,
        ),
    )


async def hybrid_ids(
    query_text: str, subject: str, grade: str, grade_band: str
) -> tuple[list[Any], dict[str, int], dict[str, int]]:
    dense, sparse = await asyncio.to_thread(bge_runtime.embed, [query_text])
    client = QdrantClient(url=settings.qdrant_url, timeout=60)
    query_filter = _filter(subject, grade, grade_band)
    limit = settings.retrieval_candidate_limit

    def search() -> tuple[list[Any], list[Any], list[Any]]:
        dense_rows = client.query_points(
            settings.qdrant_collection,
            query=dense[0],
            using="dense",
            query_filter=query_filter,
            limit=limit,
            with_payload=True,
        ).points
        sparse_rows = client.query_points(
            settings.qdrant_collection,
            query=_sparse_vector(sparse[0]),
            using="sparse",
            query_filter=query_filter,
            limit=limit,
            with_payload=True,
        ).points
        fused_rows = client.query_points(
            settings.qdrant_collection,
            prefetch=[
                models.Prefetch(
                    query=dense[0], using="dense", filter=query_filter, limit=limit
                ),
                models.Prefetch(
                    query=_sparse_vector(sparse[0]),
                    using="sparse",
                    filter=query_filter,
                    limit=limit,
                ),
            ],
            query=models.RrfQuery(rrf=models.Rrf()),
            limit=limit,
            with_payload=True,
        ).points
        return dense_rows, sparse_rows, fused_rows

    try:
        dense_rows, sparse_rows, fused_rows = await asyncio.to_thread(search)
    finally:
        client.close()
    dense_ranks = {
        str(row.payload["question_id"]): index + 1
        for index, row in enumerate(dense_rows)
    }
    sparse_ranks = {
        str(row.payload["question_id"]): index + 1
        for index, row in enumerate(sparse_rows)
    }
    return fused_rows, dense_ranks, sparse_ranks


async def rerank_candidates(
    query_text: str,
    original_text: str,
    original_type: str,
    mode: str,
    candidates: list[RetrievalCandidate],
) -> list[RetrievalCandidate]:
    documents = [
        retrieval_text(
            item.question, [point["name"] for point in item.knowledge_points]
        )
        for item in candidates
    ]
    scores = await asyncio.to_thread(bge_runtime.rerank, query_text, documents)
    original = normalize_stem(original_text)
    for item, score in zip(candidates, scores, strict=True):
        similarity = SequenceMatcher(
            None, original, normalize_stem(item.question.question_text)
        ).ratio()
        structural = structure_similarity(original_text, item.question.question_text)
        item.reranker_score = score
        item.similarity_to_original = similarity
        item.structure_similarity = structural
        same_type = item.question.question_type == original_type
        hybrid_rank_signal = (
            0.12 / math.sqrt(item.sparse_rank) if item.sparse_rank else 0.0
        ) + (0.06 / math.sqrt(item.dense_rank) if item.dense_rank else 0.0)
        if mode == "reinforce":
            item.mode_score = (
                score
                + (0.10 if same_type else 0.0)
                + 0.18 * structural
                + 0.12 * similarity
                + hybrid_rank_signal
                - max(0.0, similarity - 0.88) * 3
            )
        else:
            item.mode_score = (
                0.72 * score
                + (0.12 if not same_type else 0.0)
                + 0.28 * (1 - structural)
                + 0.12 * (1 - similarity)
                + hybrid_rank_signal
                - max(0.0, similarity - 0.60) * 1.8
            )
    candidates.sort(key=lambda item: (-item.mode_score, item.fusion_rank))
    return candidates[: settings.retrieval_result_limit]


def variant_reference(candidate: RetrievalCandidate) -> VariantReference:
    question = candidate.question
    knowledge_points: list[Any] = candidate.knowledge_points or list(
        question.knowledge_points or []
    )
    return VariantReference(
        id=question.id,
        question_text=question_with_options(question),
        answer=answer_text(question.answer),
        solution=question.solution or "",
        question_type=question.question_type,
        knowledge_points=knowledge_points,
        score=candidate.mode_score,
    )


async def search_index(
    query: str, subject: str, grade: str, grade_band: str
) -> dict[str, Any]:
    fused, dense, sparse = await hybrid_ids(query, subject, grade, grade_band)
    return {
        "hits": [
            {
                "id": str(row.payload["question_id"]),
                "fusion_score": float(row.score),
                "fusion_rank": index + 1,
                "dense_rank": dense.get(str(row.payload["question_id"])),
                "sparse_rank": sparse.get(str(row.payload["question_id"])),
            }
            for index, row in enumerate(fused)
        ]
    }


async def rank_snapshots(
    query: str,
    original_text: str,
    original_type: str,
    mode: str,
    snapshots: list[dict[str, Any]],
    excluded: list[str],
    kind: str,
) -> dict[str, Any]:
    original = normalize_stem(original_text)
    candidates = []
    for row in snapshots:
        question = SimpleNamespace(**row["question"])
        similarity = SequenceMatcher(
            None, original, normalize_stem(question.question_text)
        ).ratio()
        if question.id in excluded:
            continue
        if kind == "variant":
            if normalize_stem(question.question_text) == original:
                continue
        elif similarity >= (0.90 if mode == "variation" else 0.96):
            continue
        candidates.append(
            RetrievalCandidate(
                question,
                row["source_dataset"],
                row["knowledge_points"],
                row.get("dense_rank"),
                row.get("sparse_rank"),
                row["fusion_rank"],
                row["fusion_score"],
            )
        )
    ranked = (
        await rerank_candidates(query, original_text, original_type, mode, candidates)
        if candidates
        else []
    )
    return {
        "ranked": [
            {
                **asdict(item),
                "question": vars(item.question),
                "score_trace": {
                    key: round(getattr(item, key), 5)
                    for key in ("structure_similarity", "reranker_score", "mode_score")
                },
            }
            for item in ranked
        ],
        "references": [asdict(variant_reference(item)) for item in ranked[:5]],
    }


def prepare_query(
    question: dict[str, Any],
    analysis: dict[str, Any] | None,
    diagnosis: dict[str, Any],
    cards: list[dict[str, Any]],
    kind: str,
    mode: str,
) -> dict[str, Any]:
    from variant_compute import concept_terms

    values = (
        (analysis or {}).get("knowledge_points")
        or question.get("knowledge_points")
        or []
    )
    if kind == "variant":
        terms = concept_terms(values, question["question_text"])
        query = "\n".join(
            filter(
                None,
                (
                    f"学科：{question['subject']}",
                    f"年级：{question.get('grade') or ''}",
                    question["question_text"],
                    "知识点：" + "、".join(str(item) for item in (values or terms)),
                    "要求：保持核心知识、题型和难度"
                    if mode == "reinforce"
                    else "要求：保留核心知识，但改变题型、表达或场景",
                ),
            )
        )
        return {"query": query}
    names = [
        str(item)
        for item in (
            (analysis.get("knowledge_points") or [])
            if analysis
            else (question.get("knowledge_points") or [])
        )
    ]
    from practice_alignment import linear_task

    if linear_task(question["question_text"]):
        names = ["一元一次方程", *names]
    text = " ".join(names + [question["question_text"], question["title"]]).lower()
    supported = [
        card
        for card in cards
        if card["name"].lower() in text
        or any(len(word) >= 2 and word == card["name"] for word in names)
    ]
    ranked = sorted(
        supported,
        key=lambda card: (
            -(10 if card["name"].lower() in text else 0)
            - sum(
                2 for word in names if len(word) >= 2 and word in str(card["content"])
            ),
            card["code"],
        ),
    )
    unique = {}
    for card in ranked:
        unique.setdefault(card["name"], card)
    ranked = list(unique.values())[:3]
    knowledge = [card["name"] for card in ranked]
    target = "；".join(
        filter(
            None,
            (
                diagnosis.get("first_error_text", ""),
                diagnosis.get("root_misconception", ""),
                "、".join(diagnosis.get("missing_prerequisites") or []),
            ),
        )
    ) or (knowledge[0] if knowledge else question["title"])
    error = diagnosis.get("error_type", "unknown")
    query = "\n".join(
        filter(
            None,
            (
                f"学科：{question['subject']}",
                f"年级：{question.get('grade')}",
                question["question_text"],
                "知识点：" + "、".join(knowledge),
                f"目标技能：{target}",
                f"错误模式：{error}",
                "要求：保持核心知识和难度"
                if mode == "reinforce"
                else "要求：改变题型或情境但检验同一错误模式",
            ),
        )
    )
    return {
        "query": query,
        "knowledge_match": knowledge,
        "target_knowledge_id": ranked[0]["id"] if ranked else None,
        "target_knowledge_name": knowledge[0] if knowledge else None,
        "target_skill": target,
        "error_match": error,
    }
