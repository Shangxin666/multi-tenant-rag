from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.db.tenant_context import TenantSession

settings = get_settings()
engine = create_async_engine(
    settings.application_database_url,
    echo=settings.db_echo,
    pool_pre_ping=True,
    hide_parameters=True,
)
session_factory = async_sessionmaker(engine, expire_on_commit=False, sync_session_class=TenantSession)


async def get_db() -> AsyncIterator[AsyncSession]:
    async with session_factory() as session:
        yield session
