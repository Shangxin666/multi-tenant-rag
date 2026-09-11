from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select

from app.api.dependencies import Database, require_admin
from app.modules.users.models import User
from app.modules.users.schemas import UserPublic

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserPublic])
async def list_users(
    session: Database,
    current_user: Annotated[User, Depends(require_admin)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[UserPublic]:
    users = await session.scalars(
        select(User)
        .where(User.tenant_id == current_user.tenant_id)
        .order_by(User.created_at, User.id)
        .offset(offset)
        .limit(limit)
    )
    return [UserPublic.model_validate(user) for user in users]
