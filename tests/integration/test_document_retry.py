import asyncio
import threading
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from app.core.config import Settings
from app.modules.documents import service
from app.modules.documents.ingestion.errors import IngestionError
from app.modules.documents.ingestion.types import ChunkDraft
from app.modules.documents.models import Document
from app.modules.documents.storage import LocalStorage
from app.modules.chunks.models import Chunk

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def upload_ready(client: AsyncClient, accounts: dict) -> dict:
    a = accounts["alpha"]
    response = await client.post(f"/knowledge-bases/{a['kb_id']}/documents",
        headers=a["headers"], files={"file": ("original.md", b"Original text for ingestion.")})
    assert response.status_code == 201 and response.json()["status"] == "ready"
    return response.json()


async def set_state(engine: AsyncEngine, document_id: str, status: str) -> None:
    async with engine.begin() as connection:
        await connection.execute(update(Document).where(Document.id == UUID(document_id)).values(status=status))


async def chunk_ids(engine: AsyncEngine, document_id: str) -> list:
    async with async_sessionmaker(engine)() as session:
        return list(await session.scalars(select(Chunk.id).where(Chunk.document_id == UUID(document_id)).order_by(Chunk.chunk_index)))


async def test_failed_retry_success(client: AsyncClient, ingestion_accounts: dict, monkeypatch: pytest.MonkeyPatch) -> None:
    original = service.prepare_chunks
    def fail(*args):
        raise IngestionError("Document could not be parsed")
    monkeypatch.setattr(service, "prepare_chunks", fail)
    a = ingestion_accounts["alpha"]
    response = await client.post(f"/knowledge-bases/{a['kb_id']}/documents",
        headers=a["headers"], files={"file": ("original.md", b"Original text")})
    assert response.json()["status"] == "failed"
    monkeypatch.setattr(service, "prepare_chunks", original)
    retried = await client.post("/documents/" + response.json()["id"] + "/retry", headers=a["headers"])
    assert retried.status_code == 200 and retried.json()["status"] == "ready"
    assert retried.json()["error_message"] is None


async def test_retry_replaces_all_old_chunks(client: AsyncClient, ingestion_accounts: dict, db_engine: AsyncEngine) -> None:
    document = await upload_ready(client, ingestion_accounts)
    before = await chunk_ids(db_engine, document["id"])
    await set_state(db_engine, document["id"], "failed")
    response = await client.post(f"/documents/{document['id']}/retry", headers=ingestion_accounts["alpha"]["headers"])
    after = await chunk_ids(db_engine, document["id"])
    assert response.status_code == 200 and response.json()["status"] == "ready"
    assert before and after and not set(before) & set(after)


async def test_retry_publish_failure_preserves_old_chunks(
    client: AsyncClient, ingestion_accounts: dict, db_engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch,
) -> None:
    document = await upload_ready(client, ingestion_accounts)
    before = await chunk_ids(db_engine, document["id"])
    await set_state(db_engine, document["id"], "failed")
    original = service.publish
    async def fail_publish(session, claimed, drafts):
        drafts = [ChunkDraft(i, "Replacement", {}) for i in range(101)] + [ChunkDraft(0, "Duplicate", {})]
        await original(session, claimed, drafts)
    monkeypatch.setattr(service, "publish", fail_publish)
    response = await client.post(f"/documents/{document['id']}/retry", headers=ingestion_accounts["alpha"]["headers"])
    assert response.status_code == 200 and response.json()["status"] == "failed"
    assert await chunk_ids(db_engine, document["id"]) == before


@pytest.mark.parametrize("state", ["pending", "processing", "ready"])
async def test_retry_conflict(client: AsyncClient, ingestion_accounts: dict, db_engine: AsyncEngine, state: str) -> None:
    document = await upload_ready(client, ingestion_accounts)
    await set_state(db_engine, document["id"], state)
    response = await client.post(f"/documents/{document['id']}/retry", headers=ingestion_accounts["alpha"]["headers"])
    assert response.status_code == 409


