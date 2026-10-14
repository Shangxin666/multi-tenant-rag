from pathlib import Path
from uuid import UUID

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.modules.documents import service
from app.modules.documents.models import Document
from app.modules.documents.storage import LocalStorage
from app.modules.chunks.models import Chunk
from app.modules.documents.ingestion.types import ChunkDraft

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]
PUBLIC = {"id", "tenant_id", "knowledge_base_id", "filename", "source_type", "status",
          "error_message", "file_size_bytes", "created_at", "updated_at",
          "index_status", "index_error_message", "embedding_model", "indexed_at"}


@pytest.mark.parametrize("extension", ["md", "markdown", "html", "htm", "pdf"])
async def test_upload_ready(
    client: AsyncClient, ingestion_accounts: dict, db_engine: AsyncEngine,
    document_settings: Settings, sample_pdf: bytes, extension: str,
) -> None:
    account = ingestion_accounts["alpha"]
    data = sample_pdf if extension == "pdf" else (
        b"<title>Title</title><p>Hello HTML</p><script>ignored()</script>"
        if extension in {"html", "htm"} else ("# Heading\n\n" + "Markdown content. " * 200).encode()
    )
    response = await client.post(
        f"/knowledge-bases/{account['kb_id']}/documents", headers=account["headers"],
        files={"file": (f"../../display.{extension}", data, "application/octet-stream")},
    )
    assert response.status_code == 201
    body = response.json()
    assert set(body) == PUBLIC and body["status"] == "ready"
    assert body["filename"] == f"display.{extension}"
    assert body["file_size_bytes"] == len(data)
    async with async_sessionmaker(db_engine)() as session:
        document = await session.get(Document, UUID(body["id"]))
        assert document is not None and document.storage_key is not None
        assert "display" not in document.storage_key and not Path(document.storage_key).is_absolute()
        assert LocalStorage(document_settings.document_storage_root, document_settings.max_upload_bytes).verify(
            document.storage_key, document.file_size_bytes, document.content_sha256,
        ).read_bytes() == data
        chunks = list(await session.scalars(select(Chunk).where(Chunk.document_id == document.id).order_by(Chunk.chunk_index)))
        assert chunks and [c.chunk_index for c in chunks] == list(range(len(chunks)))
        assert {c.tenant_id for c in chunks} == {document.tenant_id}
        if extension == "pdf":
            assert [c.chunk_metadata["page"] for c in chunks] == [1, 2]
    member = await client.get("/documents/" + body["id"], headers=ingestion_accounts["member"]["headers"])
    assert member.status_code == 200 and member.json() == body
    assert (await client.get("/documents/" + body["id"], headers=ingestion_accounts["beta"]["headers"])).status_code == 404


@pytest.mark.parametrize(("name", "content", "code"), [
    ("bad.txt", b"data", 415), ("empty.md", b"", 422),
    ("big.md", b"x" * (10 * 1024 * 1024 + 1), 413),
], ids=["unsupported", "empty", "oversized"])
async def test_rejected_upload(
    client: AsyncClient, ingestion_accounts: dict, db_engine: AsyncEngine,
    document_settings: Settings, name: str, content: bytes, code: int,
) -> None:
    account = ingestion_accounts["alpha"]
    response = await client.post(f"/knowledge-bases/{account['kb_id']}/documents",
        headers=account["headers"], files={"file": (name, content)})
    assert response.status_code == code
    async with async_sessionmaker(db_engine)() as session:
        assert await session.scalar(select(func.count()).select_from(Document)) == 0
    assert not [p for p in document_settings.document_storage_root.rglob("*") if p.is_file()]


async def test_scope_and_form(client: AsyncClient, ingestion_accounts: dict) -> None:
    a, b, m = [ingestion_accounts[k] for k in ("alpha", "beta", "member")]
    path = f"/knowledge-bases/{a['kb_id']}/documents"
    assert (await client.post(path, headers=m["headers"], files={"file": ("ok.md", b"Hello")})).status_code == 403
    assert (await client.post(path, headers=b["headers"], files={"file": ("ok.md", b"Hello")})).status_code == 404
    assert (await client.post(path, files={"file": ("ok.md", b"Hello")})).status_code == 401
    assert (await client.post(path, headers=a["headers"], data={"tenant_id": b["tenant_id"]},
        files={"file": ("ok.md", b"Hello")})).status_code == 400


