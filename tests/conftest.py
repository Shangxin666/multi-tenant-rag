import secrets
from pathlib import Path

import pytest


@pytest.fixture
def config_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Keep unit tests independent of local credentials and dotenv files."""
    for key in (
        "APP_ENV", "DB_HOST", "DB_PORT", "POSTGRES_DB",
        "POSTGRES_USER", "POSTGRES_PASSWORD", "DB_ECHO",
        "JWT_SECRET", "JWT_ALGORITHM", "ACCESS_TOKEN_EXPIRE_MINUTES", "TEST_DATABASE_NAME",
        "DOCUMENT_STORAGE_ROOT", "MAX_UPLOAD_BYTES", "MAX_UPLOAD_REQUEST_BYTES",
        "CHUNK_SIZE", "CHUNK_OVERLAP", "MAX_PDF_PAGES", "MAX_PARSED_CHARS", "MAX_DOCUMENT_CHUNKS",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("POSTGRES_DB", "unit")
    monkeypatch.setenv("POSTGRES_USER", "unit")
    monkeypatch.setenv("POSTGRES_PASSWORD", secrets.token_urlsafe(24))
    monkeypatch.setenv("JWT_SECRET", secrets.token_urlsafe(48))
    return tmp_path


@pytest.fixture
def sample_pdf() -> bytes:
    """Two tiny text pages generated without an extra PDF generation dependency."""
    from io import BytesIO
    from pypdf import PdfWriter
    from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

    writer = PdfWriter()
    for text in ("Page one ingestion example", "Page two ingestion example"):
        page = writer.add_blank_page(width=300, height=200)
        font = DictionaryObject({
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        })
        page[NameObject("/Resources")] = DictionaryObject({
            NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})
        })
        stream = DecodedStreamObject()
        stream.set_data(f"BT /F1 12 Tf 20 100 Td ({text}) Tj ET".encode("ascii"))
        page[NameObject("/Contents")] = writer._add_object(stream)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()
