from typing import Literal, Annotated
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator
from app.modules.rag.schemas import RagQueryRequest

ToolName = Literal["search_knowledge_base", "get_document_info"]
ErrorCode = Literal["invalid_tool", "invalid_arguments", "resource_not_found", "budget_exceeded",
                    "timeout", "unavailable", "invalid_model_output", "invalid_citation", "forbidden"]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AgentRequest(RagQueryRequest):
    pass


class SearchArgs(Strict):
    query: str = Field(min_length=1, max_length=2000, strict=True)
    top_k: int = Field(ge=1, le=10, strict=True)

    @field_validator("query", mode="before")
    @classmethod
    def trim(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class DocumentArgs(Strict):
    document_id: UUID


class AgentSource(Strict):
    source_id: str = Field(pattern=r"^S[1-9][0-9]*$")
    kind: Literal["chunk", "document"]
    document_id: UUID
    filename: str
    chunk_index: int | None = None
    page: int | None = None
    title: str | None = None
    distance: float | None = None
    snippet: str = Field(max_length=300)


class Start(Strict):
    knowledge_base_id: UUID


class ToolStart(Strict):
    call_id: UUID
    tool: ToolName


class ToolResult(ToolStart):
    status: Literal["ok", "empty", "error"]
    source_ids: list[str] = Field(max_length=20)
    error_code: ErrorCode | None = None


class Delta(Strict):
    text: str = Field(min_length=1, max_length=512)


class Error(Strict):
    code: ErrorCode
    message: str
    retryable: bool


class End(Strict):
    status: Literal["completed", "failed"]
    finish_reason: Literal["answer", "no_evidence", "document_info", "error"]
    answer: str | None
    sources: list[AgentSource] = Field(max_length=20)
    model_calls: int
    tool_attempts: int


class Envelope(Strict):
    v: Literal[1] = 1
    run_id: UUID
    seq: int = Field(ge=1)


class StartEvent(Envelope):
    event: Literal["agent_start"]
    data: Start


class ToolStartEvent(Envelope):
    event: Literal["tool_start"]
    data: ToolStart


class ToolResultEvent(Envelope):
    event: Literal["tool_result"]
    data: ToolResult


class DeltaEvent(Envelope):
    event: Literal["answer_delta"]
    data: Delta


class ErrorEvent(Envelope):
    event: Literal["error"]
    data: Error


class EndEvent(Envelope):
    event: Literal["agent_end"]
    data: End


AgentEvent = Annotated[StartEvent | ToolStartEvent | ToolResultEvent | DeltaEvent | ErrorEvent | EndEvent,
                       Field(discriminator="event")]


class AgentError(Exception):
    def __init__(self, code: ErrorCode) -> None:
        self.code = code
        super().__init__(code)
