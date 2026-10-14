from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


async def verify_runtime_role(engine: AsyncEngine) -> None:
    """Fail closed if deployed with privileged credentials or missing RLS."""
    async with engine.connect() as connection:
        role = (await connection.execute(text(
            "SELECT current_user, rolsuper, rolbypassrls, rolcreaterole, rolcreatedb "
            "FROM pg_roles WHERE rolname=current_user"
        ))).one()
        if role[0] != "rag_app" or any(role[1:]):
            raise RuntimeError("Unsafe application database role")
        if await connection.scalar(text("SELECT count(*) FROM pg_auth_members WHERE member=(SELECT oid FROM pg_roles WHERE rolname=current_user)")):
            raise RuntimeError("Application role must not have role memberships")
        tables = (await connection.execute(text(
            "SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity, pg_get_userbyid(c.relowner) "
            "FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
            "WHERE n.nspname='public' AND c.relname IN ('tenants','users','knowledge_bases','documents','chunks')"
        ))).all()
        if len(tables) != 5 or any(not r[1] or not r[2] or r[3] != "rag_migrator" for r in tables):
            raise RuntimeError("Tenant RLS/ownership is not ready")
        if await connection.scalar(text("SELECT has_schema_privilege(current_user,'public','CREATE') OR has_schema_privilege(current_user,'app_private','CREATE') OR has_database_privilege(current_user,current_database(),'CREATE')")):
            raise RuntimeError("Application role must not create database objects")
        for table in ("tenants", "users", "knowledge_bases", "documents", "chunks"):
            if await connection.scalar(text("SELECT has_table_privilege(current_user,:table,'TRUNCATE')"), {"table": "public." + table}):
                raise RuntimeError("Application role must not truncate tenant tables")
        for name in ("login_credentials(text)", "user_tenant(uuid)"):
            if not await connection.scalar(text("SELECT has_function_privilege(current_user, :function, 'EXECUTE')"), {"function": "app_private." + name}):
                raise RuntimeError("Authentication function unavailable")
        auth_role = (await connection.execute(text("SELECT rolcanlogin, rolsuper, rolbypassrls FROM pg_roles WHERE rolname='rag_auth_lookup'"))).one()
        if any(auth_role):
            raise RuntimeError("Unsafe authentication lookup role")
        functions = (await connection.execute(text(
            "SELECT p.prosecdef, pg_get_userbyid(p.proowner), p.proconfig, "
            "EXISTS (SELECT 1 FROM aclexplode(COALESCE(p.proacl,acldefault('f',p.proowner))) a "
            "WHERE a.grantee=0 AND a.privilege_type='EXECUTE') AS public_execute "
            "FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace "
            "WHERE n.nspname='app_private' AND p.proname IN ('login_credentials','user_tenant')"
        ))).all()
        if len(functions) != 2 or any(not f[0] or f[1] != "rag_auth_lookup" or
                                     "search_path=pg_catalog, pg_temp" not in (f[2] or []) or f[3] for f in functions):
            raise RuntimeError("Unsafe authentication function configuration")
