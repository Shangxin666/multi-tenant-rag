from app.observability.trace import traced
import json
from typing import Protocol
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker
from app.db.session import session_factory
from app.db.tenant_context import bind_tenant
from app.core.config import Settings
from app.modules.users.models import User
from app.modules.knowledge_bases.models import KnowledgeBase
from app.modules.documents.models import Document
from app.modules.rag.pipeline import retrieve_evidence
from app.modules.rag.schemas import RagQueryRequest
from app.modules.rag.embedding import EmbeddingBackend
from app.modules.rag.reranking import RerankerBackend
from app.modules.agent.runtime import Scope, Run
from app.modules.agent.sources import Sources
from app.modules.agent.schemas import SearchArgs, DocumentArgs, AgentError


class ToolBackend(Protocol):
    async def execute(self, name: str, args: SearchArgs | DocumentArgs, sources: Sources) -> dict: ...


def get_agent_session_factory() -> async_sessionmaker:
    return session_factory


class ReadTools:
    def __init__(self, scope: Scope, factory: async_sessionmaker, settings: Settings,
                 embedding: EmbeddingBackend, reranker: RerankerBackend, run: Run, top_k: int) -> None:
        self.scope, self.factory, self.settings = scope, factory, settings
        self.embedding, self.reranker, self.run, self.top_k = embedding, reranker, run, top_k

    @traced("tool")
    async def execute(self, name: str, args: SearchArgs | DocumentArgs, sources: Sources) -> dict:
        scope = self.scope
        async with self.factory() as session:
            bind_tenant(session, scope.tenant_id)
            active = await session.scalar(select(User.id).where(User.id == scope.user_id,
                User.tenant_id == scope.tenant_id, User.is_active.is_(True)))
            kb = await session.scalar(select(KnowledgeBase.id).where(KnowledgeBase.id == scope.knowledge_base_id,
                KnowledgeBase.tenant_id == scope.tenant_id))
            if active is None:
                raise AgentError("forbidden")
            if kb is None:
                raise AgentError("resource_not_found")
            await session.rollback()
            if name == "search_knowledge_base" and isinstance(args, SearchArgs):
                rows = await retrieve_evidence(session, scope.tenant_id, scope.knowledge_base_id,
                    RagQueryRequest(question=args.query, top_k=min(args.top_k, self.top_k)),
                    self.settings, self.embedding, self.reranker, self.run.cpu)
                blocks = []
                exhausted = False
                for row in rows:
                    block = sources.chunk(row)
                    if block is None:
                        exhausted = True
                        break
                    blocks.append(block)
                return {"results": blocks, "context_budget_exhausted": exhausted}
            if name == "get_document_info" and isinstance(args, DocumentArgs):
                row = (await session.execute(select(Document.id, Document.filename, Document.source_type,
                    Document.status, Document.index_status, Document.created_at, Document.updated_at).where(
                    Document.id == args.document_id, Document.tenant_id == scope.tenant_id,
                    Document.knowledge_base_id == scope.knowledge_base_id))).mappings().one_or_none()
                if row is None:
                    raise AgentError("resource_not_found")
                evidence = {key: str(value) for key, value in row.items()}
                await session.rollback()
                summary = json.dumps({"status": evidence["status"], "index_status": evidence["index_status"]})
                block = sources.add("document", evidence["id"], dict(document_id=evidence["id"],
                    filename=evidence["filename"], snippet=summary), evidence)
                return {"results": [block] if block else [], "context_budget_exhausted": block is None}
            raise AgentError("invalid_tool")
