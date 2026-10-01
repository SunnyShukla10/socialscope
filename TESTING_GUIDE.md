# SocialScope tests and validation

## Recorded implementation validation (September 28-29, 2026)

This is the original implementation record, not a new test run on the recipient's machine. Documentation was reviewed against the code and Compose configuration on September 30, 2026. The documentation review did not rerun application tests or establish that the earlier Docker/disk issues still occur. It did verify the current and example alternate Compose port mappings/CORS, local documentation links, and PowerShell syntax for the command examples without executing those examples.

- Backend: **174 passed, 1 skipped**. The skipped test requires a real disposable PostgreSQL database for concurrent reservations. Sixteen dependency/deprecation warnings remain; no live provider calls are part of this suite.
- Frontend: **21 tests passed** covering query safeguards, progress, refresh decisions, cancellation, and session recovery.
- TypeScript: `tsc --noEmit --incremental false` passed after final UI changes.
- Next production compilation/type validation/page generation: passed after the final login/recruitment cleanup using the low-disk validation configuration. This skips standalone-output duplication; the normal Docker configuration still produces standalone output. Docker image packaging was not verified here.
- Production HTTP smoke: `/login`, `/projects/new`, and a Collections route returned 200 with SocialScope branding on an isolated local test port. This is not an authenticated browser/end-to-end provider workflow test.
- Alembic: all revisions 001-012 generated PostgreSQL SQL successfully. Actual application of migrations to PostgreSQL is **not yet verified**.
- Compose: configuration validation passed. Docker Desktop's engine returned 500 errors during the original validation, so clean-stack startup, database integration, and worker/broker integration remain unverified.
- Original SocialPulse: all **192 source-manifest files** retain their original SHA256 hashes. The destination's pre-existing `.git` was preserved.
- No live historical search or paid benchmark was run. Historical completeness, large-pull yield, and account-specific billing remain unverified.

The C: drive filled during an independent frontend dependency install. The interrupted destination dependency directory was removed, and validation temporarily read the source installation's existing dependencies through a junction. Source code was not changed; no package install was run through the junction. The temporary junction was removed before handoff. Install SocialScope's own dependencies with `npm ci` on a machine with sufficient free space, or use its Docker build. Fresh build directories avoided OneDrive stalls while cleaning interrupted artifacts.

## Standard offline checks

From the repository root, create a Python 3.12 virtual environment (Windows PowerShell):

```powershell
py -3.12 -m venv backend/.venv
```

Then install and run from `backend/` using that interpreter directly; activation is not required:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m alembic upgrade head --sql
```

The SQL command generates a migration script; it does not execute database changes. Normal tests use isolated SQLite fixtures and mocked providers. SQLite compilation of PostgreSQL types is a testing convenience, not evidence for row-lock behavior. During that constrained validation only, extra validation packages were placed under ignored `backend/.test-deps`; `$env:PYTHONPATH='.test-deps;.'` made them available without modifying global dependencies.

In a separate terminal, from the repository root, use Node.js 20 (matching the Dockerfile) and npm:

```powershell
cd frontend
npm ci
npm test
npx tsc --noEmit --incremental false
npm run build
```

For constrained build-only validation, SOCIALSCOPE_CHECK_BUILD=1 disables standalone duplication and webpack cache; SOCIALSCOPE_CHECK_DIR may select a fresh `.next-validation-*` directory when OneDrive stalls cleaning an old build. These are validation conveniences, not the production Docker mode. The Docker frontend builds with `npm ci` and `npm run build`, then serves standalone output as a non-root user.

## Required PostgreSQL check

Run the following Compose command from the repository root. Use an isolated database named **socialscope_test**. Never point this test or migrations at SocialPulse. Once this stack's PostgreSQL is healthy, create a dedicated test database (choose deliberately; do not overwrite an existing database):

```powershell
docker compose exec -T postgres createdb -U socialscope socialscope_test
```

From backend with dependencies installed:

```powershell
$env:TEST_DATABASE_URL='postgresql+asyncpg://socialscope:socialscope@127.0.0.1:5434/socialscope_test'
.\.venv\Scripts\python.exe -m pytest -q tests/test_research_workflow.py -k real_postgres
Remove-Item Env:TEST_DATABASE_URL
```

The URL above assumes PostgreSQL host port 5434; replace it if configured differently. See [Ports and configuration](docs/PORTS_AND_CONFIGURATION.md).

The test requires the exact disposable database name, creates a unique temporary schema, executes 36 competing requests, expects only eight reservations to succeed, and removes only its owned schema. It uses ORM metadata; separately run the actual migration chain against a fresh SocialScope database and verify `docker compose run --rm --no-deps migrate alembic current` reports 012 (run from the repository root). Exercise a clean `docker compose up --build -d` afterward. A passing PostgreSQL test verifies transaction behavior, not vendor billing behavior.

## Coverage and why it matters

| Area | Meaningful checks |
|---|---|
| Existing adapters | Endpoint/SDK arguments, parsing, timestamps, optional dates, exact boundaries, paging/cursor guards, malformed/duplicate rows |
| Spending | Shared comparison allocation/cap, preview/full accounting, retries, unknown timeouts, unapproved endpoints, reported-cost changes |
| Cache | Same-pull/configuration response reuse without new reservation |
| Data model | Project deduplication, multiple run memberships, idempotent inserts, cross-project ownership, pull-wide post ceiling |
| Lifecycle | Queued/running/terminal behavior, cancellation, completed/partial preservation, abandoned-run reconciliation |
| Results | Reversible exclusion, scope filtering, active-run project deletion rejection |
| Export | CSV escaping/Unicode, formula safety, scope and run/query provenance |
| Benchmark | Twelve unapproved plan cells; offline duplicate/date/relevance handling |
| Frontend | Existing query/progress/cancellation/session helpers and type contracts |

Provider fixtures do not confirm current remote endpoints or yields. The frontend helper tests are not comprehensive UI interaction tests. The PostgreSQL concurrency check is deliberately skipped without an explicit test URL. Crash-after-charge recovery is conservative but not lossless; the code does not implement per-page durable resume or a transactional outbox.

## Supervised pilot smoke checklist

With sufficient free disk space and a healthy Docker engine, start the independent stack and sign in using private setup credentials. Without spending, create a project, inspect source configuration, verify persistent tabs, and check empty Results/Analytics/Export states. Test invalid target 5001 and comparison budget 9 through the API: both should fail with HTTP 422.

Only when a researcher deliberately starts approved ordinary pilot collection, use a small target/allowance. Confirm preview history, dates, examples, unchanged-preview reuse, revisions retaining pull ID, full collection retaining usage, cancellation, run filtering, deduplication, exclude/restore, included analytics, and CSV context. Compare ledger summaries with vendor records where available. Do not treat this checklist as permission for the separate live historical benchmark.

Capture feedback with [docs/FEEDBACK.md](docs/FEEDBACK.md). The historical benchmark remains proposal-only; [docs/COLLECTION_FEASIBILITY.md](docs/COLLECTION_FEASIBILITY.md) explains what additional approval and evidence are needed.
