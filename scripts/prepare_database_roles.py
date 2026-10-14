"""Administrator-only, repeatable provisioning for this project's databases.

Run before Alembic. Does not drop data, reset RLS, or grant app privileges.
"""
import argparse
import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from app.core.config import Settings
from scripts.prepare_test_database import test_database_settings

TABLES = ("alembic_version", "tenants", "users", "knowledge_bases", "documents", "chunks")


async def provision(settings: Settings) -> None:
    # Validate both credentials before making any changes.
    app_password = settings.application_database_url.password
    migration_password = settings.migration_database_url.password
    engine = create_async_engine(settings.database_url, hide_parameters=True)
    try:
        async with engine.begin() as connection:
            if not await connection.scalar(text("SELECT rolsuper FROM pg_roles WHERE rolname=current_user")):
                raise RuntimeError("Provisioning requires a database administrator")
            for role, login in (("rag_app", "LOGIN"), ("rag_migrator", "LOGIN"), ("rag_auth_lookup", "NOLOGIN")):
                exists = await connection.scalar(text("SELECT 1 FROM pg_roles WHERE rolname=:role"), {"role": role})
                if not exists:
                    await connection.execute(text(f"CREATE ROLE {role}"))
                await connection.execute(text(f"ALTER ROLE {role} {login} NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION NOINHERIT"))
            for role in ("rag_app", "rag_auth_lookup"):
                if await connection.scalar(text("SELECT count(*) FROM pg_auth_members WHERE member=(SELECT oid FROM pg_roles WHERE rolname=:role)"), {"role": role}):
                    raise RuntimeError("Runtime/auth role must not inherit or SET another role")
            for role, password in (("rag_app", app_password), ("rag_migrator", migration_password)):
                await connection.execute(text("SELECT set_config('app.bootstrap_password', :password, true)"), {"password": password})
                # Keep passwords out of statement text, Python logs and exceptions.
                await connection.execute(text(f"DO $$ BEGIN EXECUTE format('ALTER ROLE {role} PASSWORD %L', current_setting('app.bootstrap_password')); END $$"))
            await connection.execute(text("GRANT rag_auth_lookup TO rag_migrator WITH INHERIT FALSE"))
            database = connection.dialect.identifier_preparer.quote(settings.postgres_db)
            await connection.execute(text(f"REVOKE CREATE ON DATABASE {database} FROM PUBLIC, rag_app, rag_auth_lookup"))
            await connection.execute(text(f"GRANT CONNECT ON DATABASE {database} TO rag_app, rag_migrator"))
            await connection.execute(text(f"GRANT CREATE ON DATABASE {database} TO rag_migrator"))
            await connection.execute(text("REVOKE CREATE ON SCHEMA public FROM PUBLIC, rag_app, rag_auth_lookup"))
            await connection.execute(text("GRANT USAGE ON SCHEMA public TO rag_app, rag_auth_lookup, rag_migrator"))
            await connection.execute(text("GRANT CREATE ON SCHEMA public TO rag_migrator"))
            # M1 requires vector extension before unprivileged migrations on a fresh DB.
            await connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            for table in TABLES:
                if await connection.scalar(text("SELECT to_regclass(:name)"), {"name": "public." + table}):
                    await connection.execute(text(f"ALTER TABLE public.{table} OWNER TO rag_migrator"))
        print("Project database roles and ownership prepared; data preserved")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", action="store_true")
    args = parser.parse_args()
    config = Settings()
    if args.test:
        config = test_database_settings(config)
    try:
        asyncio.run(provision(config))
    except Exception as error:
        # Never print driver exceptions from password provisioning.
        raise SystemExit("Role provisioning failed: " + type(error).__name__) from None
