import asyncio
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.tenant_context import TenantSession, bind_tenant
from app.db.security import verify_runtime_role
from app.modules.documents.models import Document
from app.modules.chunks.models import Chunk
from test_document_storage_migration import migrate

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]
TABLES = ("tenants", "users", "knowledge_bases", "documents", "chunks")


@pytest.fixture
def runtime_sessions(app_db_engine):
    return async_sessionmaker(app_db_engine, expire_on_commit=False, sync_session_class=TenantSession)


async def add_documents(db_engine, accounts):
    result = {}
    async with async_sessionmaker(db_engine, expire_on_commit=False)() as session:
        async with session.begin():
            for name in ("alpha", "beta"):
                a = accounts[name]
                doc = Document(tenant_id=UUID(a["tenant_id"]), knowledge_base_id=UUID(a["kb_id"]),
                               filename="rls.md", source_type="markdown", status="ready")
                session.add(doc)
                await session.flush()
                chunk = Chunk(tenant_id=doc.tenant_id, document_id=doc.id, chunk_index=0, content=name)
                session.add(chunk)
                await session.flush()
                result[name] = {"doc": doc.id, "chunk": chunk.id, "tenant": doc.tenant_id, "kb": doc.knowledge_base_id}
    return result


@pytest.mark.parametrize("table", TABLES)
async def test_unfiltered_select_and_no_context(runtime_sessions, db_engine, ingestion_accounts, table):
    data = await add_documents(db_engine, ingestion_accounts)
    column = "id" if table == "tenants" else "tenant_id"
    async with runtime_sessions() as session:
        assert list(await session.scalars(text(f"SELECT {column} FROM public.{table}"))) == []
    async with runtime_sessions() as session:
        bind_tenant(session, data["alpha"]["tenant"])
        ids = list(await session.scalars(text(f"SELECT {column} FROM public.{table}")))
        assert ids and set(ids) == {data["alpha"]["tenant"]}
        assert await session.scalar(text(f"SELECT count(*) FROM public.{table} WHERE {column}=:other"), {"other": data["beta"]["tenant"]}) == 0


@pytest.mark.parametrize("table", TABLES)
@pytest.mark.parametrize("context", ["alpha", None])
async def test_wrong_tenant_insert(runtime_sessions, db_engine, ingestion_accounts, table, context):
    data = await add_documents(db_engine, ingestion_accounts)
    b = data["beta"]
    statements = {
        "tenants": "INSERT INTO tenants (id,name,slug) VALUES (:tenant,'Bad',:slug)",
        "users": "INSERT INTO users (id,tenant_id,email,password_hash) VALUES (:id,:tenant,:slug,'not-a-real-hash')",
        "knowledge_bases": "INSERT INTO knowledge_bases (id,tenant_id,name) VALUES (:id,:tenant,:slug)",
        "documents": "INSERT INTO documents (id,tenant_id,knowledge_base_id,filename,source_type) VALUES (:id,:tenant,:kb,'bad.md','markdown')",
        "chunks": "INSERT INTO chunks (id,tenant_id,document_id,chunk_index,content) VALUES (:id,:tenant,:doc,99,'bad')",
    }
    async with runtime_sessions() as session:
        if context: bind_tenant(session, data[context]["tenant"])
        with pytest.raises(DBAPIError) as caught:
            await session.execute(text(statements[table]), {**b, "id": uuid4(), "slug": uuid4().hex})
        assert caught.value.orig.sqlstate == "42501"
        await session.rollback()
        # The failed transaction must not poison the next transaction.
        assert await session.scalar(text("SELECT 1")) == 1


