package zhiwei

import std.fs.*

public func initializeDatabase(): Unit {
    try (db = Database.fromEnvironment()) {
        let existing = db.query("SELECT table_name FROM information_schema.tables WHERE table_schema = DATABASE()")
        if (!existing.rows.isEmpty()) {
            // Never reset or silently merge an existing application database.
            throw IllegalArgumentException("初始化只允许空数据库；已有数据库请使用后续版本迁移")
        }
        let schema = String.fromUtf8(File.readFrom("schema/001_initial.sql"))
        for (statement in schema.split(";")) {
            if (!statement.trimAscii().isEmpty()) { db.query(statement) }
        }
        db.query("CREATE TABLE cangjie_schema_versions (version VARCHAR(100) PRIMARY KEY, applied_at DATETIME NOT NULL) ENGINE=InnoDB")
        db.query("INSERT INTO cangjie_schema_versions VALUES (?, UTC_TIMESTAMP())", [Some("001_initial")])
    }
    upgradeDatabase()
}


public func upgradeDatabase(): Unit {
    try (db = Database.fromEnvironment()) {
        let initial = db.query("SELECT version FROM cangjie_schema_versions WHERE version = '001_initial'").rows
        if (initial.size != 1) { throw IllegalArgumentException("缺少仓颉初始版本，不能升级") }
        let applied = db.query("SELECT version FROM cangjie_schema_versions WHERE version = '002_work_precision'").rows
        if (applied.isEmpty()) {
        // MySQL DDL commits implicitly. Repeating this ALTER after interruption is safe.
        db.query("ALTER TABLE student_works MODIFY created_at DATETIME(6) NOT NULL, MODIFY updated_at DATETIME(6) NOT NULL")
        db.query("INSERT IGNORE INTO cangjie_schema_versions VALUES ('002_work_precision', UTC_TIMESTAMP())")
        }
        if (db.query("SELECT version FROM cangjie_schema_versions WHERE version = '003_diagnosis_precision'").rows.isEmpty()) {
            db.query("ALTER TABLE diagnoses MODIFY created_at DATETIME(6) NOT NULL, MODIFY updated_at DATETIME(6) NOT NULL")
            db.query("INSERT IGNORE INTO cangjie_schema_versions VALUES ('003_diagnosis_precision', UTC_TIMESTAMP())")
        }
        if (db.query("SELECT version FROM cangjie_schema_versions WHERE version = '004_tutor_precision'").rows.isEmpty()) {
            db.query("ALTER TABLE tutor_turns MODIFY created_at DATETIME(6) NOT NULL, MODIFY updated_at DATETIME(6) NOT NULL")
            db.query("INSERT IGNORE INTO cangjie_schema_versions VALUES ('004_tutor_precision', UTC_TIMESTAMP())")
        }
        if (db.query("SELECT version FROM cangjie_schema_versions WHERE version = '005_practice_precision'").rows.isEmpty()) {
            for (table in ["practice_recommendations","dataset_practice_attempts"]) {
                db.query("ALTER TABLE ${table} MODIFY created_at DATETIME(6) NOT NULL, MODIFY updated_at DATETIME(6) NOT NULL")
            }
            db.query("INSERT IGNORE INTO cangjie_schema_versions VALUES ('005_practice_precision', UTC_TIMESTAMP())")
        }
        if (db.query("SELECT version FROM cangjie_schema_versions WHERE version = '006_learning_tasks'").rows.isEmpty()) {
            for (statement in String.fromUtf8(File.readFrom("schema/006_learning_tasks.sql")).split(";")) {
                if (!statement.trimAscii().isEmpty()) { db.query(statement) }
            }
            db.query("INSERT IGNORE INTO cangjie_schema_versions VALUES ('006_learning_tasks', UTC_TIMESTAMP())")
        }
        if (db.query("SELECT version FROM cangjie_schema_versions WHERE version = '007_self_checks'").rows.isEmpty()) {
            for (statement in String.fromUtf8(File.readFrom("schema/007_self_checks.sql")).split(";")) {
                if (!statement.trimAscii().isEmpty()) { db.query(statement) }
            }
            db.query("INSERT IGNORE INTO cangjie_schema_versions VALUES ('007_self_checks', UTC_TIMESTAMP())")
        }
        if (db.query("SELECT version FROM cangjie_schema_versions WHERE version = '008_task_handwriting'").rows.isEmpty()) {
            for (statement in String.fromUtf8(File.readFrom("schema/008_task_handwriting.sql")).split(";")) {
                if (!statement.trimAscii().isEmpty()) { db.query(statement) }
            }
            db.query("INSERT IGNORE INTO cangjie_schema_versions VALUES ('008_task_handwriting', UTC_TIMESTAMP())")
        }
        if (db.query("SELECT version FROM cangjie_schema_versions WHERE version = '009_task_sources'").rows.isEmpty()) {
            for (statement in String.fromUtf8(File.readFrom("schema/009_task_sources.sql")).split(";")) {
                if (!statement.trimAscii().isEmpty()) { db.query(statement) }
            }
            db.query("INSERT IGNORE INTO cangjie_schema_versions VALUES ('009_task_sources', UTC_TIMESTAMP())")
        }
        if (db.query("SELECT version FROM cangjie_schema_versions WHERE version = '010_study_sessions'").rows.isEmpty()) {
            for (statement in String.fromUtf8(File.readFrom("schema/010_study_sessions.sql")).split(";")) {
                if (!statement.trimAscii().isEmpty()) { db.query(statement) }
            }
            db.query("INSERT IGNORE INTO cangjie_schema_versions VALUES ('010_study_sessions', UTC_TIMESTAMP())")
        }
        if (db.query("SELECT version FROM cangjie_schema_versions WHERE version = '012_personal_learning'").rows.isEmpty()) {
            for (statement in String.fromUtf8(File.readFrom("schema/012_personal_learning.sql")).split(";")) {
                if (!statement.trimAscii().isEmpty()) { db.query(statement) }
            }
            db.query("INSERT IGNORE INTO cangjie_schema_versions VALUES ('012_personal_learning', UTC_TIMESTAMP())")
        }
        if (db.query("SELECT version FROM cangjie_schema_versions WHERE version = '011_bank_browse_index'").rows.isEmpty()) {
            // Cover eligibility, ordered browsing and facets without reading large question bodies.
            if (db.query("SELECT INDEX_NAME FROM information_schema.STATISTICS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='dataset_questions' AND INDEX_NAME='ix_bank_browse'").rows.isEmpty()) {
                db.query("ALTER TABLE dataset_questions ADD INDEX ix_bank_browse (usable_for_practice,usable_for_auto_grade,has_answer,subject,id,grade_band,dataset_source_id), ALGORITHM=INPLACE, LOCK=NONE")
            }
            db.query("INSERT IGNORE INTO cangjie_schema_versions VALUES ('011_bank_browse_index', UTC_TIMESTAMP())")
        }
        if (db.query("SELECT version FROM cangjie_schema_versions WHERE version = '013_bank_grade_index'").rows.isEmpty()) {
            if (db.query("SELECT INDEX_NAME FROM information_schema.STATISTICS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='dataset_questions' AND INDEX_NAME='ix_bank_grade'").rows.isEmpty()) {
                db.query("ALTER TABLE dataset_questions ADD INDEX ix_bank_grade (usable_for_practice,usable_for_auto_grade,has_answer,grade,subject,id), ALGORITHM=INPLACE, LOCK=NONE")
            }
            db.query("INSERT IGNORE INTO cangjie_schema_versions VALUES ('013_bank_grade_index', UTC_TIMESTAMP())")
        }
    }
}
