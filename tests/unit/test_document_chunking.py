from app.modules.documents.ingestion.chunking import split_sections
from app.modules.documents.ingestion.types import ParsedSection


def test_order_metadata_and_empty_filter() -> None:
    sections = [ParsedSection("  ", {}), ParsedSection("abcdefghij" * 5, {"page": 1}), ParsedSection("Second", {"page": 2})]
    drafts = split_sections(sections, 10, 2, 100)
    assert drafts == split_sections(sections, 10, 2, 100)
    assert [d.chunk_index for d in drafts] == list(range(len(drafts)))
    assert all(d.content.strip() for d in drafts)
    assert drafts[0].metadata == {"page": 1}
    assert drafts[-1].metadata == {"page": 2}
    assert drafts[0].content[-2:] == drafts[1].content[:2]
    assert max(len(d.content) for d in drafts) <= 10
