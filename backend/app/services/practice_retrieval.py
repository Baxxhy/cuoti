from __future__ import annotations

import asyncio
import json
import math
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from threading import Lock
from typing import Any

import httpx
from qdrant_client import QdrantClient, models
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import DatasetQuestion, DatasetSource, KnowledgePoint, QuestionKnowledgeLink
from app.services.question_mapping import normalized_grade

GENERIC_TERMS = {
    "判断",
    "计算",
    "问题",
    "方法",
    "知识点",
    "综合",
    "题目",
    "条件",
    "结果",
    "分析",
    "应用",
    "关系",
    "学生",
    "错误",
    "步骤",
    "数学",
    "物理",
    "化学",
}


def concept_terms(values: list[Any] | None, original_text: str = "") -> list[str]:
    chunks: list[str] = []
    for value in [*(str(item) for item in (values or [])), original_text]:
        chunks.extend(re.findall(r"[\u4e00-\u9fff]{2,12}|[A-Za-z][A-Za-z0-9_-]{1,20}", value))
    terms: list[str] = []
    for chunk in chunks:
        parts = re.split(r"(?:的|与|和|及|中|里|上|下|判断|问题|方法)", chunk)
        for part in [chunk, *parts]:
            value = part.strip()
            if 2 <= len(value) <= 12 and value not in GENERIC_TERMS and value not in terms:
                terms.append(value)
    domain_markers = (
        "正方体",
        "展开图",
        "相对面",
        "折叠",
        "二次函数",
        "边界条件",
        "受力分析",
        "补集",
        "并集",
        "交集",
        "定语从句",
        "关系代词",
        "离子方程式",
        "辛亥革命",
    )
    for marker in domain_markers:
        if marker in original_text or any(marker in str(item) for item in (values or [])):
            if marker not in terms:
                terms.insert(0, marker)
    return terms[:12]


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


def question_with_options(question: DatasetQuestion) -> str:
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


def retrieval_text(question: DatasetQuestion, knowledge_names: list[str]) -> str:
    options = " ".join(f"{item.get('key', '')}. {item.get('text', '')}" for item in (question.options or []))
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
    question: DatasetQuestion
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

    def embed(self, texts: list[str]) -> tuple[list[list[float]], list[dict[int, float]]]:
        with self._lock:
            response = httpx.post(
                f"{settings.retrieval_inference_url}/embed",
                json={"texts": texts},
                timeout=300,
            )
            response.raise_for_status()
            output = response.json()
        return output["dense"], [
            {int(key): float(value) for key, value in row.items()} for row in output["sparse"]
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
        name for name, markers in STRUCTURE_MARKERS.items() if any(marker in lowered for marker in markers)
    }


def structure_similarity(left: str, right: str) -> float:
    left_features, right_features = structure_features(left), structure_features(right)
    if not left_features and not right_features:
        return 0.5
    return len(left_features & right_features) / max(1, len(left_features | right_features))


def _sparse_vector(weights: dict[int, float]) -> models.SparseVector:
    ordered = sorted(weights.items())
    return models.SparseVector(indices=[item[0] for item in ordered], values=[item[1] for item in ordered])


def _filter(subject: str, grade: str, grade_band: str) -> models.Filter:
    grade_values = {normalized_grade(grade, grade_band), grade_band}
    return models.Filter(
        must=[
            models.FieldCondition(key="subject", match=models.MatchValue(value=subject)),
            models.FieldCondition(key="usable_for_practice", match=models.MatchValue(value=True)),
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
                models.Prefetch(query=dense[0], using="dense", filter=query_filter, limit=limit),
                models.Prefetch(
                    query=_sparse_vector(sparse[0]), using="sparse", filter=query_filter, limit=limit
                ),
            ],
            query=models.RrfQuery(rrf=models.Rrf()),
            limit=limit,
            with_payload=True,
        ).points
        return dense_rows, sparse_rows, fused_rows

    dense_rows, sparse_rows, fused_rows = await asyncio.to_thread(search)
    dense_ranks = {str(row.payload["question_id"]): index + 1 for index, row in enumerate(dense_rows)}
    sparse_ranks = {str(row.payload["question_id"]): index + 1 for index, row in enumerate(sparse_rows)}
    return fused_rows, dense_ranks, sparse_ranks


