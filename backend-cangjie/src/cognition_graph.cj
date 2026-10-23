package zhiwei

import std.collection.*
import stdx.encoding.json.*
import stdx.net.http.*

// Only these four node kinds can be built. Their display budgets and wire labels
// travel together, rather than being independently writable JSON strings.
enum CognitionKind {
    Knowledge | Question | Misconception | Strategy
    func label(): String {
        match (this) {
            case Knowledge => "knowledge"
            case Question => "question"
            case Misconception => "misconception"
            case Strategy => "strategy"
        }
    }
    func limit(): Int64 {
        match (this) { case Knowledge => 8; case Question => 4; case _ => 2 }
    }
}

class CognitionNode {
    let id: String
    let kind: CognitionKind
    let value: JsonObject
    init(id: String, name: String, kind: CognitionKind, score: Int64) {
        this.id = id; this.kind = kind; value = JsonObject()
        value.put("id",JsonString(id)); value.put("name",JsonString(name)); value.put("category",JsonString(kind.label())); value.put("value",JsonInt(score))
    }
    func text(key: String, text: String): Unit { value.put(key,JsonString(text)) }
}

class CognitionEdge {
    let source: String
    let target: String
    let relation: String
    init(source: String, target: String, relation: String) { this.source=source; this.target=target; this.relation=relation }
    func json(): JsonObject {
        let value=JsonObject(); value.put("source",JsonString(source)); value.put("target",JsonString(target)); value.put("relation",JsonString(relation)); return value
    }
}

class CognitionGraph {
    let nodes = HashMap<String,CognitionNode>()
    let edges = ArrayList<CognitionEdge>()
    func connect(source: String, target: String, relation: String): Unit {
        if (nodes.contains(source) && nodes.contains(target)) { edges.add(CognitionEdge(source,target,relation)) }
    }
    func visible(): (JsonArray,JsonArray) {
        let visible=HashSet<String>(); let result=JsonArray(); let links=JsonArray()
        for (kind in [CognitionKind.Knowledge,CognitionKind.Question,CognitionKind.Misconception,CognitionKind.Strategy]) {
            for (_ in 0..kind.limit()) {
                var best: Option<CognitionNode> = None
                for ((id,node) in nodes) {
                    if (node.kind.label()!=kind.label() || visible.contains(id)) { continue }
                    if (let Some(previous) <- best) {
                        let score=tutorNumber(node.value,"value"); let old=tutorNumber(previous.value,"value")
                        if (score<old || (score==old && jsonText(node.value,"name")>=jsonText(previous.value,"name"))) { continue }
                    }
                    best=Some(node)
                }
                if (let Some(node) <- best) { visible.add(node.id); result.getItems().add(node.value) } else { break }
            }
        }
        for (edge in edges) {
            if (visible.contains(edge.source) && visible.contains(edge.target)) { links.getItems().add(edge.json()) }
        }
        return (result,links)
    }
}

func cognitionPercent(value: Float64): Int64 {
    let scaled=value*100.0; let lower=Int64(scaled); let fraction=scaled-Float64(lower)
    return if (fraction>0.5 || (fraction==0.5 && lower%2!=0)) { lower+1 } else { lower }
}

func graphTopic(question: JsonObject): String {
    var raw=tutorText(question,"question_type")
    if (raw.isEmpty()) { raw="错题学习" }
    let points=tutorArray(question,"knowledge_points")
    if (!points.getItems().isEmpty()) { raw=stripWhitespace(tutorAnswerText(points.getItems()[0])) }
    match (raw) {
        case "fill_blank" => "填空题"
        case "choice" => "单选题"
        case "multiple_choice" => "多选题"
        case "calculation" => "计算题"
        case "proof" => "证明题"
        case "subjective" => "主观题"
        case "other" => "其他题型"
        case "" => "错题学习"
        case _ => raw
    }
}

