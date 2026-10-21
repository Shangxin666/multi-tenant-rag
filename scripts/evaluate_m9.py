"""Synthetic-only batch evaluation. --real explicitly permits DeepSeek calls.

Never run alongside pytest: both use the dedicated local test database.
Offline scoring: --score RUN_JSON [--reviews REVIEW_JSON]. No model judge.
"""
import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import re
import subprocess
from time import monotonic
from uuid import uuid4, uuid5

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from starlette.concurrency import run_in_threadpool
from app.core.config import Settings
from app.db.tenant_context import TenantSession, bind_tenant
from app.modules.tenants.models import Tenant
from app.modules.users.models import User
from app.modules.knowledge_bases.models import KnowledgeBase
from app.modules.documents.models import Document
from app.modules.chunks.models import Chunk
from app.modules.rag.embedding import BgeEmbedding
from app.modules.rag.reranking import BgeReranker, rerank
from app.modules.rag.retrieval import retrieve_chunks, retrieve_sparse
from app.modules.rag.fusion import fuse_rrf
from app.modules.rag.generation import DeepSeekBackend
from app.modules.rag.service import query
from app.modules.rag.schemas import RagQueryRequest
from app.modules.agent.backend import DeepSeekAgentBackend, parse_arguments
from app.modules.agent.schemas import SearchArgs, DocumentArgs, AgentError
from app.modules.agent.tools import ReadTools
from app.modules.agent.runtime import Scope, Run, Capacity
from app.modules.agent.graph import Context, execute
from app.observability.trace import capture
from scripts.prepare_test_database import test_database_settings
from scripts.evaluation.scoring import retrieval, rule_score, summarize, digest

DATA = Path(__file__).parents[1]/'tests/fixtures/evaluation/m9_v1.json'


def load_dataset() -> dict:
    raw = DATA.read_bytes().replace(b'\r\n', b'\n')
    if hashlib.sha256(raw).hexdigest() != DATA.with_suffix('.sha256').read_text().strip():
        raise ValueError('Frozen dataset hash mismatch')
    data = json.loads(raw)
    ids = [c['case_id'] for c in data['cases']]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate case id')
    return data


class Recording:
    """Evaluation-only wrapper: never installed in runtime dependency injection."""
    def __init__(self, rag, agent):
        self.rag, self.agent = rag, agent
        self.evidence: dict[str, str] = {}
        self.calls: list[dict] = []

    async def generate(self, messages):
        body = json.loads(messages[1]['content'])
        self.evidence = {m[0]: json.loads(m[1])['content'] for m in
            re.findall(r'\[(S\d+)\]\n([^\n]+)', body['Context'])}
        return await self.rag.generate(messages)

    async def complete(self, messages, *args):
        for message in messages:
            if message['role'] == 'tool':
                for block in json.loads(message['content']).get('results', []):
                    if 'evidence' in block:
                        evidence = block['evidence']
                        self.evidence[block['source_id']] = evidence.get('content') or json.dumps(evidence, ensure_ascii=False)
        turn = await self.agent.complete(messages, *args)
        for call in turn.calls:
            try:
                schema = {'search_knowledge_base': SearchArgs, 'get_document_info': DocumentArgs}[call.name]
                args_value = schema.model_validate(parse_arguments(call.arguments)).model_dump(mode='json')
                valid = True
            except Exception:
                valid, args_value = False, None
            self.calls.append({'name': call.name, 'valid': valid, 'arguments': args_value})
        return turn


