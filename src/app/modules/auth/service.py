from dataclasses import dataclass
from uuid import UUID, uuid4
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, verify_password
from app.modules.auth.schemas import RegisterRequest, RegisterResponse
from app.modules.tenants.models import Tenant
from app.modules.tenants.schemas import TenantPublic
from app.modules.users.models import User
from app.modules.users.schemas import UserPublic
from app.db.tenant_context import bind_tenant


async def register_tenant(session: AsyncSession, data: RegisterRequest) -> RegisterResponse:
    encoded = await hash_password(data.password.get_secret_value())
    tenant_id = uuid4()
    bind_tenant(session, tenant_id)
    async with session.begin():
        tenant = Tenant(id=tenant_id, name=data.tenant_name, slug=data.tenant_slug)
        session.add(tenant)
        await session.flush()
        user = User(
            tenant_id=tenant.id,
            email=str(data.email),
            password_hash=encoded,
            role="admin",
            is_active=True,
        )
        session.add(user)
        await session.flush()
        result = RegisterResponse(
            tenant=TenantPublic.model_validate(tenant),
            user=UserPublic.model_validate(user),
        )
    return result


@dataclass(frozen=True)
class AuthenticatedUser:
    id: UUID


async def authenticate(session: AsyncSession, email: str, password: str) -> AuthenticatedUser | None:
    row = (await session.execute(text("SELECT * FROM app_private.login_credentials(:email)"),
                                 {"email": email.strip().lower()})).one_or_none()
    user_id, encoded, active = (tuple(row) if row is not None else (None, None, False))
    await session.rollback()
    valid = await verify_password(password, encoded)
    if user_id is None or not valid or not active:
        return None
    return AuthenticatedUser(user_id)
