"""Read-only, size-limited cognition graph from existing evidence and mappings."""

import re

from fastapi import APIRouter, Request
from learning_core.services.academic_text import academic_summary

from .insights import METHODS, mistake_label
from .protocol import ApiError, envelope
from .question_data import select_rows
from .retrieval import answer_text

router = APIRouter(prefix="/api/v1/analytics")


def days_value(request, maximum):
    raw = request.query_params.get("days", "90").strip()
    if not re.fullmatch(r"[+-]?[0-9]+", raw):
        raise ApiError(422, "days 必须是整数")
    days = int(raw)
    if not 1 <= days <= maximum:
        raise ApiError(422, "days 超出允许范围")
    return days


def display_key(text, id):
    compact = "".join(char for char in text if not char.isspace())
    return (
        "".join(char for char in compact if char not in "，。？?：:").lower()
        if compact
        else "pending:" + id
    )


def method_label(value):
    return METHODS.get(value, value) if value else "尚未确定"


def percent(value):
    scaled = float(value) * 100
    lower = int(scaled)
    fraction = scaled - lower
    return lower + 1 if fraction > 0.5 or fraction == 0.5 and lower % 2 != 0 else lower


def learner_text(value):
    text = value or "根据最近的学习情况更新"
    for old, new in [
        ("教回", "讲解思路"),
        ("近迁移", "相似题"),
        ("远迁移", "综合题"),
        ("提示等级", "使用提示"),
    ]:
        text = text.replace(old, new)
    return text


def topic(question):
    value = question.get("question_type") or "错题学习"
    if question.get("knowledge_points"):
        value = answer_text(question["knowledge_points"][0]).strip()
    return {
        "fill_blank": "填空题",
        "choice": "单选题",
        "multiple_choice": "多选题",
        "calculation": "计算题",
        "proof": "证明题",
        "subjective": "主观题",
        "other": "其他题型",
        "": "错题学习",
    }.get(value, value)


