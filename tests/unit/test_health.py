from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import get_settings


@pytest.mark.asyncio
async def test_health(config_env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    get_settings.cache_clear()
    from app.main import create_app
    async def validated_role(engine):
        pass
    monkeypatch.setattr("app.main.verify_runtime_role", validated_role)

    app = create_app()
    try:
        # Startup security validation is covered by real-role integration tests.
        async with app.router.lifespan_context(app):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
    finally:
        get_settings.cache_clear()
