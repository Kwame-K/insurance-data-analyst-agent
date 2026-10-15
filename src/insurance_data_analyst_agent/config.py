from __future__ import annotations

from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_path: Path = Path("data/insurance_portfolio.db")
    database_url: str | None = None
    dataset_version: str = "synthetic-v1"
    audit_directory: Path = Path("output/audits")
    chart_directory: Path = Path("output/charts")

    gemini_api_key: SecretStr | None = None
    gemini_model: str | None = None

    groq_api_key: SecretStr | None = None
    groq_model: str | None = None

    log_level: str = "INFO"


settings = Settings()
