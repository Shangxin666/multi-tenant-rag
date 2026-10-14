from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator


class RagQueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=10)

    @field_validator("question", mode="before")
    @classmethod
    def strip_question(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class RagSource(BaseModel):
    source_id: str
    document_id: UUID
    filename: str
    chunk_index: int
    page: int | None = None
    title: str | None = None
    distance: float
    snippet: str


class RagQueryResponse(BaseModel):
    answer: str
    sources: list[RagSource]
