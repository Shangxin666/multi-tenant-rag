import pytest
from sqlalchemy import Connection, inspect, text
from sqlalchemy.ext.asyncio import AsyncEngine

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def test_upgrade_head_and_vector(db_engine: AsyncEngine) -> None:
    async with db_engine.connect() as connection:
        assert await connection.scalar(text("SELECT version_num FROM alembic_version")) == "0004_add_document_storage_fields"
        assert await connection.scalar(
            text("SELECT extname FROM pg_extension WHERE extname = 'vector'")
        ) == "vector"

        def inspect_schema(sync_connection: Connection) -> None:
            inspector = inspect(sync_connection)
            assert {"tenants", "users", "alembic_version"} <= set(inspector.get_table_names())
            assert {tuple(c["column_names"]) for c in inspector.get_unique_constraints("users")} == {("email",)}
            assert {tuple(c["column_names"]) for c in inspector.get_unique_constraints("tenants")} == {("slug",)}
            foreign_key = inspector.get_foreign_keys("users")[0]
            assert foreign_key["referred_table"] == "tenants"
            assert foreign_key["options"]["ondelete"] == "RESTRICT"
            checks = inspector.get_check_constraints("users")
            assert len(checks) == 1 and checks[0]["name"] == "ck_users_role"
            assert "admin" in checks[0]["sqltext"] and "member" in checks[0]["sqltext"]
            assert any(i["column_names"] == ["tenant_id"] for i in inspector.get_indexes("users"))

        await connection.run_sync(inspect_schema)


async def test_knowledge_schema(db_engine: AsyncEngine) -> None:
    def verify(connection: Connection) -> None:
        inspector = inspect(connection)
        expected_uniques = {
            "knowledge_bases": {("tenant_id", "name"), ("tenant_id", "id")},
            "documents": {("tenant_id", "id"), ("storage_key",)},
            "chunks": {("document_id", "chunk_index")},
        }
        expected_foreign_keys = {
            "knowledge_bases": (["tenant_id"], "tenants", ["id"], "RESTRICT"),
            "documents": (["tenant_id", "knowledge_base_id"], "knowledge_bases", ["tenant_id", "id"], "RESTRICT"),
            "chunks": (["tenant_id", "document_id"], "documents", ["tenant_id", "id"], "CASCADE"),
        }
        expected_checks = {
            "knowledge_bases": set(),
            "documents": {"ck_documents_source_type", "ck_documents_status", "ck_documents_storage_fields", "ck_documents_file_size", "ck_documents_sha256"},
            "chunks": {"ck_chunks_chunk_index"},
        }
        for table in expected_uniques:
            assert {tuple(c["column_names"]) for c in inspector.get_unique_constraints(table)} == expected_uniques[table]
            foreign_keys = inspector.get_foreign_keys(table)
            assert len(foreign_keys) == 1
            fk = foreign_keys[0]
            assert (
                fk["constrained_columns"], fk["referred_table"],
                fk["referred_columns"], fk["options"]["ondelete"],
            ) == expected_foreign_keys[table]
            assert {c["name"] for c in inspector.get_check_constraints(table)} == expected_checks[table]
            columns = {c["name"]: c for c in inspector.get_columns(table)}
            assert not columns["tenant_id"]["nullable"]
            assert columns["created_at"]["type"].timezone
            assert "embedding" not in columns and "vector" not in columns
        document_indexes = inspector.get_indexes("documents")
        assert any(i["column_names"] == ["tenant_id", "knowledge_base_id"] for i in document_indexes)
        assert any(i["column_names"] == ["tenant_id"] for i in inspector.get_indexes("chunks"))
        assert "metadata" in {c["name"] for c in inspector.get_columns("chunks")}
        assert "chunk_metadata" not in {c["name"] for c in inspector.get_columns("chunks")}

    async with db_engine.connect() as connection:
        await connection.run_sync(verify)
