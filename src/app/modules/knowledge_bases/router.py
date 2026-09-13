from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.dependencies import Database, get_current_user, require_admin
from app.modules.knowledge_bases.models import KnowledgeBase
from app.modules.knowledge_bases.schemas import KnowledgeBaseCreate, KnowledgeBasePublic
from app.modules.users.models import User

router = APIRouter(prefix="/knowledge-bases", tags=["knowledge-bases"])


@router.post("", response_model=KnowledgeBasePublic, status_code=status.HTTP_201_CREATED)
async def create_knowledge_base(
    data: KnowledgeBaseCreate,
    session: Database,
    current_user: Annotated[User, Depends(require_admin)],
) -> KnowledgeBasePublic:
    # Authentication has already started this Session's transaction.
    try:
        resource = KnowledgeBase(
            tenant_id=current_user.tenant_id, name=data.name, description=data.description
        )
        session.add(resource)
        await session.flush()
        response = KnowledgeBasePublic.model_validate(resource)
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        constraint = getattr(exc.orig.__cause__, "constraint_name", None)
        if (
            getattr(exc.orig, "sqlstate", None) == "23505"
            and constraint == "uq_knowledge_bases_tenant_name"
        ):
            raise HTTPException(status_code=409, detail="Knowledge base name already exists") from None
        raise
    except Exception:
        await session.rollback()
        raise
    return response


@router.get("", response_model=list[KnowledgeBasePublic])
async def list_knowledge_bases(
    session: Database,
    current_user: Annotated[User, Depends(get_current_user)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[KnowledgeBasePublic]:
    resources = await session.scalars(
        select(KnowledgeBase)
        .where(KnowledgeBase.tenant_id == current_user.tenant_id)
        .order_by(KnowledgeBase.created_at, KnowledgeBase.id)
        .limit(limit)
        .offset(offset)
    )
    return [KnowledgeBasePublic.model_validate(resource) for resource in resources]


@router.get("/{knowledge_base_id}", response_model=KnowledgeBasePublic)
async def get_knowledge_base(
    knowledge_base_id: UUID,
    session: Database,
    current_user: Annotated[User, Depends(get_current_user)],
) -> KnowledgeBasePublic:
    resource = await session.scalar(
        select(KnowledgeBase).where(
            KnowledgeBase.id == knowledge_base_id,
            KnowledgeBase.tenant_id == current_user.tenant_id,
        )
    )
    if resource is None:
        raise HTTPException(status_code=404, detail="Knowledge base not found")
    return KnowledgeBasePublic.model_validate(resource)
