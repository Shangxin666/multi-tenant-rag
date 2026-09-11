from datetime import datetime, timedelta, timezone
from pathlib import Path
import secrets
from uuid import uuid4

import jwt
import pytest

from app.core.config import Settings
from app.core.security import create_access_token, decode_access_token, hash_password, verify_password


@pytest.mark.asyncio
async def test_argon2_roundtrip() -> None:
    password = secrets.token_urlsafe(24)
    encoded = await hash_password(password)
    assert encoded.startswith("$argon2id$")
    assert password not in encoded
    assert await verify_password(password, encoded)
    assert not await verify_password(password + "wrong", encoded)
    assert not await verify_password(password, None)


def test_token_payload(config_env: Path) -> None:
    settings = Settings()
    user_id = uuid4()
    token = create_access_token(user_id, settings)
    payload = jwt.decode(token, settings.jwt_secret.get_secret_value(), algorithms=["HS256"])
    assert set(payload) == {"sub", "exp"}
    assert decode_access_token(token, settings) == user_id


@pytest.mark.parametrize("case", ["expired", "missing_sub", "missing_exp", "bad_sub", "wrong_algorithm", "wrong_key"])
def test_reject_invalid_tokens(config_env: Path, case: str) -> None:
    settings = Settings()
    payload = {"sub": str(uuid4()), "exp": datetime.now(timezone.utc) + timedelta(minutes=1)}
    key = settings.jwt_secret.get_secret_value()
    algorithm = "HS256"
    if case == "expired":
        payload["exp"] = datetime.now(timezone.utc) - timedelta(seconds=1)
    elif case == "missing_sub":
        del payload["sub"]
    elif case == "missing_exp":
        del payload["exp"]
    elif case == "bad_sub":
        payload["sub"] = "not-a-uuid"
    elif case == "wrong_algorithm":
        algorithm = "HS384"
        key = key + key
    else:
        key = secrets.token_urlsafe(48)
    token = jwt.encode(payload, key, algorithm=algorithm)
    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token(token, settings)
