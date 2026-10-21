from uuid import UUID
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.core.config import Settings
from app.modules.documents.ingestion.errors import log_failure
from app.modules.rag.embedding import EmbeddingBackend, validate_vectors
from app.modules.rag.retrieval import has_chunks, retrieve_chunks, retrieve_sparse
from app.modules.rag.fusion import fuse_rrf
from app.modules.rag.reranking import RerankerBackend, rerank
from app.modules.rag.context import build_context
from app.modules.rag.generation import LlmBackend, GenerationError, generate_answer
from app.modules.rag.schemas import RagQueryRequest, RagQueryResponse

NO_ANSWER = "当前知识库中没有足够的信息回答该问题"


async def query(session: AsyncSession, tenant_id: UUID, kb_id: UUID, request: RagQueryRequest,
                settings: Settings, embedding: EmbeddingBackend, llm: LlmBackend, reranker: RerankerBackend) -> RagQueryResponse:
    try:
        exists = await has_chunks(session, tenant_id, kb_id, settings.embedding_model)
        await session.rollback()
    except Exception as exc:
        log_failure("Check indexed chunks", exc)
        await session.rollback()
        raise HTTPException(503, "Retrieval unavailable") from None
    if not exists:
        return RagQueryResponse(answer=NO_ANSWER, sources=[])
    try:
        vector = await run_in_threadpool(embedding.embed_query, request.question)
        vector = validate_vectors([vector], 1)[0]
    except Exception as exc:
        log_failure("Query embedding", exc)
        raise HTTPException(503, "Query embedding unavailable") from None
    try:
        dense = await retrieve_chunks(session, tenant_id, kb_id, settings.embedding_model, vector, settings.dense_candidate_k)
        sparse = await retrieve_sparse(session, tenant_id, kb_id, settings.embedding_model, vector,
                                       request.question, settings.sparse_candidate_k)
        await session.rollback()
    except Exception as exc:
        log_failure("Hybrid retrieval", exc)
        await session.rollback()
        raise HTTPException(503, "Retrieval unavailable") from None
    candidates = [item.chunk for item in fuse_rrf([dense, sparse], settings.rrf_k)[:settings.rerank_candidate_k]]
    try:
        rows = await run_in_threadpool(rerank, reranker, request.question, candidates, request.top_k)
    except Exception as exc:
        log_failure("Rerank", exc)
        raise HTTPException(503, "Reranking unavailable") from None
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
