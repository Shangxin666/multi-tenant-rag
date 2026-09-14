import hashlib
from io import BytesIO
from pathlib import Path
from uuid import uuid4

import pytest

from app.modules.documents.ingestion.errors import IngestionError, UploadError
from app.modules.documents.storage import COPY_BLOCK_BYTES, LocalStorage, upload_name


def test_safe_streamed_save(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path, 200_000)
    data = b"example" * 20_000
    class BoundedStream(BytesIO):
        def read(self, size: int = -1) -> bytes:
            assert size == COPY_BLOCK_BYTES
            return super().read(size)
    display, source = upload_name("../../private/secret.md")
    saved = storage.save(BoundedStream(data), uuid4())
    assert display == "secret.md" and source == "markdown"
    assert "secret" not in saved.key and not Path(saved.key).is_absolute()
    assert saved.size == len(data) and saved.sha256 == hashlib.sha256(data).hexdigest()
    path = storage.verify(saved.key, saved.size, saved.sha256)
    assert path.is_relative_to(tmp_path.resolve()) and path.read_bytes() == data
    assert not list(tmp_path.rglob("*.part"))


@pytest.mark.parametrize("key", ["../escape", "/absolute", "C:/private", "a/../../b", "\\\\server\\file"])
def test_reject_unsafe_key(tmp_path: Path, key: str) -> None:
    with pytest.raises(IngestionError):
        LocalStorage(tmp_path, 10).path_for(key)


@pytest.mark.parametrize(("data", "code"), [(b"", 422), (b"x" * 11, 413)])
def test_rejected_file_cleanup(tmp_path: Path, data: bytes, code: int) -> None:
    with pytest.raises(UploadError) as error:
        LocalStorage(tmp_path, 10).save(BytesIO(data), uuid4())
    assert error.value.status_code == code
    assert not [p for p in tmp_path.rglob("*") if p.is_file()]


def test_partial_write_cleanup(tmp_path: Path) -> None:
    class BrokenStream(BytesIO):
        def read(self, size: int = -1) -> bytes:
            if self.tell():
                raise OSError("Simulated input failure")
            return super().read(size)
    with pytest.raises(OSError):
        LocalStorage(tmp_path, 200_000).save(BrokenStream(b"x" * 100_000), uuid4())
    assert not [p for p in tmp_path.rglob("*") if p.is_file()]


def test_integrity_check(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path, 100)
    saved = storage.save(BytesIO(b"original"), uuid4())
    storage.path_for(saved.key).write_bytes(b"modified")
    with pytest.raises(IngestionError):
        storage.verify(saved.key, saved.size, saved.sha256)
    storage.remove(saved.key)
    with pytest.raises(IngestionError):
        storage.verify(saved.key, saved.size, saved.sha256)


@pytest.mark.parametrize("name", [None, "", "bad.exe", "bad\x00.md"])
def test_bad_filename(name: str | None) -> None:
    with pytest.raises(UploadError):
        upload_name(name)
