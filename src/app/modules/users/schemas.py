from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.modules.users.models import Role


class UserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    email: str
    role: Role
    is_active: bool
    created_at: datetime
