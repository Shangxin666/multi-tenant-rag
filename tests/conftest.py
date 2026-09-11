import secrets
from pathlib import Path

import pytest


@pytest.fixture
def config_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Keep unit tests independent of local credentials and dotenv files."""
    for key in (
        "APP_ENV", "DB_HOST", "DB_PORT", "POSTGRES_DB",
        "POSTGRES_USER", "POSTGRES_PASSWORD", "DB_ECHO",
        "JWT_SECRET", "JWT_ALGORITHM", "ACCESS_TOKEN_EXPIRE_MINUTES", "TEST_DATABASE_NAME",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("POSTGRES_DB", "unit")
    monkeypatch.setenv("POSTGRES_USER", "unit")
    monkeypatch.setenv("POSTGRES_PASSWORD", secrets.token_urlsafe(24))
    monkeypatch.setenv("JWT_SECRET", secrets.token_urlsafe(48))
    return tmp_path
