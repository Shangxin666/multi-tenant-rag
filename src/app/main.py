from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes.health import router
from app.db.session import engine


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    try:
        yield
    finally:
        await engine.dispose()


def create_app() -> FastAPI:
    application = FastAPI(title="Knowledge Base API", lifespan=lifespan)
    application.include_router(router)
    return application


app = create_app()
