from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.local_secret import load_local_secret


class Settings(BaseSettings):
    database_url: str = "mysql+asyncmy://minddimension:minddimension@127.0.0.1:3307/minddimension"
    api_pool_path: Path = Path("backend/config/api_pool.json")
    ai_logical_model: str = "Qwen"
    upload_dir: Path = Path("uploads")
    ai_mode: str = "live"
    ai_probe_on_startup: bool = False
    auth_secret: str = Field(default_factory=load_local_secret)
    qdrant_url: str = "http://127.0.0.1:6333"
    qdrant_collection: str = "minddimension_questions_v1"
    retrieval_inference_url: str = "http://127.0.0.1:8011"
    retrieval_embedding_model: str = "BAAI/bge-m3"
    retrieval_embedding_dimension: int = 1024
    retrieval_reranker_model: str = "BAAI/bge-reranker-v2-m3"
    retrieval_model_cache: Path = Path(".models/bge")
    retrieval_batch_size: int = 16
    retrieval_max_length: int = 512
    retrieval_candidate_limit: int = 50
    retrieval_result_limit: int = 10

    @field_validator("auth_secret")
    @classmethod
    def validate_auth_secret(cls, value: str) -> str:
        if value == "minddimension-local-session-secret":
            return load_local_secret()
        if len(value) < 32:
            raise ValueError("AUTH_SECRET 至少需要 32 个字符")
        return value

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
