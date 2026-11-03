# Development ports and configuration

Development uses `compose.development.yml` plus private `.env.development`. Production uses `compose.production.yml` plus `.env.production`. They are standalone files, not layers to merge.

## Ports and service addresses

| Service | Development loopback host port | Container port | Internal address |
|---|---|---|---|
| Frontend | 3102 | 3001 | `http://frontend:3001` |
| API | 8102 | 8001 | `http://backend:8001` |
| PostgreSQL | 5534 | 5432 | `postgres:5432` |
| Redis | 6481 | 6379 | `redis://redis:6379/0` |

Migration, seed, worker, and scheduler have no published ports. Development runs Next's development server and Uvicorn reload; production keeps its packaged application images. The browser calls the frontend's same-origin `/api` proxy. Provider keys never belong in frontend configuration.

`SOCIALSCOPE_WEB_PORT`, `SOCIALSCOPE_API_PORT`, `SOCIALSCOPE_POSTGRES_PORT`, and `SOCIALSCOPE_REDIS_PORT` in `.env.development` change host ports only. Internal ports and URLs remain unchanged. Origins follow the configured development web port. Ports must be unused on the target machine; changing ports does not create a new database.

## Setup and explicit commands

```bash
python scripts/setup.py
# Review .env.development privately.
docker compose --env-file .env.development -f compose.development.yml config --quiet
docker compose --env-file .env.development -f compose.development.yml up --build -d
docker compose --env-file .env.development -f compose.development.yml ps --all
python scripts/check-connectivity.py
```

Setup generates independent database, signing, and admin secrets and leaves provider keys blank. It never overwrites an existing `.env.development`, legacy `.env`, or production configuration. Migrations precede seed, seed precedes API readiness, and the frontend waits for the healthy API. Migration/seed exit code 0 is normal.

Because filenames are explicit, always use both flags. `--env-file` supplies Compose interpolation; service `env_file` supplies runtime values. Exported shell variables can override interpolation, including project identity and host ports; check for unintended overrides. Never share full resolved Compose output because it includes credentials. `config --quiet` avoids printing them.

## Read-only connectivity checks

```bash
docker compose --env-file .env.development -f compose.development.yml port frontend 3001
docker compose --env-file .env.development -f compose.development.yml port backend 8001
docker compose --env-file .env.development -f compose.development.yml port postgres 5432
docker compose --env-file .env.development -f compose.development.yml port redis 6379
```

The helper uses these exact development files to discover current ports. It checks reachability/JSON parsing, not every dependency field. Inspect `/api/health` for database/Redis booleans as well. On a VM, forward the web port through SSH and use the forwarded browser address; the helper does not test that tunnel.

## Storage and coexistence

The development project is `socialscope-dev`, which gives its own network and volumes: `socialscope-dev_postgres_data`, `socialscope-dev_redis_data`, `socialscope-dev_export_data`, plus frontend dependency/cache volumes. None is external or references production storage. Database/user are `socialscope_dev`; Compose constructs its URL using the generated URL-safe `SOCIALSCOPE_DEV_DB_PASSWORD`.

Production remains project `socialscope` with explicit external volume names and loopback web port 3002 by default. Use separate source folders on the VM, and never override the development name with production's name. Both environments still share machine resources; container limits do not cap image builds or guarantee production performance.

Legacy `.env` and `socialscope_*` volumes are left untouched. New development accounts/projects start separately. Do not attach old production volumes just to make old data appear. Arrange a deliberate sanitized restore if old test data is needed. Changing database-password settings does not change an initialized PostgreSQL password.

`stop` releases runtime resources; `down` removes development containers/network but keeps named volumes. Do not use `down -v` unless deliberately deleting development data, and do not run global prune commands as cleanup.

## Native development compatibility

The Python settings loader is unchanged and still supports a private `backend/.env` for raw native execution. For this optional workflow, supply the development signing/admin settings and host-based URLs using the actual generated development password (URL-encoded in DATABASE_URL):

```dotenv
DATABASE_URL=postgresql+asyncpg://socialscope_dev:URL_ENCODED_DEVELOPMENT_PASSWORD@127.0.0.1:5534/socialscope_dev
REDIS_URL=redis://127.0.0.1:6481/0
CORS_ORIGINS=http://localhost:3102,http://127.0.0.1:3102
```

Do not copy a container URL directly into a host process; host processes cannot resolve Docker service names. Native Uvicorn should use the chosen host API port (8102 by default). Native Next needs `API_INTERNAL_URL=http://127.0.0.1:8102` before starting and port 3102. Do not run native servers and Docker-published servers on the same host ports. The root development environment is not automatically loaded by native app processes.
