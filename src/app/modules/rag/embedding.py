from functools import lru_cache
from threading import Lock
from typing import Any, Protocol, Sequence

import numpy as np
from fastapi import Depends
from typing import Annotated

from app.core.config import Settings, get_settings

DIMENSION = 512
QUERY_INSTRUCTION = "为这个句子生成表示以用于检索相关文章："


class EmbeddingError(Exception):
    """Embedding failed; never expose backend exception text."""


def validate_vectors(values: Any, count: int) -> list[list[float]]:
    try:
        array = np.asarray(values, dtype=np.float32)
        if count < 1 or array.shape != (count, DIMENSION) or not np.isfinite(array).all():
            raise ValueError()
        norms = np.linalg.norm(array, axis=1)
        if not np.allclose(norms, 1.0, atol=1e-3, rtol=1e-3):
            raise ValueError()
        return array.tolist()
    except (ValueError, TypeError, OverflowError):
        raise EmbeddingError("Invalid embedding output") from None


class EmbeddingBackend(Protocol):
    def embed_passages(self, texts: Sequence[str]) -> list[list[float]]: ...
    def embed_query(self, question: str) -> list[float]: ...


class BgeEmbedding:
    def __init__(self, model: str, device: str, batch_size: int) -> None:
        self.model_name, self.device, self.batch_size = model, device, batch_size
        self._model: Any = None
        self._lock = Lock()

    def _load(self) -> Any:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer(self.model_name, device=self.device, trust_remote_code=False)
        if model.get_sentence_embedding_dimension() != DIMENSION:
            raise EmbeddingError("Invalid model dimension")
        return model

    def _encode(self, texts: Sequence[str]) -> list[list[float]]:
        # Caller runs this entire operation in a worker thread. Serialize loading
        # and inference per process to bound model memory and avoid duplicate loads.
        with self._lock:
            if self._model is None:
                self._model = self._load()
            output = self._model.encode(
                list(texts), batch_size=self.batch_size, normalize_embeddings=True,
                convert_to_numpy=True, show_progress_bar=False, precision="float32",
            )
        return validate_vectors(output, len(texts))

    def embed_passages(self, texts: Sequence[str]) -> list[list[float]]:
        return self._encode(texts)

    def embed_query(self, question: str) -> list[float]:
        return self._encode([QUERY_INSTRUCTION + question])[0]


@lru_cache(maxsize=1)
def cached_backend(model: str, device: str, batch_size: int) -> BgeEmbedding:
    # Construction is cheap; model loading happens only in _encode.
    return BgeEmbedding(model, device, batch_size)


def get_embedding_backend(settings: Annotated[Settings, Depends(get_settings)]) -> EmbeddingBackend:
    return cached_backend(settings.embedding_model, settings.embedding_device, settings.embedding_batch_size)
