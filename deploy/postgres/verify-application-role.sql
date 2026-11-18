-- Permission probes match zero rows and the transaction rolls back. No passwords are printed.
\set ON_ERROR_STOP on
BEGIN;
SELECT current_database(), current_user;
-- Require an actual login as the runtime role, not SET ROLE from the owner.
SELECT 1 / ((current_user = :'app_role' AND session_user = :'app_role'
             AND current_database() = :'database_name')::integer) AS identity_verified;
SELECT 1 / ((NOT rolsuper AND NOT rolcreatedb AND NOT rolcreaterole
             AND NOT rolreplication AND NOT rolbypassrls AND NOT rolinherit
             AND rolcanlogin)::integer) AS role_flags_verified
FROM pg_roles WHERE rolname = current_user;
SELECT 1 / ((
    NOT has_schema_privilege(current_user, 'public', 'CREATE')
    AND NOT has_database_privilege(current_user, current_database(), 'CREATE')
    AND NOT has_table_privilege(current_user, 'public.alembic_version', 'UPDATE')
    AND NOT has_table_privilege(current_user, 'public.alembic_version', 'INSERT')
    AND NOT has_table_privilege(current_user, 'public.alembic_version', 'DELETE')
    AND NOT EXISTS (SELECT 1 FROM pg_auth_members WHERE member = (SELECT oid FROM pg_roles WHERE rolname = current_user))
)::integer) AS restrictions_verified;
SELECT version_num FROM public.alembic_version;
SELECT count(*) AS projects FROM public.projects;
-- Exercise existing-table DML permissions without inserting/deleting/changing rows.
INSERT INTO public.projects SELECT * FROM public.projects WHERE false;
UPDATE public.projects SET name = name WHERE false;
DELETE FROM public.projects WHERE false;
ROLLBACK;