async def test_retry_scope(client: AsyncClient, ingestion_accounts: dict, db_engine: AsyncEngine) -> None:
    document = await upload_ready(client, ingestion_accounts)
    await set_state(db_engine, document["id"], "failed")
    assert (await client.post(f"/documents/{document['id']}/retry", headers=ingestion_accounts["beta"]["headers"])).status_code == 404
    assert (await client.post(f"/documents/{document['id']}/retry", headers=ingestion_accounts["member"]["headers"])).status_code == 403


async def test_concurrent_retry_single_claim(
    client: AsyncClient, ingestion_accounts: dict, db_engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch,
) -> None:
    document = await upload_ready(client, ingestion_accounts)
    await set_state(db_engine, document["id"], "failed")
    entered, release = threading.Event(), threading.Event()
    original = service.prepare_chunks
    calls = []
    def blocked(*args):
        calls.append(1)
        entered.set()
        if not release.wait(10):
            raise RuntimeError("Test barrier timed out")
        return original(*args)
    monkeypatch.setattr(service, "prepare_chunks", blocked)
    path = f"/documents/{document['id']}/retry"
    headers = ingestion_accounts["alpha"]["headers"]
    first = asyncio.create_task(client.post(path, headers=headers))
    try:
        assert await asyncio.wait_for(asyncio.to_thread(entered.wait, 5), timeout=6)
        second = await client.post(path, headers=headers)
        assert second.status_code == 409
    finally:
        release.set()
        result = await first
    assert result.status_code == 200 and result.json()["status"] == "ready"
    assert len(calls) == 1


async def test_retry_integrity_failure(
    client: AsyncClient, ingestion_accounts: dict, db_engine: AsyncEngine, document_settings: Settings,
) -> None:
    document = await upload_ready(client, ingestion_accounts)
    await set_state(db_engine, document["id"], "failed")
    before = await chunk_ids(db_engine, document["id"])
    async with async_sessionmaker(db_engine)() as session:
        row = await session.get(Document, UUID(document["id"]))
        path = LocalStorage(document_settings.document_storage_root, document_settings.max_upload_bytes).path_for(row.storage_key)
    path.write_bytes(b"Changed")
    response = await client.post(f"/documents/{document['id']}/retry", headers=ingestion_accounts["alpha"]["headers"])
    assert response.json()["status"] == "failed"
    assert response.json()["error_message"] == "Original file integrity check failed"
    assert await chunk_ids(db_engine, document["id"]) == before


async def test_legacy_without_file_cannot_retry(client: AsyncClient, ingestion_accounts: dict, db_engine: AsyncEngine) -> None:
    a = ingestion_accounts["alpha"]
    async with async_sessionmaker(db_engine, expire_on_commit=False)() as session:
        async with session.begin():
            row = Document(tenant_id=UUID(a["tenant_id"]), knowledge_base_id=UUID(a["kb_id"]),
                filename="legacy.md", source_type="markdown", status="failed")
            session.add(row)
        document_id = row.id
    assert (await client.post(f"/documents/{document_id}/retry", headers=a["headers"])).status_code == 409


async def test_retry_commit_failure_preserves_old_chunks(
    client: AsyncClient, ingestion_accounts: dict, db_engine: AsyncEngine,
) -> None:
    from sqlalchemy import Connection, event, text

    document = await upload_ready(client, ingestion_accounts)
    before = await chunk_ids(db_engine, document["id"])
    await set_state(db_engine, document["id"], "failed")
    failures = []

    def fail_before_commit(connection: Connection) -> None:
        current = connection.scalar(text("SELECT status FROM documents WHERE id=:id"), {"id": document["id"]})
        if current == "ready" and not failures:
            failures.append(True)
            raise RuntimeError("Simulated final commit failure")

    event.listen(db_engine.sync_engine, "commit", fail_before_commit)
    try:
        response = await client.post(f"/documents/{document['id']}/retry", headers=ingestion_accounts["alpha"]["headers"])
        assert response.status_code == 200 and response.json()["status"] == "failed"
    finally:
        event.remove(db_engine.sync_engine, "commit", fail_before_commit)
    assert failures == [True]
    assert await chunk_ids(db_engine, document["id"]) == before
