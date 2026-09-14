from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.modules.documents.models import DocumentStatus, SourceType


class DocumentPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    knowledge_base_id: UUID
    filename: str
    source_type: SourceType
    status: DocumentStatus
    error_message: str | None
    file_size_bytes: int | None
    created_at: datetime
    updated_at: datetime