async def evaluate(limit: int | None = None) -> Path:
    data = load_dataset()
    settings = test_database_settings(Settings())
    if settings.llm_base_url.rstrip('/') != 'https://api.deepseek.com' or not settings.deepseek_api_key:
        raise ValueError('Real evaluation requires approved DeepSeek endpoint and configured key')
    # Independent engines; the application runtime role is used for every retrieval/tool.
    admin = create_async_engine(settings.database_url, hide_parameters=True)
    runtime = create_async_engine(settings.application_database_url, hide_parameters=True)
    factory = async_sessionmaker(runtime, expire_on_commit=False, sync_session_class=TenantSession)
    tenant, kb, empty_kb, user = uuid4(), uuid4(), uuid4(), uuid4()
    ids = {key: uuid5(tenant, key) for key in data['documents']}
    chunk_keys = {str(uuid5(tenant, 'chunk:'+key)): key for key in ids}
    report = {'version': 'm9-v1', 'mode': 'real', 'dataset_hash': hashlib.sha256(DATA.read_bytes().replace(b'\r\n', b'\n')).hexdigest(),
              'code_head': subprocess.check_output(['git','rev-parse','HEAD']).decode().strip(),
              'worktree_dirty': bool(subprocess.check_output(['git','status','--porcelain'])),
              'platform': platform.platform(), 'model': settings.llm_model, 'records': [],
              'started_at': datetime.now(timezone.utc).isoformat(), 'status': 'running',
              'scope': 'artificial data; in-process real services and PostgreSQL RLS, not HTTP latency',
              'candidate_budgets': [settings.dense_candidate_k, settings.sparse_candidate_k, settings.rerank_candidate_k]}
    import importlib.metadata
    report['versions'] = {p: importlib.metadata.version(p) for p in ('openai','langgraph','sentence-transformers','sqlalchemy')}
    report['source_hash'] = digest({str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(Path('src/app').rglob('*.py'))})
    directory = Path('.data/evaluations')/('m9-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'-'+uuid4().hex[:6])
    directory.mkdir(parents=True)
    output = directory/'run.json'
    def save():
        report['summary'] = summarize(report['records'])
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    save()
    embedding = BgeEmbedding(settings.embedding_model, 'cpu', settings.embedding_batch_size)
    reranker = BgeReranker(settings.reranker_model, 'cpu', settings.reranker_batch_size, settings.reranker_max_length)
    try:
        started = monotonic()
        vectors = await run_in_threadpool(embedding.embed_passages, list(data['documents'].values()))
        await run_in_threadpool(reranker.score, 'E1001', ['E1001 认证令牌过期'])
        report['cold_load_and_corpus_embedding_seconds'] = monotonic()-started
        report['model_revisions'] = {'embedding': getattr(embedding._model[0].auto_model.config,'_commit_hash',None),
                                     'reranker': getattr(reranker._model.model.config,'_commit_hash',None)}
        async with admin.begin() as conn:
            await conn.execute(Tenant.__table__.insert().values(id=tenant, name='M9 artificial', slug='m9-'+tenant.hex))
            await conn.execute(User.__table__.insert().values(id=user, tenant_id=tenant, email=tenant.hex+'@example.com', password_hash='unusable-evaluation-account', role='admin', is_active=True))
            for kid in (kb, empty_kb):
                await conn.execute(KnowledgeBase.__table__.insert().values(id=kid, tenant_id=tenant, name=str(kid)))
            for i, (key, content) in enumerate(data['documents'].items()):
                await conn.execute(Document.__table__.insert().values(id=ids[key], tenant_id=tenant, knowledge_base_id=kb,
                    filename=key+'.md', source_type='markdown', status='ready', index_status='ready', embedding_model=settings.embedding_model, indexed_at=datetime.now(timezone.utc)))
                await conn.execute(Chunk.__table__.insert().values(id=uuid5(tenant,'chunk:'+key),tenant_id=tenant,document_id=ids[key],chunk_index=0,content=content,embedding=vectors[i]))
        for case in data['cases'][:limit]:
            recorder = Recording(DeepSeekBackend(settings), DeepSeekAgentBackend(settings))
            question = case['question']
            if case.get('document_key'):
                # Unknown IDs deliberately produce the same invisible-resource behavior.
                question = question.replace('{document_id}',str(ids.get(case['document_key'], uuid5(tenant,case['document_key']))))
            selected_kb = empty_kb if case.get('empty_kb') else kb
            ranks = {}
            if case['mode'] == 'rag' and not case.get('empty_kb'):
                vector = await run_in_threadpool(embedding.embed_query, question)
                async with factory() as session:
                    bind_tenant(session, tenant)
                    dense = await retrieve_chunks(session,tenant,selected_kb,settings.embedding_model,vector,30)
                    sparse = await retrieve_sparse(session,tenant,selected_kb,settings.embedding_model,vector,question,30)
                    await session.rollback()
                fused = [x.chunk for x in fuse_rrf([dense,sparse])[:30]]
                final = await run_in_threadpool(rerank,reranker,question,fused,10)
                ranks = {name:[chunk_keys[str(r.chunk_id)] for r in rows] for name,rows in [('dense',dense),('sparse',sparse),('rrf',fused),('rerank',final)]}
            answer, error, sources, events = '', None, [], []
            started = monotonic()
            with capture() as trace:
                try:
                    async with asyncio.timeout(180):
                        if case['mode'] == 'rag':
                            async with factory() as session:
                                bind_tenant(session,tenant)
                                result = await query(session,tenant,selected_kb,RagQueryRequest(question=question),settings,embedding,recorder,reranker)
                                answer, sources = result.answer, [s.model_dump(mode='json') for s in result.sources]
                        else:
                            pool = Capacity(); pool.acquire(1)
                            run = Run(settings.agent_timeout_seconds,pool)
                            tools = ReadTools(Scope(user,tenant,selected_kb),factory,settings,embedding,reranker,run,5)
                            async def emit(event, payload):
                                events.append({'event':event,'data':json.loads(json.dumps(payload,default=str))})
                            try:
                                state = await execute(Context(run,settings,recorder,tools,emit),question)
                                answer, sources = state['final']['answer'],state['final']['sources']
                            finally:
                                run.close()
                                if run.jobs: await asyncio.gather(*run.jobs,return_exceptions=True)
                except Exception as exc:
                    error = exc.code if isinstance(exc,AgentError) else 'timeout' if isinstance(exc,TimeoutError) else 'infrastructure_or_generation'
            record = {'case_id':case['case_id'],'mode':case['mode'],'split':case['split'],'question':question,
                      'answer':answer,'sources':sources,'evidence':recorder.evidence,'calls':recorder.calls,
                      'events':events,'error':error,'seconds':monotonic()-started,'trace':trace.summary(),
                      'retrieval':{name:{str(k):retrieval(keys,case['relevant'],k) for k in (1,5,10)} for name,keys in ranks.items()},
                      'rules':rule_score(case,answer,recorder.evidence,recorder.calls)}
            report['records'].append(record)
            save()
            print(case['case_id'], 'error='+str(error), 'seconds='+str(round(record['seconds'],2)), flush=True)
        report['status'] = 'complete' if len(report['records']) == len(data['cases']) else 'partial'
    except Exception as exc:
        report['status'], report['error_type'] = 'failed',type(exc).__name__
        raise
    finally:
        try:
            async with admin.begin() as conn:
                for model in (Chunk,Document,KnowledgeBase,User):
                    await conn.execute(delete(model).where(model.tenant_id==tenant))
                await conn.execute(delete(Tenant).where(Tenant.id==tenant))
        finally:
            await admin.dispose(); await runtime.dispose(); save()
    print(str(output),flush=True)
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--real',action='store_true')
    parser.add_argument('--limit',type=int)
    parser.add_argument('--score',type=Path)
    parser.add_argument('--reviews',type=Path)
    args = parser.parse_args()
    if args.score:
        records=json.loads(args.score.read_text(encoding='utf-8'))['records']
        reviews=json.loads(args.reviews.read_text(encoding='utf-8')) if args.reviews else {}
        print(json.dumps(summarize(records,reviews),ensure_ascii=False,indent=2))
    elif args.real:
        asyncio.run(evaluate(args.limit))
    else:
        parser.error('Choose offline --score RUN_JSON or explicit --real synthetic evaluation')