async def test_update_delete_and_parent_consistency(runtime_sessions, db_engine, ingestion_accounts):
    data = await add_documents(db_engine, ingestion_accounts)
    a, b = data["alpha"], data["beta"]
    async with runtime_sessions() as session:
        bind_tenant(session, a["tenant"])
        result = await session.execute(text("UPDATE documents SET filename='changed.md' WHERE id=:id"), {"id": b["doc"]})
        assert result.rowcount == 0
        assert (await session.execute(text("DELETE FROM chunks WHERE id=:id"), {"id": b["chunk"]})).rowcount == 0
        await session.commit()
        with pytest.raises(DBAPIError) as caught:
            await session.execute(text("UPDATE chunks SET tenant_id=:tenant, document_id=:doc WHERE id=:id"),
                                  {"id": a["chunk"], "tenant": b["tenant"], "doc": b["doc"]})
        assert caught.value.orig.sqlstate == "42501"
        await session.rollback()
        with pytest.raises(DBAPIError) as caught:
            await session.execute(text("UPDATE chunks SET document_id=:doc, chunk_index=99 WHERE id=:id"), {"id": a["chunk"], "doc": b["doc"]})
        assert caught.value.orig.sqlstate == "23503"
        await session.rollback()
        # Intentionally no WHERE: RLS must protect B while allowing A's delete.
        assert (await session.execute(text("DELETE FROM chunks"))).rowcount == 1
        await session.commit()
    async with db_engine.connect() as conn:
        assert await conn.scalar(text("SELECT count(*) FROM chunks WHERE id=:id"), {"id": b["chunk"]}) == 1


async def test_transaction_restart_and_pool_reuse(runtime_sessions, app_db_engine, ingestion_accounts):
    a, b = [UUID(ingestion_accounts[n]["tenant_id"]) for n in ("alpha", "beta")]
    pids = []
    async with runtime_sessions() as session:
        await session.execute(text("SELECT 1"))
        with pytest.raises(RuntimeError, match="Finish authentication"):
            bind_tenant(session, a)
        await session.rollback()
        bind_tenant(session, a)
        for end in (session.commit, session.rollback, session.commit):
            assert await session.scalar(text("SELECT current_setting('app.tenant_id')")) == str(a)
            pids.append(await session.scalar(text("SELECT pg_backend_pid()")))
            await end()
        with pytest.raises(RuntimeError, match="switch tenants"):
            bind_tenant(session, b)
    assert "tenant_id" not in session.info
    # Raw pooled connection proves context reset independently of the ORM hook.
    async with app_db_engine.connect() as connection:
        pids.append(await connection.scalar(text("SELECT pg_backend_pid()")))
        assert await connection.scalar(text("SELECT current_setting('app.tenant_id', true)")) in (None, "")
        assert await connection.scalar(text("SELECT count(*) FROM tenants")) == 0
    for tenant in (b, None, a):
        async with runtime_sessions() as session:
            if tenant: bind_tenant(session, tenant)
            pids.append(await session.scalar(text("SELECT pg_backend_pid()")))
            assert list(await session.scalars(text("SELECT id FROM tenants"))) == ([tenant] if tenant else [])
    assert len(set(pids)) == 1


async def test_concurrent_tenants(runtime_sessions, client, ingestion_accounts):
    async def read(name):
        tenant = UUID(ingestion_accounts[name]["tenant_id"])
        async with runtime_sessions() as session:
            bind_tenant(session, tenant)
            for _ in range(3):
                assert list(await session.scalars(text("SELECT id FROM tenants"))) == [tenant]
                await session.commit()
                await asyncio.sleep(0)
        response = await client.get("/users", headers=ingestion_accounts[name]["headers"])
        assert response.status_code == 200 and all(u["tenant_id"] == str(tenant) for u in response.json())
    await asyncio.gather(*(read(name) for name in ("alpha", "beta", "alpha", "beta")))


async def test_invalid_guc_and_privilege_denials(app_db_engine, ingestion_accounts):
    async with app_db_engine.connect() as conn:
        await conn.execute(text("SELECT set_config('app.tenant_id','invalid',true)"))
        with pytest.raises(DBAPIError): await conn.execute(text("SELECT * FROM tenants"))
        await conn.rollback()
        for command in ("SET ROLE rag_migrator", "SET ROLE rag_auth_lookup", "TRUNCATE chunks",
                        "ALTER TABLE chunks DISABLE ROW LEVEL SECURITY", "CREATE TABLE public.rls_forbidden(id int)"):
            with pytest.raises(DBAPIError): await conn.execute(text(command))
            await conn.rollback()


async def test_unfiltered_vector_search_and_missing_context_writes(runtime_sessions, db_engine, ingestion_accounts):
    from sqlalchemy import update
    data = await add_documents(db_engine, ingestion_accounts)
    vector = [1.0] + [0.0] * 511
    async with db_engine.begin() as conn:
        await conn.execute(update(Chunk).values(embedding=vector))
    async with runtime_sessions() as session:
        assert (await session.execute(text("UPDATE chunks SET content='bad'"))).rowcount == 0
        assert (await session.execute(text("DELETE FROM chunks"))).rowcount == 0
        await session.commit()
    async with runtime_sessions() as session:
        bind_tenant(session, data["alpha"]["tenant"])
        # Deliberately remove every application WHERE condition.
        ids = list(await session.scalars(select(Chunk.id).join(Document).order_by(Chunk.embedding.cosine_distance(vector))))
        assert ids == [data["alpha"]["chunk"]]


