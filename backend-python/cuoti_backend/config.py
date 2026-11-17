import os
from pathlib import Path

from dotenv import dotenv_values
from pydantic import BaseModel, Field, SecretStr
from sqlalchemy.engine import URL


def configuration():
    root = Path(__file__).resolve().parents[2]
    preferred = root / ".env.python"
    legacy = root / ".env.cangjie"
    default = preferred if preferred.exists() or not legacy.exists() else legacy
    path = Path(os.environ.get("CUOTI_ENV_FILE", str(default))).resolve()
    values = dotenv_values(path) if path.is_file() else {}
    return path, {**values, **os.environ}


class Settings(BaseModel):
    host: str = "127.0.0.1"
    port: int = Field(default=8002, ge=1, le=65535)
    log_level: str = Field(
        default="INFO", pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$"
    )
    db_host: str = "127.0.0.1"
    db_port: int = Field(default=3307, ge=1, le=65535)
    db_name: str = ""
    db_user: str = ""
    db_password: SecretStr = SecretStr("")
    db_timeout: int = Field(default=3, ge=1, le=30)
    project_root: str = str(Path(__file__).resolve().parents[2])
    media_root: str = ""
    question_bank_root: str = ""
    auth_secret: SecretStr = SecretStr("")
    algorithm_secret: SecretStr = SecretStr("")
    api_pool_path: str = ""
    compute_timeout: float = Field(default=200, ge=0.01, le=600)
    learning_task_worker_enabled: bool = False
    max_request_bytes: int = Field(default=16 * 1024 * 1024, ge=1)

    @classmethod
    def load(cls):
        # Parse trusted local configuration without executing shell code.
        path, values = configuration()
        result = {}
        for field in cls.model_fields:
            key = "CUOTI_" + field.upper()
            legacy = "CANGJIE_" + field.upper()
            if key in values:
                result[field] = values[key]
            elif legacy in values and (
                field.startswith("db_")
                or field
                in [
                    "auth_secret",
                    "algorithm_secret",
                    "api_pool_path",
                    "media_root",
                    "question_bank_root",
                ]
            ):
                result[field] = values[legacy]
        if "CUOTI_PORT" not in values and "CANGJIE_BACKEND_PORT" in values:
            result["port"] = values["CANGJIE_BACKEND_PORT"]
        result.setdefault("project_root", str(path.parent))
        root = Path(result["project_root"])
        for field, stem in [
            ("auth_secret", "auth-secret"),
            ("algorithm_secret", "algorithm-secret"),
        ]:
            for prefix in ["cuoti-", "cangjie-"]:
                file = root / ".runtime" / (prefix + stem)
                if field not in result and file.is_file():
                    result[field] = file.read_text().strip()
        if "CUOTI_MEDIA_ROOT" not in values and values.get("CANGJIE_MEDIA_ROOT"):
            legacy_media = Path(values["CANGJIE_MEDIA_ROOT"])
            result["media_root"] = str(
                legacy_media
                if legacy_media.is_absolute()
                else root / "backend-cangjie" / legacy_media
            )
        if not result.get("media_root"):
            legacy_media = root / "backend-cangjie/media"
            result["media_root"] = str(
                legacy_media if legacy_media.is_dir() else root / "media"
            )
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
