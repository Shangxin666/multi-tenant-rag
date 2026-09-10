from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import get_settings


@pytest.mark.asyncio
async def test_health(config_env: Path) -> None:
    get_settings.cache_clear()
    from app.main import create_app

    app = create_app()
    try:
        # Explicitly exercise lifespan too; no database is running or needed.
        async with app.router.lifespan_context(app):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
    finally:
        get_settings.cache_clear()
