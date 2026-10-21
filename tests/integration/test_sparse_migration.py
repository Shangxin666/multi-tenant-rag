from uuid import uuid4
import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from test_document_storage_migration import migrate, legacy_row

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def test_0006_history_and_generated_column(db_engine, database_settings):
    try:
        await migrate(database_settings, "downgrade", "0006_enable_tenant_rls")
        for _ in range(2):
            doc = await legacy_row(db_engine)
            async with db_engine.begin() as conn:
                await conn.execute(text("INSERT INTO chunks (id, tenant_id, document_id, chunk_index, content) SELECT :id, tenant_id, id, 0, 'E1001 年假' FROM documents WHERE id=:doc"), {"id": uuid4(), "doc": doc})
    finally:
        await migrate(database_settings, "upgrade", "head")
    async with db_engine.begin() as conn:
        assert await conn.scalar(text("SELECT count(*) FROM chunks WHERE search_vector @@ app_private.search_question('E1001')")) == 2
        await conn.execute(text("UPDATE chunks SET content='E10010'"))
        assert await conn.scalar(text("SELECT count(*) FROM chunks WHERE search_vector @@ app_private.search_question('E1001')")) == 0
        assert await conn.scalar(text("SELECT count(*) FROM chunks WHERE search_vector @@ app_private.search_question('e10010')")) == 2
        assert await conn.scalar(text("SELECT attgenerated::text FROM pg_attribute WHERE attrelid='chunks'::regclass AND attname='search_vector'")) == "s"
        assert await conn.scalar(text("SELECT count(*) FROM pg_indexes WHERE indexname='ix_chunks_search_vector_gin' AND indexdef LIKE '%USING gin%'")) == 1
        assert await conn.scalar(text("SELECT relrowsecurity AND relforcerowsecurity FROM pg_class WHERE oid='chunks'::regclass"))
    await migrate(database_settings, "check")


async def test_function_immutability_acl_and_settings(db_engine, app_db_engine):
    async with db_engine.connect() as conn:
        functions = (await conn.execute(text("SELECT proname, provolatile::text, prosecdef, proconfig, pg_get_userbyid(proowner), EXISTS (SELECT 1 FROM aclexplode(proacl) a WHERE grantee=0 AND privilege_type='EXECUTE') FROM pg_proc WHERE pronamespace='app_private'::regnamespace AND proname LIKE 'search_%'"))).all()
        assert len(functions) == 3
        for name, volatility, definer, config, owner, public in functions:
            assert volatility == "i" and not definer and owner == "rag_migrator" and not public
            assert "search_path=pg_catalog, pg_temp" in config
            assert await conn.scalar(text("SELECT has_function_privilege('rag_app', :fn, 'EXECUTE')"), {"fn": f"app_private.{name}(text)"})
            assert not await conn.scalar(text("SELECT has_function_privilege('rag_auth_lookup', :fn, 'EXECUTE')"), {"fn": f"app_private.{name}(text)"})
        # Check the actual overloads used, not only the declared volatility of wrappers.
        signatures = ["regexp_matches(text,text,text)", "textregexeq(text,text)", "length(text)",
                      "translate(text,text,text)", "substr(text,integer,integer)", "ascii(text)",
                      "to_hex(integer)", "generate_series(integer,integer)", "string_agg(text,text)",
                      "to_tsvector(regconfig,text)", "to_tsquery(regconfig,text)", "left(text,integer)",
                      "array_append(anycompatiblearray,anycompatible)", "unnest(anyarray)", "min(bigint)"]
        for signature in signatures:
            assert await conn.scalar(text("SELECT provolatile::text FROM pg_proc WHERE oid=CAST(:signature AS regprocedure)"), {"signature": signature}) == "i", signature
    async with app_db_engine.connect() as conn:
        assert await conn.scalar(text("SELECT has_schema_privilege(current_user,'app_private','USAGE')"))
        assert not await conn.scalar(text("SELECT has_schema_privilege(current_user,'app_private','CREATE')"))
        baseline = await conn.scalar(text("SELECT app_private.search_document('E1001 年假 ZX-200')::text"))
        for config in ("english", "simple"):
            await conn.execute(text("SELECT set_config('default_text_search_config',:config,true)"), {"config": config})
            assert await conn.scalar(text("SELECT app_private.search_document('E1001 年假 ZX-200')::text")) == baseline
        with pytest.raises(DBAPIError):
            await conn.execute(text("CREATE FUNCTION app_private.forbidden() RETURNS int LANGUAGE sql AS 'SELECT 1'"))
        await conn.rollback()


async def test_token_bounds_and_matching(app_db_engine):
    async with app_db_engine.connect() as conn:
        for value, good, bad in [("ZX-200", "zx-200", "ZX-200S"), ("E1001", "e1001", "E10010"),
                                 ("带薪年假", "年假", "产假"), ("timeout", "TIMEOUT", "timeouts")]:
            stmt = text("SELECT app_private.search_document(:value) @@ app_private.search_question(:query)")
            assert await conn.scalar(stmt, {"value": value, "query": good})
            assert not await conn.scalar(stmt, {"value": value, "query": bad})
        assert await conn.scalar(text("SELECT app_private.search_question('!!!') IS NULL"))
        assert await conn.scalar(text("SELECT numnode(app_private.search_question(:q))"), {"q": ' '.join(f"x{i}" for i in range(100))}) == 127
