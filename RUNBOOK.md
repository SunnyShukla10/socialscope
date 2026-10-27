# SocialScope local operations

Run commands from the destination `socialscope` directory. Do not run them against SocialPulse. The Compose project is `socialscope`; default host ports are 3002 web, 8002 API, 5434 PostgreSQL, 6381 Redis, all bound to 127.0.0.1. Internal ports remain 3001/8001/5432/6379. Change SOCIALSCOPE_*_PORT in .env for host conflicts; internal DATABASE_URL/REDIS_URL remain service addresses. The [port and configuration guide](docs/PORTS_AND_CONFIGURATION.md) lists every service, alternate-port examples, verification commands, and native-development differences.

## Configuration and lifecycle

```powershell
python scripts/setup.py
# Privately edit .env and add shared provider keys.
docker compose up --build -d
docker compose ps --all
docker compose logs --tail 50 migrate seed
python scripts/check-connectivity.py
```

Services: postgres, redis, migrate (one-shot), seed (one-shot), backend, worker, scheduler, frontend. Migrate runs `alembic upgrade head`; seed creates the local organization/admin. Backend and worker use Python 3.12; frontend uses a Next production standalone image. Export files live in the shared backend export volume. Redis uses AOF persistence.

`migrate` and `seed` should finish with exit code 0; an exited one-shot service is normal. Wait for seed before login. The frontend does not explicitly wait for seed, so a reachable login page alone does not establish that the account exists.

Check dependency health as well as HTTP reachability (substitute your API port if changed):

```powershell
Invoke-RestMethod http://127.0.0.1:8002/api/health
```

Expected fields are `status: ok`, `database: true`, and `redis: true`. The current endpoint returns HTTP 200 even when status is `degraded`. Both the connectivity script and backend container health probe can therefore pass while a dependency is unavailable; inspect the response fields and worker logs before accepting the installation. None of these checks contacts a social provider.

Dashboard displays configured-source booleans and version/build. API root reports service version; `/api/sources` includes BUILD_ID. Seed uses LOCAL_ADMIN_EMAIL/PASSWORD; re-running it preserves existing account details. Use the interactive operator tool for password resets. Provider keys stay server-side.

```powershell
docker compose logs --tail 100 migrate seed backend worker scheduler
docker compose restart backend worker scheduler
docker compose down
```

`restart` restarts existing containers with their existing environment and port mappings. After editing .env, use `docker compose up -d --force-recreate` for affected services; see the [port guide](docs/PORTS_AND_CONFIGURATION.md). Schedule recreation after active collections finish.

`down` keeps named volumes. **Do not use `down -v` unless deliberately deleting this application's data.** Do not run global Docker prune/reset commands to repair SocialScope. Avoid multiple collection workers: provider rate controls are process-local until the roadmap's distributed controls exist.

## Troubleshooting

| Symptom | Checks and action |
|---|---|
| Docker engine error / 500 / not reachable | Start Docker Desktop in Linux-container mode; check free disk and engine health before retrying this stack |
| Build runs out of space | Free several GB outside source/application data; retry a clean build; do not delete databases or shared Docker storage |
| Login fails | Wait for seed to finish; inspect seed logs; use the private .env login values; verify web/API proxy connectivity |
| New password in .env has no effect | Expected for existing accounts. Use `docker compose exec backend python -m app.manage_users reset-password`; seed does not reset passwords |
| 401 during work | Sign in again; SocialScope uses its own browser token key |
| Missing source key | Edit .env privately, then recreate backend/worker/scheduler with `docker compose up -d --force-recreate backend worker scheduler` |
| Queued run stays queued | Check Redis and worker logs/queue subscription; commit-to-publish crash gap is not automatically repaired; don't replay paid work blindly |
| Provider timeout / 429 / 502 | Inspect platform stop reason and ledger; retry safeguards count potentially billed attempts; do not assume refunds |
| Completed with few/no posts | Inspect dates, exclusions, query, comparison shares, source availability, and stop details before changing scope |
| Cancel requested but remote work continues | Cancellation is cooperative; a submitted SDK/server operation may continue billing; stored partial results remain |
| Stale running job | Keep scheduler and worker alive; reconciler uses progress age and inspection; default stale threshold is 900 seconds |
| Export missing after a restore | Restore the export volume along with PostgreSQL; a database row alone does not restore its file |

Never paste .env, bearer tokens, request headers, or unreviewed raw provider payloads into feedback. Share sanitized run ID/platform/stop codes and build information. Source queries and public text may still be sensitive research material.

## Migrations and backups

Migration 012 removes recruitment tables and merges project duplicates while retaining run memberships. It cannot be losslessly downgraded. Fresh SocialScope starts in its own database; do not point DATABASE_URL at SocialPulse. Before changing an existing database, finish or cancel active collections and wait for terminal status, record the application revision, and back up database and exports. Do not interrupt billable remote work merely to take a backup.

The following commands keep the binary PostgreSQL dump inside the container until `docker compose cp`; this avoids Windows PowerShell corrupting a binary stdout redirect. Choose a new backup filename rather than overwriting an earlier backup.

