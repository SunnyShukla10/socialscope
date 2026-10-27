# Docker ports and configuration

Reviewed against `docker-compose.yml`, `.env.example`, the Dockerfiles, and `frontend/next.config.js` on September 30, 2026. These are the configured defaults, not evidence that containers are currently running. Run commands from the `socialscope` repository root unless a different directory is stated.

## Every service and its ports

A **host port** is the port on your computer. A **container port** is where a service listens inside Docker. For example, `127.0.0.1:3002:3001` forwards your computer's port 3002 to the frontend container's port 3001.

| Compose service | Role | Default host port | Container port | Address from another container | Host-port setting in root .env |
|---|---|---:|---:|---|---|
| `frontend` | Next.js web application | 3002 | 3001 | `http://frontend:3001` | `SOCIALSCOPE_WEB_PORT` |
| `backend` | FastAPI HTTP API | 8002 | 8001 | `http://backend:8001` | `SOCIALSCOPE_API_PORT` |
| `redis` | Celery broker and result backend | 6381 | 6379 | `redis://redis:6379/0` | `SOCIALSCOPE_REDIS_PORT` |
| `postgres` | PostgreSQL database | 5434 | 5432 | `postgres:5432` | `SOCIALSCOPE_POSTGRES_PORT` |
| `worker` | Celery collection tasks | None | No listening service port | Connects to Redis/PostgreSQL and provider APIs | None |
| `scheduler` | Celery beat, schedules reconciliation | None | No listening service port | Connects to Redis to enqueue tasks | None |
| `migrate` | One-shot Alembic migration | None | No listening service port | Connects to PostgreSQL | None |
| `seed` | One-shot local account setup | None | No listening service port | Connects to PostgreSQL | None |

Docker itself has no additional SocialScope application port. Docker Desktop/Engine manages these containers; this Compose file does not publish a Docker Engine API port. External provider HTTPS connections are outbound traffic, not additional local ports to open.

All four published services bind to **127.0.0.1**, so they are accessible from the host computer, not directly from other computers on the network. In-container `0.0.0.0` bindings do not change that host restriction. Redis and PostgreSQL are not websites; use their clients rather than a browser.

Default host addresses:

- Web: http://localhost:3002
- API reference: http://localhost:8002/api/docs
- Dependency health: http://localhost:8002/api/health
- PostgreSQL client: host `127.0.0.1`, port `5434`, database/user `socialscope` (the Compose file sets the local password to `socialscope`).
- Redis client: host `127.0.0.1`, port `6381`, database `0` (no Redis password is configured for this loopback-only pilot).

The browser normally requests `/api` on the frontend's origin. Next forwards that request to `http://backend:8001` through Docker's service network. A frontend host-port change therefore does not require changing the internal API URL.

## Change host ports

Finish or cancel active collections and wait for them to reach terminal status before recreating services. In the repository root's private `.env`, edit the existing four settings. For example:

```dotenv
SOCIALSCOPE_WEB_PORT=3102
SOCIALSCOPE_API_PORT=8102
SOCIALSCOPE_POSTGRES_PORT=5534
SOCIALSCOPE_REDIS_PORT=6481
```

Choose unused ports and keep just one definition of each variable. Keep the container connection strings unchanged:

```dotenv
DATABASE_URL=postgresql+asyncpg://socialscope:socialscope@postgres:5432/socialscope
REDIS_URL=redis://redis:6379/0
```

Do not replace their internal ports with 5534/6481 for the Docker deployment. Those new ports are only for host clients. The internal frontend proxy remains `http://backend:8001`.

From the repository root:

```powershell
docker compose config --quiet
docker compose up -d --force-recreate
```

This recreates the stack's containers with the new mappings and preserves its named volumes. It also reruns the one-shot migration/seed services; seed creates a missing account only and preserves existing account details. Use the interactive operator tool in RUNBOOK.md for password resets. `docker compose restart` alone does not apply changed environment values or published ports. Port-only changes do not require rebuilding images; a first installation still uses `docker compose up --build -d`.

The Compose backend CORS setting is calculated from SOCIALSCOPE_WEB_PORT for both localhost and 127.0.0.1. You do not need to manually change CORS_ORIGINS for a Docker host-port-only change. The explicit Compose value takes precedence over the backend's env_file value.

