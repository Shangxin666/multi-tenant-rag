from app.observability.trace import traced
from uuid import UUID
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.modules.documents.ingestion.errors import log_failure
from app.modules.rag.embedding import EmbeddingBackend
from app.modules.rag.reranking import RerankerBackend
from app.modules.rag.pipeline import retrieve_evidence
from app.modules.rag.context import build_context
from app.modules.rag.generation import LlmBackend, GenerationError, generate_answer
from app.modules.rag.schemas import RagQueryRequest, RagQueryResponse

NO_ANSWER = "当前知识库中没有足够的信息回答该问题"


@traced("rag.query", root=True)
async def query(session: AsyncSession, tenant_id: UUID, kb_id: UUID, request: RagQueryRequest,
                settings: Settings, embedding: EmbeddingBackend, llm: LlmBackend, reranker: RerankerBackend) -> RagQueryResponse:
    rows = await retrieve_evidence(session, tenant_id, kb_id, request, settings, embedding, reranker)
    context = build_context(rows, settings.max_rag_context_chars)
    if not context.sources:
        return RagQueryResponse(answer=NO_ANSWER, sources=[])
    try:
        answer = await generate_answer(llm, request.question, context)
    except GenerationError as exc:
        log_failure("Generate answer", exc)
        raise HTTPException(exc.status_code, str(exc)) from None
    except Exception as exc:
        log_failure("Generate answer", exc)
        raise HTTPException(502, "Invalid answer from provider") from None
    return RagQueryResponse(answer=answer, sources=context.sources)
