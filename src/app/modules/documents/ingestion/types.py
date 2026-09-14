from dataclasses import dataclass
from pydantic import JsonValue


@dataclass(frozen=True)
class ParsedSection:
    text: str
    metadata: dict[str, JsonValue]


@dataclass(frozen=True)
class ChunkDraft:
    chunk_index: int
    content: str
    metadata: dict[str, JsonValue]
