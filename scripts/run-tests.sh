#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
(cd backend && python -m pytest -q)
(cd frontend && npm test && npx tsc --noEmit --incremental false && npm run build)
