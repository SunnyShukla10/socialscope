# SocialScope local operations

Run commands from the destination `socialscope` directory. Do not run them against SocialPulse. The development Compose project is `socialscope-dev`; default host ports are 3102 web, 8102 API, 5534 PostgreSQL, 6481 Redis, all bound to 127.0.0.1. Internal ports remain 3001/8001/5432/6379. Change SOCIALSCOPE_*_PORT in .env.development for host conflicts; internal DATABASE_URL/REDIS_URL remain service addresses. The [port and configuration guide](docs/PORTS_AND_CONFIGURATION.md) lists service ports, configuration checks, and native-development differences.

## Configuration and lifecycle

```powershell
python scripts/setup.py
# Review .env.development privately; add provider keys only for deliberate live tests.
docker compose --env-file .env.development -f compose.development.yml up --build -d
docker compose --env-file .env.development -f compose.development.yml ps --all
docker compose --env-file .env.development -f compose.development.yml logs --tail 50 migrate seed
python scripts/check-connectivity.py
```

Services: postgres, redis, migrate (one-shot), seed (one-shot), backend, worker, scheduler, frontend. Migrate runs `alembic upgrade head`; seed creates the local organization/admin. Backend and worker use Python 3.12; frontend uses its dedicated development Dockerfile and Next development server. Export files live in the shared backend export volume. Redis uses AOF persistence.

`migrate` and `seed` should finish with exit code 0; an exited one-shot service is normal. Wait for seed before login. The development backend waits for seed, and the frontend waits for the healthy backend. A successful seed container exits normally.

Check dependency health as well as HTTP reachability (substitute your API port if changed):

```powershell
Invoke-RestMethod http://127.0.0.1:8102/api/health
```

Expected fields are `status: ok`, `database: true`, and `redis: true` with HTTP 200. A failed database or Redis probe returns HTTP 503 and `status: degraded`. Probes run concurrently with bounded timeouts; Redis clients are closed on failures too. Inspect dependency fields and worker logs before accepting the installation. None of these checks contacts a social provider.

Dashboard displays configured-source booleans and version/build. API root reports service version; `/api/sources` includes BUILD_ID. Seed uses LOCAL_ADMIN_EMAIL/PASSWORD; re-running it preserves existing account details. Use the interactive operator tool for password resets. Provider keys stay server-side.

```powershell
docker compose --env-file .env.development -f compose.development.yml logs --tail 100 migrate seed backend worker scheduler
docker compose --env-file .env.development -f compose.development.yml restart backend worker scheduler
docker compose --env-file .env.development -f compose.development.yml down
```

`restart` restarts existing containers with their existing environment and port mappings. After editing .env.development, use `docker compose --env-file .env.development -f compose.development.yml up -d --force-recreate` for affected services; see the [port guide](docs/PORTS_AND_CONFIGURATION.md). Schedule recreation after active collections finish.

`down` keeps named volumes. **Do not use `down -v` unless deliberately deleting this application's data.** Do not run global Docker prune/reset commands to repair SocialScope. Avoid multiple collection workers: provider rate controls are process-local until the roadmap's distributed controls exist.

## Troubleshooting

| Symptom | Checks and action |
|---|---|
| Docker engine error / 500 / not reachable | Start Docker Desktop in Linux-container mode; check free disk and engine health before retrying this stack |
| Build runs out of space | Free several GB outside source/application data; retry a clean build; do not delete databases or shared Docker storage |
| Login fails | Wait for seed to finish; inspect seed logs; use the private .env.development login values; verify web/API proxy connectivity |
| New password in .env.development has no effect | Expected for existing accounts. Use `docker compose --env-file .env.development -f compose.development.yml exec backend python -m app.manage_users reset-password`; seed does not reset passwords |
| 401 during work | Sign in again; SocialScope uses its own browser token key |
| Missing source key | Edit .env.development privately, then recreate backend/worker/scheduler with `docker compose --env-file .env.development -f compose.development.yml up -d --force-recreate backend worker scheduler` |
| Queued run stays queued | Check Redis and worker logs/queue subscription; commit-to-publish crash gap is not automatically repaired; don't replay paid work blindly |
| Provider timeout / 429 / 502 | Inspect platform stop reason and ledger; retry safeguards count potentially billed attempts; do not assume refunds |
| Completed with few/no posts | Inspect dates, exclusions, query, comparison shares, source availability, and stop details before changing scope |
| Cancel requested but remote work continues | Cancellation is cooperative; a submitted SDK/server operation may continue billing; stored partial results remain |
| Stale running job | Keep scheduler and worker alive; reconciler uses progress age and inspection; default stale threshold is 900 seconds |
| Export missing after a restore | Restore the export volume along with PostgreSQL; a database row alone does not restore its file |

