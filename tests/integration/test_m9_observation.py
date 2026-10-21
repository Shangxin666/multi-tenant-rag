import json
from uuid import UUID
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker
from app.db.tenant_context import TenantSession, bind_tenant
from app.observability.trace import capture, configure
from app.modules.rag.service import query
from app.modules.rag.schemas import RagQueryRequest
from app.modules.rag.reranking import get_reranker_backend
from test_rag import seed, vector, backends

pytestmark=[pytest.mark.integration,pytest.mark.asyncio]


async def test_trace_preserves_scoped_query(db_engine,app_db_engine,ingestion_accounts,document_settings,application,backends):
    a,b=ingestion_accounts['alpha'],ingestion_accounts['beta']
    own=await seed(db_engine,a,index_status='ready',vectors=[vector()]*3)
    await seed(db_engine,b,index_status='ready',vectors=[vector()]*3)
    factory=async_sessionmaker(app_db_engine,sync_session_class=TenantSession)
    with capture() as trace:
        async with factory() as session:
            bind_tenant(session,UUID(a['tenant_id']))
            result=await query(session,UUID(a['tenant_id']),UUID(a['kb_id']),RagQueryRequest(question='PRIVATE query'),
                document_settings,*backends,application.dependency_overrides[get_reranker_backend]())
            assert not session.in_transaction()
    assert {s.document_id for s in result.sources}=={own}
    text=json.dumps(trace.summary())
    assert 'PRIVATE' not in text and a['tenant_id'] not in text and str(own) not in text
    assert {'rag.query','dense_search','sparse_search','rrf','rerank','context'} <= {s['name'] for s in trace.spans}


async def test_local_trace_enabled_does_not_change_api(client,application,ingestion_accounts,db_engine,backends,tmp_path):
    a=ingestion_accounts['alpha']
    await seed(db_engine,a,index_status='ready',vectors=[vector()]*3)
    path=tmp_path/'trace.jsonl'
    configure(path)
    try:
        response=await client.post(f"/knowledge-bases/{a['kb_id']}/query",headers=a['headers'],json={'question':'SECRET QUERY'})
        assert response.status_code==200 and set(response.json())=={'answer','sources'}
        record=json.loads(path.read_text())
        assert 'SECRET' not in json.dumps(record)
        assert record['spans'][0]['name']=='rag.query'
    finally:
        configure(None)
