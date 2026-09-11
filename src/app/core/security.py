import secrets
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from uuid import UUID

import jwt
from pwdlib import PasswordHash
from starlette.concurrency import run_in_threadpool

from app.core.config import Settings

password_hasher = PasswordHash.recommended()


@lru_cache(maxsize=1)
def _dummy_hash() -> str:
    return password_hasher.hash(secrets.token_urlsafe(32))


async def hash_password(password: str) -> str:
    return await run_in_threadpool(password_hasher.hash, password)


async def verify_password(password: str, encoded: str | None) -> bool:
    def verify() -> bool:
        return password_hasher.verify(password, encoded if encoded is not None else _dummy_hash())

    return await run_in_threadpool(verify)


def create_access_token(user_id: UUID, settings: Settings) -> str:
    expires = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    return jwt.encode(
        {"sub": str(user_id), "exp": expires},
        settings.jwt_secret.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )


def decode_access_token(token: str, settings: Settings) -> UUID:
    payload = jwt.decode(
        token,
        settings.jwt_secret.get_secret_value(),
        algorithms=[settings.jwt_algorithm],
        options={"require": ["sub", "exp"]},
    )
    try:
        return UUID(payload["sub"])
    except (ValueError, TypeError, AttributeError) as exc:
        raise jwt.InvalidTokenError("Invalid subject") from exc
