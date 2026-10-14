from uuid import uuid4
import pytest
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import Settings
from app.db.tenant_context import TenantSession, bind_tenant


@pytest.mark.asyncio
async def test_session_binding_lifetime():
    tenant = uuid4()
    async with AsyncSession(sync_session_class=TenantSession) as session:
        bind_tenant(session, tenant)
        bind_tenant(session, tenant)
        with pytest.raises(RuntimeError, match="switch tenants"):
            bind_tenant(session, uuid4())
        with pytest.raises(TypeError): bind_tenant(session, str(tenant))
        async with session.begin():
            with pytest.raises(RuntimeError, match="Finish authentication"):
                bind_tenant(session, tenant)
        assert session.info["tenant_id"] == tenant
    assert "tenant_id" not in session.info


def test_runtime_needs_no_admin_or_migration_secret(config_env, monkeypatch):
    monkeypatch.delenv("POSTGRES_PASSWORD")
    settings = Settings()
    assert settings.application_database_url.username == "rag_app"
    with pytest.raises(ValueError): _ = settings.database_url
    with pytest.raises(ValueError): _ = settings.migration_database_url


def test_no_privileged_fallback(config_env, monkeypatch):
    monkeypatch.delenv("APP_DB_PASSWORD")
    settings = Settings()
    assert settings.database_url.username == "unit"
    with pytest.raises(ValueError): _ = settings.application_database_url


def test_separate_urls_escape_secrets(config_env):
    settings = Settings(app_db_password=SecretStr("test@:/%#"), migration_db_password=SecretStr("migration@:/%#"))
    assert settings.application_database_url.password == "test@:/%#"
    assert settings.migration_database_url.password == "migration@:/%#"
    assert settings.migration_database_url.username == "rag_migrator"
    assert "test@" not in str(settings.application_database_url)
