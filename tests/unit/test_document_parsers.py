from pathlib import Path

import pytest

from app.modules.documents.ingestion.errors import IngestionError
from app.modules.documents.ingestion.parsers import parse_document


def test_markdown(tmp_path: Path) -> None:
    path = tmp_path / "sample"
    path.write_text("# Title\n\n```python\nprint(1)\n```", encoding="utf-8-sig")
    sections = parse_document(path, "markdown", 200, 10000)
    assert sections[0].text.startswith("# Title")
    assert "print(1)" in sections[0].text


def test_html(tmp_path: Path) -> None:
    path = tmp_path / "sample"
    path.write_text("<title>Example</title><body><h1>Hello</h1><script>bad()</script><style>.bad{}</style><p>World", encoding="utf-8")
    section = parse_document(path, "html", 200, 10000)[0]
    assert "Hello" in section.text and "World" in section.text
    assert "bad" not in section.text
    assert section.metadata == {"title": "Example"}


def test_pdf(tmp_path: Path, sample_pdf: bytes) -> None:
    path = tmp_path / "sample"
    path.write_bytes(sample_pdf)
    sections = parse_document(path, "pdf", 200, 10000)
    assert len(sections) == 2
    assert [s.metadata for s in sections] == [{"page": 1}, {"page": 2}]
    assert "Page one" in sections[0].text and "Page two" in sections[1].text


@pytest.mark.parametrize(("source", "content"), [
    ("pdf", b"not a PDF"), ("markdown", b"\xff"), ("html", b"\xff"),
    ("markdown", b" \n "), ("html", b"<script>ignored()</script>"),
])
def test_parse_errors(tmp_path: Path, source: str, content: bytes) -> None:
    path = tmp_path / "sample"
    path.write_bytes(content)
    with pytest.raises(IngestionError):
        parse_document(path, source, 200, 10000)


def test_pdf_page_limit(tmp_path: Path, sample_pdf: bytes) -> None:
    path = tmp_path / "sample"
    path.write_bytes(sample_pdf)
    with pytest.raises(IngestionError):
        parse_document(path, "pdf", 1, 10000)


def test_parser_diagnostics_do_not_log_file_content(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    path = tmp_path / "sample"
    path.write_bytes(b"PRIVATE document content that must not enter diagnostic logs")
    with pytest.raises(IngestionError):
        parse_document(path, "pdf", 200, 10000)
    assert "PRIVA" not in caplog.text
