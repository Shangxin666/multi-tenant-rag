"""Real retrieval experiments; no LLM calls, no lexical substitutes for PostgreSQL.

offline: production BGE + exact cosine in memory; supplemental dense+rerank.
postgres: production Dense / ts_rank / RRF / RRF+rerank against dedicated DB.
"""
import argparse
import asyncio
from datetime import datetime, timezone
import importlib.metadata
import json
from pathlib import Path
import platform
import subprocess
from time import perf_counter
from uuid import UUID

import numpy as np
from sqlalchemy import delete, select, func, text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.core.config import Settings
from app.db.security import verify_runtime_role
from app.db.tenant_context import TenantSession, bind_tenant
from app.modules.tenants.models import Tenant
from app.modules.users.models import User  # register FK metadata
from app.modules.knowledge_bases.models import KnowledgeBase
from app.modules.documents.models import Document
from app.modules.chunks.models import Chunk
from app.modules.rag.embedding import BgeEmbedding
from app.modules.rag.retrieval import RetrievedChunk, retrieve_chunks, retrieve_sparse
from app.modules.rag.fusion import fuse_rrf
from app.modules.rag.reranking import BgeReranker, rerank
from app.observability.trace import capture
from scripts.prepare_test_database import test_database_settings
from scripts.evaluation.dataset import DEFAULT, ROOT, load, validate, sha, write_json
from scripts.evaluation.metrics import aggregate, retrieval_metrics
from scripts.evaluation.real_tech import (load_exploratory, enrich_record, compare_pair,
    summarize_exploratory, render_exploratory, file_sha)


def provenance(root):
    files = sorted(list((ROOT/'src/app').rglob('*.py')) + list((ROOT/'scripts/evaluation').glob('*.py')))
    return {'started_at': datetime.now(timezone.utc).isoformat(),
            'code_head': subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip(),
            'worktree_dirty': bool(subprocess.check_output(['git','status','--porcelain'],cwd=ROOT)),
            'source_sha256': sha(json.dumps({str(p.relative_to(ROOT)):sha(p.read_bytes()) for p in files},sort_keys=True).encode()),
            'dataset_sha256': sha((root/'dataset.json').read_bytes()), 'platform':platform.platform(),
            'versions':{p:importlib.metadata.version(p) for p in ('numpy','sqlalchemy','sentence-transformers','langgraph')}}


def record(case, strategy, rows, elapsed, all_chunks, trace):
    ranked = [str(r.chunk_id) for r in rows[:10]]
    violations = [cid for cid in ranked if cid not in all_chunks or any(all_chunks[cid][k]!=case[k] for k in ('tenant_id','knowledge_base_id'))]
    # A leaked row must never gain relevance credit. Keep its occupied rank.
    scored = [cid if cid not in violations else 'SCOPE_VIOLATION' for cid in ranked]
    metrics = retrieval_metrics(scored,case['relevant_chunk_ids'])
    return {'case_id':case['id'], 'question':case['question'], 'strategy':strategy, 'split':case['split'],
            'category':case['category'], 'answerable':case['answerable'], 'ranked':ranked,
            'relevant_chunk_ids':case['relevant_chunk_ids'], 'metrics':metrics, 'latency_ms':elapsed*1000,
            'scope_violations':violations, 'trace_id':trace['trace_id'], 'trace':trace,
            'failed':bool(violations) or (metrics.get('recall@10',0)<1 if case['answerable'] else bool(ranked))}


