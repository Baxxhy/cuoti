package zhiwei

import std.env.*
import std.convert.*
import stdx.net.http.*
import stdx.log.*

main(args: Array<String>): Int64 {
    if (args.size == 1 && args[0] == "--question-bank") { return questionBankCommand() }
    if (args.size == 1 && args[0] == "--create-local-user") { return localUserCommand() }
    if (args.size == 1 && args[0] == "--init-db") {
        initializeDatabase()
        println("仓颉独立数据库初始化完成")
        return 0
    }
    if (args.size == 1 && args[0] == "--upgrade-db") { upgradeDatabase(); println("仓颉数据库升级完成"); return 0 }
    if (args.size == 1 && args[0] == "--seed-knowledge") { seedPublicKnowledge(); println("公开知识卡初始化完成"); return 0 }
    if (!args.isEmpty()) { throw IllegalArgumentException("未知启动参数") }
    let port = UInt16.parse(getVariable("CANGJIE_BACKEND_PORT") ?? "8002")
    let server = ServerBuilder().addr("127.0.0.1").port(port).maxRequestBodySize(16 * 1024 * 1024).distributor(ApiDistributor()).build()
    server.logger.level = LogLevel.OFF
    server.afterBind({ => recoverRecognitionJobs(); spawn { learningTaskWorker() }; spawn { learningTaskWorker() }; () })
    let accounts = Accounts(getVariable("CANGJIE_AUTH_SECRET") ?? "")
    accounts.routes(server)
    server.distributor.register("/api/v1/learning-tasks", { ctx => guarded(ctx, { => learningTasks(ctx,accounts) }, successStatus:if (ctx.request.method=="POST") { 202 } else { 200 }) })
    server.distributor.register("/api/v1/learning-tasks/{task_id}", { ctx => guarded(ctx, { => readLearningTask(ctx,accounts) }) })
    server.distributor.register("/api/v1/learning-tasks/{task_id}/actions", { ctx => guarded(ctx, { => learningTaskAction(ctx,accounts) },successStatus:202) })
    server.distributor.register("/api/v1/learning-tasks/{task_id}/handwriting", { ctx => guarded(ctx, { => uploadTaskHandwriting(ctx,accounts) },successStatus:202) })
    server.distributor.register("/api/v1/learning-tasks/{task_id}/self-check", { ctx => guarded(ctx, { => learningSelfCheck(ctx,accounts) }) })
    server.distributor.register("/api/v1/learning-tasks/{task_id}/history", { ctx => guarded(ctx, { => learningTaskHistory(ctx,accounts) }) })
    server.distributor.register("/api/v1/learning-tasks/{task_id}/cancel", { ctx => guarded(ctx, { => learningTaskAction(ctx,accounts,cancel:true) }) })
    server.distributor.register("/api/v1/dashboard", { ctx => guarded(ctx, { => learningDashboard(ctx, accounts) }) })
    server.distributor.register("/api/v1/student-preferences", { ctx => guarded(ctx, { => studentLearningPreferences(ctx, accounts) }) })
    server.distributor.register("/api/v1/analytics/error-sources", { ctx => guarded(ctx, { => studentErrorSources(ctx, accounts) }) })
    server.distributor.register("/api/v1/analytics/overview", { ctx => guarded(ctx, { => learningAnalytics(ctx, accounts) }) })
    server.distributor.register("/api/v1/analytics/cognition-graph", { ctx => guarded(ctx, { => readCognitionGraph(ctx, accounts) }) })
    server.distributor.register("/api/v1/knowledge/cards", { ctx => guarded(ctx, { => knowledgeCards(ctx) }) })
    server.distributor.register("/api/v1/knowledge/framework", { ctx => guarded(ctx, { => personalKnowledgeFramework(ctx,accounts) }) })
    server.distributor.register("/api/v1/knowledge/cards/{code}", { ctx => guarded(ctx, { => readKnowledgeCard(ctx) }) })
    server.distributor.register("/api/v1/knowledge/cards/{code}/lessons", { ctx => guarded(ctx, { => knowledgeLessons(ctx,accounts) }) })
    server.distributor.register("/api/v1/questions/{question_id}/ocr", { ctx => guarded(ctx, { => startRecognition(ctx, accounts, true) }) })
    server.distributor.register("/api/v1/questions/{question_id}/reprocess", { ctx => guarded(ctx, { => startRecognition(ctx, accounts, false) }) })
    server.distributor.register("/api/v1/questions/{question_id}/crop", { ctx => guarded(ctx, { => cropQuestion(ctx, accounts) }) })
    server.distributor.register("/api/v1/questions/{question_id}/draft", { ctx => guarded(ctx, { => saveOcrEdits(ctx, accounts, false) }) })
    server.distributor.register("/api/v1/questions/{question_id}/confirm", { ctx => guarded(ctx, { => saveOcrEdits(ctx, accounts, true) }) })
    server.distributor.register("/api/v1/questions/{question_id}/analyze", { ctx => guarded(ctx, { => analyzeQuestion(ctx, accounts) }) })
    server.distributor.register("/api/v1/questions/{question_id}/student-work", { ctx => guarded(ctx, { => submitStudentWork(ctx, accounts) }) })
    server.distributor.register("/api/v1/reviews/today", { ctx => guarded(ctx, { => listReviews(ctx, accounts, false) }) })
    server.distributor.register("/api/v1/reviews/search", { ctx => guarded(ctx, { => searchReviewQuestions(ctx,accounts) }) })
    server.distributor.register("/api/v1/reviews/filters", { ctx => guarded(ctx, { => savedReviewFilters(ctx,accounts,false) }) })
    server.distributor.register("/api/v1/reviews/filters/{filter_id}", { ctx => guarded(ctx, { => savedReviewFilters(ctx,accounts,true) }) })
    server.distributor.register("/api/v1/reviews/history", { ctx => guarded(ctx, { => listReviews(ctx, accounts, true) }) })
    server.distributor.register("/api/v1/reviews/{plan_id}/attempt", { ctx => guarded(ctx, { => attemptReview(ctx, accounts) }) })
    server.distributor.register("/api/v1/reviews/{plan_id}/grade", { ctx => guarded(ctx, { => gradeReview(ctx, accounts) }) })
    server.distributor.register("/api/v1/practice/questions/{question_id}/images/{image_index}", { ctx => servePracticeImage(ctx, accounts) })
    server.distributor.register("/api/v1/study-bank", { ctx => guarded(ctx, { => studyBank(ctx,accounts) }) })
    server.distributor.register("/api/v1/study-sessions", { ctx => guarded(ctx, { => studySessions(ctx,accounts) }) })
    server.distributor.register("/api/v1/study-sessions/{session_id}", { ctx => guarded(ctx, { => studySessionApi(ctx,accounts) }) })
    server.distributor.register("/api/v1/study-sessions/{session_id}/submit", { ctx => guarded(ctx, { => studySessionApi(ctx,accounts) }) })
    server.distributor.register("/api/v1/practice/recommend", { ctx => guarded(ctx, { => recommendPractice(ctx, accounts) }) })
    server.distributor.register("/api/v1/practice/attempt", { ctx => guarded(ctx, { => attemptPractice(ctx, accounts) }) })
    server.distributor.register("/api/v1/answers/handwriting", { ctx => guarded(ctx, { => uploadHandwriting(ctx, accounts) }) })
    server.distributor.register("/api/v1/tutor/sessions/{session_id}/visualization", { ctx => guarded(ctx, { => sessionVisualization(ctx, accounts) }) })
    server.distributor.register("/api/v1/system/health", { ctx => guarded(ctx, { => systemApi(ctx, "health") }) })
    server.distributor.register("/api/v1/system/providers", { ctx => guarded(ctx, { => systemApi(ctx, "providers") }) })
    server.distributor.register("/api/v1/system/providers/probe", { ctx => guarded(ctx, { => systemApi(ctx, "probe") }) })
    server.distributor.register("/api/v1/system/voice", { ctx => guarded(ctx, { => systemApi(ctx, "voice") }) })
    server.distributor.register("/api/v1/admin/workbench", { ctx => guarded(ctx, { => adminApi(ctx, accounts, "workbench") }) })
    server.distributor.register("/api/v1/admin/students/{student_id}", { ctx => guarded(ctx, { => adminApi(ctx, accounts, "student") }) })
    server.distributor.register("/api/v1/admin/sessions/{session_id}", { ctx => guarded(ctx, { => adminApi(ctx, accounts, "session") }) })
    server.distributor.register("/api/v1/voice/transcribe", { ctx => guarded(ctx, { => transcribeVoice(ctx, accounts) }) })
    server.distributor.register("/api/v1/voice/synthesize", { ctx => guarded(ctx, { => synthesizeVoice(ctx, accounts) }) })
    server.distributor.register("/api/v1/papers", { ctx => guarded(ctx, { => papersApi(ctx, accounts) }) })
    server.distributor.register("/api/v1/papers/candidates", { ctx => guarded(ctx, { => paperCandidates(ctx, accounts) }) })
    server.distributor.register("/api/v1/papers/{paper_id}/export", { ctx => guarded(ctx, { => exportPaper(ctx, accounts) }) })
    server.distributor.register("/api/v1/papers/{paper_id}/download", { ctx => downloadPaper(ctx, accounts) })
    server.distributor.register("/api/v1/papers/{paper_id}", { ctx => guarded(ctx, { => paperApi(ctx, accounts) }) })
    server.distributor.register("/api/v1/variants/{variant_id}/attempt", { ctx => guarded(ctx, { => variantAttempt(ctx, accounts) }) })
    server.distributor.register("/api/v1/visualizations/types", { ctx => guarded(ctx, { => visualizationTypes(ctx) }) })
    server.distributor.register("/api/v1/visualizations/{visualization_id}", { ctx => guarded(ctx, { => readVisualization(ctx, accounts) }) })
    server.distributor.register("/api/v1/tutor/sessions/{session_id}/turns", { ctx => guarded(ctx, { => tutorDialogue(ctx, accounts) }) })
    server.distributor.register("/api/v1/tutor/sessions/{session_id}/teach-back", { ctx => guarded(ctx, { => teachBackTutor(ctx, accounts) }) })
    server.distributor.register("/api/v1/tutor/sessions/{session_id}/finish", { ctx => guarded(ctx, { => finishTutor(ctx, accounts) }) })
    server.distributor.register("/api/v1/tutor/sessions/{session_id}/activity/answer", { ctx => guarded(ctx, { => answerTutorActivity(ctx, accounts) }) })
    server.distributor.register("/api/v1/tutor/sessions/{session_id}/advance", { ctx => guarded(ctx, { => navigateTutor(ctx, accounts, false) }) })
    server.distributor.register("/api/v1/tutor/sessions/{session_id}/rewind", { ctx => guarded(ctx, { => navigateTutor(ctx, accounts, true) }) })
    server.distributor.register("/api/v1/tutor/sessions/{session_id}/variant", { ctx => guarded(ctx, { => tutorVariant(ctx, accounts) }) })
    server.distributor.register("/api/v1/tutor/sessions/{session_id}", { ctx => guarded(ctx, { => readTutor(ctx, accounts) }) })
    server.distributor.register("/api/v1/tutor/sessions", { ctx => guarded(ctx, { => startTutor(ctx, accounts) }) })
    server.distributor.register("/api/v1/questions/{question_id}/diagnose", { ctx => guarded(ctx, { => diagnoseQuestion(ctx, accounts) }) })
    server.distributor.register("/api/v1/questions/{question_id}/diagnosis", { ctx => guarded(ctx, { => diagnosisRoute(ctx, accounts) }) })
    server.distributor.register("/api/v1/questions/{question_id}/diagnosis/counterfactual", { ctx => guarded(ctx, { => counterfactualQuestion(ctx, accounts) }) })
    server.distributor.register("/api/v1/questions/ingest", { ctx => guarded(ctx, { => ingestQuestion(ctx, accounts) }) })
    server.distributor.register("/api/v1/jobs/{job_id}/retry", { ctx => guarded(ctx, { => retryJob(ctx, accounts) }) })
    server.distributor.register("/api/v1/jobs/{job_id}", { ctx => guarded(ctx, { => getJob(ctx, accounts) }) })
    server.distributor.register("/uploads/*", { ctx => serveMedia(ctx, accounts) })
    server.distributor.register("/reports/*", { ctx => serveMedia(ctx, accounts) })
    server.distributor.register("/api/v1/questions", { ctx => guarded(ctx, { => questionList(ctx, accounts) }) })
    server.distributor.register("/api/v1/questions/manual", { ctx => guarded(ctx, { => createManualQuestion(ctx, accounts) }) })
    server.distributor.register("/api/v1/questions/{question_id}/journey", { ctx => guarded(ctx, { => learningJourney(ctx, accounts) }) })
    server.distributor.register("/api/v1/questions/{question_id}", { ctx => guarded(ctx, { => questionRoute(ctx, accounts) }) })
    // Liveness deliberately makes no claim about database or AI readiness.
    server.distributor.register("/livez", { context =>
        if (context.request.method != "GET") {
            context.responseBuilder.status(405).header("Allow", "GET").body("")
        } else {
            context.responseBuilder.header("Content-Type", "application/json; charset=utf-8")
                .body(##"{"service":"zhiwei-cangjie","status":"alive","version":"0.1.0"}"##)
        }
        ()
    })
    server.distributor.register("/readyz", { context =>
        context.responseBuilder.header("Content-Type", "application/json; charset=utf-8")
        if (context.request.method != "GET") {
            context.responseBuilder.status(405).header("Allow", "GET").body("")
        } else {
            try (db = Database.fromEnvironment()) {
                db.query("SELECT id FROM users LIMIT 1")
                let version = db.query("SELECT version FROM cangjie_schema_versions WHERE version = ?", [Some("010_study_sessions")])
                if (version.rows.size != 1) { throw DatabaseException(2000) }
                context.responseBuilder.body(##"{"database":"mysql","schema":"010_study_sessions","status":"database_ready","ai":"not_connected"}"##)
            } catch (_: Exception) {
                context.responseBuilder.status(503).body(##"{"status":"database_unavailable"}"##)
            }
        }
        ()
    })
    println("错题帮仓颉独立后端 http://127.0.0.1:${port}")
    server.serve()
    return 0
}