async def load_candidates(
    db: AsyncSession, fused_rows: list[Any], dense_ranks: dict[str, int], sparse_ranks: dict[str, int]
) -> list[RetrievalCandidate]:
    ids = [str(row.payload["question_id"]) for row in fused_rows]
    if not ids:
        return []
    questions = {
        item.id: item for item in await db.scalars(select(DatasetQuestion).where(DatasetQuestion.id.in_(ids)))
    }
    sources = {item.id: item.key for item in await db.scalars(select(DatasetSource))}
    link_rows = (
        await db.execute(
            select(
                QuestionKnowledgeLink.dataset_question_id,
                QuestionKnowledgeLink.role,
                KnowledgePoint.id,
                KnowledgePoint.name,
            )
            .join(KnowledgePoint, KnowledgePoint.id == QuestionKnowledgeLink.knowledge_point_id)
            .where(QuestionKnowledgeLink.dataset_question_id.in_(ids))
        )
    ).all()
    links: dict[str, list[dict[str, str]]] = {}
    for question_id, role, knowledge_id, name in link_rows:
        links.setdefault(question_id, []).append({"id": knowledge_id, "name": name, "role": role})
    return [
        RetrievalCandidate(
            question=questions[question_id],
            source_dataset=sources[questions[question_id].dataset_source_id],
            knowledge_points=links.get(question_id, []),
            dense_rank=dense_ranks.get(question_id),
            sparse_rank=sparse_ranks.get(question_id),
            fusion_rank=index + 1,
            fusion_score=float(row.score),
        )
        for index, row in enumerate(fused_rows)
        if (question_id := str(row.payload["question_id"])) in questions
    ]


async def rerank_candidates(
    query_text: str, original_text: str, original_type: str, mode: str, candidates: list[RetrievalCandidate]
) -> list[RetrievalCandidate]:
    documents = [
        retrieval_text(item.question, [point["name"] for point in item.knowledge_points])
        for item in candidates
    ]
    scores = await asyncio.to_thread(bge_runtime.rerank, query_text, documents)
    original = normalize_stem(original_text)
    for item, score in zip(candidates, scores, strict=True):
        similarity = SequenceMatcher(None, original, normalize_stem(item.question.question_text)).ratio()
        structural = structure_similarity(original_text, item.question.question_text)
        item.reranker_score = score
        item.similarity_to_original = similarity
        item.structure_similarity = structural
        same_type = item.question.question_type == original_type
        hybrid_rank_signal = (0.12 / math.sqrt(item.sparse_rank) if item.sparse_rank else 0.0) + (
            0.06 / math.sqrt(item.dense_rank) if item.dense_rank else 0.0
        )
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
    knowledge_points: list[Any] = candidate.knowledge_points or list(question.knowledge_points or [])
    return VariantReference(
        id=question.id,
        question_text=question_with_options(question),
        answer=answer_text(question.answer),
        solution=question.solution or "",
        question_type=question.question_type,
        knowledge_points=knowledge_points,
        score=candidate.mode_score,
    )


async def retrieve_variant_references(
    db: AsyncSession,
    *,
    subject: str,
    grade: str,
    question_type: str,
    knowledge_points: list[Any] | None,
    original_text: str,
    transfer_type: str,
    excluded_question_ids: set[str] | None = None,
    limit: int = 5,
) -> list[VariantReference]:
    """Retrieve tutor transfer references through the shared BGE/Qdrant/reranker path."""
    mode = "reinforce" if transfer_type == "near" else "variation"
    terms = concept_terms(knowledge_points, original_text)
    query_text = "\n".join(
        filter(
            None,
            (
                f"学科：{subject}",
                f"年级：{grade}",
                original_text,
                "知识点：" + "、".join(str(item) for item in (knowledge_points or terms)),
                "要求：保持核心知识、题型和难度"
                if mode == "reinforce"
                else "要求：保留核心知识，但改变题型、表达或场景",
            ),
        )
    )
    fused, dense_ranks, sparse_ranks = await hybrid_ids(
        query_text,
        subject,
        grade,
        "高中" if grade.startswith("高") or grade == "高中" else "初中",
    )
    candidates = await load_candidates(db, fused, dense_ranks, sparse_ranks)
    excluded_ids = excluded_question_ids or set()
    original = normalize_stem(original_text)
    filtered = [
        item
        for item in candidates
        if item.question.id not in excluded_ids and normalize_stem(item.question.question_text) != original
    ]
    ranked = await rerank_candidates(query_text, original_text, question_type, mode, filtered)
    return [variant_reference(item) for item in ranked[:limit]]
