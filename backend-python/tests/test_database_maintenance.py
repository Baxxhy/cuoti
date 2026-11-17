import json
import os
import subprocess
from pathlib import Path
from uuid import uuid4

import pytest
from cuoti_backend import manage_db, schema
from cuoti_backend.config import Settings
from cuoti_backend.database import Database
from cuoti_backend.protocol import ApiError
from sqlalchemy import create_engine, text


def test_packaged_historical_schema_matches_reference():
    original = Path(__file__).resolve().parents[2] / "backend-cangjie/schema"
    for source in original.glob("*.sql"):
        assert (
            schema.RESOURCES / "schema" / source.name
        ).read_bytes() == source.read_bytes()
    assert (schema.RESOURCES / "knowledge_seed.json").read_bytes() == (
        original / "knowledge_seed.json"
    ).read_bytes()


@pytest.mark.mysql
@pytest.mark.skipif(
    os.environ.get("CUOTI_TEST_MAINTENANCE") != "1",
    reason="temporary MySQL database check not enabled",
)
def test_fresh_database_seed_backup_and_upgrade(tmp_path, monkeypatch):
    # Explicit opt-in: use a UUID database, never the configured student's database.
    local = Settings.load()
    name = "cuoti_maintenance_" + uuid4().hex
    restored_name = name + "_restore"
    settings = Settings(
        db_host=local.db_host,
        db_port=local.db_port,
        db_user="root",
        db_name=name,
        project_root=str(tmp_path),
    )
    admin_url = settings.database_url().set(database="mysql")
    admin = create_engine(admin_url)
    database = None
    try:
        with admin.connect() as connection:
            connection.execute(
                text(
                    f"CREATE DATABASE `{name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                )
            )
        database = Database(settings)
        result = manage_db.maintain(database, settings, "init")
        assert result["initialized"] and set(result["versions"]) == schema.VERSIONS
        with pytest.raises(ApiError, match="空数据库"):
            manage_db.maintain(database, settings, "init")
        assert manage_db.maintain(database, settings, "status")["missing"] == []
        assert manage_db.maintain(database, settings, "upgrade")["upgraded"] is False
        with database.engine.connect() as connection:
            tables = set(connection.execute(text("SHOW TABLES")).scalars())
            expected = set(
                json.loads((schema.RESOURCES / "row_types.json").read_text())
            )
            assert expected <= tables, expected - tables
            assert (
                connection.execute(
                    text(
                        "SELECT DATETIME_PRECISION FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='student_works' AND COLUMN_NAME='created_at'"
                    )
                ).scalar_one()
                == 6
            )
        seeded = manage_db.maintain(database, settings, "seed-knowledge")
        backup = Path(seeded["backup"])
        assert backup.stat().st_size > 1000 and backup.stat().st_mode & 0o777 == 0o600
        assert "CREATE TABLE" in backup.read_text()
        data = json.loads((schema.RESOURCES / "knowledge_seed.json").read_text())
        with database.engine.connect() as connection:
            before = list(
                connection.execute(
                    text("SELECT id,code FROM knowledge_points ORDER BY code")
                )
            )
            count = connection.execute(
                text("SELECT COUNT(*) FROM knowledge_relations")
            ).scalar_one()
        assert len(before) == len(data["cards"]) and count == len(data["relations"])
        second = manage_db.maintain(database, settings, "seed-knowledge")
        restored = subprocess.run(
            [
                "mysql",
                "--no-defaults",
                "--host=" + settings.db_host,
                "--port=" + str(settings.db_port),
                "--user=root",
            ],
            input=Path(second["backup"]).read_text().replace(name, restored_name),
            text=True,
            capture_output=True,
            timeout=120,
            check=False,
        )
        assert restored.returncode == 0, "临时数据库备份恢复失败"
        with admin.connect() as connection:
            recovered = list(
                connection.execute(
                    text(
                        f"SELECT id,code FROM `{restored_name}`.knowledge_points ORDER BY code"
                    )
                )
            )
            assert recovered == before
        with database.engine.connect() as connection:
            assert (
                list(
                    connection.execute(
                        text("SELECT id,code FROM knowledge_points ORDER BY code")
                    )
                )
                == before
            )
            assert (
                connection.execute(
                    text("SELECT COUNT(*) FROM knowledge_relations")
                ).scalar_one()
                == count
            )
            # Only remove a synthetic index/version to exercise a real upgrade and backup.
            connection.execute(
                text("ALTER TABLE dataset_questions DROP INDEX ix_bank_grade")
            )
            connection.execute(
                text(
                    "DELETE FROM cangjie_schema_versions WHERE version='013_bank_grade_index'"
                )
            )
            connection.commit()
        upgraded = manage_db.maintain(database, settings, "upgrade")
        assert Path(upgraded["backup"]).is_file()
        assert manage_db.maintain(database, settings, "status")["missing"] == []

        def failed_backup(_):
            raise ApiError(503, "模拟备份失败")

        def forbidden_seed(_):
            pytest.fail("backup failed but seed ran")

        monkeypatch.setattr(manage_db, "backup", failed_backup)
        monkeypatch.setattr(schema, "seed", forbidden_seed)
        with pytest.raises(ApiError, match="备份失败"):
            manage_db.maintain(database, settings, "seed-knowledge")
    finally:
        if database is not None:
            database.close()
        with admin.connect() as connection:
            connection.execute(text(f"DROP DATABASE IF EXISTS `{restored_name}`"))
            connection.execute(text(f"DROP DATABASE IF EXISTS `{name}`"))
        admin.dispose()
