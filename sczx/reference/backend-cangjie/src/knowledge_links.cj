package zhiwei

import std.collection.*
import stdx.encoding.json.*

func knowledgeLabel(text: String): String {
    let result = StringBuilder()
    for (rune in text.toAsciiLower().runes()) {
        if ((rune >= r'a' && rune <= r'z') || (rune >= r'0' && rune <= r'9') || (rune >= r'\u{4e00}' && rune <= r'\u{9fff}')) { result.append(rune) }
    }
    return result.toString()
}

func syncKnowledgeLinks(db: Database, question: JsonObject, analysis: JsonObject, diagnosis!: Option<JsonObject> = None): Unit {
    let cards = db.query("SELECT * FROM knowledge_points WHERE subject = ? ORDER BY id", [Some(jsonText(question,"subject"))]).rows
    let selected = HashMap<String, JsonObject>()
    let sources = ArrayList<(JsonValue,String)>([(question["knowledge_points"], "primary"), (analysis["knowledge_points"], "primary"), (analysis["prerequisites"], "prerequisite")])
    if (let Some(item) <- diagnosis) { sources.add((item["missing_prerequisites"],"prerequisite")) }
    for ((values, role) in sources) {
        for (item in (values as JsonArray).getOrThrow().getItems()) {
            let phrase = (item as JsonString).getOrThrow().getValue()
            let needle = knowledgeLabel(phrase)
            if (runeCount(needle) < 2) { continue }
            var bestId = ""
            var bestScore = 0.0
            var bestLength: Int64 = -1
            for (row in cards) {
                let card = rowJson("knowledge_points",row)
                let names = ArrayList<String>([jsonText(card,"name"),jsonText(card,"code")])
                if (let Some(content) <- (card["content"] as JsonObject)) {
                    if (let Some(aliases) <- content.get("related_knowledge")) {
                        if (let Some(array) <- (aliases as JsonArray)) {
                            for (alias in array.getItems()) {
                                names.add(if (let Some(text) <- (alias as JsonString)) { text.getValue() } else { alias.toString() })
                            }
                        }
                    }
                }
                var score = 0.0
                for (name in names) {
                    let normalized = knowledgeLabel(name)
                    if (normalized == needle) { score = 1.0; break }
                    if (runeCount(normalized) >= 2 && (normalized.contains(needle) || needle.contains(normalized))) { score = 0.86 }
                }
                let length = runeCount(knowledgeLabel(jsonText(card,"name")))
                if (score > 0.0 && (score > bestScore || (score == bestScore && length > bestLength))) {
                    bestId = jsonText(card,"id"); bestScore = score; bestLength = length
                }
            }
            if (bestId.isEmpty()) { continue }
            if (let Some(old) <- selected.get(bestId)) {
                let oldRole = jsonText(old,"role")
                if ((oldRole == "primary" && role == "prerequisite") || (oldRole == role && editNumber(old["confidence"]) >= bestScore)) { continue }
            }
            let link = JsonObject()
            link.put("role",JsonString(role)); link.put("confidence",JsonFloat(bestScore))
            link.put("method",JsonString(if (bestScore == 1.0) { "exact_label" } else { "contained_label" }))
            link.put("evidence",JsonString(shortTitle(phrase,255)))
            selected[bestId] = link
        }
    }
    for ((cardId,link) in selected) {
        db.query("INSERT INTO user_question_knowledge_links (id,user_id,question_id,knowledge_point_id,role,confidence,mapping_method,evidence_text,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,UTC_TIMESTAMP(),UTC_TIMESTAMP()) ON DUPLICATE KEY UPDATE role=VALUES(role),confidence=VALUES(confidence),mapping_method=VALUES(mapping_method),evidence_text=VALUES(evidence_text),updated_at=UTC_TIMESTAMP()", [Some(newId()),Some(jsonText(question,"user_id")),Some(jsonText(question,"id")),Some(cardId),Some(jsonText(link,"role")),Some(link["confidence"].toString()),Some(jsonText(link,"method")),Some(jsonText(link,"evidence"))])
    }
}