async def test_auth_role_policies_and_function_output(db_engine, app_db_engine, ingestion_accounts):
    async with app_db_engine.connect() as conn:
        assert await conn.scalar(text("SELECT count(*) FROM users")) == 0
        row = (await conn.execute(text("SELECT * FROM app_private.login_credentials('alpha@example.com')"))).one()
        assert set(row._mapping) == {"user_id", "password_hash", "is_active"}
        assert row.password_hash.startswith("$argon2id$")
        assert await conn.scalar(text("SELECT app_private.user_tenant(:id)"), {"id": row.user_id}) == UUID(ingestion_accounts["alpha"]["tenant_id"])
        assert (await conn.execute(text("SELECT * FROM app_private.login_credentials(:email)"), {"email": "' OR true --"})).all() == []
    async with db_engine.connect() as conn:
        role = (await conn.execute(text("SELECT rolcanlogin, rolsuper, rolbypassrls FROM pg_roles WHERE rolname='rag_auth_lookup'"))).one()
        assert tuple(role) == (False, False, False)
        assert await conn.scalar(text("SELECT pg_get_userbyid(relowner) FROM pg_class WHERE oid='public.users'::regclass")) == "rag_migrator"
        functions = (await conn.execute(text("SELECT p.prosecdef, pg_get_userbyid(p.proowner), p.proconfig, p.proacl::text FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='app_private' AND p.proname IN ('login_credentials','user_tenant')"))).all()
        assert len(functions) == 2
        for secure, owner, config, acl in functions:
            assert secure and owner == "rag_auth_lookup" and "search_path=pg_catalog, pg_temp" in config
            assert "=X/" not in acl.replace("rag_app=X/", "").replace("rag_auth_lookup=X/", "")
        await conn.execute(text("SET LOCAL ROLE rag_auth_lookup"))
        # SELECT policy, not ownership/BYPASSRLS, makes this read possible.
        assert await conn.scalar(text("SELECT count(id) FROM public.users")) == 3
        with pytest.raises(DBAPIError): await conn.execute(text("SELECT role FROM users"))
        await conn.rollback()
        await conn.execute(text("SET LOCAL ROLE rag_auth_lookup"))
        with pytest.raises(DBAPIError): await conn.execute(text("SELECT * FROM documents"))
        await conn.rollback()


async def test_force_owner_and_startup_checks(db_engine, app_db_engine, database_settings, ingestion_accounts):
    await verify_runtime_role(app_db_engine)
    with pytest.raises(RuntimeError): await verify_runtime_role(db_engine)
    engine = create_async_engine(database_settings.migration_database_url)
    try:
        async with engine.connect() as conn:
            assert await conn.scalar(text("SELECT count(*) FROM tenants")) == 0
            assert await conn.scalar(text("SELECT count(*) FROM users")) == 0
    finally:
        await engine.dispose()


async def test_rls_upgrade_downgrade_preserves_data(db_engine, database_settings, ingestion_accounts):
    try:
        await migrate(database_settings, "downgrade", "0005_add_vector_indexing")
        async with db_engine.connect() as conn:
            assert await conn.scalar(text("SELECT count(*) FROM tenants")) == 2
            assert await conn.scalar(text("SELECT has_table_privilege('rag_app','public.chunks','SELECT')")) is False
            assert await conn.scalar(text("SELECT relrowsecurity FROM pg_class WHERE oid='public.chunks'::regclass")) is False
    finally:
        await migrate(database_settings, "upgrade", "head")
    async with db_engine.connect() as conn:
        assert await conn.scalar(text("SELECT count(*) FROM pg_policies WHERE schemaname='public' AND tablename IN ('tenants','users','knowledge_bases','documents','chunks')")) == 21
        assert await conn.scalar(text("SELECT count(*) FROM pg_class WHERE oid IN ('tenants'::regclass,'users'::regclass,'knowledge_bases'::regclass,'documents'::regclass,'chunks'::regclass) AND relrowsecurity AND relforcerowsecurity")) == 5
    await migrate(database_settings, "check")