Never paste .env.development, bearer tokens, request headers, or unreviewed raw provider payloads into feedback. Share sanitized run ID/platform/stop codes and build information. Source queries and public text may still be sensitive research material.

## Migrations and backups

Migration 012 removes recruitment tables and merges project duplicates while retaining run memberships. It cannot be losslessly downgraded. Fresh SocialScope starts in its own database; do not point DATABASE_URL at SocialPulse. Before changing an existing database, finish or cancel active collections and wait for terminal status, record the application revision, and back up database and exports. Do not interrupt billable remote work merely to take a backup.

The following commands keep the binary PostgreSQL dump inside the container until `docker compose --env-file .env.development -f compose.development.yml cp`; this avoids Windows PowerShell corrupting a binary stdout redirect. Choose a new backup filename rather than overwriting an earlier backup.

```powershell
$backupDir = Join-Path $PWD ("backups/" + (Get-Date -Format 'yyyyMMdd-HHmmss'))
New-Item -ItemType Directory -Path $backupDir -ErrorAction Stop

# Stop on a failed native command; PowerShell does not do this automatically.
function Invoke-ComposeChecked {
    & docker compose --env-file .env.development -f compose.development.yml @args
    if ($LASTEXITCODE -ne 0) { throw "Docker Compose command failed; inspect its output." }
}

Invoke-ComposeChecked stop worker scheduler backend
try {
    Invoke-ComposeChecked exec -T postgres pg_dump -U socialscope_dev -d socialscope_dev -Fc -f /tmp/socialscope-backup.dump
    Invoke-ComposeChecked cp postgres:/tmp/socialscope-backup.dump "$backupDir/socialscope-backup.dump"
    Invoke-ComposeChecked run --rm --no-deps -v "${backupDir}:/backup" backend python -c "import tarfile; t=tarfile.open('/backup/socialscope-exports.tar.gz','w:gz'); t.add('/tmp/socialscope_exports',arcname='exports'); t.close()"
} finally {
    Invoke-ComposeChecked start backend worker scheduler
}
```

Also preserve .env.development privately/encrypted and note which build produced the backup. Do not commit backups. CSV exports alone omit users, usage records, and application state.

Restore rehearsal into a **new database** in this stack (use a fresh name if it exists):

```powershell
docker compose --env-file .env.development -f compose.development.yml exec -T postgres createdb -U socialscope_dev socialscope_restore_test
# Set this to the actual timestamped backup folder.
$restoreDir = Join-Path $PWD 'backups/REPLACE_WITH_BACKUP_TIMESTAMP'
docker compose --env-file .env.development -f compose.development.yml cp "$restoreDir/socialscope-backup.dump" postgres:/tmp/socialscope-restore.dump
docker compose --env-file .env.development -f compose.development.yml exec -T postgres pg_restore -U socialscope_dev -d socialscope_restore_test --no-owner /tmp/socialscope-restore.dump
docker compose --env-file .env.development -f compose.development.yml exec -T postgres psql -U socialscope_dev -d socialscope_restore_test -c "SELECT count(*) FROM projects; SELECT count(*) FROM run_posts; SELECT count(*) FROM provider_usage;"
```

