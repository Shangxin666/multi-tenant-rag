from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker
from app.api.dependencies import Database, get_current_user
from app.core.config import Settings, get_settings
from app.modules.users.models import User
from app.modules.knowledge_bases.models import KnowledgeBase
from app.modules.rag.embedding import EmbeddingBackend, get_embedding_backend
from app.modules.rag.reranking import RerankerBackend, get_reranker_backend
from app.modules.agent.backend import AgentBackend, DeepSeekAgentBackend, get_agent_backend
from app.modules.agent.tools import ReadTools, get_agent_session_factory
from app.modules.agent.runtime import Scope, Run, capacity
from app.modules.agent.graph import Context
from app.modules.agent.schemas import AgentRequest
from app.modules.agent.streaming import AgentResponse

router = APIRouter(tags=["agent"])


@router.post("/knowledge-bases/{knowledge_base_id}/agent/stream", response_class=AgentResponse)
async def agent_stream(knowledge_base_id: UUID, request: AgentRequest, session: Database,
    user: Annotated[User, Depends(get_current_user)], settings: Annotated[Settings, Depends(get_settings)],
    backend: Annotated[AgentBackend, Depends(get_agent_backend)],
    embedding: Annotated[EmbeddingBackend, Depends(get_embedding_backend)],
    reranker: Annotated[RerankerBackend, Depends(get_reranker_backend)],
    factory: Annotated[async_sessionmaker, Depends(get_agent_session_factory)]) -> AgentResponse:
    scope = Scope(user.id, user.tenant_id, knowledge_base_id)
    try:
        kb = await session.scalar(select(KnowledgeBase.id).where(KnowledgeBase.id == knowledge_base_id,
                                                               KnowledgeBase.tenant_id == scope.tenant_id))
    except Exception:
        raise HTTPException(503, "Agent unavailable") from None
    finally:
        await session.rollback()
        await session.close()
    if kb is None:
        raise HTTPException(404, "Knowledge base not found")
    if isinstance(backend, DeepSeekAgentBackend) and (settings.deepseek_api_key is None or not settings.deepseek_api_key.get_secret_value().strip()):
        raise HTTPException(503, "Agent unavailable")
    if not capacity.acquire(settings.agent_max_concurrent):
        raise HTTPException(429, "Agent capacity exhausted", headers={"Retry-After": "5"})
    run = Run(settings.agent_timeout_seconds, capacity)
    try:
        tools = ReadTools(scope, factory, settings, embedding, reranker, run, request.top_k)
        context = Context(run, settings, backend, tools, None)
        return AgentResponse(context, request.question, knowledge_base_id)
    except BaseException:
        run.close()
        raise
