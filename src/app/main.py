from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.body_limit import RequestBodyLimitMiddleware
from app.core.config import Settings, get_settings
from app.observability.trace import configure

from app.api.routes.health import router
from app.db.session import engine
from app.db.security import verify_runtime_role
from sqlalchemy.ext.asyncio import AsyncEngine
from app.modules.documents.router import router as documents_router
from app.modules.auth.router import router as auth_router
from app.modules.users.router import router as users_router
from app.modules.knowledge_bases.router import router as knowledge_bases_router
from app.modules.rag.router import router as rag_router
from app.modules.agent.router import router as agent_router


def create_app(settings: Settings | None = None, *, database_engine: AsyncEngine | None = None) -> FastAPI:
    settings = settings or get_settings()
    runtime_engine = database_engine if database_engine is not None else engine
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        configure(settings.trace_path if settings.trace_enabled else None)
        try:
            await verify_runtime_role(runtime_engine)
            yield
        finally:
            configure(None)
            await runtime_engine.dispose()
    application = FastAPI(title="Knowledge Base API", lifespan=lifespan)
    application.add_middleware(RequestBodyLimitMiddleware, max_body_size=settings.max_upload_request_bytes)
    application.include_router(documents_router)
    application.include_router(rag_router)
    application.include_router(agent_router)
    application.include_router(router)
    application.include_router(auth_router)
    application.include_router(users_router)
    application.include_router(knowledge_bases_router)
    return application


app = create_app()
