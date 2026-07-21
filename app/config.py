from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "GridWatch AI"
    database_url: str = "sqlite:///./gridwatch.db"
    minimum_analysis_points: int = 12
    minimum_monitoring_points: int = Field(default=300, ge=300)
    maximum_monitoring_points: int = 50_000
    log_level: str = "INFO"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()