@router.get("/cognition-graph")
def graph(request: Request):
    days, subject = days_value(request, 3650), request.query_params.get("subject", "")
    service = request.app.state.questions
    with service.database.session() as db, db.begin():
        owner = service.user(request, db).id
        all_updates = select_rows(
            db,
            "cognitive_updates",
            "SELECT * FROM cognitive_updates WHERE user_id=? AND created_at>=TIMESTAMPADD(DAY,?,UTC_TIMESTAMP(6)) AND entity_type<>'note_evidence' ORDER BY created_at,id",
            [owner, -days],
        )
        all_mappings = select_rows(
            db,
            "user_question_knowledge_links",
            "SELECT * FROM user_question_knowledge_links WHERE user_id=? AND created_at>=TIMESTAMPADD(DAY,?,UTC_TIMESTAMP(6)) ORDER BY created_at,id",
            [owner, -days],
        )
        referenced = {
            item.get("question_id")
            for item in [*all_updates, *all_mappings]
            if item.get("question_id")
        }
        questions, seen = {}, set()
        for q in select_rows(
            db,
            "questions",
            "SELECT * FROM questions WHERE user_id=? AND status<>'archived' ORDER BY updated_at DESC,id DESC",
            [owner],
        ):
            if q["id"] not in referenced:
                continue
            key = display_key(q["question_text"], q["id"])
            if key in seen:
                continue
            seen.add(key)
            if not subject or q["subject"] == subject:
                questions[q["id"]] = q
        updates = [
            item
            for item in all_updates
            if not item.get("question_id") or item["question_id"] in questions
        ]
        mappings = [
            item
            for item in all_mappings
            if not subject or item["question_id"] in questions
        ]
        cards, labels = {}, {}
        for card in select_rows(
            db, "knowledge_points", "SELECT * FROM knowledge_points ORDER BY id"
        ):
            if subject and card["subject"] != subject:
                continue
            cards[card["id"]] = card
            for key in [card["name"], card["code"]]:
                labels[(card["subject"], key)] = card
        topics = {}
        for item in updates:
            if (
                item.get("question_id")
                and item["entity_type"] == "mastery"
                and item["entity_key"]
            ):
                topics.setdefault(item["question_id"], item["entity_key"])
        for mapping in mappings:
            card = cards.get(mapping["knowledge_point_id"])
            if card and (
                mapping["role"] == "primary" or mapping["question_id"] not in topics
            ):
                topics[mapping["question_id"]] = card["name"]
        nodes, edges, mistakes = {}, [], {}

        def node(id, name, category, value, **extra):
            nodes[id] = {
                "id": id,
                "name": name,
                "category": category,
                "value": value,
                **extra,
            }

        def connect(source, target, relation):
            if source in nodes and target in nodes:
                edges.append({"source": source, "target": target, "relation": relation})

        for item in select_rows(
            db,
            "mastery_states",
            "SELECT * FROM mastery_states WHERE user_id=? ORDER BY updated_at,id",
            [owner],
        ):
            row_subject, point = item["subject"], item["knowledge_point"]
            if subject and row_subject != subject:
                continue
            card = labels.get((row_subject, point))
            if subject and not card:
                continue
            key = card["code"] if card else point
            node(
                f"knowledge:{row_subject}:{key}",
                point,
                "knowledge",
                percent(item["mastery_score"]),
                subject=row_subject,
                detail=learner_text(item.get("update_reason")),
                confidence=item["confidence"],
            )
        for item in select_rows(
            db,
            "misconception_states",
            "SELECT * FROM misconception_states WHERE user_id=? ORDER BY probability DESC,id",
            [owner],
        ):
            row_subject = item["subject"]
            if subject and row_subject != subject:
                continue
            label = mistake_label(item["label"])
            id = f"misconception:{row_subject}:{label}"
            mistakes[(row_subject, item["code"])] = id
            if id in nodes:
                continue
            node(
                id,
                label,
                "misconception",
                percent(item["probability"]),
                subject=row_subject,
                status=item["status"],
                detail=f"已参考 {item['evidence_count']} 次学习记录；有效方法："
                + method_label(item.get("successful_strategy")),
            )
            strategies = set()
            for field in ["successful_strategy", "failed_strategy"]:
                strategy = item.get(field) or ""
                if not strategy or strategy in strategies:
                    continue
                strategies.add(strategy)
                strategy_id = "strategy:" + strategy
                node(
                    strategy_id,
                    method_label(strategy),
                    "strategy",
                    35,
                    detail="学习过程中使用过的方法",
                )
                connect(
                    id,
                    strategy_id,
                    "有效策略"
                    if strategy == item.get("successful_strategy")
                    else "待改进策略",
                )
        for id, q in questions.items():
            name = topics.get(id, topic(q))
            title = (
                "相关错题" if name in ["错题学习", "其他题型"] else name + "相关错题"
            )
            node(
                "question:" + id,
                title,
                "question",
                28,
                subject=q["subject"],
                detail=academic_summary(q["question_text"], 120),
                question_id=id,
            )
        for mapping in mappings:
            source = "question:" + mapping["question_id"]
            card = cards.get(mapping["knowledge_point_id"])
            if source not in nodes or not card:
                continue
            target = f"knowledge:{card['subject']}:{card['code']}"
            if target not in nodes:
                node(
                    target,
                    card["name"],
                    "knowledge",
                    45,
                    subject=card["subject"],
                    detail="由你的错题映射到共享知识点；依据："
                    + (mapping.get("evidence_text") or ""),
                    confidence=mapping["confidence"],
                )
            connect(
                source,
                target,
                "涉及知识点" if mapping["role"] == "primary" else "需要先修",
            )
        for item in updates:
            q = questions.get(item.get("question_id"))
            if not q:
                continue
            source = "question:" + q["id"]
            if item["entity_type"] == "mastery":
                target = next(
                    (
                        id
                        for id, value in nodes.items()
                        if value["category"] == "knowledge"
                        and value.get("subject") == q["subject"]
                        and value["name"] == item["entity_key"]
                    ),
                    None,
                )
                if target:
                    connect(source, target, "提供掌握证据")
            elif item["entity_type"] == "misconception":
                target = mistakes.get((q["subject"], item["entity_key"]))
                if target:
                    connect(source, target, "暴露错因")
        for relation in select_rows(
            db, "knowledge_relations", "SELECT * FROM knowledge_relations ORDER BY id"
        ):
            source, target = (
                cards.get(relation["source_id"]),
                cards.get(relation["target_id"]),
            )
            if source and target:
                connect(
                    f"knowledge:{source['subject']}:{source['code']}",
                    f"knowledge:{target['subject']}:{target['code']}",
                    relation["relation_type"],
                )
        visible = []
        for kind, maximum in [
            ("knowledge", 8),
            ("question", 4),
            ("misconception", 2),
            ("strategy", 2),
        ]:
            visible.extend(
                sorted(
                    (node for node in nodes.values() if node["category"] == kind),
                    key=lambda node: (-node["value"], node["name"]),
                )[:maximum]
            )
        ids = {node["id"] for node in visible}
        return envelope(
            request,
            {
                "nodes": visible,
                "links": [
                    edge
                    for edge in edges
                    if edge["source"] in ids and edge["target"] in ids
                ],
                "categories": ["knowledge", "misconception", "question", "strategy"],
                "filters": {
                    "subject": subject if "subject" in request.query_params else None,
                    "days": days,
                },
                "evidence_count": len(updates),
                "personal_mapping_count": len(mappings),
                "mapped_question_count": len(
                    {item["question_id"] for item in mappings}
                ),
            },
        )


