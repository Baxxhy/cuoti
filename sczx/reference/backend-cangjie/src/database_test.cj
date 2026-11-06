package zhiwei

import std.unittest.*
import std.unittest.testmacro.*
import std.env.*
import std.convert.*

func testDatabase(): Database {
    let name = getVariable("CANGJIE_DB_NAME") ?? ""
    if (!name.startsWith("zhiwei_cangjie_test")) {
        throw IllegalArgumentException("数据库测试必须显式使用 zhiwei_cangjie_test 前缀的独立库")
    }
    return Database.fromEnvironment()
}

@Test
class DatabaseTest {
    @TestCase
    func parametersUnicodeNullAndInjection() {
        try (db = testDatabase()) {
            db.query("CREATE TEMPORARY TABLE cj_values (id INT PRIMARY KEY, text_value TEXT NULL) ENGINE=InnoDB")
            let text = "中文数学题：x² = 4 😀 ' OR 1=1; -- \\"
            @Expect(db.query("INSERT INTO cj_values VALUES (?, ?)", [Some("1"), Some(text)]).affected, 1)
            db.query("INSERT INTO cj_values VALUES (?, ?)", [Some("2"), None])
            db.query("INSERT INTO cj_values VALUES (?, ?)", [Some("3"), Some("")])
            db.query("INSERT INTO cj_values VALUES (?, ?)", [Some("4"), Some("a\u{0}b")])
            let rows = db.query("SELECT id, text_value FROM cj_values ORDER BY id").rows
            @Expect(rows.size, 4)
            @Expect(rows[0]["text_value"], Some(text))
            @Expect(rows[1]["text_value"], None)
            @Expect(rows[2]["text_value"], Some(""))
            @Expect(rows[3]["text_value"], Some("a\u{0}b"))
            @Expect(db.query("SELECT id FROM cj_values WHERE text_value = ?", [Some("' OR 1=1 --")]).rows.size, 0)
        }
    }

    @TestCase
    func commitAndRollback() {
        try (db = testDatabase()) {
            db.query("CREATE TEMPORARY TABLE cj_tx (id INT PRIMARY KEY) ENGINE=InnoDB")
            db.transaction<Unit>({ tx => tx.query("INSERT INTO cj_tx VALUES (?)", [Some("1")]); () })
            var failed = false
            try {
                db.transaction<Unit>({ tx =>
                    tx.query("INSERT INTO cj_tx VALUES (?)", [Some("2")])
                    tx.query("INSERT INTO cj_tx VALUES (?)", [Some("1")])
                    ()
                })
            } catch (_: DatabaseException) { failed = true }
            @Expect(failed, true)
            let rows = db.query("SELECT id FROM cj_tx ORDER BY id").rows
            @Expect(rows.size, 1)
            @Expect(rows[0]["id"], Some("1"))
            db.transaction<Unit>({ tx => tx.query("INSERT INTO cj_tx VALUES (?)", [Some("3")]); () })
            @Expect(db.query("SELECT id FROM cj_tx").rows.size, 2)
        }
    }

    @TestCase
    func concurrentTransactionsRemainAtomic() {
        try (db = testDatabase()) {
            db.query("CREATE TEMPORARY TABLE cj_counter (n INT NOT NULL) ENGINE=InnoDB")
            db.query("INSERT INTO cj_counter VALUES (0)")
            let tasks = Array(8, { _ => spawn {
                db.transaction<Unit>({ tx =>
                    let current = Int64.parse(tx.query("SELECT n FROM cj_counter").rows[0]["n"].getOrThrow())
                    sleep(5 * Duration.millisecond)
                    tx.query("UPDATE cj_counter SET n = ?", [Some((current + 1).toString())])
                    ()
                })
            } })
            for (task in tasks) { task.get() }
            @Expect(db.query("SELECT n FROM cj_counter").rows[0]["n"], Some("8"))
        }
    }

    @TestCase
    func validationAndClosedConnection() {
        let db = testDatabase()
        try {
            var rejected = false
            try { db.query("SELECT ?", []) } catch (_: IllegalArgumentException) { rejected = true }
            @Expect(rejected, true)
            rejected = false
            try {
                db.transaction<Unit>({ tx => tx.transaction<Unit>({ _ => () }) })
            } catch (_: IllegalArgumentException) { rejected = true }
            @Expect(rejected, true)
            @Expect(db.query("SELECT 1 AS n").rows[0]["n"], Some("1"))
        } finally { db.close() }
        db.close()
        @Expect(db.isClosed(), true)
        var rejected = false
        try { db.query("SELECT 1") } catch (_: DatabaseException) { rejected = true }
        @Expect(rejected, true)
    }
}
