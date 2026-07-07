from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_title: str = "PR Reviewer Assignment Service"
    app_version: str = "1.0.0"
    app_host: str = "0.0.0.0"
    app_port: int = Field(default=8080, ge=1, le=65535)

    database_url: str = (
        "postgresql+asyncpg://postgres:postgres@postgres:5432/pr_reviewer_assignment"
    )
    database_echo: bool = False
    database_pool_size: int = Field(default=5, ge=1)
    database_max_overflow: int = Field(default=10, ge=0)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