Check each restore command succeeds before proceeding; do not create or overwrite a database that already contains useful work.

A full recovery should start a separately named Compose stack with distinct ports/volumes, restore PostgreSQL and exports there, and test login, memberships, usage totals, and downloads before switching users. Do not restore over a running pilot. Do not use `--clean` against an unverified target. Determine recovery-time/data-loss requirements before shared hosting.

## Native development

Docker is the recommended handoff path. For development, run PostgreSQL/Redis in Docker and the app on the host, or use the full Docker stack; do not start two servers on the same host port. See [native port configuration](docs/PORTS_AND_CONFIGURATION.md#native-development) for the exact environment settings.

A native backend needs Python 3.12, a virtual environment, and `backend/requirements.txt`. Run Alembic, seed, and Uvicorn from `backend/` so their relative configuration paths resolve. Supply a private `backend/.env` with your login/signing/provider settings and host-based database/Redis URLs; the root Compose .env.development uses container addresses and cannot be used unchanged. Uvicorn should listen on port 8102. Celery workers are best run in Linux/Docker; Windows worker behavior is not the deployment target.

For a native frontend, run `npm ci` from `frontend/`, set API_INTERNAL_URL before starting Next, then `npm run dev -- --port 3102`. Production rewrites are generated at build time, so set API_INTERNAL_URL before `npm run build` as well. Install this application's own dependencies; the temporary validation junction described in TESTING_GUIDE has been removed.

## Shared-account and hosting boundaries

The local row-locked ledger records provider usage for each pull without enforcing credit or per-pull request caps. Provider balances and billing remain external. Previews retain small operation limits. Process-local rate limits do not coordinate multiple workers. Host binding is loopback only. Before public/shared hosting, follow [ROADMAP](docs/ROADMAP.md): validate organization isolation, centralized secrets and account limits, distributed rate limits, TLS, monitoring, and tested recovery. Individual accounts are prepared; project grants are needed only if projects must be private within a team.

## Future multi-user pilot: accounts and admin oversight (2026-10-26)

This release prepares accounts and oversight; it does not add participants or change hosting. Back up the database before applying migrations. Migration **014** adds feedback, collection initiators, session versions, and activity indexes without deleting existing data. Deploy the matching API and worker code after applying it. A downgrade removes the new records/fields; restore a verified backup if rolling back requires retaining them.

The existing migration service applies `alembic upgrade head` at deployment. This implementation has not applied migrations to your live database. Use the established deployment procedure when ready; no deployment is part of this change.

### Initial administrator

Setup generates credentials in private `.env.development`. Seed creates the configured account only if missing and preserves existing account details on reruns. Changing `LOCAL_ADMIN_PASSWORD` no longer changes an existing password. New seed accounts require a password of at least 12 characters and at most 72 UTF-8 bytes; the setup-generated password meets this rule. Existing accounts are not forced to change their passwords.

For explicit provisioning, run from the backend directory in a configured operator environment:

```bash
python -m app.manage_users bootstrap
```

Or, for an already running configured container:

```bash
docker compose --env-file .env.development -f compose.development.yml exec backend python -m app.manage_users bootstrap
```

The command prompts for email, organization slug/name, administrator name, and a hidden password with confirmation. No password goes in the command line. An existing email is left unchanged, including a member or disabled account; this is not a promotion/reactivation command. Do not run it just to validate the installation.

### Add members later

1. Log in with your individual admin account and open **Admin ? Users**.
2. Create a member with their name, email, and a unique password. Share credentials privately through an encrypted channel. No invitation is sent.
3. Members are assigned to the admin's organization by the server, but projects are private to each user. Organization membership does not grant project access. Admins retain organization-wide activity/feedback oversight; normal research screens show their own projects plus unassigned legacy/retained projects.
4. Click a person's email, or select them in the activity filter, to inspect their recorded actions. The filter offers the current Users page; navigate Users pages to find another person.
5. Disable access when required. Disabling revokes existing tokens; re-enabling requires a fresh login. The final active admin is protected, including concurrent changes serialized by an organization row lock on PostgreSQL.

### Password reset

Run `python -m app.manage_users reset-password` in the backend directory, or:

```bash
docker compose --env-file .env.development -f compose.development.yml exec backend python -m app.manage_users reset-password
```

Enter the email and hidden new password twice. Previous tokens are invalidated. Account role and active status stay unchanged. There is no email recovery or password in arguments, output, or application activity records.

### Activity and feedback

The admin workspace has Activity, Users, and Feedback & issues views. Use **Create user** in Users to open the compact account form; closing it clears the entered password. Click a user's email to open their activity. **Refresh records** reloads the current pages/filters without a full page reload and shows the last successful update time. Provider status is collapsed above the workspace and has a separate **Refresh connections** control.

To remove old activity, choose a person (or All users / System), select an age of 30, 90, 180, or 365 days, and click **Review cleanup**. The server previews the count for this organization and the exact cutoff. Confirm the permanent deletion in the dialog. This removes matching activity across all pages, not only the visible page. Research projects, collected data, users, and feedback are retained. A new activity entry records the administrator, cutoff, optional user filter, and actual deletion count in the same transaction; if that audit entry fails, the deletion rolls back. Counts can change between preview and confirmation. This is manual cleanup, not automatic retention. Keep any required activity backup before deleting.

Activity includes logins, account changes, project creation/deletion, collection submission and terminal outcomes, post exclusion/restoration, CSV generation, and export download requests. It records meaningful actions, not every page view or proof of online presence. Download requests are not proof of completed file transfer. Legacy collection initiators remain System / Unknown; they are not reconstructed by guessing. New background outcomes retain the submitting person's identity. Project deletion preserves activity labels and history. Previously deleted history cannot be recovered by this change.

Reports use **Feedback / Report an issue** in the sidebar. Admins see their organization's submissions under **Feedback & issues** and can toggle **Reviewed**. Refresh reloads the records; lists are paginated. No attachments, email notifications, comments, or public issue tracker are included.

### Troubleshooting and remaining hosting blockers

- A missing-table/column error after updating code usually indicates migration 014 has not been applied.
- A 403 on admin routes means the account is not an active administrator; members cannot grant themselves access.
- A 409 when disabling the final active admin is intentional. Provision a second authorized admin through the operator process if needed.
- A reset or disable invalidates tokens; sign in again after access is restored.
- A failed feedback request retains its message in the form. Do not retry after a confirmed success.
- Shared VM exposure still needs encrypted access, production configuration, backups/restores, monitoring, provider-account rate coordination, and live multi-user validation. None was changed or certified here.

## Private projects, account deletion, and pasted errors ? 2026-10-27

### Migration 015 and existing projects

Back up the database and apply migration **015** with the matching application release before using these changes. No migration or deployment was performed by this implementation. The migration adds nullable `projects.owner_user_id` and `feedback.error_details`.

For existing projects, ownership is backfilled only when a single valid same-organization creator can be identified from `project_created` activity. Ambiguous/missing creators remain unassigned and visible only to organization admins. No project data is erased. New projects always belong to the authenticated creator. Project routes and all child job/post/analytics/export routes check ownership; changing a URL cannot access a coworker's project. Both dashboard KPIs and project lists use the same visibility rule.

Do not downgrade this migration as a casual rollback: removing ownership with older code restores organization-wide project sharing. Review access and restore a verified backup as appropriate before any rollback.

### Delete a member account

Use **Admin ? Users ? Delete** and review the confirmation. No admin account can be deleted through this endpoint, including when multiple admins exist. Members cannot delete accounts. A member with queued/running/cancelling collections must finish those jobs first; the endpoint returns 409 otherwise.

Deletion removes the account and invalidates its tokens because the user no longer exists. Research projects, exports, activity, and feedback are retained. Project ownership becomes unassigned (administrator-only); activity and feedback keep identity snapshots while their user references are cleared. Recreating the same email creates a new identity with an empty project list. Deletion is not a research-data erasure action. The existing project delete operation remains separate.

### Password visibility and feedback

The account form's eye button affects only the password currently being typed; stored passwords cannot be retrieved. New passwords start hidden, and successful creation hides/clears the field.

Feedback opens from the sidebar above the page, including on mobile. Its optional **Error details** field preserves pasted line breaks and indentation (maximum 20,000 characters). The message remains required. Both fields survive a failed submission. Reports stay private to same-organization admins and show the exact pasted error in a scrollable text block. Ask reporters to remove secrets before submitting; the application does not automatically collect console logs or error responses.

## Production deployment controls - 2026-11-17

Runtime services and seed explicitly use `ENV=production`. Startup rejects placeholder/short signing secrets and non-HTTPS, wildcard, placeholder, or path-bearing CORS origins. Supply a unique random signing secret of at least 32 characters and the exact HTTPS origin without a trailing slash. The maintenance migration command receives only its database URL and does not start the authenticated runtime. Development explicitly uses `ENV=development`.

Frontend images now use Node 22, Next.js 16, and React 19. Rebuild both frontend and backend images for this release; do not copy new source into an old image. JWT handling uses PyJWT with the same HS256 token format, signing key, expiration, and session-version checks. Keep the signing key/algorithm stable to preserve valid existing sessions; rotating the key deliberately invalidates them. Runtime Python dependencies are in `backend/requirements.txt`; local test tools are in `backend/requirements-dev.txt` and are excluded from the backend image.

For an existing development frontend dependency volume, rebuild its development image, stop frontend, run `docker compose --env-file .env.development -f compose.development.yml run --rm --no-deps frontend npm ci`, then start frontend again. This refreshes the existing node_modules volume for the new Next/React versions without deleting application data. Local frontend commands require Node 22.12 or newer; the Docker images use Node 22.

Use standalone [compose.production.yml](compose.production.yml) with private configuration copied from [.env.production.example](.env.production.example). Always supply both production flags. Development remains a separate checkout/project with independent storage. DNS, Nginx, Certbot, private configuration, and target-host acceptance remain operator steps.

### Controls and limits

Only the frontend publishes a loopback port (3002). Runtime services receive an explicit settings allowlist and a restricted database URL. Only migrate receives the maintenance database URL; only opt-in seed receives initial administrator credentials. There is no whole-file environment injection. Docker image contexts exclude environment files.

API/worker/frontend limits are 768 MiB and 0.5 CPU each; PostgreSQL is 512 MiB/0.5 CPU, Redis 256 MiB/0.25 CPU, scheduler 256 MiB/0.25 CPU. Migration/seed inherit 768 MiB/0.5 CPU. These are ceilings, not reservations or proven capacity; builds are not limited by these settings. Budget capacity across all three apps on the VM.

Redis uses AOF and a 192 MiB noeviction ceiling: full Redis rejects writes rather than silently evicting queued jobs. Monitor memory and queue failures. The collection worker is fixed to one process because provider limits are process-local; other apps using the same provider account still share external quotas. The worker has a two-minute shutdown grace period. Scheduler state persists in its own volume, initialized with the non-root image user's permissions. Existing incorrectly owned volumes require explicit operator repair.

Every long-running service has a health check. Worker checks its own Celery node; scheduler checks its PID (not proof tasks are delivered). Restart policies restart exited processes, not merely unhealthy containers. Logs remain bounded. Monitor externally and test backup/restore.

### New empty installation or previous PostgreSQL container

Starting empty is supported. Inspect the previous SocialScope container's Compose labels and mounts on the VM first. Stop the old SocialScope stack before starting this one: never run two PostgreSQL servers against one data volume. Removing a container does not reset its database volume.

For an empty installation, choose new, unused SocialScope volume names in private configuration and explicitly create those three external volumes. This leaves old storage available until the new deployment is verified. Alternatively, reuse verified SocialScope PostgreSQL 16 storage with its actual credentials; existing accounts/schema remain. POSTGRES_PASSWORD does not reset an initialized database password. Do not reuse SocialPulse/LitIQ volumes, remove their containers, or run global prune commands. No container/volume removal is performed by these source changes.

### First deployment on the Linux VM

Run from this checkout. Privately complete configuration first. POSTGRES_USER/POSTGRES_DB must be socialscope for the guarded role setup below. Generate independent maintenance, runtime, signing, and administrator secrets. POSTGRES_URL_PASSWORD is the URL-encoded maintenance password; APP_DB_URL_PASSWORD encodes the separate runtime password. Remove the obsolete DATABASE_URL entry from any older production configuration.

Create the three chosen external volumes deliberately before startup. Then:

```bash
docker compose --env-file .env.production -f compose.production.yml config --quiet
docker compose --env-file .env.production -f compose.production.yml build backend frontend
docker compose --env-file .env.production -f compose.production.yml up -d --wait postgres redis
docker compose --env-file .env.production -f compose.production.yml --profile maintenance run --rm migrate
```

Do not print full resolved configuration: it contains secrets. Stop if migration fails. The role script requires revision 015 and tables owned by the maintenance user; future releases must use their verified revision.

```bash
docker compose --env-file .env.production -f compose.production.yml exec -T postgres psql -X -U socialscope -d socialscope -v ON_ERROR_STOP=1 -v database_name=socialscope -v maintenance_role=socialscope -v app_role=socialscope_app -v expected_revision=015 < deploy/postgres/prepare-application-role.sql
docker compose --env-file .env.production -f compose.production.yml exec postgres psql -X -U socialscope -d socialscope
```

In interactive psql, run the following and enter the runtime password at the hidden prompts. Then exit with backslash-q.

```text
SET password_encryption = 'scram-sha-256';
\password socialscope_app
```

The transactional role script refuses an existing role, unexpected database, schema head, or ownership. Never drop an existing role to retry; inspect and resume at the appropriate step. It grants table DML and sequence use, removes PUBLIC schema CREATE, denies Alembic revision writes, and prepares future grants for objects created by the maintenance user. It does not change ownership. Runtime cannot administer roles/databases. The maintenance user remains privileged; this is runtime credential separation.

Verify a real runtime login over TCP with a hidden password prompt:

```bash
docker compose --env-file .env.production -f compose.production.yml exec postgres psql -X -h 127.0.0.1 -U socialscope_app -d socialscope -W
```

Paste [verify-application-role.sql](deploy/postgres/verify-application-role.sql), preceded by these psql variables:

```text
\set database_name socialscope
\set app_role socialscope_app
```

All checks must pass. DML probes match zero rows and roll back. Then provision the initial admin and start runtime:

```bash
docker compose --env-file .env.production -f compose.production.yml --profile bootstrap run --rm seed
docker compose --env-file .env.production -f compose.production.yml up -d --wait backend worker scheduler frontend
docker compose --env-file .env.production -f compose.production.yml ps --all
```

Seed preserves existing accounts; it does not reset passwords. Confirm dependency health, login, two-user project isolation, mocked-provider worker delivery, CSV downloads, feedback/admin flows, and restart behavior before inviting users. Configure DNS/Nginx/Certbot for the exact public origin and verify HTTPS. Test backup restoration separately. Health checks alone do not establish production readiness.

### Later releases

Finish active collections, back up and verify storage, build uniquely tagged images, and stop backend/worker/scheduler/frontend before explicit maintenance migrations. Run migrations as the same object owner so default runtime grants apply. Verify schema/permissions before recreating runtime with the matching release. Seed and role creation are first-install steps, not routine startup steps. Never use down -v to update. Retain prior images and a verified backup; a schema change may require restoration rather than only an image rollback.

## Development / production naming and isolation - 2026-11-02

| Environment | Compose | Private configuration | Project | Default web |
|---|---|---|---|---|
| Development | `compose.development.yml` | `.env.development` | `socialscope-dev` | `127.0.0.1:3102` |
| Production | `compose.production.yml` | `.env.production` | `socialscope` | `127.0.0.1:3002` behind the future HTTPS proxy |

The old `docker-compose.yml` and `.env.example` have been renamed, not kept as duplicate aliases. All Compose commands must explicitly select the environment file and Compose file. Bare `docker compose up` is no longer the documented startup command. The production Compose file, production example, production Dockerfiles, and application/authentication/provider logic were not changed.

### Existing development configuration and data

Existing private `.env`, containers, and volumes are untouched. Do not blindly rename the old private `.env` into `.env.development`: its old ports and credentials are not the isolated development defaults. `python scripts/setup.py` creates the new private file with generated development secrets and blank provider keys. If it already exists, setup leaves it unchanged. Copy only deliberate non-secret tuning values and authorized provider keys after review.

The renamed stack intentionally selects **new** project-scoped volumes (`socialscope-dev_postgres_data`, `socialscope-dev_redis_data`, and `socialscope-dev_export_data`). Old `socialscope_*` data has not disappeared and has not been migrated. Never point development at production external volumes or a production database URL. If old test data must be retained, plan a sanitized backup/restore into development explicitly. Do not start an old checkout's default Compose on the VM: it uses the production project name. Do not override the development project name with `-p socialscope` or a conflicting `COMPOSE_PROJECT_NAME`.

Development uses database/user `socialscope_dev` and a generated `SOCIALSCOPE_DEV_DB_PASSWORD`. Compose constructs the internal DATABASE_URL; it also fixes REDIS_URL, BUILD_ID, origins, and one collection worker process. This prevents an old DATABASE_URL entry from selecting production. The development frontend forces same-origin browser API calls, overriding an old frontend `.env.local` API URL.

### Everyday development on the VM

Use a separate checkout such as `/opt/socialscope-dev` for feature branches and `/opt/socialscope-prod` for the deployed release. Source mounts refer to the folder containing the selected Compose file. Do not edit the production checkout to develop.

```bash
python3 scripts/setup.py
# Review .env.development privately. Initial image/dependency builds run on the VM:
docker compose --env-file .env.development -f compose.development.yml up --build -d
python3 scripts/check-connectivity.py
```

Forward VM loopback port 3102 through VS Code Remote SSH and open its forwarded address. No public development firewall port is needed. API/PostgreSQL/Redis also bind only to loopback (8102/5534/6481); forward those only when needed. Another process can occupy these ports; verify on the target VM and change only development port settings if necessary.

The frontend uses `frontend/Dockerfile.development` and runs Next's development server. Its dependencies and `.next` cache live in separate development-only volumes. UI source edits refresh without a production build. The API reloads on backend source edits. Celery workers/scheduler do not automatically reload imported task code; after active development collections finish, restart those two development services with the same explicit flags.

If frontend package dependencies change, stop the development frontend, rebuild its development image as needed, and update the development dependency volume using:

```bash
docker compose --env-file .env.development -f compose.development.yml run --rm --no-deps frontend npm ci
docker compose --env-file .env.development -f compose.development.yml up -d frontend
```

Do not delete all volumes to refresh dependencies. Backend requirement changes require rebuilding the affected development Python images. No such build/install was run while preparing this change.

Development containers have conservative memory/CPU limits and bounded logs. Limits apply to running containers, **not** image builds; they do not reserve production capacity. Keep builds and live collection tests out of busy production periods. Development is not automatically restarted on VM reboot; start it only when needed and stop it to release resources. Provider keys are blank by default; real keys can spend credits and share provider-account limits even with isolated databases.

```bash
docker compose --env-file .env.development -f compose.development.yml stop
```

No private configuration, accounts, volumes, databases, running containers, or VM state was changed by this file rename. Existing raw native Python workflows may still use `backend/.env` via the unchanged settings loader; that legacy native path is not consumed by the development Compose file.