async def test_request_limit_without_content_length(client: AsyncClient, ingestion_accounts: dict) -> None:
    async def body():
        yield b'--test\r\nContent-Disposition: form-data; name="file"; filename="big.md"\r\nContent-Type: text/plain\r\n\r\n'
        for _ in range(12):
            yield b"x" * (1024 * 1024)
        yield b"\r\n--test--\r\n"
    a = ingestion_accounts["alpha"]
    response = await client.post(f"/knowledge-bases/{a['kb_id']}/documents",
        headers={**a["headers"], "Content-Type": "multipart/form-data; boundary=test"},
        content=body())
    assert response.status_code == 413


async def test_committed_states_outside_parse(
    client: AsyncClient, ingestion_accounts: dict, db_engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch,
) -> None:
    states = []
    original_claim, original_process = service.claim, service.process

    async def observe_claim(session, document_id, tenant_id, expected):
        assert not session.in_transaction()
        async with async_sessionmaker(db_engine)() as observer:
            document = await observer.get(Document, document_id)
            states.append(document.status)
        return await original_claim(session, document_id, tenant_id, expected)

    async def observe_process(session, document, storage, settings):
        assert not session.in_transaction()
        async with async_sessionmaker(db_engine)() as observer:
            states.append((await observer.get(Document, document.id)).status)
        response = await original_process(session, document, storage, settings)
        states.append(response.status)
        return response

    monkeypatch.setattr(service, "claim", observe_claim)
    monkeypatch.setattr(service, "process", observe_process)
    a = ingestion_accounts["alpha"]
    response = await client.post(f"/knowledge-bases/{a['kb_id']}/documents",
        headers=a["headers"], files={"file": ("ok.md", b"Hello")})
    assert response.status_code == 201 and states == ["pending", "processing", "ready"]


async def test_parser_failure(client: AsyncClient, ingestion_accounts: dict, db_engine: AsyncEngine) -> None:
    a = ingestion_accounts["alpha"]
    response = await client.post(f"/knowledge-bases/{a['kb_id']}/documents",
        headers=a["headers"], files={"file": ("broken.pdf", b"invalid PDF")})
    assert response.status_code == 201
    assert response.json()["status"] == "failed"
    assert response.json()["error_message"] == "Document could not be parsed"
    async with async_sessionmaker(db_engine)() as session:
        assert await session.scalar(select(func.count()).select_from(Chunk)) == 0


async def test_publish_failure_rolls_back_first_batch(
    client: AsyncClient, ingestion_accounts: dict, db_engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = service.publish
    async def invalid_publish(session, document, drafts):
        drafts = [ChunkDraft(i, "new content", {}) for i in range(101)] + [ChunkDraft(0, "duplicate", {})]
        await original(session, document, drafts)
    monkeypatch.setattr(service, "publish", invalid_publish)
    a = ingestion_accounts["alpha"]
    response = await client.post(f"/knowledge-bases/{a['kb_id']}/documents",
        headers=a["headers"], files={"file": ("ok.md", b"Hello")})
    assert response.status_code == 201 and response.json()["status"] == "failed"
    async with async_sessionmaker(db_engine)() as session:
        assert await session.scalar(select(func.count()).select_from(Chunk)) == 0


async def test_pending_insert_failure_cleans_file(
    client: AsyncClient, ingestion_accounts: dict, document_settings: Settings, monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def broken_flush(self, objects=None):
        raise RuntimeError("Simulated insert failure")
    monkeypatch.setattr(AsyncSession, "flush", broken_flush)
    a = ingestion_accounts["alpha"]
    response = await client.post(f"/knowledge-bases/{a['kb_id']}/documents",
        headers=a["headers"], files={"file": ("ok.md", b"Hello")})
    assert response.status_code == 503
    assert not [p for p in document_settings.document_storage_root.rglob("*") if p.is_file()]
