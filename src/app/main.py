from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.body_limit import RequestBodyLimitMiddleware
from app.core.config import Settings, get_settings

from app.api.routes.health import router
from app.db.session import engine
from app.modules.documents.router import router as documents_router
from app.modules.auth.router import router as auth_router
from app.modules.users.router import router as users_router
from app.modules.knowledge_bases.router import router as knowledge_bases_router
from app.modules.rag.router import router as rag_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    try:
        yield
    finally:
        await engine.dispose()


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    application = FastAPI(title="Knowledge Base API", lifespan=lifespan)
    application.add_middleware(RequestBodyLimitMiddleware, max_body_size=settings.max_upload_request_bytes)
    application.include_router(documents_router)
    application.include_router(rag_router)
    application.include_router(router)
    application.include_router(auth_router)
    application.include_router(users_router)
    application.include_router(knowledge_bases_router)
    return application


app = create_app()