func readCognitionGraph(context: HttpContext, accounts: Accounts): JsonValue {
    requireMethod(context,"GET")
    let form=insightQuery(context); let days=insightDays(form,90,3650); let subject=queryLast(form,"subject")
    try (db=Database.fromEnvironment()) {
        let user=accounts.currentUser(context,db)
        return db.transaction<JsonValue>({ tx =>
            let allUpdates=tx.query("SELECT * FROM cognitive_updates WHERE user_id=? AND created_at>=TIMESTAMPADD(DAY,?,UTC_TIMESTAMP(6)) AND entity_type<>'note_evidence' ORDER BY created_at,id",[user["id"],Some((-days).toString())]).rows
            let allMappings=tx.query("SELECT * FROM user_question_knowledge_links WHERE user_id=? AND created_at>=TIMESTAMPADD(DAY,?,UTC_TIMESTAMP(6)) ORDER BY created_at,id",[user["id"],Some((-days).toString())]).rows
            let referenced=HashSet<String>()
            for (row in allUpdates) { if (let Some(id) <- row["question_id"]) { if (!id.isEmpty()) { referenced.add(id) } } }
            for (row in allMappings) { referenced.add(rowText(row,"question_id")) }
            let questions=HashMap<String,JsonObject>(); let seen=HashSet<String>()
            for (row in tx.query("SELECT * FROM questions WHERE user_id=? AND status<>'archived' ORDER BY updated_at DESC,id DESC",[user["id"]]).rows) {
                let id=rowText(row,"id"); if (!referenced.contains(id)) { continue }
                let key=questionDisplayKey(rowText(row,"question_text"),id)
                if (seen.contains(key)) { continue }; seen.add(key)
                if (subject.isEmpty() || rowText(row,"subject")==subject) { questions[id]=rowJson("questions",row) }
            }
            let updates=ArrayList<JsonObject>(); let mappings=ArrayList<JsonObject>(); let mappedQuestions=HashSet<String>()
            for (row in allUpdates) {
                let id=row["question_id"] ?? ""
                if (id.isEmpty() || questions.contains(id)) { updates.add(rowJson("cognitive_updates",row)) }
            }
            for (row in allMappings) {
                let id=rowText(row,"question_id")
                if (subject.isEmpty() || questions.contains(id)) { mappings.add(rowJson("user_question_knowledge_links",row)); mappedQuestions.add(id) }
            }
            let cardsById=HashMap<String,JsonObject>(); let cardsByLabel=HashMap<String,JsonObject>()
            for (row in tx.query("SELECT * FROM knowledge_points ORDER BY id").rows) {
                let card=rowJson("knowledge_points",row); let cardSubject=jsonText(card,"subject")
                if (!subject.isEmpty() && cardSubject!=subject) { continue }
                cardsById[jsonText(card,"id")]=card
                cardsByLabel[insightPair(cardSubject,jsonText(card,"name"))]=card
                cardsByLabel[insightPair(cardSubject,jsonText(card,"code"))]=card
            }
            let topics=HashMap<String,String>()
            for (update in updates) {
                let id=tutorText(update,"question_id"); let key=tutorText(update,"entity_key")
                if (!id.isEmpty() && tutorText(update,"entity_type")=="mastery" && !key.isEmpty() && !topics.contains(id)) { topics[id]=key }
            }
            for (mapping in mappings) {
                if (let Some(card) <- cardsById.get(jsonText(mapping,"knowledge_point_id"))) {
                    let id=jsonText(mapping,"question_id")
                    if (jsonText(mapping,"role")=="primary" || !topics.contains(id)) { topics[id]=jsonText(card,"name") }
                }
            }
            let graph=CognitionGraph(); let mistakesByCode=HashMap<String,String>()
            for (row in tx.query("SELECT * FROM mastery_states WHERE user_id=? ORDER BY updated_at,id",[user["id"]]).rows) {
                let item=rowJson("mastery_states",row); let rowSubject=jsonText(item,"subject"); let point=jsonText(item,"knowledge_point")
                if (!subject.isEmpty() && rowSubject!=subject) { continue }
                let card=cardsByLabel.get(insightPair(rowSubject,point))
                if (!subject.isEmpty() && card.isNone()) { continue }
                let key=if (let Some(found) <- card) { jsonText(found,"code") } else { point }
                let node=CognitionNode("knowledge:${rowSubject}:${key}",point,CognitionKind.Knowledge,cognitionPercent(editNumber(item["mastery_score"])))
                node.text("subject",rowSubject); node.text("detail",insightLearnerText(tutorText(item,"update_reason"))); node.value.put("confidence",item["confidence"]); graph.nodes[node.id]=node
            }
            for (row in tx.query("SELECT * FROM misconception_states WHERE user_id=? ORDER BY probability DESC,id",[user["id"]]).rows) {
                let item=rowJson("misconception_states",row); let rowSubject=jsonText(item,"subject")
                if (!subject.isEmpty() && rowSubject!=subject) { continue }
                let label=canonicalMistakeLabel(jsonText(item,"label")); let id="misconception:${rowSubject}:${label}"
                mistakesByCode[insightPair(rowSubject,jsonText(item,"code"))]=id
                if (graph.nodes.contains(id)) { continue }
                let node=CognitionNode(id,label,CognitionKind.Misconception,cognitionPercent(editNumber(item["probability"])))
                node.text("subject",rowSubject); node.text("status",jsonText(item,"status"))
                node.text("detail","已参考 ${tutorNumber(item,'evidence_count')} 次学习记录；有效方法："+learningMethodLabel(tutorText(item,"successful_strategy")))
                graph.nodes[id]=node
                let strategies=HashSet<String>()
                for (field in ["successful_strategy","failed_strategy"]) {
                    let strategy=tutorText(item,field)
                    if (strategy.isEmpty() || strategies.contains(strategy)) { continue }; strategies.add(strategy)
                    let strategyNode=CognitionNode("strategy:${strategy}",learningMethodLabel(strategy),CognitionKind.Strategy,35)
                    strategyNode.text("detail","学习过程中使用过的方法"); graph.nodes[strategyNode.id]=strategyNode
                    graph.connect(id,strategyNode.id,if (strategy==tutorText(item,"successful_strategy")) { "有效策略" } else { "待改进策略" })
                }
            }
            for ((id,question) in questions) {
                let topic=topics.get(id) ?? graphTopic(question)
                let title=if (topic=="错题学习" || topic=="其他题型") { "相关错题" } else { topic+"相关错题" }
                let node=CognitionNode("question:${id}",title,CognitionKind.Question,28)
                node.text("subject",jsonText(question,"subject")); node.text("detail",academicSummary(jsonText(question,"question_text"),120)); node.text("question_id",id); graph.nodes[node.id]=node
            }
            for (mapping in mappings) {
                let questionNode="question:"+jsonText(mapping,"question_id")
                if (!graph.nodes.contains(questionNode)) { continue }
                if (let Some(card) <- cardsById.get(jsonText(mapping,"knowledge_point_id"))) {
                    let id="knowledge:"+jsonText(card,"subject")+":"+jsonText(card,"code")
                    if (!graph.nodes.contains(id)) {
                        let node=CognitionNode(id,jsonText(card,"name"),CognitionKind.Knowledge,45)
                        node.text("subject",jsonText(card,"subject")); node.text("detail","由你的错题映射到共享知识点；依据："+tutorText(mapping,"evidence_text")); node.value.put("confidence",mapping["confidence"]); graph.nodes[id]=node
                    }
                    graph.connect(questionNode,id,if (jsonText(mapping,"role")=="primary") { "涉及知识点" } else { "需要先修" })
                }
            }
            for (update in updates) {
                let questionId=tutorText(update,"question_id"); let questionNode="question:${questionId}"
                if (let Some(question) <- questions.get(questionId)) {
                    let rowSubject=jsonText(question,"subject"); let key=jsonText(update,"entity_key")
                    if (jsonText(update,"entity_type")=="mastery") {
                        for ((id,node) in graph.nodes) {
                            if (node.kind.label()=="knowledge" && tutorText(node.value,"subject")==rowSubject && jsonText(node.value,"name")==key) { graph.connect(questionNode,id,"提供掌握证据"); break }
                        }
                    } else if (jsonText(update,"entity_type")=="misconception") {
                        if (let Some(target) <- mistakesByCode.get(insightPair(rowSubject,key))) { graph.connect(questionNode,target,"暴露错因") }
                    }
                }
            }
            for (row in tx.query("SELECT * FROM knowledge_relations ORDER BY id").rows) {
                if (let Some(source) <- cardsById.get(rowText(row,"source_id"))) {
                    if (let Some(target) <- cardsById.get(rowText(row,"target_id"))) {
                        graph.connect("knowledge:"+jsonText(source,"subject")+":"+jsonText(source,"code"),"knowledge:"+jsonText(target,"subject")+":"+jsonText(target,"code"),rowText(row,"relation_type"))
                    }
                }
            }
            let (nodes,links)=graph.visible(); let filters=JsonObject()
            filters.put("subject",if (form.getAll("subject").isEmpty()) { JsonNull() } else { JsonString(subject) }); filters.put("days",JsonInt(days))
            let categories=JsonArray(); for (kind in [CognitionKind.Knowledge,CognitionKind.Misconception,CognitionKind.Question,CognitionKind.Strategy]) { categories.getItems().add(JsonString(kind.label())) }
            let result=JsonObject(); result.put("nodes",nodes); result.put("links",links); result.put("categories",categories); result.put("filters",filters)
            result.put("evidence_count",JsonInt(updates.size)); result.put("personal_mapping_count",JsonInt(mappings.size)); result.put("mapped_question_count",JsonInt(mappedQuestions.size))
            return result
        })
    }
    throw ApiError(503,"数据库暂时不可用")
}
