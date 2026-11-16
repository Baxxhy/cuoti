import os
from pathlib import Path

from dotenv import dotenv_values
from pydantic import BaseModel, Field, SecretStr
from sqlalchemy.engine import URL


class Settings(BaseModel):
    host: str = "127.0.0.1"
    port: int = Field(default=8003, ge=1, le=65535)
    log_level: str = Field(
        default="INFO", pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$"
    )
    db_host: str = "127.0.0.1"
    db_port: int = Field(default=3307, ge=1, le=65535)
    db_name: str = ""
    db_user: str = ""
    db_password: SecretStr = SecretStr("")
    db_timeout: int = Field(default=3, ge=1, le=30)
    max_request_bytes: int = Field(default=16 * 1024 * 1024, ge=1)

    @classmethod
    def load(cls):
        # Local legacy configuration is reused without running shell code.
        default = Path(__file__).resolve().parents[2] / ".env.cangjie"
        path = Path(os.environ.get("CUOTI_ENV_FILE", str(default)))
        values = {**dotenv_values(path), **os.environ}
        result = {}
        for field in cls.model_fields:
            key = "CUOTI_" + field.upper()
            legacy = "CANGJIE_" + field.upper()
            if key in values:
                result[field] = values[key]
            elif field.startswith("db_") and legacy in values:
                result[field] = values[legacy]
        return cls.model_validate(result)

    def database_url(self):
        if not self.db_name or not self.db_user:
            raise ValueError("尚未配置 MySQL 数据库")
        return URL.create(
            "mysql+pymysql",
            username=self.db_user,
            password=self.db_password.get_secret_value(),
            host=self.db_host,
            port=self.db_port,
            database=self.db_name,
            query={"charset": "utf8mb4"},
        )