def render(report):
    lines = ['# Retrieval evaluation', '', f"Status: {report['status']}; mode: {report['mode']}; split: {report['split']}",
             '', f"Dataset: `{report['dataset_sha256']}`; code: `{report['code_head']}`", '',
             '| Strategy | n / answerable / negative | R@1 | R@3 | R@5 | R@10 | MRR@10 | Hit@1 / 3 / 5 / 10 | nDCG@10 | P50 / P95 ms | Negative empty accuracy |',
             '| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |']
    for strategy, s in report.get('summary',{}).items():
        m = s['metrics']
        fmt = lambda v: 'N/A' if v is None else f'{v:.4f}'
        lines.append(f"| {strategy} | {s['n']} / {s['answerable_n']} / {s['unanswerable_n']} | " + ' | '.join(fmt(m.get(k)) for k in ('recall@1','recall@3','recall@5','recall@10','mrr@10')) + ' | ' + ' / '.join(fmt(m.get(f'hit_rate@{k}')) for k in (1,3,5,10)) + f" | {fmt(m.get('ndcg@10'))} | {fmt(s['p50_ms'])} / {fmt(s['p95_ms'])} | {fmt(s['no_result_accuracy'])} |")
    lines += ['', 'Unavailable strategies: '+json.dumps(report.get('unavailable',{}),ensure_ascii=False), '',
              'Binary chunk relevance. Recall divides by ALL labeled relevant chunks; Hit is any hit; MRR is first relevant reciprocal rank at 10; nDCG uses binary gain and ideal min(10, |relevant|). Duplicates consume slots and receive credit once. Macro averages exclude unanswerable queries. Negative accuracy is empty-result detection only, not semantic refusal.', '',
              'P50/P95: linear interpolation on warm per-query pipeline time; includes query encoding; excludes corpus encoding/model loading. Shared query encoding time is charged to every strategy. Single sequential run; not an HTTP/concurrency benchmark.', '',
              '## Failures (all individual rows and local traces in JSON)', '', '| Case | Strategy | Category | Recall@10 | Scope violations |', '| --- | --- | --- | --- | --- |']
    for r in report.get('records',[]):
        if r['failed']:
            lines.append(f"| {r['case_id']} | {r['strategy']} | {r['category']} | {r['metrics'].get('recall@10','N/A')} | {len(r['scope_violations'])} |")
    if report.get('error_type'):
        lines += ['', 'Error: '+report['error_type']]
    if report.get('experiment_class') == 'exploratory':
        lines += [render_exploratory(report)]
    return '\n'.join(lines)+'\n'


def save(report, output):
    output.parent.mkdir(parents=True,exist_ok=True)
    strategies = sorted({r['strategy'] for r in report['records']})
    report['summary'] = {s:aggregate([r for r in report['records'] if r['strategy']==s]) for s in strategies}
    report['by_category'] = {s:{c:aggregate([r for r in report['records'] if r['strategy']==s and r['category']==c]) for c in sorted({r['category'] for r in report['records']})} for s in strategies}
    if report.get('experiment_class') == 'exploratory':
        summarize_exploratory(report)
    write_json(output,report)
    output.with_suffix('.md').write_text(render(report),encoding='utf-8')


