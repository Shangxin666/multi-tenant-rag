from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from app.api.dependencies import Database, get_current_user, require_admin
from app.core.config import Settings, get_settings
from app.modules.documents import indexing
from app.modules.documents.service import get_public, unavailable
from app.modules.documents.schemas import DocumentPublic
from app.modules.documents.ingestion.errors import log_failure
from app.modules.knowledge_bases.models import KnowledgeBase
from app.modules.users.models import User
from app.modules.rag.embedding import EmbeddingBackend, get_embedding_backend
from app.modules.rag.generation import LlmBackend, get_llm_backend
from app.modules.rag.schemas import RagQueryRequest, RagQueryResponse
from app.modules.rag.service import query
from app.modules.rag.reranking import RerankerBackend, get_reranker_backend

router = APIRouter(tags=["rag"])
SettingsDep = Annotated[Settings, Depends(get_settings)]
EmbeddingDep = Annotated[EmbeddingBackend, Depends(get_embedding_backend)]
RerankerDep = Annotated[RerankerBackend, Depends(get_reranker_backend)]
LlmDep = Annotated[LlmBackend, Depends(get_llm_backend)]


@router.post("/documents/{document_id}/index", response_model=DocumentPublic)
async def index_document(document_id: UUID, session: Database,
                         user: Annotated[User, Depends(require_admin)],
                         settings: SettingsDep, embedding: EmbeddingDep) -> DocumentPublic:
    tenant_id = user.tenant_id
    try:
        await get_public(session, document_id, tenant_id)
        await session.rollback()
    except HTTPException:
        raise
    except Exception as exc:
        log_failure("Scope indexing document", exc)
        await session.rollback()
        raise unavailable(document_id) from None
    try:
        await indexing.claim(session, document_id, tenant_id)
    except HTTPException:
        raise
    except Exception as exc:
        log_failure("Claim indexing", exc)
        await session.rollback()
        raise unavailable(document_id) from None
    return await indexing.process(session, document_id, tenant_id, embedding, settings)


@router.post("/knowledge-bases/{knowledge_base_id}/query", response_model=RagQueryResponse)
async def query_knowledge_base(knowledge_base_id: UUID, request: RagQueryRequest, session: Database,
                               user: Annotated[User, Depends(get_current_user)],
                               settings: SettingsDep, embedding: EmbeddingDep, llm: LlmDep, reranker: RerankerDep) -> RagQueryResponse:
    tenant_id = user.tenant_id
    try:
        kb_id = await session.scalar(select(KnowledgeBase.id).where(
            KnowledgeBase.id == knowledge_base_id, KnowledgeBase.tenant_id == tenant_id,
        ))
        await session.rollback()
    except Exception as exc:
        log_failure("Scope query knowledge base", exc)
        await session.rollback()
        raise HTTPException(503, "Retrieval unavailable") from None
    if kb_id is None:
        raise HTTPException(404, "Knowledge base not found")
    return await query(session, tenant_id, kb_id, request, settings, embedding, llm, reranker)
