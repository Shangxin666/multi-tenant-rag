import json
from types import SimpleNamespace
import httpx
import pytest
from openai import AsyncOpenAI
from pydantic import SecretStr
from app.core.config import Settings
from app.observability.trace import capture
from app.modules.agent import backend
from app.modules.rag import generation
from scripts.export_m9_langsmith import sanitized, export


@pytest.mark.asyncio
async def test_agent_usage_final_empty_choice_chunk(config_env,monkeypatch):
    def handler(request):
        assert json.loads(request.content)['stream_options']=={'include_usage':True}
        base={'id':'x','object':'chat.completion.chunk','created':0,'model':'fake'}
        chunks=[{**base,'choices':[{'index':0,'delta':{'content':'answer'},'finish_reason':'stop'}]},
                {**base,'choices':[],'usage':{'prompt_tokens':7,'completion_tokens':3,'total_tokens':10}}]
        return httpx.Response(200,headers={'content-type':'text/event-stream'},content=''.join('data: '+json.dumps(c)+'\n\n' for c in chunks)+'data: [DONE]\n\n')
    monkeypatch.setattr(backend,'AsyncOpenAI',lambda **kw:AsyncOpenAI(**kw,http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler))))
    settings=Settings().model_copy(update={'deepseek_api_key':SecretStr('fake')})
    with capture() as trace:
        result=await backend.DeepSeekAgentBackend(settings).complete([],True,10,1)
    assert result.content=='answer'
    assert trace.summary()['usage']['total_tokens']==10 and trace.summary()['usage']['complete']


@pytest.mark.asyncio
async def test_rag_usage(config_env,monkeypatch):
    def handler(request):
        return httpx.Response(200,json={'id':'x','object':'chat.completion','created':0,'model':'fake',
            'choices':[{'index':0,'finish_reason':'stop','message':{'role':'assistant','content':'answer'}}],
            'usage':{'prompt_tokens':4,'completion_tokens':2,'total_tokens':6}})
    monkeypatch.setattr(generation,'AsyncOpenAI',lambda **kw:AsyncOpenAI(**kw,http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler))))
    with capture() as trace:
        assert await generation.DeepSeekBackend(Settings().model_copy(update={'deepseek_api_key':SecretStr('fake')})).generate([])=='answer'
    assert trace.summary()['usage']['total_tokens']==6


def test_export_whitelist_no_payload_or_identifiers():
    record={'trace_id':'PRIVATE','inputs':'SECRET','spans':[{'name':'llm','duration_ms':3,'status':'error',
        'error_code':'SECRET','usage':{'prompt_tokens':1,'completion_tokens':2,'total_tokens':3,'key':'SECRET'},'messages':['SECRET']}]}
    assert 'SECRET' not in json.dumps(sanitized(record)) and 'PRIVATE' not in json.dumps(sanitized(record))
    calls=[]
    export([record],SimpleNamespace(create_run=lambda **kw:calls.append(kw)),'test')
    assert calls[0]['inputs']=={} and calls[0]['outputs']==sanitized(record)
