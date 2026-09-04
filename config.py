from __future__ import annotations

from functools import lru_cache
from typing import Any, Annotated

from pydantic import Field, BeforeValidator, AnyUrl, computed_field
from pydantic_settings import BaseSettings


def parse_cors(v: Any) -> list[str] | str:
    if isinstance(v, str) and not v.startswith("["):
        return [i.strip() for i in v.split(",") if i.strip()]
    elif isinstance(v, list | str):
        return v
    raise ValueError(v)


class Settings(BaseSettings):
    app_env: str = Field("development", alias="APP_ENV")
    log_level: str = Field("INFO", alias="LOG_LEVEL")
    db_host: str = Field("localhost", alias="DB_HOST")
    db_port: int = Field(5432, alias="DB_PORT")
    db_name: str = Field("dalphin_db", alias="DB_NAME")
    db_user: str = Field("postgres", alias="DB_USER")
    db_password: str = Field("root", alias="DB_PASSWORD")
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_model: str = Field("gpt-4o", alias="OPENAI_MODEL")
    openai_temperature: float = Field(0.0, alias="OPENAI_TEMPERATURE")
    openai_max_tokens: int = Field(4000, alias="OPENAI_MAX_TOKENS")
    chunk_size: int = Field(500, alias="CHUNK_SIZE")
    faiss_knn: int = Field(10, alias="FAISS_KNN")  # Balanced: increased from 3 to 10 for better video suggestions while maintaining reasonable latency
    faiss_index_path: str = Field("./storage/faiss_index", alias="FAISS_INDEX_PATH")
    debug_mode: bool = Field(False, alias="DEBUG_MODE")
    verbose_logging: bool = Field(False, alias="VERBOSE_LOGGING")
    scheduler_timezone: str = Field("Asia/Kolkata")
    
    # Query Expansion Settings
    enable_query_expansion: bool = Field(True, alias="ENABLE_QUERY_EXPANSION")
    query_expansion_use_llm: bool = Field(True, alias="QUERY_EXPANSION_USE_LLM")

   #parth
    external_api_key: str = Field("test-mode", alias="EXTERNAL_API_KEY")
    external_api_base_url: str = Field("test-mode", alias="EXTERNAL_API_BASE_URL")
    auth_api_base_url: str = Field("test-mode", alias="AUTH_API_BASE_URL")
    secret_key: str = Field("test-mode", alias="SECRET_KEY")
    algorithm: str = Field("test-mode", alias="ALGORITHM")
    image_base_url: str = Field("http://localhost:8000", alias="IMAGE_BASE_URL")
    forgot_password_api_url: str = Field("", alias="FORGOT_PASSWORD_API_URL")
    #parth

    # CORS settings
    FRONTEND_HOST:str = "http://localhost:3000"
    BACKEND_CORS_ORIGINS: Annotated[
        list[AnyUrl] | str, BeforeValidator(parse_cors)
    ] = []

    @computed_field  # type: ignore[prop-decorator]
    @property
    def all_cors_origins(self) -> list[str]:
        return [str(origin).rstrip("/") for origin in self.BACKEND_CORS_ORIGINS] + [
            self.FRONTEND_HOST
        ]

    # Rate Limiting
    enable_rate_limiting: bool = Field(True, alias="ENABLE_RATE_LIMITING")
    rate_limit_default: str = Field("100/minute", alias="RATE_LIMIT_DEFAULT")
    rate_limit_storage_url: str = Field("memory://", alias="RATE_LIMIT_STORAGE_URL")
    rate_limit_strategy: str = Field("fixed-window", alias="RATE_LIMIT_STRATEGY")

    # Rate limit buckets (auth endpoints)
    rate_limit_auth: str = Field("10/minute", alias="RATE_LIMIT_AUTH")
    rate_limit_api: str = Field("60/minute", alias="RATE_LIMIT_API")
    rate_limit_chat: str = Field("30/minute", alias="RATE_LIMIT_CHAT")

    serve_static_files: bool = Field(True, alias="SERVE_STATIC_FILES")
    ui_directory: str = Field("ui", alias="UI_DIRECTORY")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()