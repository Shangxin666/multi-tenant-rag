from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr, ValidationInfo, field_validator

from app.modules.tenants.schemas import TenantPublic
from app.modules.users.schemas import UserPublic


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr = Field(max_length=254)
    password: SecretStr = Field(min_length=1, max_length=128)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value


class RegisterRequest(LoginRequest):
    tenant_name: str = Field(min_length=1, max_length=100)
    tenant_slug: str = Field(
        min_length=1, max_length=63, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$"
    )
    password: SecretStr = Field(min_length=12, max_length=128)

    @field_validator("tenant_name", "tenant_slug", mode="before")
    @classmethod
    def normalize_tenant(cls, value: object, info: ValidationInfo) -> object:
        if not isinstance(value, str):
            return value
        value = value.strip()
        return value.lower() if info.field_name == "tenant_slug" else value


class RegisterResponse(BaseModel):
    tenant: TenantPublic
    user: UserPublic


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
