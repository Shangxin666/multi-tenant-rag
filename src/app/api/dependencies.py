from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text

from app.core.config import Settings, get_settings
from app.core.security import decode_access_token
from app.db.session import get_db
from app.modules.users.models import User
from app.db.tenant_context import bind_tenant

bearer = HTTPBearer(auto_error=False)
Database = Annotated[AsyncSession, Depends(get_db)]


def unauthorized(detail: str = "Invalid authentication credentials") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(
    session: Database,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> User:
    if credentials is None:
        raise unauthorized()
    try:
        user_id = decode_access_token(credentials.credentials, settings)
    except jwt.InvalidTokenError:
        raise unauthorized() from None
    tenant_id = await session.scalar(text("SELECT app_private.user_tenant(:user_id)"), {"user_id": user_id})
    await session.rollback()
    if tenant_id is None:
        raise unauthorized()
    bind_tenant(session, tenant_id)
    user = await session.scalar(select(User).where(User.id == user_id, User.tenant_id == tenant_id))
    if user is None or not user.is_active:
        raise unauthorized()
    return user


async def require_admin(user: Annotated[User, Depends(get_current_user)]) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin permission required")
    return user