@router.get("/error-sources")
def error_sources(request: Request):
    days, subject = days_value(request, 365), request.query_params.get("subject", "")
    service = request.app.state.questions
    with service.database.session() as db, db.begin():
        owner = service.user(request, db).id
        questions = select_rows(
            db,
            "questions",
            "SELECT q.* FROM questions q JOIN diagnoses d ON d.id=(SELECT d2.id FROM diagnoses d2 WHERE d2.question_id=q.id ORDER BY d2.created_at DESC,d2.id DESC LIMIT 1) WHERE q.user_id=? AND q.status<>'archived' AND q.confirmed=1 AND (?='' OR q.subject=?) AND d.created_at>=TIMESTAMPADD(DAY,?,UTC_TIMESTAMP(6)) ORDER BY q.updated_at DESC,q.id DESC LIMIT 201",
            [owner, subject, subject, -days],
        )
        sources, seen = [], set()
        for q in questions[:200]:
            key = display_key(q["question_text"], q["id"])
            if key in seen:
                continue
            seen.add(key)
            diagnosis = select_rows(
                db,
                "diagnoses",
                "SELECT * FROM diagnoses WHERE question_id=? ORDER BY created_at DESC,id DESC LIMIT 1",
                [q["id"]],
            )
            plans = select_rows(
                db,
                "review_plans",
                "SELECT * FROM review_plans WHERE user_id=? AND question_id=? AND status='pending' AND due_at<TIMESTAMP(DATE(UTC_TIMESTAMP()+INTERVAL 8 HOUR))+INTERVAL 16 HOUR ORDER BY due_at,id LIMIT 1",
                [owner, q["id"]],
            )
            sources.append(
                {
                    **{
                        key: q[key]
                        for key in [
                            "id",
                            "subject",
                            "grade",
                            "question_text",
                            "knowledge_points",
                            "updated_at",
                        ]
                    },
                    "diagnosis": diagnosis[0] if diagnosis else None,
                    "due_review_id": plans[0]["id"] if plans else None,
                }
            )
        return envelope(
            request,
            {
                "sources": sources,
                "days": days,
                "limit": 200,
                "truncated": len(questions) > 200,
            },
        )
