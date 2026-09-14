from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        hide_input_in_errors=True,
    )

    app_env: Literal["local", "test", "production"] = "local"
    db_host: str = Field(default="127.0.0.1", min_length=1)
    db_port: int = Field(default=5433, ge=1, le=65535)
    postgres_db: str = Field(min_length=1)
    postgres_user: str = Field(min_length=1)
    postgres_password: SecretStr
    db_echo: bool = False
    jwt_secret: SecretStr
    jwt_algorithm: Literal["HS256"] = "HS256"
    access_token_expire_minutes: int = Field(default=30, ge=1, le=1440)
    test_database_name: str | None = None
    document_storage_root: Path = Path(".data/documents")
    max_upload_bytes: int = Field(default=10 * 1024 * 1024, ge=1)
    max_upload_request_bytes: int = Field(default=11 * 1024 * 1024, ge=1)
    chunk_size: int = Field(default=1000, ge=1)
    chunk_overlap: int = Field(default=150, ge=0)
    max_pdf_pages: int = Field(default=200, ge=1)
    max_parsed_chars: int = Field(default=2_000_000, ge=1)
    max_document_chunks: int = Field(default=5000, ge=1)

    @model_validator(mode="after")
    def validate_ingestion_limits(self) -> "Settings":
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("CHUNK_OVERLAP must be smaller than CHUNK_SIZE")
        if self.max_upload_request_bytes <= self.max_upload_bytes:
            raise ValueError("Request size limit must allow multipart overhead")
        return self

    @field_validator("jwt_secret")
    @classmethod
    def validate_jwt_secret(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value().strip().encode("utf-8")) < 32:
            raise ValueError("JWT_SECRET must contain at least 32 bytes")
        return value

    @field_validator("postgres_password")
    @classmethod
    def password_not_empty(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value().strip():
            raise ValueError("POSTGRES_PASSWORD must not be empty")
        return value

    @property
    def database_url(self) -> URL:
        return URL.create(
            drivername="postgresql+asyncpg",
            username=self.postgres_user,
            password=self.postgres_password.get_secret_value(),
            host=self.db_host,
            port=self.db_port,
            database=self.postgres_db,
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
