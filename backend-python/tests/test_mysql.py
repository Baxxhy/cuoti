import os

import pytest
from cuoti_backend.config import Settings
from cuoti_backend.main import create_app
from fastapi.testclient import TestClient
from sqlalchemy import text


@pytest.mark.mysql
@pytest.mark.skipif(
    os.environ.get("CUOTI_TEST_MYSQL") != "1", reason="local MySQL check not enabled"
)
def test_local_mysql_read_queries():
    app = create_app(Settings.load())
    database = app.state.database
    with TestClient(app) as client:
        with database.session() as first, database.session() as second:
            assert first is not second
            assert first.execute(text("SELECT 1")).scalar_one() == 1
            assert (
                second.execute(text("SELECT DATABASE()")).scalar_one()
                == app.state.settings.db_name
            )
        response = client.get("/readyz")
        assert response.status_code == 200
        assert response.json()["status"] == "database_ready"
