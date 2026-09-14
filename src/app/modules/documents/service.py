from dataclasses import dataclass
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import delete, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.core.config import Settings
from app.modules.chunks.models import Chunk
from app.modules.documents.ingestion.chunking import split_sections
from app.modules.documents.ingestion.errors import IngestionError, log_failure
from app.modules.documents.ingestion.parsers import parse_document
from app.modules.documents.ingestion.types import ChunkDraft
from app.modules.documents.models import Document
from app.modules.documents.schemas import DocumentPublic
from app.modules.documents.storage import LocalStorage, StoredFile


@dataclass(frozen=True)
class ProcessingDocument:
    id: UUID
    tenant_id: UUID
    storage_key: str
    file_size_bytes: int
    content_sha256: str
    source_type: str


def unavailable(document_id: UUID) -> HTTPException:
    return HTTPException(503, detail={
        "message": "Document processing is temporarily unavailable; check its status",
        "document_id": str(document_id),
    })


async def get_public(session: AsyncSession, document_id: UUID, tenant_id: UUID) -> DocumentPublic:
    document = await session.scalar(select(Document).where(
        Document.id == document_id, Document.tenant_id == tenant_id,
    ))
    if document is None:
        raise HTTPException(404, "Document not found")
    return DocumentPublic.model_validate(document)


async def create_pending(
    session: AsyncSession, tenant_id: UUID, knowledge_base_id: UUID,
    filename: str, source_type: str, stored: StoredFile, storage: LocalStorage,
) -> UUID:
    document_id = uuid4()
    commit_started = False
    try:
        session.add(Document(
            id=document_id, tenant_id=tenant_id, knowledge_base_id=knowledge_base_id,
            filename=filename, source_type=source_type, status="pending",
            storage_key=stored.key, file_size_bytes=stored.size, content_sha256=stored.sha256,
        ))
        await session.flush()
        commit_started = True
        await session.commit()
        return document_id
    except Exception as exc:
        log_failure("Create pending document", exc)
        await session.rollback()
        # A lost commit acknowledgement must not cause deletion of a committed file.
        if commit_started:
            try:
                exists = await session.scalar(select(Document.id).where(
                    Document.id == document_id, Document.tenant_id == tenant_id,
                ))
                await session.rollback()
                if exists is not None:
                    return document_id
            except Exception as check_error:
                log_failure("Reconcile pending document", check_error)
                await session.rollback()
            # Conservatively retain the file when commit outcome is uncertain.
        else:
            try:
                await run_in_threadpool(storage.remove, stored.key)
            except Exception as cleanup_error:
                log_failure("Clean unreferenced file", cleanup_error)
        raise unavailable(document_id) from None


async def claim(
    session: AsyncSession, document_id: UUID, tenant_id: UUID, expected: str,
) -> ProcessingDocument:
    async with session.begin():
        row = (await session.execute(
            update(Document).where(
                Document.id == document_id, Document.tenant_id == tenant_id,
                Document.status == expected, Document.storage_key.is_not(None),
            ).values(status="processing", error_message=None).returning(
                Document.id, Document.tenant_id, Document.storage_key,
                Document.file_size_bytes, Document.content_sha256, Document.source_type,
            )
        )).one_or_none()
        if row is None:
            raise HTTPException(409, "Document cannot be processed in its current state")
        return ProcessingDocument(*row)


def prepare_chunks(document: ProcessingDocument, storage: LocalStorage, settings: Settings) -> list[ChunkDraft]:
    path = storage.verify(document.storage_key, document.file_size_bytes, document.content_sha256)
    sections = parse_document(path, document.source_type, settings.max_pdf_pages, settings.max_parsed_chars)
    return split_sections(sections, settings.chunk_size, settings.chunk_overlap, settings.max_document_chunks)


async def publish(
    session: AsyncSession, document: ProcessingDocument, drafts: list[ChunkDraft],
) -> None:
    if not drafts:
        raise IngestionError("No extractable text found")
    async with session.begin():
        current = await session.scalar(select(Document).where(
            Document.id == document.id, Document.tenant_id == document.tenant_id,
        ).with_for_update())
        if current is None or current.status != "processing":
            raise IngestionError("Document processing state changed")
        await session.execute(delete(Chunk).where(
            Chunk.document_id == document.id, Chunk.tenant_id == document.tenant_id,
        ))
        for start in range(0, len(drafts), 100):
            await session.execute(insert(Chunk), [{
                "id": uuid4(), "tenant_id": document.tenant_id, "document_id": document.id,
                "chunk_index": draft.chunk_index, "content": draft.content,
                "chunk_metadata": draft.metadata,
            } for draft in drafts[start:start + 100]])
        current.status = "ready"
        current.error_message = None
        # The context commits all Chunk batches and status together.


async def process(
    session: AsyncSession, document: ProcessingDocument, storage: LocalStorage, settings: Settings,
) -> DocumentPublic:
    try:
        drafts = await run_in_threadpool(prepare_chunks, document, storage, settings)
        await publish(session, document, drafts)
    except Exception as exc:
        log_failure("Document ingestion", exc)
        summary = str(exc) if isinstance(exc, IngestionError) else "Document processing failed"
        try:
            await session.rollback()
            async with session.begin():
                # Never overwrite ready after an ambiguous publish commit.
                await session.execute(update(Document).where(
                    Document.id == document.id, Document.tenant_id == document.tenant_id,
                    Document.status == "processing",
                ).values(status="failed", error_message=summary))
        except Exception as status_error:
            log_failure("Record ingestion failure", status_error)
            await session.rollback()
            raise unavailable(document.id) from None
    try:
        return await get_public(session, document.id, document.tenant_id)
    except HTTPException:
        raise
    except Exception as exc:
        log_failure("Read ingestion result", exc)
        raise unavailable(document.id) from None
