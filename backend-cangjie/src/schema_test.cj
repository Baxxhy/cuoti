package zhiwei

import std.unittest.*
import std.unittest.testmacro.*

@Test
class SchemaUpgradeTest {
    @TestCase
    func practicePrecisionUpgradeRetainsDataAndRepeats() {
        let id=newId()
        try (db=testDatabase()) {
            db.query("INSERT INTO users (id,email,name,role,password_hash,created_at,updated_at) VALUES (?,?,'升级保留测试','student','fixture',UTC_TIMESTAMP(),UTC_TIMESTAMP())",[Some(id),Some("${id}@schema.local")])
            try {
                db.query("DELETE FROM cangjie_schema_versions WHERE version='005_practice_precision'")
                for (table in ["practice_recommendations","dataset_practice_attempts"]) {
                    db.query("ALTER TABLE ${table} MODIFY created_at DATETIME NOT NULL, MODIFY updated_at DATETIME NOT NULL")
                }
                upgradeDatabase(); upgradeDatabase()
                @Expect(db.query("SELECT version FROM cangjie_schema_versions WHERE version='005_practice_precision'").rows.size,1)
                @Expect(db.query("SELECT id FROM users WHERE id=?",[Some(id)]).rows.size,1)
                for (table in ["practice_recommendations","dataset_practice_attempts"]) {
                    let rows=db.query("SELECT datetime_precision AS precision_value FROM information_schema.columns WHERE table_schema=DATABASE() AND table_name=? AND column_name='created_at'",[Some(table)]).rows
                    @Expect(rowText(rows[0],"precision_value"),"6")
                }
            } finally { db.query("DELETE FROM users WHERE id=?",[Some(id)]) }
        }
    }
}
