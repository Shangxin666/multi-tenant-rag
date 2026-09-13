from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes.health import router
from app.db.session import engine
from app.modules.auth.router import router as auth_router
from app.modules.users.router import router as users_router
from app.modules.knowledge_bases.router import router as knowledge_bases_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    try:
        yield
    finally:
        await engine.dispose()


def create_app() -> FastAPI:
    application = FastAPI(title="Knowledge Base API", lifespan=lifespan)
    application.include_router(router)
    application.include_router(auth_router)
    application.include_router(users_router)
    application.include_router(knowledge_bases_router)
    return application


app = create_app()
