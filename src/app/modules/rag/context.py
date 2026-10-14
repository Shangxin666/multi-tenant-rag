from dataclasses import dataclass
import json

from app.modules.rag.retrieval import RetrievedChunk
from app.modules.rag.schemas import RagSource


@dataclass(frozen=True)
class RagContext:
    text: str
    sources: list[RagSource]


def build_context(rows: list[RetrievedChunk], max_chars: int) -> RagContext:
    blocks: list[str] = []
    sources: list[RagSource] = []
    length = 0
    for row in rows:
        metadata = row.metadata or {}
        page = metadata.get("page")
        page = page if type(page) is int and page > 0 else None
        title = metadata.get("title")
        title = title[:300] if isinstance(title, str) else None
        source_id = f"S{len(sources) + 1}"
        # JSON escaping keeps untrusted filenames/content inside data values.
        block = f"[{source_id}]\n" + json.dumps({
            "document": row.filename, "page": page, "title": title, "content": row.content,
        }, ensure_ascii=False)
        added = len(block) + (2 if blocks else 0)
        if length + added > max_chars:
            break
        blocks.append(block)
        length += added
        sources.append(RagSource(
            source_id=source_id, document_id=row.document_id, filename=row.filename,
            chunk_index=row.chunk_index, page=page, title=title,
            distance=row.distance, snippet=row.content[:300],
        ))
    return RagContext("\n\n".join(blocks), sources)
