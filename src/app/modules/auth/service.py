from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, verify_password
from app.modules.auth.schemas import RegisterRequest, RegisterResponse
from app.modules.tenants.models import Tenant
from app.modules.tenants.schemas import TenantPublic
from app.modules.users.models import User
from app.modules.users.schemas import UserPublic


async def register_tenant(session: AsyncSession, data: RegisterRequest) -> RegisterResponse:
    encoded = await hash_password(data.password.get_secret_value())
    async with session.begin():
        tenant = Tenant(name=data.tenant_name, slug=data.tenant_slug)
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


async def authenticate(session: AsyncSession, email: str, password: str) -> User | None:
    user = await session.scalar(select(User).where(User.email == email))
    valid = await verify_password(password, user.password_hash if user else None)
    if user is None or not valid or not user.is_active:
        return None
    return user
