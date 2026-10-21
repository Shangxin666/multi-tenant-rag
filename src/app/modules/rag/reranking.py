from functools import lru_cache
from threading import Lock
from typing import Annotated, Any, Protocol, Sequence
import numpy as np
from fastapi import Depends
from app.core.config import Settings, get_settings
from app.modules.rag.retrieval import RetrievedChunk


class RerankingError(Exception):
    """Safe public summary; never expose model input text."""


class RerankerBackend(Protocol):
    def score(self, question: str, passages: Sequence[str]) -> list[float]: ...


def validate_scores(values: Any, count: int) -> list[float]:
    try:
        array = np.asarray(values)
        if array.shape != (count,) or array.dtype.kind not in "fi" or not np.isfinite(array).all():
            raise ValueError()
        return array.astype(float).tolist()
    except (TypeError, ValueError, OverflowError):
        raise RerankingError("Invalid reranker output") from None


class BgeReranker:
    def __init__(self, model: str, device: str, batch_size: int, max_length: int) -> None:
        self.model_name, self.device = model, device
        self.batch_size, self.max_length = batch_size, max_length
        self._model: Any = None
        self._lock = Lock()

    def _load(self) -> Any:
        from sentence_transformers import CrossEncoder
        from torch.nn import Identity
        return CrossEncoder(self.model_name, device=self.device, max_length=self.max_length,
                            activation_fn=Identity(), trust_remote_code=False)

    def score(self, question: str, passages: Sequence[str]) -> list[float]:
        if not passages:
            return []
        with self._lock:
            if self._model is None:
                self._model = self._load()
            scores = self._model.predict([(question, passage) for passage in passages],
                batch_size=self.batch_size, show_progress_bar=False, convert_to_numpy=True)
        return validate_scores(scores, len(passages))


def rerank(backend: RerankerBackend, question: str, rows: list[RetrievedChunk], top_k: int) -> list[RetrievedChunk]:
    if not rows:
        return []
    scores = validate_scores(backend.score(question, [row.content for row in rows]), len(rows))
    order = sorted(range(len(rows)), key=lambda i: (-scores[i], i, rows[i].chunk_id))
    return [rows[i] for i in order[:top_k]]


@lru_cache(maxsize=1)
def cached_reranker(model: str, device: str, batch_size: int, max_length: int) -> BgeReranker:
    return BgeReranker(model, device, batch_size, max_length)


def get_reranker_backend(settings: Annotated[Settings, Depends(get_settings)]) -> RerankerBackend:
    return cached_reranker(settings.reranker_model, settings.reranker_device,
                           settings.reranker_batch_size, settings.reranker_max_length)
