import logging
from pathlib import Path

from bs4 import BeautifulSoup
from pypdf import PdfReader

from app.modules.documents.ingestion.errors import IngestionError
from app.modules.documents.ingestion.types import ParsedSection

# Third-party warnings can contain raw PDF bytes. Our service logs safe failure
# types and stack locations instead of forwarding document-derived diagnostics.
pdf_logger = logging.getLogger("pypdf")
pdf_logger.setLevel(logging.CRITICAL + 1)
pdf_logger.addHandler(logging.NullHandler())
pdf_logger.propagate = False


def parse_document(path: Path, source_type: str, max_pages: int, max_chars: int) -> list[ParsedSection]:
    sections: list[ParsedSection] = []
    try:
        if source_type == "pdf":
            with path.open("rb") as stream:
                reader = PdfReader(stream)
                if reader.is_encrypted:
                    raise IngestionError("Encrypted PDFs are not supported")
                if len(reader.pages) > max_pages:
                    raise IngestionError("Document exceeds processing limits")
                length = 0
                for number, page in enumerate(reader.pages, start=1):
                    text = page.extract_text() or ""
                    length += len(text)
                    if length > max_chars:
                        raise IngestionError("Document exceeds processing limits")
                    sections.append(ParsedSection(text, {"page": number}))
        elif source_type in {"markdown", "html"}:
            text = path.read_text(encoding="utf-8-sig")
            if source_type == "html":
                soup = BeautifulSoup(text, "html.parser")
                title = soup.title.get_text(" ", strip=True) if soup.title else ""
                for node in soup(["script", "style", "noscript", "template", "head"]):
                    node.decompose()
                text = (soup.body or soup).get_text("\n", strip=True)
                sections = [ParsedSection(text, {"title": title[:255]} if title else {})]
            else:
                sections = [ParsedSection(text, {})]
        else:
            raise IngestionError("Unsupported document format")
    except UnicodeDecodeError as exc:
        raise IngestionError("File is not valid UTF-8") from exc
    except IngestionError:
        raise
    except Exception as exc:
        raise IngestionError("Document could not be parsed") from exc
    if sum(len(section.text) for section in sections) > max_chars:
        raise IngestionError("Document exceeds processing limits")
    if not any(section.text.strip() for section in sections):
        raise IngestionError("No extractable text found")
    return sections
