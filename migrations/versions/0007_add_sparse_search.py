"""Deterministic lexical search; no table-reading or privileged functions."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import TSVECTOR

revision = "0007_add_sparse_search"
down_revision = "0006_enable_tenant_rls"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ASCII translation and C collation avoid locale-dependent token boundaries.
    # All called catalog functions are immutable; no configuration/table lookups.
    # Encode lexemes as ASCII hex so FTS cannot split identifier punctuation.
    op.execute(r"""
        CREATE FUNCTION app_private.search_tokens(source text) RETURNS text[]
        LANGUAGE plpgsql IMMUTABLE STRICT SECURITY INVOKER
        SET search_path = pg_catalog, pg_temp AS $$
        DECLARE part text[]; word text; tokens text[] := ARRAY[]::text[]; i integer;
        BEGIN
          FOR part IN SELECT regexp_matches(source COLLATE "C",
            '[A-Za-z0-9]+(?:[._-][A-Za-z0-9]+)*|[一-鿿]+', 'g') LOOP
            word := part[1];
            IF word COLLATE "C" ~ '^[A-Za-z0-9]' THEN
              IF length(word) <= 128 THEN
                word := translate(word, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz');
                tokens := array_append(tokens, 'w' || (SELECT string_agg(to_hex(ascii(substr(word, n, 1))), 'z' ORDER BY n) FROM generate_series(1, length(word)) AS n));
              END IF;
            ELSIF length(word) = 1 THEN
              tokens := array_append(tokens, 'c' || to_hex(ascii(word)));
            ELSE
              FOR i IN 1..length(word)-1 LOOP
                tokens := array_append(tokens, 'c' || to_hex(ascii(substr(word, i, 1))) || 'z' || to_hex(ascii(substr(word, i+1, 1))));
              END LOOP;
            END IF;
          END LOOP;
          RETURN tokens;
        END $$
    """)
    op.execute("""
        CREATE FUNCTION app_private.search_document(source text) RETURNS tsvector
        LANGUAGE sql IMMUTABLE STRICT SECURITY INVOKER
        SET search_path = pg_catalog, pg_temp
        AS $$ SELECT to_tsvector('pg_catalog.simple'::regconfig,
                     coalesce(string_agg(token, ' ' ORDER BY position), ''))
              FROM unnest(app_private.search_tokens(source)) WITH ORDINALITY AS t(token, position) $$
    """)
    op.execute("""
        CREATE FUNCTION app_private.search_question(source text) RETURNS tsquery
        LANGUAGE sql IMMUTABLE STRICT SECURITY INVOKER
        SET search_path = pg_catalog, pg_temp
        AS $$ SELECT CASE WHEN count(*) = 0 THEN NULL::tsquery
                  ELSE to_tsquery('pg_catalog.simple'::regconfig,
                       string_agg(token, ' | ' ORDER BY priority, position)) END
              FROM (SELECT token, min(position) AS position,
                           CASE WHEN left(token, 1) = 'w' THEN 0 ELSE 1 END AS priority
                    FROM unnest(app_private.search_tokens(source)) WITH ORDINALITY AS t(token, position)
                    GROUP BY token ORDER BY priority, min(position) LIMIT 64) bounded $$
    """)
    op.execute("GRANT USAGE ON SCHEMA app_private TO rag_app")
    for name in ("search_tokens", "search_document", "search_question"):
        op.execute(f"REVOKE ALL ON FUNCTION app_private.{name}(text) FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION app_private.{name}(text) TO rag_app")
    op.add_column("chunks", sa.Column("search_vector", TSVECTOR(),
        sa.Computed("app_private.search_document(content)", persisted=True), nullable=False))
    op.create_index("ix_chunks_search_vector_gin", "chunks", ["search_vector"], postgresql_using="gin")


def downgrade() -> None:
    op.drop_index("ix_chunks_search_vector_gin", table_name="chunks")
    op.drop_column("chunks", "search_vector")
    for name in ("search_question", "search_document", "search_tokens"):
        op.execute(f"DROP FUNCTION app_private.{name}(text)")
