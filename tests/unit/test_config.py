from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_dotenv_and_environment_override(config_env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (config_env / ".env").write_text("DB_PORT=5434\nDB_ECHO=true\n", encoding="utf-8")
    assert Settings().db_port == 5434
    assert Settings().db_echo is True
    monkeypatch.setenv("DB_PORT", "5435")
    assert Settings().db_port == 5435


@pytest.mark.parametrize("password", [None, ""])
def test_password_required(config_env: Path, monkeypatch: pytest.MonkeyPatch, password: str | None) -> None:
    monkeypatch.delenv("POSTGRES_PASSWORD")
    if password is not None:
        monkeypatch.setenv("POSTGRES_PASSWORD", password)
    with pytest.raises(ValidationError):
        Settings()


@pytest.mark.parametrize("port", ["invalid", "0", "65536"])
def test_invalid_port(config_env: Path, monkeypatch: pytest.MonkeyPatch, port: str) -> None:
    monkeypatch.setenv("DB_PORT", port)
    with pytest.raises(ValidationError):
        Settings()


def test_url_preserves_password(config_env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import secrets

    password = secrets.token_urlsafe(24) + "@:/%#"
    monkeypatch.setenv("POSTGRES_PASSWORD", password)
    settings = Settings()
    assert settings.database_url.password == password
    assert settings.database_url.drivername == "postgresql+asyncpg"
    assert password not in repr(settings)
    assert password not in str(settings.database_url)
