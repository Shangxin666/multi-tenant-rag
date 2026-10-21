from app.observability.trace import traced
"""Rank-only fusion; raw retrieval scores are never added together."""
from dataclasses import dataclass
from uuid import UUID
from app.modules.rag.retrieval import RetrievedChunk


@dataclass(frozen=True)
class FusedChunk:
    chunk: RetrievedChunk
    score: float


@traced("rrf")
def fuse_rrf(lists: list[list[RetrievedChunk]], k: int = 60) -> list[FusedChunk]:
    if k < 1:
        raise ValueError("RRF k must be positive")
    scores: dict[UUID, float] = {}
    chunks: dict[UUID, RetrievedChunk] = {}
    for rows in lists:
        seen: set[UUID] = set()
        for rank, row in enumerate(rows, 1):
            if row.chunk_id in seen:
                continue
            seen.add(row.chunk_id)
            chunks.setdefault(row.chunk_id, row)
            scores[row.chunk_id] = scores.get(row.chunk_id, 0.0) + 1 / (k + rank)
    return [FusedChunk(chunks[key], scores[key])
            for key in sorted(scores, key=lambda key: (-scores[key], key))]
