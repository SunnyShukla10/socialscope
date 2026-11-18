-- Operator-only, single-use role creation. No passwords, ownership changes or schema migrations.
-- Invoke with psql -X -v ON_ERROR_STOP=1 and the variables documented in RUNBOOK.md.
\set ON_ERROR_STOP on
BEGIN;
-- Fail closed if the connection, known application, schema head or ownership differs.
SELECT 1 / ((
    current_database() = :'database_name'
    AND current_user = :'maintenance_role'
    AND :'database_name' = 'socialscope'
    AND :'app_role' = :'database_name' || '_app'
    AND (SELECT rolsuper FROM pg_roles WHERE rolname = current_user)
    AND (SELECT count(*) = 1 AND bool_and(version_num = :'expected_revision') FROM public.alembic_version)
    AND NOT EXISTS (
        SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p', 'S', 'v', 'm')
          AND c.relowner <> (SELECT oid FROM pg_roles WHERE rolname = current_user)
    )
)::integer) AS target_verified;

-- Deliberately fails if this role already exists; never overwrite an existing login/password.
CREATE ROLE :"app_role" LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE
    NOREPLICATION NOBYPASSRLS NOINHERIT;
GRANT CONNECT ON DATABASE :"database_name" TO :"app_role";
-- On upgraded databases PUBLIC might still have CREATE; remove that inherited access.
-- This affects PUBLIC's schema permission, not table contents or ownership.
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO :"app_role";
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO :"app_role";
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO :"app_role";
-- Runtime may inspect the migration version but must not change it.
REVOKE INSERT, UPDATE, DELETE ON TABLE public.alembic_version FROM :"app_role";

-- Future migrations MUST run as this same maintenance/owner role.
ALTER DEFAULT PRIVILEGES FOR ROLE :"maintenance_role" IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO :"app_role";
ALTER DEFAULT PRIVILEGES FOR ROLE :"maintenance_role" IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO :"app_role";
COMMIT;
\echo Role and grants prepared. Set its password privately with the interactive psql password command next.