With the example settings, use http://localhost:3102 and http://localhost:8102/api/docs. Host database clients and TEST_DATABASE_URL must use 5534; host Redis clients must use 6481. Existing browser bookmarks need updating, and changing the web port creates a different browser origin, so sign in again. The setup helper prints default 3002 even when an existing .env uses another port; rely on the resolved mapping below.

Environment variables set in your terminal can override the root .env when Compose resolves port settings. If a mapping differs from what you edited, check `Get-ChildItem Env:SOCIALSCOPE_*` and remove only an unintended override (for example `Remove-Item Env:SOCIALSCOPE_WEB_PORT`). Never share full `docker compose config` output: it can contain provider keys and other private environment values. `--quiet` validates without printing them.

## Verify the effective ports and readiness

These commands use **container** ports as arguments and print the effective host mappings:

```powershell
docker compose ps --all
docker compose port frontend 3001
docker compose port backend 8001
docker compose port postgres 5432
docker compose port redis 6379
python scripts/check-connectivity.py
```

The helper discovers the current frontend/backend mappings automatically. It checks HTTP reachability/JSON parsing, not complete dependency readiness. Also inspect the health JSON, substituting your chosen API host port:

```powershell
Invoke-RestMethod http://127.0.0.1:8102/api/health
```

Look for `status: ok`, `database: true`, and `redis: true`. HTTP 200 can also accompany degraded status in this pilot. Migration and seed should exit 0; check their logs if login or schema setup fails. These checks do not call social providers.

If a host port is occupied, choose another one in .env and recreate the containers. On Windows you can inspect listeners, for example `Get-NetTCPConnection -State Listen -LocalPort 3002 -ErrorAction SilentlyContinue`. Do not stop an unrelated application's process merely to reclaim its port.

## Native development

Host processes use published host addresses, not Docker service names. For a native backend, use a private `backend/.env` with the required signing/login/provider configuration and override the connection strings for the host. With default ports:

```dotenv
DATABASE_URL=postgresql+asyncpg://socialscope:socialscope@127.0.0.1:5434/socialscope
REDIS_URL=redis://127.0.0.1:6381/0
CORS_ORIGINS=http://localhost:3002,http://127.0.0.1:3002
```

Use 5534/6481 and web 3102 instead if you selected the example alternate ports. Run Uvicorn from `backend/` on host port 8002 (or your chosen API port). Root SOCIALSCOPE_* variables configure Compose mappings; they do not automatically change Uvicorn's `--port` or Next's development server port.

In a native frontend terminal, from `frontend/`:

```powershell
$env:API_INTERNAL_URL='http://127.0.0.1:8002'
npm ci
npm run dev -- --port 3002
```

For a native production build, set API_INTERNAL_URL before `npm run build`, because the proxy rewrite is generated at build time. The root Compose .env is not automatically loaded by a native frontend. Keep provider keys out of frontend environment files. Do not run native servers and Docker-published servers on the same host ports; choose one mode or deliberately separate them.

## Internal ports and multiple installations

For ordinary conflicts, change only host ports. Changing an internal port is a coordinated code/configuration change: frontend PORT/healthcheck/mapping, backend Uvicorn/healthcheck/Next build-time proxy, or PostgreSQL/Redis server listener and every client URL must agree. Simply changing a host variable does none of that, and changing API_INTERNAL_URL in root .env alone does not rebuild the Docker frontend's proxy. Internal port changes are not needed for this pilot.

SocialScope's default Compose project name is `socialscope`; its named volumes are scoped to that project. Port changes alone do not create a separate database or a second installation. To run an additional isolated SocialScope stack, use a separate project name consistently (`docker compose -p socialscope_second ...`) as well as distinct host ports and private configuration. The connectivity helper currently assumes the default project unless COMPOSE_PROJECT_NAME is set in its environment. Independent stacks still share spending if configured with the same provider credentials.

For remote use, keep loopback bindings and use an intentional tunnel, or follow the [shared-hosting roadmap](ROADMAP.md) before exposing services. Do not publish the Docker Engine, database, or Redis ports to the network just to share the web application. [RUNBOOK](../RUNBOOK.md) covers operations; [START_HERE](../START_HERE.md) covers first setup.