```powershell
$backupDir = Join-Path $PWD ("backups/" + (Get-Date -Format 'yyyyMMdd-HHmmss'))
New-Item -ItemType Directory -Path $backupDir -ErrorAction Stop

# Stop on a failed native command; PowerShell does not do this automatically.
function Invoke-ComposeChecked {
    & docker compose @args
    if ($LASTEXITCODE -ne 0) { throw "Docker Compose command failed; inspect its output." }
}

Invoke-ComposeChecked stop worker scheduler backend
try {
    Invoke-ComposeChecked exec -T postgres pg_dump -U socialscope -d socialscope -Fc -f /tmp/socialscope-backup.dump
    Invoke-ComposeChecked cp postgres:/tmp/socialscope-backup.dump "$backupDir/socialscope-backup.dump"
    Invoke-ComposeChecked run --rm --no-deps -v "${backupDir}:/backup" backend python -c "import tarfile; t=tarfile.open('/backup/socialscope-exports.tar.gz','w:gz'); t.add('/tmp/socialscope_exports',arcname='exports'); t.close()"
} finally {
    Invoke-ComposeChecked start backend worker scheduler
}
```

Also preserve .env privately/encrypted and note which build produced the backup. Do not commit backups. CSV exports alone omit users, usage records, and application state.

Restore rehearsal into a **new database** in this stack (use a fresh name if it exists):

```powershell
docker compose exec -T postgres createdb -U socialscope socialscope_restore_test
# Set this to the actual timestamped backup folder.
$restoreDir = Join-Path $PWD 'backups/REPLACE_WITH_BACKUP_TIMESTAMP'
docker compose cp "$restoreDir/socialscope-backup.dump" postgres:/tmp/socialscope-restore.dump
docker compose exec -T postgres pg_restore -U socialscope -d socialscope_restore_test --no-owner /tmp/socialscope-restore.dump
docker compose exec -T postgres psql -U socialscope -d socialscope_restore_test -c "SELECT count(*) FROM projects; SELECT count(*) FROM run_posts; SELECT count(*) FROM provider_usage;"
```

Check each restore command succeeds before proceeding; do not create or overwrite a database that already contains useful work.

A full recovery should start a separately named Compose stack with distinct ports/volumes, restore PostgreSQL and exports there, and test login, memberships, usage totals, and downloads before switching users. Do not restore over a running pilot. Do not use `--clean` against an unverified target. Determine recovery-time/data-loss requirements before shared hosting.

## Native development

Docker is the recommended handoff path. For development, run PostgreSQL/Redis in Docker and the app on the host, or use the full Docker stack; do not start two servers on the same host port. See [native port configuration](docs/PORTS_AND_CONFIGURATION.md#native-development) for the exact environment settings.

A native backend needs Python 3.12, a virtual environment, and `backend/requirements.txt`. Run Alembic, seed, and Uvicorn from `backend/` so their relative configuration paths resolve. Supply a private `backend/.env` with your login/signing/provider settings and host-based database/Redis URLs; the root Compose .env uses container addresses and cannot be used unchanged. Uvicorn should listen on port 8002. Celery workers are best run in Linux/Docker; Windows worker behavior is not the deployment target.

For a native frontend, run `npm ci` from `frontend/`, set API_INTERNAL_URL before starting Next, then `npm run dev -- --port 3002`. Production rewrites are generated at build time, so set API_INTERNAL_URL before `npm run build` as well. Install this application's own dependencies; the temporary validation junction described in TESTING_GUIDE has been removed.

## Shared-account and hosting boundaries

The local row-locked ledger records provider usage for each pull without enforcing credit or per-pull request caps. Provider balances and billing remain external. Previews retain small operation limits. Process-local rate limits do not coordinate multiple workers. Host binding is loopback only. Before public/shared hosting, follow [ROADMAP](docs/ROADMAP.md): validate organization isolation, centralized secrets and account limits, distributed rate limits, TLS, monitoring, and tested recovery. Individual accounts are prepared; project grants are needed only if projects must be private within a team.

## Future multi-user pilot: accounts and admin oversight (2026-10-26)

This release prepares accounts and oversight; it does not add participants or change hosting. Back up the database before applying migrations. Migration **014** adds feedback, collection initiators, session versions, and activity indexes without deleting existing data. Deploy the matching API and worker code after applying it. A downgrade removes the new records/fields; restore a verified backup if rolling back requires retaining them.

The existing migration service applies `alembic upgrade head` at deployment. This implementation has not applied migrations to your live database. Use the established deployment procedure when ready; no deployment is part of this change.

### Initial administrator

Setup generates credentials in private `.env`. Seed creates the configured account only if missing and preserves existing account details on reruns. Changing `LOCAL_ADMIN_PASSWORD` no longer changes an existing password. New seed accounts require a password of at least 12 characters and at most 72 UTF-8 bytes; the setup-generated password meets this rule. Existing accounts are not forced to change their passwords.

For explicit provisioning, run from the backend directory in a configured operator environment:

```bash
python -m app.manage_users bootstrap
```

Or, for an already running configured container:

```bash
docker compose exec backend python -m app.manage_users bootstrap
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
docker compose exec backend python -m app.manage_users reset-password
```

Enter the email and hidden new password twice. Previous tokens are invalidated. Account role and active status stay unchanged. There is no email recovery or password in arguments, output, or application activity records.

### Activity and feedback

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
