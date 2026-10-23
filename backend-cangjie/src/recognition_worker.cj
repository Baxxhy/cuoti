package zhiwei

import std.collection.*
import std.convert.*
import stdx.encoding.base64.*
import stdx.encoding.json.*

func recognitionFingerprint(row: HashMap<String, Option<String>>): String {
    let value = JsonArray()
    for (key in ["question_text", "student_answer", "subject", "grade", "formulas", "options", "question_type", "knowledge_points", "confirmed"]) {
        value.getItems().add(if (let Some(text) <- row[key]) { JsonString(text) } else { JsonNull() })
    }
    return sha256(value.toString().toArray())
}

func nullableJsonText(object: JsonObject, key: String): Option<String> {
    if (let Some(value) <- object.get(key)) {
        if (value is JsonNull) { return None }
        return Some((value as JsonString).getOrThrow().getValue())
    }
    return None
}

func collapseWhitespace(value: String): String {
    let result = StringBuilder()
    var space = false
    var hasText = false
    for (rune in value.runes()) {
        let one = StringBuilder(); one.append(rune)
        if (pythonWhitespace.contains(one.toString())) { space = hasText }
        else {
            if (space) { result.append(" ") }
            result.append(rune); space = false; hasText = true
        }
    }
    return result.toString()
}

// Display summaries must never cut a TeX delimiter or a mathematical step.
func academicSummary(value: String, limit: Int64): String {
    return if (value.contains("$") || value.contains("\\")) { value } else { shortTitle(value, limit) }
}

func shortTitle(value: String, limit: Int64): String {
    let builder = StringBuilder()
    var count: Int64 = 0
    var mathSeen = false
    var prefix = ""
    var truncated = false
    for (rune in value.runes()) {
        if (count >= limit) { truncated = true; break }
        let one = StringBuilder(); one.append(rune)
        if (!mathSeen && (one.toString() == "$" || one.toString() == "\\")) {
            mathSeen = true; prefix = builder.toString()
        }
        builder.append(rune); count++
    }
    if (truncated && mathSeen) { return if (stripWhitespace(prefix).isEmpty()) { "题目详情" } else { prefix + "…" } }
    return if (count == 0) { "待确认错题" } else { builder.toString() }
}

func finishRecognitionFailure(jobId: String, questionId: String, fingerprint: String, recovered!: Bool = false): Unit {
    try (db = Database.fromEnvironment()) {
        db.transaction<Unit>({ tx =>
            let questions = tx.query("SELECT * FROM questions WHERE id = ? FOR UPDATE", [Some(questionId)]).rows
            let jobs = tx.query("SELECT status FROM processing_jobs WHERE id = ? AND question_id = ? FOR UPDATE", [Some(jobId), Some(questionId)]).rows
            if (questions.isEmpty() || jobs.isEmpty()) { return }
            let status = rowText(jobs[0], "status")
            if (status != "pending" && status != "running") { return }
            let cancelled = rowText(questions[0], "status") == "archived" || (!fingerprint.isEmpty() && recognitionFingerprint(questions[0]) != fingerprint)
            tx.query("UPDATE processing_jobs SET status = ?, error = ?, updated_at = UTC_TIMESTAMP() WHERE id = ?",
                [Some(if (cancelled) { "cancelled" } else { "failed" }), Some(if (cancelled) { "题目已修改或归档，识别结果未应用" } else if (recovered) { "识别任务因服务重启中断，请重试" } else { "识别暂时未完成，请检查图片后重试" }), Some(jobId)])
            let questionStatus = rowText(questions[0], "status")
            if (!cancelled && (!recovered || questionStatus == "processing" || questionStatus == "pending" || questionStatus == "awaiting_crop")) {
                tx.query("UPDATE questions SET status = 'partial', updated_at = UTC_TIMESTAMP() WHERE id = ?", [Some(questionId)])
            }
            ()
        })
    } catch (_: Exception) { /* Startup recovery handles unavailable database failures. */ }
}

