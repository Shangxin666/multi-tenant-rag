from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import re
from typing import BinaryIO
from uuid import UUID, uuid4

from app.modules.documents.ingestion.errors import IngestionError, UploadError

COPY_BLOCK_BYTES = 64 * 1024
KEY_PATTERN = re.compile(r"[0-9a-f]{32}/[0-9a-f]{32}")
EXTENSIONS = {".pdf": "pdf", ".md": "markdown", ".markdown": "markdown", ".html": "html", ".htm": "html"}


@dataclass(frozen=True)
class StoredFile:
    key: str
    size: int
    sha256: str


def upload_name(filename: str | None) -> tuple[str, str]:
    if not filename or any(ord(c) < 32 or ord(c) == 127 for c in filename):
        raise UploadError(422, "Invalid filename")
    display = filename.replace("\\", "/").rsplit("/", 1)[-1].strip()
    if not display or len(display) > 255:
        raise UploadError(422, "Invalid filename")
    source = EXTENSIONS.get(Path(display).suffix.lower())
    if source is None:
        raise UploadError(415, "Unsupported file extension")
    return display, source


class LocalStorage:
    def __init__(self, root: Path, max_bytes: int) -> None:
        self.root = root.resolve()
        self.max_bytes = max_bytes

    def path_for(self, key: str) -> Path:
        if not KEY_PATTERN.fullmatch(key):
            raise IngestionError("Original file is unavailable")
        path = (self.root / key).resolve()
        if not path.is_relative_to(self.root):
            raise IngestionError("Original file is unavailable")
        return path

    def save(self, stream: BinaryIO, tenant_id: UUID) -> StoredFile:
        key = tenant_id.hex + "/" + uuid4().hex
        final = self.path_for(key)
        final.parent.mkdir(parents=True, exist_ok=True)
        temporary = final.with_name(final.name + ".part")
        digest = hashlib.sha256()
        size = 0
        try:
            with temporary.open("xb") as target:
                while block := stream.read(COPY_BLOCK_BYTES):
                    size += len(block)
                    if size > self.max_bytes:
                        raise UploadError(413, "File exceeds upload limit")
                    target.write(block)
                    digest.update(block)
                if size == 0:
                    raise UploadError(422, "Empty file")
                target.flush()
                os.fsync(target.fileno())
            os.replace(temporary, final)
            return StoredFile(key, size, digest.hexdigest())
        finally:
            temporary.unlink(missing_ok=True)

    def verify(self, key: str, size: int, sha256: str) -> Path:
        path = self.path_for(key)
        digest = hashlib.sha256()
        total = 0
        try:
            with path.open("rb") as stream:
                while block := stream.read(COPY_BLOCK_BYTES):
                    total += len(block)
                    if total > self.max_bytes or total > size:
                        raise IngestionError("Original file integrity check failed")
                    digest.update(block)
        except OSError as exc:
            raise IngestionError("Original file is unavailable") from exc
        if total != size or digest.hexdigest() != sha256:
            raise IngestionError("Original file integrity check failed")
        return path

    def remove(self, key: str) -> None:
        self.path_for(key).unlink(missing_ok=True)
