from functools import lru_cache
from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "HelpBot"
    environment: str = "development"
    log_level: str = "INFO"

    openrouter_api_key: str = Field(default="", repr=False)
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_chat_model: str = "openai/gpt-4o-mini"
    openrouter_embedding_model: str = "openai/text-embedding-3-large"
    openrouter_http_referer: str = "http://localhost:8000"
    openrouter_x_title: str = "HelpBot"

    database_url: str = "postgresql://helpbot:helpbot@localhost:5432/helpbot"
    docs_dir: Path = Path("backend/docs")
    prompt_path: Path = Path("backend/prompt.txt")

    embedding_dimensions: int = 3072
    rag_top_k: int = 4
    rag_similarity_threshold: float = 0.45
    request_timeout_seconds: float = 24
    llm_timeout_seconds: float = 18
    max_context_chars: int = 6500
    max_message_chars: int = 2000

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @model_validator(mode="after")
    def normalize_embedding_dimensions(self) -> "Settings":
        expected_dimensions = _known_embedding_dimensions(self.openrouter_embedding_model)
        if expected_dimensions is not None:
            self.embedding_dimensions = expected_dimensions
        return self

    @property
    def has_openrouter_key(self) -> bool:
        return bool(self.openrouter_api_key and self.openrouter_api_key != "replace-me")


@lru_cache
def get_settings() -> Settings:
    return Settings()


def _known_embedding_dimensions(model: str) -> int | None:
    normalized = model.lower()
    if normalized.endswith("text-embedding-3-large"):
        return 3072
    if normalized.endswith("text-embedding-3-small"):
        return 1536
    return None
