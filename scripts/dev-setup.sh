#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 scripts/setup.py
printf '%s\n' 'Review .env.development, then run: docker compose --env-file .env.development -f compose.development.yml up --build -d'
