from uuid import UUID
import numpy as np
import pytest
from app.modules.rag.retrieval import RetrievedChunk
from app.modules.rag.fusion import fuse_rrf
from app.modules.rag.reranking import BgeReranker, rerank, validate_scores, RerankingError


def row(i: int) -> RetrievedChunk:
    return RetrievedChunk(UUID(int=i), UUID(int=100), "test.md", i, str(i), None, 0.5)


def test_rrf_scores_duplicates_ties_and_empty():
    a, b = row(1), row(2)
    result = fuse_rrf([[a, b, a], [b, a]])
    assert [r.chunk.chunk_id for r in result] == [a.chunk_id, b.chunk_id]
    assert [r.score for r in result] == pytest.approx([1/61 + 1/62] * 2)
    assert fuse_rrf([[], []]) == []
    assert fuse_rrf([[], [b]])[0].chunk == b
    with pytest.raises(ValueError): fuse_rrf([], 0)


def test_rerank_and_tie_order():
    class Backend:
        def score(self, question, passages):
            assert question == "q" and passages == ["3", "1", "2"]
            return [-2., 4., 4.]
    rows = [row(3), row(1), row(2)]
    assert rerank(Backend(), "q", rows, 2) == [rows[1], rows[2]]
    assert rerank(Backend(), "q", [], 5) == []


@pytest.mark.parametrize("scores", [[1], [[1, 2]], [float("nan"), 1], [float("inf"), 1],
                                       [True, False], ["1", "2"], [None, 1]])
def test_invalid_scores(scores):
    with pytest.raises(RerankingError): validate_scores(scores, 2)


def test_model_cache_and_pairs(monkeypatch):
    model = BgeReranker("model", "cpu", 8, 512)
    calls, loads = [], []
    class Fake:
        def predict(self, pairs, **kwargs):
            calls.append((pairs, kwargs))
            return np.asarray([-1., 2.])
    def load():
        loads.append(True)
        return Fake()
    monkeypatch.setattr(model, "_load", load)
    for _ in range(2): assert model.score("问题", ["甲", "乙"]) == [-1., 2.]
    assert len(loads) == 1
    assert calls[0][0] == [("问题", "甲"), ("问题", "乙")]
    assert calls[0][1]["batch_size"] == 8


def test_quality_metrics():
    from scripts.evaluate_m7 import metrics
    assert metrics(["wrong", "right"], ["right"]) == {
        "recall@1": 0., "recall@5": 1., "recall@10": 1., "mrr@10": .5}
    assert metrics(["wrong"], []) == {}


def test_concurrent_load_is_cached(monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    backend = BgeReranker("model", "cpu", 8, 512)
    loads = []
    class Model:
        def predict(self, pairs, **kwargs): return np.asarray([1.])
    def load():
        loads.append(True)
        return Model()
    monkeypatch.setattr(backend, "_load", load)
    barrier = Barrier(2)
    def work():
        barrier.wait(timeout=5)
        return backend.score("q", ["text"])
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(work) for _ in range(2)]
        assert [future.result(timeout=5) for future in futures] == [[1.], [1.]]
    assert len(loads) == 1
