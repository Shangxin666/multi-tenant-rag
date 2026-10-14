"""Transaction-local context is not protection against arbitrary SQL execution."""
from uuid import UUID
from sqlalchemy import Connection, event, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session, SessionTransaction


class TenantSession(Session):
    """Only runtime sessions use this class; maintenance sessions do not."""

    def close(self) -> None:
        try:
            super().close()
        finally:
            self.info.pop("tenant_id", None)


def bind_tenant(session: AsyncSession, tenant_id: UUID) -> None:
    if not isinstance(tenant_id, UUID):
        raise TypeError("Tenant identity must be a UUID")
    if session.in_transaction():
        raise RuntimeError("Finish authentication transaction before binding tenant")
    previous = session.info.get("tenant_id")
    if previous is not None and previous != tenant_id:
        raise RuntimeError("A session cannot switch tenants")
    if session.identity_map or session.new or session.dirty or session.deleted:
        raise RuntimeError("Bind tenant before loading or changing ORM objects")
    session.info["tenant_id"] = tenant_id


@event.listens_for(TenantSession, "after_begin")
def apply_tenant(session: Session, transaction: SessionTransaction, connection: Connection) -> None:
    tenant_id = session.info.get("tenant_id")
    connection.execute(text("SELECT pg_catalog.set_config('app.tenant_id', :tenant, true)"),
                       {"tenant": str(tenant_id) if tenant_id is not None else ""})
