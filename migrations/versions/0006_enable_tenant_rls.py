"""Tenant RLS and narrowly scoped pre-authentication lookup functions."""
from alembic import op
import sqlalchemy as sa

revision = "0006_enable_tenant_rls"
down_revision = "0005_add_vector_indexing"
branch_labels = None
depends_on = None

TABLES = ("tenants", "users", "knowledge_bases", "documents", "chunks")


def upgrade() -> None:
    connection = op.get_bind()
    if connection.scalar(sa.text("SELECT current_user")) != "rag_migrator":
        raise RuntimeError("Run migrations as rag_migrator after role provisioning")
    op.execute("CREATE SCHEMA IF NOT EXISTS app_private AUTHORIZATION rag_migrator")
    op.execute("REVOKE ALL ON SCHEMA app_private FROM PUBLIC")
    op.execute("GRANT USAGE ON SCHEMA app_private TO rag_app, rag_auth_lookup")
    op.execute("GRANT CREATE ON SCHEMA app_private TO rag_auth_lookup")
    for table in TABLES:
        column = "id" if table == "tenants" else "tenant_id"
        predicate = f"{column} = NULLIF(pg_catalog.current_setting('app.tenant_id', true), '')::uuid"
        op.execute(f"REVOKE ALL ON TABLE public.{table} FROM PUBLIC, rag_app, rag_auth_lookup")
        for command in ("SELECT", "INSERT", "UPDATE", "DELETE"):
            clauses = (f"WITH CHECK ({predicate})" if command == "INSERT" else
                       f"USING ({predicate}) WITH CHECK ({predicate})" if command == "UPDATE" else
                       f"USING ({predicate})")
            op.execute(f"CREATE POLICY {table}_tenant_{command.lower()} ON public.{table} FOR {command} TO rag_app {clauses}")
        op.execute(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE public.{table} FORCE ROW LEVEL SECURITY")
    op.execute("GRANT SELECT, INSERT ON public.tenants, public.users, public.knowledge_bases TO rag_app")
    op.execute("GRANT SELECT, INSERT, UPDATE ON public.documents TO rag_app")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON public.chunks TO rag_app")
    op.execute("GRANT SELECT (id, tenant_id, email, password_hash, is_active) ON public.users TO rag_auth_lookup")
    op.execute("CREATE POLICY users_auth_lookup ON public.users FOR SELECT TO rag_auth_lookup USING (true)")
    op.execute("""
        CREATE FUNCTION app_private.login_credentials(requested_email text)
        RETURNS TABLE(user_id uuid, password_hash text, is_active boolean)
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, pg_temp
        AS 'SELECT u.id, u.password_hash, u.is_active FROM public.users AS u WHERE u.email = requested_email'
    """)
    op.execute("""
        CREATE FUNCTION app_private.user_tenant(requested_user uuid)
        RETURNS uuid LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, pg_temp
        AS 'SELECT u.tenant_id FROM public.users AS u WHERE u.id = requested_user'
    """)
    for signature in ("login_credentials(text)", "user_tenant(uuid)"):
        op.execute(f"ALTER FUNCTION app_private.{signature} OWNER TO rag_auth_lookup")
        # Migrator has explicit SET membership, not inherited runtime privileges.
        op.execute("SET LOCAL ROLE rag_auth_lookup")
        op.execute(f"REVOKE ALL ON FUNCTION app_private.{signature} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION app_private.{signature} TO rag_app")
        op.execute("RESET ROLE")
    op.execute("REVOKE CREATE ON SCHEMA app_private FROM rag_auth_lookup")


def downgrade() -> None:
    # Fail closed during rollback: do not expose tenant tables to the new app.
    for table in TABLES:
        op.execute(f"REVOKE ALL ON TABLE public.{table} FROM rag_app")
    op.execute("SET LOCAL ROLE rag_auth_lookup")
    for signature in ("login_credentials(text)", "user_tenant(uuid)"):
        op.execute(f"DROP FUNCTION app_private.{signature}")
    op.execute("RESET ROLE")
    op.execute("DROP POLICY users_auth_lookup ON public.users")
    op.execute("REVOKE SELECT (id, tenant_id, email, password_hash, is_active) ON public.users FROM rag_auth_lookup")
    for table in reversed(TABLES):
        for command in ("select", "insert", "update", "delete"):
            op.execute(f"DROP POLICY {table}_tenant_{command} ON public.{table}")
        op.execute(f"ALTER TABLE public.{table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE public.{table} DISABLE ROW LEVEL SECURITY")
    op.execute("DROP SCHEMA app_private")