async def evaluate(root, output, mode, split, dataset_kind='synthetic', allow_unverified=False):
    exploratory = dataset_kind == 'real-tech-exploratory'
    metadata = {}
    if exploratory:
        if mode != 'offline' or split != 'dev':
            raise ValueError('Unverified real-tech data is limited to offline exploratory dev')
        if output.exists() or output.with_suffix('.md').exists():
            raise ValueError('Refusing to overwrite an existing exploratory run')
        data, counts, metadata = load_exploratory(root, allow_unverified=allow_unverified)
    else:
        counts, data = validate(root), load(root)
    settings = Settings()
    if exploratory:
        # A fixed first baseline, never a parameter sweep or implicit environment tuning.
        settings = settings.model_copy(update={'embedding_model':'BAAI/bge-small-zh-v1.5',
            'embedding_device':'cpu', 'embedding_batch_size':32, 'dense_candidate_k':30,
            'rerank_candidate_k':30, 'reranker_model':'BAAI/bge-reranker-base',
            'reranker_device':'cpu', 'reranker_batch_size':8, 'reranker_max_length':512})
    report = {**provenance(root), 'dataset_version':data['version'], 'counts':counts, 'mode':mode, 'split':split,
              'status':'running', 'records':[], 'unavailable':{}, 'top_k':[1,3,5,10],
              'config':{k:getattr(settings,k) for k in ('embedding_model','embedding_device','embedding_batch_size','reranker_model','reranker_device','reranker_batch_size','reranker_max_length','dense_candidate_k','sparse_candidate_k','rrf_k','rerank_candidate_k')},
              'chunk_size':data['chunk_size'], 'chunk_overlap':data['chunk_overlap'], 'llm_calls':0,
              'index_config':{'dense':'exact cosine; no ANN index in existing migrations', 'sparse':'GIN / custom Chinese bigram + ASCII identifier / ts_rank; not BM25'},
              'latency_scope':'warm per query encoding + strategy pipeline; offline exact cosine is not PostgreSQL latency'}
    report.update(metadata)
    report['stage'] = 'initializing'
    save(report,output)
    embedding = BgeEmbedding(settings.embedding_model, settings.embedding_device, settings.embedding_batch_size)
    reranker = BgeReranker(settings.reranker_model,settings.reranker_device,settings.reranker_batch_size,settings.reranker_max_length)
    admin = runtime = None
    created_tenants = []
    chunks = data['chunks']
    by_id = {c['id']:c for c in chunks}
    by_doc = {d['id']:d for d in data['documents']}
    def row(c, distance=0.):
        return RetrievedChunk(UUID(c['id']),UUID(c['document_id']),by_doc[c['document_id']]['path'],c['chunk_index'],c['content'],c['metadata'],float(distance))
    try:
        if mode=='postgres':
            target = test_database_settings(settings)
            admin = create_async_engine(target.database_url,connect_args={'timeout':5},hide_parameters=True)
            runtime = create_async_engine(target.application_database_url,connect_args={'timeout':5},hide_parameters=True)
            await verify_runtime_role(runtime)
        report['stage'] = 'model_loading_and_corpus_encoding'
        started = perf_counter()
        vectors = np.asarray(await asyncio.to_thread(embedding.embed_passages,[c['content'] for c in chunks]),dtype=np.float32)
        await asyncio.to_thread(reranker.score,'模型预热',['synthetic 模拟业务资料'])
        report['cold_load_and_corpus_encoding_seconds'] = perf_counter()-started
        report['model_revisions'] = {'embedding':getattr(embedding._model[0].auto_model.config,'_commit_hash',None),
                                     'reranker':getattr(reranker._model.model.config,'_commit_hash',None)}
        if exploratory:
            import os
            import torch
            report['hardware'] = {'processor':platform.processor(), 'logical_cpu_count':os.cpu_count(),
                                  'torch_threads':torch.get_num_threads(), 'torch_version':torch.__version__,
                                  'device':'cpu', 'hf_hub_offline':os.environ.get('HF_HUB_OFFLINE')}
            report['stage'] = 'per_query_evaluation'
            save(report,output)
        if mode=='postgres':
            # Atomic import, collision aborts instead of modifying an earlier run.
            tenants = sorted({d['tenant_id'] for d in data['documents']})
            async with admin.begin() as conn:
                for t in tenants:
                    await conn.execute(Tenant.__table__.insert().values(id=UUID(t),name='synthetic v2 evaluation',slug='eval-v2-'+UUID(t).hex))
                for kb in sorted({d['knowledge_base_id'] for d in data['documents']}):
                    t = next(d['tenant_id'] for d in data['documents'] if d['knowledge_base_id']==kb)
                    await conn.execute(KnowledgeBase.__table__.insert().values(id=UUID(kb),tenant_id=UUID(t),name='synthetic v2'))
                for d in data['documents']:
                    await conn.execute(Document.__table__.insert().values(id=UUID(d['id']),tenant_id=UUID(d['tenant_id']),knowledge_base_id=UUID(d['knowledge_base_id']),filename=d['path'],source_type=d['source_type'],status='ready',index_status='ready',embedding_model=settings.embedding_model,indexed_at=datetime.now(timezone.utc)))
                for c,v in zip(chunks,vectors,strict=True):
                    await conn.execute(Chunk.__table__.insert().values(id=UUID(c['id']),tenant_id=UUID(c['tenant_id']),document_id=UUID(c['document_id']),chunk_index=c['chunk_index'],content=c['content'],embedding=v.tolist(),metadata={**c['metadata'],'synthetic':True}))
            created_tenants = tenants
            factory = async_sessionmaker(runtime,sync_session_class=TenantSession)
            report['database_scope_checks'] = []
            for t in tenants:
                async with factory() as session:
                    bind_tenant(session,UUID(t))
                    # Intentionally omit tenant WHERE: verify actual RLS, not only query filtering.
                    visible_tenants = list((await session.scalars(select(Chunk.tenant_id).distinct())).all())
                    count = await session.scalar(select(func.count()).select_from(Chunk))
                    expected_count = sum(c['tenant_id']==t for c in chunks)
                    if visible_tenants!=[UUID(t)] or count!=expected_count:
                        raise RuntimeError('Evaluation tenant isolation/count validation failed')
                    report['database_scope_checks'].append({'tenant_id':t,'visible_chunks':count,'passed':True})
                    await session.rollback()
            async with runtime.connect() as conn:
                report['actual_indexes'] = [dict(r) for r in (await conn.execute(text("SELECT indexname,indexdef FROM pg_indexes WHERE tablename='chunks'"))).mappings()]
        else:
            report['unavailable'] = {s:'PostgreSQL not used in offline mode; no substitute results' for s in ('dense_pgvector','sparse_ts_rank','hybrid','hybrid_rerank')}
        for case in [q for q in data['cases'] if q['split']==split]:
            begin = perf_counter()
            vector = await asyncio.to_thread(embedding.embed_query,case['question'])
            encode_time = perf_counter()-begin
            with capture() as trace:
                started = perf_counter()
                if mode=='offline':
                    eligible = [i for i,c in enumerate(chunks) if all(c[k]==case[k] for k in ('tenant_id','knowledge_base_id'))]
                    distances = 1-vectors[eligible] @ np.asarray(vector,dtype=np.float32)
                    order = sorted(zip(eligible,distances),key=lambda pair:(pair[1],chunks[pair[0]]['id']))[:settings.dense_candidate_k]
                    dense = [row(chunks[i],dist) for i,dist in order]
                    dense_time = perf_counter()-started
                    dense_record = record(case,'dense_exact_offline',dense,encode_time+dense_time,by_id,trace.summary())
                    if exploratory:
                        enrich_record(dense_record, case, {'query_embedding':encode_time*1000,
                            'dense_search':dense_time*1000, 'cross_encoder_rerank':0.0})
                        dense_record['dense_candidate_ids'] = [str(r.chunk_id) for r in dense]
                        dense_record['candidate_count'] = len(eligible)
                    report['records'].append(dense_record)
                    started = perf_counter()
                    final = await asyncio.to_thread(rerank,reranker,case['question'],dense[:settings.rerank_candidate_k],10)
                    rerank_time = perf_counter()-started
                    rerank_record = record(case,'dense_rerank_offline',final,encode_time+dense_time+rerank_time,by_id,trace.summary())
                    if exploratory:
                        enrich_record(rerank_record, case, {'query_embedding':encode_time*1000,
                            'dense_search':dense_time*1000, 'cross_encoder_rerank':rerank_time*1000})
                        rerank_record['dense_candidate_ids'] = [str(r.chunk_id) for r in dense]
                        rerank_record['candidate_count'] = len(eligible)
                        compare_pair(dense_record, rerank_record)
                    report['records'].append(rerank_record)
                else:
                    async with factory() as session:
                        bind_tenant(session,UUID(case['tenant_id']))
                        args = (session,UUID(case['tenant_id']),UUID(case['knowledge_base_id']),settings.embedding_model,vector)
                        dense = await retrieve_chunks(*args,settings.dense_candidate_k)
                        dense_time = perf_counter()-started
                        started = perf_counter()
                        sparse = await retrieve_sparse(*args,case['question'],settings.sparse_candidate_k)
                        sparse_time = perf_counter()-started
                        await session.rollback()
                    started = perf_counter()
                    fused = [r.chunk for r in fuse_rrf([dense,sparse],settings.rrf_k)[:settings.rerank_candidate_k]]
                    hybrid_time = dense_time+sparse_time+perf_counter()-started
                    started = perf_counter()
                    final = await asyncio.to_thread(rerank,reranker,case['question'],fused,10)
                    rerank_time = perf_counter()-started
                    for name, rows, latency in [('dense_pgvector',dense,dense_time),('sparse_ts_rank',sparse,sparse_time),('hybrid',fused,hybrid_time),('hybrid_rerank',final,hybrid_time+rerank_time)]:
                        report['records'].append(record(case,name,rows,encode_time+latency,by_id,trace.summary()))
            save(report,output)
            print(case['id'],flush=True)
        report['status']='complete'
        report['stage']='finished'
    except Exception as exc:
        report['status']='failed'; report['error_type']=type(exc).__name__
        raise
    finally:
        try:
            if created_tenants:
                async with admin.begin() as conn:
                    for model in (Chunk,Document,KnowledgeBase):
                        await conn.execute(delete(model).where(model.tenant_id.in_([UUID(t) for t in created_tenants])))
                    await conn.execute(delete(Tenant).where(Tenant.id.in_([UUID(t) for t in created_tenants])))
        finally:
            if admin is not None: await admin.dispose()
            if runtime is not None: await runtime.dispose()
            if exploratory:
                changed = [name for name, expected in metadata['protected_input_sha256'].items()
                           if file_sha(Path(name)) != expected]
                report['protected_inputs_unchanged'] = not changed
                report['changed_protected_inputs'] = changed
                if changed:
                    report['status'] = 'failed'
                    report['error_type'] = 'ProtectedInputChanged'
            report['finished_at']=datetime.now(timezone.utc).isoformat()
            save(report,output)
    return report


if __name__=='__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,default=DEFAULT)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--mode',choices=['offline','postgres'])
    p.add_argument('--split',choices=['dev','final'],default='dev')
    p.add_argument('--dataset-kind',choices=['synthetic','real-tech-exploratory'],default='synthetic')
    p.add_argument('--allow-unverified-exploratory',action='store_true')
    p.add_argument('--render',type=Path,help='Render existing JSON only; no model/DB access')
    a = p.parse_args()
    if a.render:
        a.output.parent.mkdir(parents=True,exist_ok=True)
        a.output.write_text(render(json.loads(a.render.read_text(encoding='utf-8'))),encoding='utf-8')
    else:
        if a.mode is None:
            p.error('--mode required when running experiments')
        asyncio.run(evaluate(a.root,a.output,a.mode,a.split,a.dataset_kind,a.allow_unverified_exploratory))
