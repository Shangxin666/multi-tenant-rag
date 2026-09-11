from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError

from app.api.dependencies import Database, get_current_user, unauthorized
from app.core.config import Settings, get_settings
from app.core.security import create_access_token
from app.modules.auth.schemas import LoginRequest, RegisterRequest, RegisterResponse, TokenResponse
from app.modules.auth.service import authenticate, register_tenant
from app.modules.users.models import User
from app.modules.users.schemas import UserPublic

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=RegisterResponse, status_code=201)
async def register(data: RegisterRequest, session: Database) -> RegisterResponse:
    try:
        return await register_tenant(session, data)
    except IntegrityError as exc:
        # The transaction context has already rolled back, including the Tenant.
        cause = exc.orig.__cause__
        constraint = getattr(cause, "constraint_name", None)
        if getattr(exc.orig, "sqlstate", None) == "23505" and constraint in {
            "uq_tenants_slug", "uq_users_email"
        }:
            raise HTTPException(status_code=409, detail="Registration conflicts with existing data") from None
        raise


@router.post("/login", response_model=TokenResponse)
async def login(
    data: LoginRequest,
    session: Database,
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenResponse:
    user = await authenticate(session, str(data.email), data.password.get_secret_value())
    if user is None:
        raise unauthorized("Invalid email or password")
    return TokenResponse(access_token=create_access_token(user.id, settings))


@router.get("/me", response_model=UserPublic)
async def me(user: Annotated[User, Depends(get_current_user)]) -> UserPublic:
    return UserPublic.model_validate(user)