public func runRecognition(jobId: String, questionId: String, imagePath: String, requireCrop!: Bool = false): Unit {
    let files = ArrayList<String>()
    var committed = false
    var fingerprint = ""
    try (db = Database.fromEnvironment()) {
        let started = db.transaction<Option<String>>({ tx =>
            let questions = tx.query("SELECT * FROM questions WHERE id = ? FOR UPDATE", [Some(questionId)]).rows
            let jobs = tx.query("SELECT status FROM processing_jobs WHERE id = ? AND question_id = ? FOR UPDATE", [Some(jobId), Some(questionId)]).rows
            if (questions.isEmpty() || jobs.isEmpty() || rowText(jobs[0], "status") != "pending") { return None }
            if (rowText(questions[0], "status") == "archived") {
                tx.query("UPDATE processing_jobs SET status = 'cancelled', error = '题目已归档', updated_at = UTC_TIMESTAMP() WHERE id = ?", [Some(jobId)])
                return None
            }
            let sources = tx.query("SELECT id FROM question_assets WHERE question_id = ? AND path = ? AND kind = ?", [Some(questionId), Some(imagePath), Some(if (requireCrop) { "crop" } else { "original" })]).rows
            if (sources.isEmpty()) { throw ApiError(422, "识别图片不存在") }
            tx.query("UPDATE processing_jobs SET status = 'running', progress = 15, error = NULL, updated_at = UTC_TIMESTAMP() WHERE id = ?", [Some(jobId)])
            return Some(recognitionFingerprint(questions[0]))
        })
        if (started.isNone()) { return }
        let expected = started.getOrThrow()
        fingerprint = expected
        let input = JsonObject()
        input.put("operation", JsonString("preprocess"))
        input.put("image_base64", JsonString(toBase64String(readMedia(imagePath))))
        let prepared = algorithmCompute(input)
        db.query("UPDATE processing_jobs SET progress = 45, updated_at = UTC_TIMESTAMP() WHERE id = ? AND status = 'running'", [Some(jobId)])
        input.put("operation", JsonString("recognize"))
        let computed = algorithmCompute(input)
        let recognition = (computed["recognition"] as JsonObject).getOrThrow()
        let assets = ArrayList<JsonObject>()
        for (collection in [(prepared["assets"] as JsonArray).getOrThrow(), (computed["assets"] as JsonArray).getOrThrow()]) {
            for (item in collection.getItems()) {
                let asset = (item as JsonObject).getOrThrow()
                let kind = jsonText(asset, "kind")
                if (!(kind == "clean" || kind == "red_mask" || kind == "overlay" || kind == "question_figure" || kind == "student_working_figure" || kind == "teacher_annotation_region")) { throw ApiError(503, "图片结果类型不正确") }
                let path = "uploads/${questionId}/derived/" + newId() + if (kind == "red_mask") { ".png" } else { ".jpg" }
                writeMedia(path, algorithmImage(asset))
                files.add(path)
                asset.put("path", JsonString(path))
                assets.add(asset)
            }
        }
        committed = db.transaction<Bool>({ tx =>
            let questions = tx.query("SELECT * FROM questions WHERE id = ? FOR UPDATE", [Some(questionId)]).rows
            let jobs = tx.query("SELECT status FROM processing_jobs WHERE id = ? AND question_id = ? FOR UPDATE", [Some(jobId), Some(questionId)]).rows
            if (questions.isEmpty() || jobs.isEmpty() || rowText(jobs[0], "status") != "running") { return false }
            if (rowText(questions[0], "status") == "archived" || recognitionFingerprint(questions[0]) != expected) {
                tx.query("UPDATE processing_jobs SET status = 'cancelled', error = '题目已修改或归档，识别结果未应用', updated_at = UTC_TIMESTAMP() WHERE id = ?", [Some(jobId)])
                return false
            }
            invalidateQuestionLearning(tx, questionId)
            tx.query("DELETE FROM teacher_marks WHERE question_id = ?", [Some(questionId)])
            tx.query("DELETE FROM question_assets WHERE question_id = ? AND kind IN ('question_figure','student_working_figure','teacher_annotation_region')", [Some(questionId)])
            for (asset in assets) {
                tx.query("INSERT INTO question_assets (id,question_id,kind,path,sha256,role,bbox,description,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,UTC_TIMESTAMP(),UTC_TIMESTAMP())",
                    [Some(newId()), Some(questionId), Some(jsonText(asset, "kind")), Some(jsonText(asset, "path")), Some(jsonText(asset, "sha256")), nullableJsonText(asset, "role"), Some((asset.get("bbox") ?? JsonArray()).toString()), nullableJsonText(asset, "description")])
            }
            let confidence = recognition["recognition_confidence"].toString()
            tx.query("INSERT INTO ocr_runs (id,question_id,provider,raw_result,confidence,stream,status,model_name,duration_ms,error,created_at,updated_at) VALUES (?,?,'qwen-pool',?,?,'qwen_crop','completed','Qwen',?,NULL,UTC_TIMESTAMP(),UTC_TIMESTAMP())",
                [Some(newId()), Some(questionId), Some(recognition.toString()), Some(confidence), Some(computed["duration_ms"].toString())])
            let text = jsonText(recognition, "question_text")
            tx.query("UPDATE questions SET confirmed = 0, question_text = ?, student_answer = ?, subject = ?, grade = ?, question_type = ?, formulas = JSON_ARRAY(), options = ?, title = ?, status = 'needs_confirmation', updated_at = UTC_TIMESTAMP() WHERE id = ?",
                [Some(text), nullableJsonText(recognition, "student_answer"), Some(jsonText(recognition, "subject")), nullableJsonText(recognition, "grade"), Some(jsonText(recognition, "question_type")), Some(recognition["options"].toString()), Some(shortTitle(text, 60)), Some(questionId)])
            let work = newId()
            tx.query("INSERT INTO student_works (id,question_id,user_id,answer,explanation,created_at,updated_at) VALUES (?,?,?,?,'',UTC_TIMESTAMP(6),UTC_TIMESTAMP(6))", [Some(work), Some(questionId), questions[0]["user_id"], Some(nullableJsonText(recognition, "student_answer") ?? "")])
            for (item in (recognition["student_steps"] as JsonArray).getOrThrow().getItems()) {
                let step = (item as JsonObject).getOrThrow()
                let stepText = jsonText(step, "text")
                let index = Int64.parse(step["index"].toString()) - 1
                tx.query("INSERT INTO student_steps (id,work_id,step_index,text,bbox,raw_text,normalized_text,formula,confidence,source,user_confirmed,created_at,updated_at) VALUES (?,?,?,?,JSON_ARRAY(),?,?,?,?,'qwen_crop',0,UTC_TIMESTAMP(),UTC_TIMESTAMP())",
                    [Some(newId()), Some(work), Some(index.toString()), Some(stepText), Some(stepText), Some(collapseWhitespace(stepText)), Some(if (stepText.contains("=")) { stepText } else { "" }), Some(confidence)])
            }
            for (item in (recognition["teacher_annotations"] as JsonArray).getOrThrow().getItems()) {
                let mark = (item as JsonObject).getOrThrow()
                tx.query("INSERT INTO teacher_marks (id,question_id,mark_type,comment,bbox,confidence,source,created_at,updated_at) VALUES (?,?,?,?,JSON_ARRAY(),?,'qwen_crop',UTC_TIMESTAMP(),UTC_TIMESTAMP())",
                    [Some(newId()), Some(questionId), Some(jsonText(mark, "type")), Some(jsonText(mark, "text")), Some(confidence)])
            }
            tx.query("UPDATE processing_jobs SET status = 'completed', progress = 100, error = NULL, updated_at = UTC_TIMESTAMP() WHERE id = ?", [Some(jobId)])
            return true
        })
    } catch (_: Exception) { finishRecognitionFailure(jobId, questionId, fingerprint) }
    finally { if (!committed) { for (path in files) { try { removeMedia(path) } catch (_: Exception) {} } } }
}

public func recoverRecognitionJobs(): Unit {
    try (db = Database.fromEnvironment()) {
        let jobs = db.query("SELECT id,question_id FROM processing_jobs WHERE status IN ('pending','running') AND kind IN ('ingest','crop','ocr','reprocess') ORDER BY question_id,id").rows
        for (job in jobs) { finishRecognitionFailure(rowText(job, "id"), rowText(job, "question_id"), "", recovered: true) }
    } catch (_: Exception) { /* Database readiness is reported separately. */ }
}
