from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile

from app.api.dependencies import Database, get_current_user, require_admin
from app.core.config import Settings, get_settings
from app.modules.documents import service
from app.modules.documents.ingestion.errors import UploadError, log_failure
from app.modules.documents.schemas import DocumentPublic
from app.modules.documents.storage import LocalStorage, upload_name
from app.modules.knowledge_bases.models import KnowledgeBase
from app.modules.users.models import User

router = APIRouter(tags=["documents"])
SettingsDependency = Annotated[Settings, Depends(get_settings)]
UPLOAD_OPENAPI = {
    "requestBody": {
        "required": True,
        "content": {"multipart/form-data": {"schema": {
            "type": "object", "required": ["file"], "additionalProperties": False,
            "properties": {"file": {"type": "string", "format": "binary"}},
        }}},
    }
}


async def claim_and_process(
    session: AsyncSession, document_id: UUID, tenant_id: UUID, expected: str,
    storage: LocalStorage, settings: Settings,
) -> DocumentPublic:
    try:
        claimed = await service.claim(session, document_id, tenant_id, expected)
    except HTTPException:
        raise
    except Exception as exc:
        log_failure("Claim document", exc)
        await session.rollback()
        raise service.unavailable(document_id) from None
    return await service.process(session, claimed, storage, settings)


@router.post(
    "/knowledge-bases/{knowledge_base_id}/documents",
    status_code=201, response_model=DocumentPublic, openapi_extra=UPLOAD_OPENAPI,
)
async def upload(
    knowledge_base_id: UUID, request: Request, session: Database,
    current_user: Annotated[User, Depends(require_admin)], settings: SettingsDependency,
) -> DocumentPublic:
    tenant_id = current_user.tenant_id
    kb_id = await session.scalar(select(KnowledgeBase.id).where(
        KnowledgeBase.id == knowledge_base_id, KnowledgeBase.tenant_id == tenant_id,
    ))
    if kb_id is None:
        raise HTTPException(404, "Knowledge base not found")
    # Release the authentication/read transaction before even parsing multipart.
    await session.rollback()
    storage = LocalStorage(settings.document_storage_root, settings.max_upload_bytes)
    if request.headers.get("content-type", "").split(";", 1)[0].lower() != "multipart/form-data":
        raise HTTPException(415, "Expected multipart/form-data")
    async with request.form(max_files=1, max_fields=0) as form:
        entries = form.multi_items()
        if len(entries) != 1 or entries[0][0] != "file" or not isinstance(entries[0][1], UploadFile):
            raise HTTPException(422, "Exactly one file is required")
        uploaded = entries[0][1]
        try:
            filename, source_type = upload_name(uploaded.filename)
            stored = await run_in_threadpool(storage.save, uploaded.file, tenant_id)
        except UploadError as exc:
            raise HTTPException(exc.status_code, exc.detail) from None
        except OSError as exc:
            log_failure("Save uploaded file", exc)
            raise HTTPException(503, "File storage is temporarily unavailable") from None
    document_id = await service.create_pending(
        session, tenant_id, kb_id, filename, source_type, stored, storage,
    )
    return await claim_and_process(session, document_id, tenant_id, "pending", storage, settings)


@router.get("/documents/{document_id}", response_model=DocumentPublic)
async def detail(
    document_id: UUID, session: Database,
    current_user: Annotated[User, Depends(get_current_user)],
) -> DocumentPublic:
    return await service.get_public(session, document_id, current_user.tenant_id)


@router.post("/documents/{document_id}/retry", response_model=DocumentPublic)
async def retry(
    document_id: UUID, session: Database,
    current_user: Annotated[User, Depends(require_admin)], settings: SettingsDependency,
) -> DocumentPublic:
    tenant_id = current_user.tenant_id
    # Scope check is separate from the conditional claim, never the authority to claim.
    await service.get_public(session, document_id, tenant_id)
    await session.rollback()
    storage = LocalStorage(settings.document_storage_root, settings.max_upload_bytes)
    return await claim_and_process(session, document_id, tenant_id, "failed", storage, settings)
