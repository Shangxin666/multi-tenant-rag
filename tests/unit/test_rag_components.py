import json
from types import SimpleNamespace
from uuid import uuid4
import numpy as np
import pytest
import httpx

from app.core.config import Settings
from app.modules.rag.embedding import BgeEmbedding, QUERY_INSTRUCTION, validate_vectors, EmbeddingError
from app.modules.rag.context import build_context
from app.modules.rag.retrieval import RetrievedChunk
from app.modules.rag.generation import DeepSeekBackend, GenerationError, generate_answer


def unit(axis=0):
    value = [0.0] * 512
    value[axis] = 1.0
    return value


def test_embedding_adapter(monkeypatch):
    calls, loads = [], []
    class Model:
        def encode(self, texts, **kwargs):
            calls.append((texts, kwargs))
            return np.asarray([unit(i) for i in range(len(texts))])
    backend = BgeEmbedding("BAAI/bge-small-zh-v1.5", "cpu", 32)
    def load():
        loads.append(1)
        return Model()
    monkeypatch.setattr(backend, "_load", load)
    assert backend.embed_passages(["first", "second"]) == [unit(0), unit(1)]
    assert backend.embed_query("问题") == unit()
    assert calls[0][0] == ["first", "second"]
    assert calls[1][0] == [QUERY_INSTRUCTION + "问题"]
    assert all(kwargs["normalize_embeddings"] for _, kwargs in calls)
    assert len(loads) == 1


@pytest.mark.parametrize("case", ["count", "dimension", "nan", "inf", "zero", "norm"])
def test_invalid_vectors(case):
    vectors = [unit()]
    if case == "count": vectors = []
    if case == "dimension": vectors = [[1.0]]
    if case == "nan": vectors[0][0] = float("nan")
    if case == "inf": vectors[0][0] = float("inf")
    if case == "zero": vectors[0][0] = 0
    if case == "norm": vectors[0][0] = 2
    with pytest.raises(EmbeddingError): validate_vectors(vectors, 1)


def rows():
    return [RetrievedChunk(uuid4(), uuid4(), "document.md", i, f"content {i}",
                           {"page": i + 1, "title": "标题", "private": "hidden"}, float(i)) for i in range(3)]


def test_context_budget_and_metadata():
    retrieved = rows()
    first = build_context(retrieved[:1], 12000)
    context = build_context(retrieved, len(first.text))
    assert context.text == first.text and len(context.sources) == 1
    assert build_context(retrieved, len(first.text) - 1).sources == []
    all_context = build_context(retrieved, 12000)
    assert [s.source_id for s in all_context.sources] == ["S1", "S2", "S3"]
    assert [s.page for s in all_context.sources] == [1, 2, 3]
    assert "private" not in all_context.text and "hidden" not in all_context.text
    assert all(s.title == "标题" for s in all_context.sources)


@pytest.mark.asyncio
async def test_prompt_and_citations():
    context = build_context(rows(), 12000)
    class Fake:
        async def generate(self, messages):
            assert context.text not in messages[0]["content"]
            data = json.loads(messages[1]["content"])
            assert data == {"Question": "问题", "Context": context.text}
            return "Answer [S1]"
    assert await generate_answer(Fake(), "问题", context) == "Answer [S1]"
    class Bad:
        async def generate(self, messages): return "Answer [S99]"
    with pytest.raises(GenerationError): await generate_answer(Bad(), "问题", context)


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [200, 429, 503, 400])
async def test_deepseek_request_and_errors(config_env, monkeypatch, status):
    from openai import AsyncOpenAI
    from app.modules.rag import generation
    from pydantic import SecretStr
    def respond(request):
        body = json.loads(request.content)
        assert body["thinking"] == {"type": "disabled"}
        assert body["stream"] is False and body["model"] == "configured-model"
        if status != 200:
            return httpx.Response(status, json={"error": {"message": "private upstream text"}})
        return httpx.Response(200, json={"id": "test", "created": 0, "object": "chat.completion", "model": "configured-model",
            "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": "Answer [S1]"}}]})
    def client(**kwargs):
        return AsyncOpenAI(**kwargs, http_client=httpx.AsyncClient(transport=httpx.MockTransport(respond)))
    monkeypatch.setattr(generation, "AsyncOpenAI", client)
    settings = Settings(deepseek_api_key=SecretStr("test-only-placeholder"), llm_model="configured-model")
    if status == 200:
        assert await DeepSeekBackend(settings).generate([]) == "Answer [S1]"
    else:
        with pytest.raises(GenerationError) as caught:
            await DeepSeekBackend(settings).generate([])
        assert caught.value.status_code == (503 if status in (429, 503) else 502)
        assert "private" not in str(caught.value)


@pytest.mark.asyncio
async def test_deepseek_timeout(config_env, monkeypatch):
    from openai import AsyncOpenAI
    from app.modules.rag import generation
    from pydantic import SecretStr
    def respond(request):
        raise httpx.ReadTimeout("private provider diagnostic", request=request)
    monkeypatch.setattr(generation, "AsyncOpenAI", lambda **kwargs: AsyncOpenAI(
        **kwargs, http_client=httpx.AsyncClient(transport=httpx.MockTransport(respond))))
    with pytest.raises(GenerationError) as caught:
        await DeepSeekBackend(Settings(deepseek_api_key=SecretStr("test-only-placeholder"))).generate([])
    assert caught.value.status_code == 503 and "private" not in str(caught.value)


@pytest.mark.parametrize("field,value", [("embedding_batch_size", 0), ("llm_timeout_seconds", 0),
    ("max_rag_context_chars", 0), ("llm_max_tokens", 0), ("embedding_model", "other")])
def test_rag_settings_validation(config_env, field, value):
    from pydantic import ValidationError
    with pytest.raises(ValidationError): Settings(**{field: value})
