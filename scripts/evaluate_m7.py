"""Manual real-model evaluation on artificial data only. Never calls an LLM.

Uses the dedicated local test database; do not run alongside pytest.
Results contain artificial questions/IDs and process metrics, never credentials.
"""
import argparse
import asyncio
import ctypes
import hashlib
import json
import os
from pathlib import Path
import platform
import statistics
from time import perf_counter
from uuid import uuid4, uuid5
from datetime import datetime, timezone

from sqlalchemy import delete, text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from starlette.concurrency import run_in_threadpool

from app.core.config import Settings
from app.db.tenant_context import TenantSession, bind_tenant
from app.modules.tenants.models import Tenant
from app.modules.users.models import User  # register metadata FK targets
from app.modules.knowledge_bases.models import KnowledgeBase
from app.modules.documents.models import Document
from app.modules.chunks.models import Chunk
from app.modules.rag.embedding import BgeEmbedding
from app.modules.rag.reranking import BgeReranker, rerank
from app.modules.rag.retrieval import retrieve_chunks, retrieve_sparse
from app.modules.rag.fusion import fuse_rrf
from scripts.prepare_test_database import test_database_settings


def memory_mib() -> dict[str, float]:
    if os.name == "nt":
        from ctypes import wintypes
        class Counters(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + [
                (name, ctypes.c_size_t) for name in ("PeakWorkingSetSize", "WorkingSetSize",
                "QuotaPeakPagedPoolUsage", "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage",
                "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage")]
        counters = Counters()
        counters.cb = ctypes.sizeof(counters)
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.GetCurrentProcess.restype = wintypes.HANDLE
        get_info = ctypes.WinDLL("psapi", use_last_error=True).GetProcessMemoryInfo
        get_info.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
        if not get_info(kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
            raise ctypes.WinError(ctypes.get_last_error())
        return {"rss": counters.WorkingSetSize / 2**20, "peak_rss": counters.PeakWorkingSetSize / 2**20}
    import resource
    # ru_maxrss units are KiB on Linux and bytes on macOS.
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (2**20 if platform.system() == "Darwin" else 1024)
    return {"peak_rss": peak}


def metrics(ranked: list[str], relevant: list[str]) -> dict[str, float]:
    if not relevant:
        return {}
    truth = set(relevant)
    result = {f"recall@{k}": len(set(ranked[:k]) & truth) / len(truth) for k in (1, 5, 10)}
    result["mrr@10"] = next((1 / rank for rank, key in enumerate(ranked[:10], 1) if key in truth), 0.)
    return result


async def evaluate(output: Path) -> None:
    settings = test_database_settings(Settings())
    corpus_file = Path(__file__).with_name("m7_cases.json")
    corpus = json.loads(corpus_file.read_text(encoding="utf-8"))
    report = {"status": "running", "dataset_sha256": hashlib.sha256(corpus_file.read_bytes()).hexdigest(),
              "platform": platform.platform(), "cpu": platform.processor(), "cpu_count": os.cpu_count(),
              "llm_calls": 0, "queries": [], "memory_mib": {"start": memory_mib()},
              "budgets": {"dense": settings.dense_candidate_k, "sparse": settings.sparse_candidate_k,
                          "rerank": settings.rerank_candidate_k, "rrf_k": settings.rrf_k}}
    output.parent.mkdir(parents=True, exist_ok=True)
    def save() -> None:
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    save()
    admin = create_async_engine(settings.database_url, hide_parameters=True)
    runtime = create_async_engine(settings.application_database_url, hide_parameters=True)
    tenant, kb, doc = uuid4(), uuid4(), uuid4()
    keys = list(corpus["documents"])
    contents = list(corpus["documents"].values())
    id_to_key = {uuid5(tenant, key): key for key in keys}
    embedding = BgeEmbedding(settings.embedding_model, "cpu", settings.embedding_batch_size)
    reranker = BgeReranker(settings.reranker_model, "cpu", settings.reranker_batch_size, settings.reranker_max_length)
    try:
        started = perf_counter()
        await run_in_threadpool(reranker.score, "E1001", contents)
        report["reranker_cold_seconds_including_load_or_download"] = perf_counter() - started
        report["memory_mib"]["reranker_loaded"] = memory_mib()
        report["reranker_revision"] = getattr(reranker._model.model.config, "_commit_hash", None)
        report["warm_reranker_seconds"] = []
        for _ in range(3):
            started = perf_counter()
            await run_in_threadpool(reranker.score, "E1001", contents)
            report["warm_reranker_seconds"].append(perf_counter() - started)
        long_passages = [(content * (1000 // len(content) + 1))[:1000] for content in contents]
        started = perf_counter()
        await run_in_threadpool(reranker.score, "E1001", long_passages)
        report["warm_reranker_24x1000_chars_seconds"] = perf_counter() - started
        print("Real CPU reranker loaded and warm runs completed", flush=True)
        save()
        started = perf_counter()
        vectors = await run_in_threadpool(embedding.embed_passages, contents)
        report["embedding_cold_seconds"] = perf_counter() - started
        report["embedding_revision"] = getattr(embedding._model[0].auto_model.config, "_commit_hash", None)
        report["memory_mib"]["both_models_loaded"] = memory_mib()
        import torch
        report["torch_threads"] = torch.get_num_threads()
        async with async_sessionmaker(admin)() as session:
            async with session.begin():
                session.add(Tenant(id=tenant, name="M7 artificial evaluation", slug="m7-eval-" + tenant.hex))
                await session.flush()
                session.add(KnowledgeBase(id=kb, tenant_id=tenant, name="M7 fixtures"))
                await session.flush()
                session.add(Document(id=doc, tenant_id=tenant, knowledge_base_id=kb, filename="artificial.md",
                    source_type="markdown", status="ready", index_status="ready", embedding_model=settings.embedding_model,
                    indexed_at=datetime.now(timezone.utc)))
                await session.flush()
                session.add_all([Chunk(id=uuid5(tenant, key), tenant_id=tenant, document_id=doc,
                    chunk_index=i, content=contents[i], embedding=vectors[i]) for i, key in enumerate(keys)])
        factory = async_sessionmaker(runtime, sync_session_class=TenantSession)
        for case in corpus["queries"]:
            started = perf_counter()
            vector = await run_in_threadpool(embedding.embed_query, case["question"])
            encoded_at = perf_counter()
            async with factory() as session:
                bind_tenant(session, tenant)
                dense = await retrieve_chunks(session, tenant, kb, settings.embedding_model, vector, settings.dense_candidate_k)
                dense_at = perf_counter()
                sparse = await retrieve_sparse(session, tenant, kb, settings.embedding_model, vector, case["question"], settings.sparse_candidate_k)
                await session.rollback()
            sql_at = perf_counter()
            fused = [item.chunk for item in fuse_rrf([dense, sparse], settings.rrf_k)[:settings.rerank_candidate_k]]
            final = await run_in_threadpool(rerank, reranker, case["question"], fused, 10)
            ranks = {name: [id_to_key[r.chunk_id] for r in rows] for name, rows in
                     (("dense", dense), ("sparse", sparse), ("rrf", fused), ("rerank", final))}
            report["queries"].append({**case, "ranks": ranks,
                "metrics": {name: metrics(values, case["relevant"]) for name, values in ranks.items()},
                "candidate_recall": (len(set(ranks["rrf"]) & set(case["relevant"])) / len(case["relevant"])) if case["relevant"] else None,
                "seconds": {"embed": encoded_at-started, "dense_sql": dense_at-encoded_at,
                            "sparse_sql_and_close": sql_at-dense_at, "rerank": perf_counter()-sql_at,
                            "hybrid_total": perf_counter()-started, "dense_total": dense_at-started}})
            save()
        summaries = {}
        for name in ("dense", "sparse", "rrf", "rerank"):
            scored = [q["metrics"][name] for q in report["queries"] if q["relevant"]]
            summaries[name] = {metric: statistics.mean(q[metric] for q in scored) for metric in scored[0]}
        report.update(status="complete", summary=summaries)
        report["by_category"] = {}
        for category in sorted({q["category"] for q in report["queries"] if q["relevant"]}):
            selected = [q for q in report["queries"] if q["category"] == category]
            report["by_category"][category] = {
                name: {metric: statistics.mean(q["metrics"][name][metric] for q in selected)
                       for metric in summaries[name]} for name in summaries}
        report["latency_seconds"] = {}
        for stage in report["queries"][0]["seconds"]:
            times = [q["seconds"][stage] for q in report["queries"]]
            report["latency_seconds"][stage] = {"mean": statistics.mean(times),
                "p95": statistics.quantiles(times, n=100, method="inclusive")[94]}
        report["memory_mib"]["finished"] = memory_mib()
        print(json.dumps(summaries, ensure_ascii=False), flush=True)
    except Exception as exc:
        report.update(status="failed", error_type=type(exc).__name__)
        print("Evaluation failed: " + type(exc).__name__, flush=True)
        raise
    finally:
        async with admin.begin() as conn:
            for table in (Chunk, Document, KnowledgeBase):
                await conn.execute(delete(table).where(table.tenant_id == tenant))
            await conn.execute(delete(Tenant).where(Tenant.id == tenant))
        await runtime.dispose()
        await admin.dispose()
        save()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path(".data/evaluations/m7.json"))
    args = parser.parse_args()
    asyncio.run(evaluate(args.output))
