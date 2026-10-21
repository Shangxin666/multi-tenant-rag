import json
import httpx
import pytest
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionChunk
from app.core.config import Settings
from app.modules.agent import backend
from app.modules.agent.backend import Assembler, DeepSeekAgentBackend
from app.modules.agent.schemas import AgentError


def chunk(delta, finish=None):
    return ChatCompletionChunk.model_validate({"id": "test", "object": "chat.completion.chunk",
        "created": 0, "model": "fake", "choices": [{"index": 0, "delta": delta, "finish_reason": finish}]})


def test_incremental_calls_and_finish():
    assembler = Assembler()
    assembler.add(chunk({"tool_calls": [{"index": 0, "id": "call1", "type": "function", "function": {"name": "search_knowledge_base", "arguments": '{"query":'}}]}))
    assembler.add(chunk({"tool_calls": [{"index": 0, "function": {"arguments": '"年假","top_k":5}'}}]}, "tool_calls"))
    result = assembler.result()
    assert json.loads(result.calls[0].arguments)["query"] == "年假"


@pytest.mark.parametrize("finish", [None, "length", "content_filter"])
def test_invalid_finish(finish):
    assembler = Assembler()
    assembler.add(chunk({"content": "partial"}, finish))
    with pytest.raises(AgentError): assembler.result()


@pytest.mark.asyncio
async def test_installed_sdk_stream_and_thinking_disabled(config_env, monkeypatch):
    from pydantic import SecretStr
    requests = []
    def handler(request):
        data = json.loads(request.content)
        requests.append(data)
        assert data["thinking"] == {"type": "disabled"} and data["stream"]
        parts = [chunk({"content": "回答", "reasoning_content": "do not expose"}), chunk({}, "stop")]
        raw = ''.join('data: '+p.model_dump_json()+'\n\n' for p in parts)+'data: [DONE]\n\n'
        return httpx.Response(200, headers={"Content-Type": "text/event-stream"}, content=raw)
    def client(**kwargs):
        return AsyncOpenAI(**kwargs, http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    monkeypatch.setattr(backend, "AsyncOpenAI", client)
    settings = Settings().model_copy(update={"deepseek_api_key": SecretStr("fake-for-mock-only")})
    result = await DeepSeekAgentBackend(settings).complete([{"role": "user", "content": "q"}], True, 1024, 5)
    assert result.content == "回答" and not result.calls
    assert requests[0]["model"] == settings.llm_model
