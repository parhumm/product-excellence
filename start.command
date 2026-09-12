#!/bin/bash
# Double-click this file to start Product Excellence, or run it from a terminal.
set -euo pipefail
cd "$(dirname "$0")"
export PATH="/opt/homebrew/bin:/opt/homebrew/opt/postgresql/bin:/usr/local/bin:/Applications/ChatGPT.app/Contents/Resources:$HOME/.local/bin:$PATH"
PORT=${PEX_PORT:-8741}

if curl -fsS "http://127.0.0.1:$PORT/api/health" >/dev/null 2>&1; then
  if command -v open >/dev/null; then open "http://127.0.0.1:$PORT"; fi
  echo "Product Excellence is already running at http://127.0.0.1:$PORT"
  exit 0
fi

if [ ! -x .venv/bin/python ]; then ./scripts/setup.sh; fi
mkdir -p data

# Database: an explicit DATABASE_URL wins; an existing local PostgreSQL cluster is
# kept; anything else starts on SQLite, so a fresh install needs nothing installed.
if [ -z "${DATABASE_URL:-}" ]; then
  if [ -d data/postgres ]; then
    if ! command -v pg_ctl >/dev/null; then
      echo 'This installation keeps its records in data/postgres, but the PostgreSQL commands are not on PATH.'
      echo 'Install PostgreSQL, or set DATABASE_URL. See docs/REFERENCE.md.'
      exit 1
    fi
    if ! pg_ctl -D data/postgres status >/dev/null 2>&1; then pg_ctl -D data/postgres -l data/postgres.log -o '-p 55439 -h 127.0.0.1 -k /tmp' start; fi
    if ! psql -h 127.0.0.1 -p 55439 -d product_excellence -c 'SELECT 1' >/dev/null 2>&1; then createdb -h 127.0.0.1 -p 55439 product_excellence; fi
  else
    export DATABASE_URL="sqlite:///$PWD/data/records.db"
  fi
fi

if command -v open >/dev/null; then (sleep 2; open "http://127.0.0.1:$PORT") & fi
exec .venv/bin/uvicorn app:app --host 127.0.0.1 --port "$PORT"
