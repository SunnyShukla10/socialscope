#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 scripts/setup.py
printf '%s
' 'Privately review .env, then run: docker compose up --build -d'
