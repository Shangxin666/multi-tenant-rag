import json
import re
from typing import Any
from app.modules.agent.schemas import AgentSource, AgentError
from app.modules.rag.retrieval import RetrievedChunk


class Sources:
    """Only public metadata is retained here; full evidence lives once in messages."""
    def __init__(self) -> None:
        self.items: dict[tuple[str, str], AgentSource] = {}
        self.chars = 0

    def add(self, kind: str, key: str, info: dict, evidence: Any) -> dict | None:
        identity = (kind, key)
        if identity in self.items:
            return {"source_id": self.items[identity].source_id, "already_provided": True}
        source_id = f"S{len(self.items)+1}"
        block = {"source_id": source_id, "kind": kind, "evidence": evidence}
        size = len(json.dumps(block, ensure_ascii=False))
        if len(self.items) >= 20 or self.chars + size > 12000:
            return None
        self.items[identity] = AgentSource(source_id=source_id, kind=kind, **info)
        self.chars += size
        return block

    def chunk(self, row: RetrievedChunk) -> dict | None:
        metadata = row.metadata or {}
        page = metadata.get("page")
        page = page if type(page) is int and page > 0 else None
        title = metadata.get("title")
        title = title[:300] if isinstance(title, str) else None
        info = dict(document_id=row.document_id, filename=row.filename, chunk_index=row.chunk_index,
                    page=page, title=title, distance=row.distance, snippet=row.content[:300])
        return self.add("chunk", str(row.chunk_id), info,
            {**info, "document_id": str(row.document_id), "content": row.content, "snippet": None})

    def finalize(self, answer: str) -> tuple[str, list[AgentSource], str]:
        known = {item.source_id: item for item in self.items.values()}
        references = set(re.findall(r"\bS\d+\b", answer))
        if not references.issubset(known):
            raise AgentError("invalid_citation")
        if not known:
            return "当前没有可引用的知识库证据。请补充问题或文档信息，我可以帮助检索。", [], "no_evidence"
        if not references or any(f"[{ref}]" not in answer for ref in references):
            raise AgentError("invalid_citation")
        sources = [item for item in known.values() if item.source_id in references]
        if not any(item.kind == "chunk" for item in sources):
            # A status-only result cannot license free-form claims about document contents.
            answer = "\n".join(f"文档状态 [{item.source_id}]：{item.snippet}" for item in sources)
            return answer, sources, "document_info"
        return answer, sources, "answer"
