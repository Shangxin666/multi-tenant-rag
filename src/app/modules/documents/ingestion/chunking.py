from copy import deepcopy
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.modules.documents.ingestion.errors import IngestionError
from app.modules.documents.ingestion.types import ChunkDraft, ParsedSection


def split_sections(
    sections: list[ParsedSection], chunk_size: int, chunk_overlap: int, max_chunks: int,
) -> list[ChunkDraft]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size, chunk_overlap=chunk_overlap, length_function=len,
        separators=["\n\n", "\n", "。", "！", "？", ". ", " ", ""],
    )
    drafts: list[ChunkDraft] = []
    for section in sections:
        for text in splitter.split_text(section.text):
            content = text.strip()
            if not content:
                continue
            if len(drafts) >= max_chunks:
                raise IngestionError("Document exceeds processing limits")
            drafts.append(ChunkDraft(len(drafts), content, deepcopy(section.metadata)))
    if not drafts:
        raise IngestionError("No extractable text found")
    return drafts
